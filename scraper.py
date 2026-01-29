import requests
from bs4 import BeautifulSoup
import re
import json
import datetime

# --- НАСТРОЙКИ ---
CHANNEL_URL = "https://t.me/s/zoe_alarm" 
MAX_PAGES = 10  # Сколько страниц истории листать назад (1 стр ≈ 20 сообщений)

MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12
}

def clean_text(text):
    text = text.replace('<br>', '\n').replace('<br/>', '\n')
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def parse_telegram():
    schedule_data = []
    next_url = CHANNEL_URL
    
    print(f"Starting deep scan of {CHANNEL_URL}...")

    for page in range(1, MAX_PAGES + 1):
        print(f"Scanning page {page}... [URL: {next_url}]")
        
        try:
            resp = requests.get(next_url, timeout=10)
            if resp.status_code != 200:
                print(f"Error loading page: {resp.status_code}")
                break
        except Exception as e:
            print(f"Connection error: {e}")
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Находим блоки сообщений (весь блок, чтобы достать ID)
        message_wrappers = soup.select('.tgme_widget_message_wrap')
        
        if not message_wrappers:
            print("No messages found on this page.")
            break

        # Нам нужны только сообщения с текстом
        # Идем с конца (от новых к старым на текущей странице)
        for wrap in reversed(message_wrappers):
            msg_div = wrap.select_one('.tgme_widget_message')
            text_div = wrap.select_one('.tgme_widget_message_text')
            
            if not text_div: continue # Пропускаем картинки без подписи
            
            raw_html = str(text_div)
            text_content = clean_text(raw_html)
            text_lower = text_content.lower()

            # --- ЛОГИКА ПОИСКА ГРАФИКА ---
            if not any(x in text_lower for x in ["гпв", "графік", "черги"]):
                continue # Мусор

            print(f"-- Found potential schedule! Analyzing...")

            # 1. Поиск даты
            date_match = re.search(r"(\d{1,2})\s+(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)", text_lower)
            
            current_date = None
            if date_match:
                day = int(date_match.group(1))
                month_name = date_match.group(2)
                month = MONTHS.get(month_name)
                year = datetime.datetime.now().year
                if month == 1 and datetime.datetime.now().month == 12: year += 1
                if month == 12 and datetime.datetime.now().month == 1: year -= 1
                current_date = f"{day:02d}.{month:02d}.{year}"
            else:
                # Пробуем 29.01
                date_short = re.search(r"(\d{1,2})\.(\d{1,2})", text_content)
                if date_short:
                    day = int(date_short.group(1))
                    month = int(date_short.group(2))
                    year = datetime.datetime.now().year
                    current_date = f"{day:02d}.{month:02d}.{year}"

            if not current_date:
                print("   Date not found in text, skipping.")
                continue

            print(f"   Date identified: {current_date}")

            # 2. Поиск очередей
            queues = {}
            # Паттерн: 1.1 ... 00-04
            matches = re.findall(r"(?:Черга|Група)?\s*(\d(?:\.\d)?)\s*[:\-\)]\s*([\d\:\s\-\–,;]+)", text_content)
            
            for q_id, q_times in matches:
                if not any(c.isdigit() for c in q_times): continue
                clean_time = q_times.replace('–', '-').replace('—', '-').replace(',', ', ').replace(';', ', ')
                clean_time = re.sub(r'[^\d\:\-\,\s]', '', clean_time)
                clean_time = re.sub(r'\s+', '', clean_time)
                clean_time = clean_time.replace('-', ' - ').replace(',', ', ')
                queues[q_id] = clean_time.strip()

            if queues:
                schedule_data.append({
                    "date": current_date,
                    "queues": queues
                })
                print(f"   SUCCESS! Schedule found.")
                return schedule_data # Нашли самый свежий - выходим сразу

        # --- ПАГИНАЦИЯ ---
        # Если график не найден на этой странице, вычисляем URL для следующей (старой)
        # Берем ID самого первого (старого) сообщения на странице
        try:
            oldest_msg = message_wrappers[0].select_one('.tgme_widget_message')
            post_id_str = oldest_msg.get('data-post') # пример: zoe_alarm/2350
            post_id = int(post_id_str.split('/')[-1])
            
            print(f"   No schedule on page {page}. Loading messages before ID {post_id}...")
            next_url = f"{CHANNEL_URL}?before={post_id}"
        except Exception as e:
            print(f"Error calculating pagination: {e}")
            break

    return schedule_data

if __name__ == "__main__":
    data = parse_telegram()
    if data:
        with open('schedule.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Final Success! Data found for: {[d['date'] for d in data]}")
    else:
        print("No schedule found after deep scan.")
