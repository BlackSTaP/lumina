import requests
from bs4 import BeautifulSoup
import re
import json
import datetime

# Настройка для маскировки под обычный браузер
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

URL = "https://www.zoe.com.ua/outage/"

# Карта месяцев для парсинга дат
MONTHS = {
    "СІЧНЯ": 1, "ЛЮТОГО": 2, "БЕРЕЗНЯ": 3, "КВІТНЯ": 4, "ТРАВНЯ": 5, "ЧЕРВНЯ": 6,
    "ЛИПНЯ": 7, "СЕРПНЯ": 8, "ВЕРЕСНЯ": 9, "ЖОВТНЯ": 10, "ЛИСТОПАДА": 11, "ГРУДНЯ": 12
}

def clean_text(text):
    # Убираем лишние пробелы и неразрывные пробелы
    return re.sub(r'\s+', ' ', text).strip()

def parse_zoe():
    try:
        # verify=False нужен, так как у ZOE иногда проблемы с SSL сертификатами
        response = requests.get(URL, headers=HEADERS, verify=False, timeout=30)
        response.encoding = 'utf-8'
    except Exception as e:
        print(f"Error fetching site: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Сайт ZOE часто меняет верстку, но текст обычно лежит в div или p.
    # Берем весь текст страницы для надежности
    full_text = soup.get_text(separator="\n")
    
    schedule_data = []
    
    # 1. Ищем блоки по датам (Пример: 28 СІЧНЯ ... ГПВ)
    # Разбиваем текст на куски, начиная с дат
    date_pattern = re.compile(r"(\d{1,2})\s+([А-ЯІЇЄ]+)\s+.*(?:ГПВ|ВІДКЛЮЧЕНЬ)", re.IGNORECASE)
    
    lines = full_text.split('\n')
    current_date = None
    current_queues = {}
    
    for line in lines:
        line = clean_text(line)
        if not line:
            continue
            
        # Поиск заголовка даты
        date_match = date_pattern.search(line)
        if date_match:
            # Если нашли новую дату, сохраняем предыдущую
            if current_date and current_queues:
                schedule_data.append({
                    "date": current_date,
                    "queues": current_queues
                })
            
            day = int(date_match.group(1))
            month_name = date_match.group(2).upper()
            month = MONTHS.get(month_name, datetime.datetime.now().month)
            
            # Формируем строку даты для текущего года
            year = datetime.datetime.now().year
            # Корректировка года для января, если скрипт запускается в декабре (и наоборот)
            if month == 1 and datetime.datetime.now().month == 12:
                year += 1
                
            current_date = f"{day:02d}.{month:02d}.{year}"
            current_queues = {}
            continue
            
        # Поиск очередей (Пример: 1.1: 03:00 – 08:00, 12:00 – 17:00)
        # Поддерживаем разные виды тире и двоеточий
        queue_pattern = re.search(r"(\d\.\d)[:\s]+([\d\:\s–,-]+)", line)
        if current_date and queue_pattern:
            queue_id = queue_pattern.group(1)
            times_raw = queue_pattern.group(2)
            
            # Очистка времени (замена длинных тире на дефис)
            times_clean = times_raw.replace('–', '-').replace('—', '-').replace(',', ', ')
            # Удаляем лишние пробелы вокруг дефисов
            times_clean = re.sub(r'\s*-\s*', '-', times_clean)
            
            current_queues[queue_id] = times_clean.strip()

    # Добавляем последний найденный блок
    if current_date and current_queues:
        schedule_data.append({
            "date": current_date,
            "queues": current_queues
        })
        
    return schedule_data

if __name__ == "__main__":
    data = parse_zoe()
    if data:
        with open('schedule.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Schedule updated successfully.")
    else:
        print("No data found.")
