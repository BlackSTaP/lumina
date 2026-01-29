import requests
from bs4 import BeautifulSoup
import re
import json
import datetime

# --- НАСТРОЙКИ ---
# Используем веб-версию канала zoe_alarm
CHANNEL_URL = "https://t.me/s/zoe_alarm" 

MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12
}

def clean_text(text):
    # Заменяем HTML переносы на настоящие
    text = text.replace('<br>', '\n').replace('<br/>', '\n')
    # Убираем теги
    text = re.sub(r'<[^>]+>', '', text)
    # Убираем лишние пробелы
    return re.sub(r'\s+', ' ', text).strip()

def parse_telegram():
    print(f"Fetching {CHANNEL_URL}...")
    try:
        resp = requests.get(CHANNEL_URL, timeout=10)
        if resp.status_code != 200:
            print(f"Error: Status code {resp.status_code}")
            return None
    except Exception as e:
        print(f"Connection error: {e}")
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Ищем сообщения
    messages = soup.select('.tgme_widget_message_text')
    
    if not messages:
        print("No messages found. Parsing failed.")
        return None

    schedule_data = []
    
    # Смотрим с конца (самые свежие)
    for msg in reversed(messages):
        raw_html = str(msg)
        text_content = clean_text(raw_html)
        text_lower = text_content.lower()

        # 1. Фильтр: ищем слова "график", "гпв", "відключень"
        if not any(x in text_lower for x in ["гпв", "графік", "відключень"]):
            continue
            
        # 2. Ищем дату (Например: "29 січня", "на 29.01")
        # Regex ищет день + месяц словом
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
            # Если дата не найдена словом, пробуем формат ЧЧ.ММ (например 29.01)
            date_short = re.search(r"(\d{1,2})\.(\d{1,2})", text_content)
            if date_short:
                day = int(date_short.group(1))
                month = int(date_short.group(2))
                year = datetime.datetime.now().year
                current_date = f"{day:02d}.{month:02d}.{year}"
            else:
                continue

        print(f"Found schedule for: {current_date}")

        # 3. Парсим очереди
        # Ищет: "1.1 ... 00-04" или "Черга 1 ... 00-04"
        queues = {}
        
        # Regex ловит: (Группа)(Разделитель)(Время)
        # Группа: 1.1 или просто 1
        matches = re.findall(r"(?:Черга|Група)?\s*(\d(?:\.\d)?)\s*[:\-\)]\s*([\d\:\s\-\–,;]+)", text_content)
        
        for q_id, q_times in matches:
            # Валидация времени: должно содержать цифры
            if not any(c.isdigit() for c in q_times): continue
            
            # Чистка строки времени
            clean_time = q_times.replace('–', '-').replace('—', '-').replace(',', ', ').replace(';', ', ')
            # Оставляем только цифры, двоеточия, дефисы, запятые
            clean_time = re.sub(r'[^\d\:\-\,\s]', '', clean_time)
            clean_time = re.sub(r'\s+', '', clean_time) # сжимаем пробелы
            clean_time = clean_time.replace('-', ' - ').replace(',', ', ')
            
            queues[q_id] = clean_time.strip()

        if queues:
            schedule_data.append({
                "date": current_date,
                "queues": queues
            })
            # Нашли свежий график — выходим (чтобы не брать старые)
            break 
    
    return schedule_data

if __name__ == "__main__":
    data = parse_telegram()
    if data:
        with open('schedule.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Success! Data found for: {[d['date'] for d in data]}")
    else:
        print("No schedule found.")
