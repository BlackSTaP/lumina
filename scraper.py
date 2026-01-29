import requests
from bs4 import BeautifulSoup
import re
import json
import datetime
import time

# Список User-Agent для ротации
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (Linux; Android 10; SM-A505FN) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.105 Mobile Safari/537.36'
]

URL = "https://www.zoe.com.ua/outage/"

# Карта месяцев
MONTHS = {
    "СІЧНЯ": 1, "ЛЮТОГО": 2, "БЕРЕЗНЯ": 3, "КВІТНЯ": 4, "ТРАВНЯ": 5, "ЧЕРВНЯ": 6,
    "ЛИПНЯ": 7, "СЕРПНЯ": 8, "ВЕРЕСНЯ": 9, "ЖОВТНЯ": 10, "ЛИСТОПАДА": 11, "ГРУДНЯ": 12
}

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def get_page_content():
    """Пытается загрузить страницу напрямую, а если не выйдет - через публичные веб-прокси"""
    
    # 1. Попытка напрямую (вдруг повезет)
    try:
        print("Attempting direct connection...")
        resp = requests.get(URL, headers={'User-Agent': USER_AGENTS[0]}, verify=False, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"Direct connection failed: {e}")

    # 2. Если не вышло - используем Web-Proxy сервисы (CORS-proxy или анонимайзеры)
    # Это позволяет запросу прийти с другого IP.
    
    # Вариант А: Использование allorigins (иногда работает для простого GET)
    proxies = [
        f"https://api.allorigins.win/get?url={URL}",
        # Можно добавить другие
    ]
    
    for proxy_url in proxies:
        try:
            print(f"Attempting via proxy wrapper: {proxy_url}")
            resp = requests.get(proxy_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                # allorigins возвращает JSON с полем contents
                if 'contents' in data:
                    return data['contents']
        except Exception as e:
            print(f"Proxy failed: {e}")
            
    return None

def parse_zoe():
    html_content = get_page_content()
    
    if not html_content:
        print("Failed to retrieve content from all sources.")
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    full_text = soup.get_text(separator="\n")
    
    schedule_data = []
    
    # Регулярка для даты: "28 СІЧНЯ ... ГПВ"
    date_pattern = re.compile(r"(\d{1,2})\s+([А-ЯІЇЄ]+)\s+.*(?:ГПВ|ВІДКЛЮЧЕНЬ)", re.IGNORECASE)
    
    lines = full_text.split('\n')
    current_date = None
    current_queues = {}
    
    for line in lines:
        line = clean_text(line)
        if not line:
            continue
            
        date_match = date_pattern.search(line)
        if date_match:
            if current_date and current_queues:
                schedule_data.append({"date": current_date, "queues": current_queues})
            
            day = int(date_match.group(1))
            month_name = date_match.group(2).upper()
            month = MONTHS.get(month_name, datetime.datetime.now().month)
            
            year = datetime.datetime.now().year
            if month == 1 and datetime.datetime.now().month == 12:
                year += 1
            if month == 12 and datetime.datetime.now().month == 1:
                year -= 1 # На случай если смотрим старый декабрь в январе
                
            current_date = f"{day:02d}.{month:02d}.{year}"
            current_queues = {}
            continue
            
        queue_pattern = re.search(r"(\d\.\d)[:\s]+([\d\:\s–,-]+)", line)
        if current_date and queue_pattern:
            queue_id = queue_pattern.group(1)
            times_raw = queue_pattern.group(2)
            times_clean = times_raw.replace('–', '-').replace('—', '-').replace(',', ', ')
            times_clean = re.sub(r'\s*-\s*', '-', times_clean)
            current_queues[queue_id] = times_clean.strip()

    if current_date and current_queues:
        schedule_data.append({"date": current_date, "queues": current_queues})
        
    return schedule_data

if __name__ == "__main__":
    # Отключаем предупреждения SSL (так как verify=False)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    data = parse_zoe()
    if data:
        with open('schedule.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Schedule updated successfully. Found {len(data)} days.")
    else:
        print("No data found or parsing error.")
