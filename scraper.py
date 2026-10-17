#!/usr/bin/env python3
"""Lumina scraper: читает t.me/s/<канал>, сохраняет график + время публикации + историю версий."""
import json
import logging
import re
import sys
import time
from datetime import datetime, date, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CHANNEL_URL = "https://t.me/s/zoe_alarm"
MAX_PAGES = 12
KEEP_DAYS = 3
MAX_VERSIONS = 12
OUTPUT = Path("schedule.json")
TZ = ZoneInfo("Europe/Kyiv")
KEYWORDS = ("гпв", "графік", "графiк", "черги", "черга")

MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}
DATE_RE = re.compile(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")", re.I)
QUEUE_RE = re.compile(r"^(?:черг[аи]|група)?\s*(\d\.\d)\s*[:.\-–—]\s*(.+)$", re.I)
RANGE_RE = re.compile(r"(\d{1,2}):(\d{2})\s*(?:[-–—]|до)\s*(\d{1,2}):(\d{2})", re.I)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("lumina")


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers["User-Agent"] = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")
    s.headers["Accept-Language"] = "uk,ru;q=0.8,en;q=0.5"
    return s


def element_text(el) -> str:
    for br in el.find_all("br"):
        br.replace_with("\n")
    return el.get_text()


def resolve_date(day: int, month: int, today: date):
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            cand = date(year, month, day)
        except ValueError:
            continue
        if best is None or abs((cand - today).days) < abs((best - today).days):
            best = cand
    return best


def format_ranges(raw: str) -> str:
    ranges, seen = [], set()
    for h1, m1, h2, m2 in RANGE_RE.findall(raw):
        a, b = f"{int(h1):02d}:{m1}", f"{int(h2):02d}:{m2}"
        if (a, b) not in seen:
            seen.add((a, b))
            ranges.append((a, b))
    ranges.sort(key=lambda r: r[0])
    return ", ".join(f"{a} - {b}" for a, b in ranges)


def parse_post(text: str, today: date):
    low = text.lower()
    if not any(k in low for k in KEYWORDS):
        return None
    dm = DATE_RE.search(low)
    if not dm:
        return None
    d = resolve_date(int(dm.group(1)), MONTHS[dm.group(2).lower()], today)
    if not d:
        return None
    queues = {}
    for line in text.splitlines():
        m = QUEUE_RE.match(line.strip())
        if not m:
            continue
        times = format_ranges(re.sub(r"\(.*?\)", "", m.group(2)))
        if times:
            queues[m.group(1)] = times
    if not queues:
        return None
    return d, dict(sorted(queues.items()))


def post_datetime(wrap) -> datetime:
    """Время публикации поста в Киеве (из <time datetime=...> Telegram)."""
    t = wrap.select_one(".tgme_widget_message_date time")
    if t is not None and t.get("datetime"):
        try:
            return datetime.fromisoformat(t["datetime"]).astimezone(TZ).replace(microsecond=0)
        except ValueError:
            pass
    return datetime.now(TZ).replace(microsecond=0)


def scan_channel(session, today: date) -> dict:
    """date -> {published_iso: queues}"""
    found: dict = {}
    url = CHANNEL_URL
    for page in range(1, MAX_PAGES + 1):
        log.info("Страница %d: %s", page, url)
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.error("Ошибка сети: %s", e)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        wraps = soup.select(".tgme_widget_message_wrap")
        if not wraps:
            break

        for wrap in wraps:
            text_div = wrap.select_one(".tgme_widget_message_text")
            if not text_div:
                continue
            parsed = parse_post(element_text(text_div), today)
            if not parsed:
                continue
            d, queues = parsed
            iso = post_datetime(wrap).isoformat()
            found.setdefault(d, {})[iso] = queues

        # Нужен запас: ещё один день сверх KEEP_DAYS, чтобы собрать все версии свежих дат
        if len(found) > KEEP_DAYS:
            break

        try:
            first = wraps[0].select_one(".tgme_widget_message")
            post_id = int(first["data-post"].split("/")[-1])
            url = f"{CHANNEL_URL}?before={post_id}"
        except (AttributeError, KeyError, ValueError, TypeError):
            break
        time.sleep(0.7)
    return found


def load_existing() -> dict:
    if not OUTPUT.exists():
        return {}
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    out: dict = {}
    for item in data:
        try:
            d = datetime.strptime(item["date"], "%d.%m.%Y").date()
            versions = item.get("versions") or [{
                "published_at": item.get("published_at")
                or datetime.combine(d, dtime(0, 0), TZ).isoformat(),
                "queues": item["queues"],
            }]
            out[d] = {v["published_at"]: v["queues"] for v in versions}
        except (KeyError, ValueError, TypeError):
            continue
    return out


def build_versions(vmap: dict) -> list:
    """Хронологически; оставляем только версии, где график реально изменился."""
    items = sorted(vmap.items(), key=lambda kv: datetime.fromisoformat(kv[0]))
    kept = []
    for iso, queues in items:
        if not kept or kept[-1]["queues"] != queues:
            kept.append({"published_at": iso, "queues": queues})
    return list(reversed(kept[-MAX_VERSIONS:]))  # новейшая первой


def main() -> int:
    today = datetime.now(TZ).date()
    fresh = scan_channel(make_session(), today)
    if not fresh:
        log.warning("Новых данных нет — schedule.json не трогаю.")
        return 0

    merged = load_existing()
    for d, vmap in fresh.items():
        merged.setdefault(d, {}).update(vmap)

    result = []
    for d in sorted(merged, reverse=True)[:KEEP_DAYS]:
        versions = build_versions(merged[d])
        latest = versions[0]
        result.append({
            "date": d.strftime("%d.%m.%Y"),
            "published_at": latest["published_at"],
            "queues": latest["queues"],
            "versions": versions,
        })

    new_text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    old_text = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
    if new_text == old_text:
        log.info("Без изменений.")
        return 0
    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    tmp.replace(OUTPUT)
    log.info("schedule.json обновлён (%d дн.).", len(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
