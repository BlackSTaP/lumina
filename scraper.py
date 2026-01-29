import requests
from bs4 import BeautifulSoup
import re
import json
import datetime

# --- НАСТРОЙКИ ---
CHANNEL_URL = "https://t.me/s/zoe_alarm" 
MAX_PAGES = 10 

MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12
}

def clean_html(raw_html):
    # Превращаем <br> в реальные переносы строк для построчного чтения
    text = raw_html.replace('<br>', '\n').replace('<br/>', '\n')
    text = re.sub(r'<[^>]+>', '', text) # Удаляем теги
    return text

def parse_telegram():
    schedule_data = []
    next_url = CHANNEL_URL
    
    print(f"Starting deep scan of {CHANNEL_URL}...")

    for page in range(1, MAX_PAGES + 1):
        print(f"Scanning page {page}... [URL: {next_url}]")
        
        try:
            resp = requests.get(next_url, timeout=10)
            if resp.status_code != 200: break
        except Exception as e:
            print(f"Connection error: {e}")
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        message_wrappers = soup.select('.tgme_widget_message_wrap')
        
        if not message_wrappers: break

        # Идем от новых к старым
        for wrap in reversed(message_wrappers):
            text_div = wrap.select_one('.tgme_widget_message_text')
            if not text_div: continue 
            
            # Чистим HTML
            text_content = clean_html(str(text_div))
            text_lower = text_content.lower()

            # Фильтр: ищем слова про ГПВ/График
            if not any(x in text_lower for x in ["гпв", "графік", "черги"]):
                continue

            # 1. Поиск даты
            date_match = re.search(r"(\d{1,2})\s+(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)", text_lower)
            
            current_date = None
            if date_match:
                day = int(date_match.group(1))
                month_name = date_match.group(2)
                month = MONTHS.get(month_name)
                year = datetime.datetime.now().year
                
                if month == 1 and datetime.datetime.now().month == 12: year += 1
                elif month == 12 and datetime.datetime.now().month == 1: year -= 1
                
                current_date = f"{day:02d}.{month:02d}.{year}"
            else:
                continue # Без даты пост нам не нужен

            print(f"Found Post: {current_date}")

            # 2. Парсим очереди ПОСТРОЧНО
            queues = {}
            lines = text_content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line: continue
                
                # СТРОГИЙ ПОИСК: строка ОБЯЗАНА начинаться с "1.1:" или "1.1."
                # ^(\d\.\d) - начало строки и группа цифр
                # \s*[:\.] - разделитель (двоеточие или точка)
                # \s*(.+) - всё остальное (время)
                match = re.match(r"^(\d\.\d)\s*[:\.]\s*(.+)", line)
                
                if match:
                    q_id = match.group(1)
                    q_times_raw = match.group(2)
                    
                    # Валидация: во времени должны быть цифры
                    if not any(c.isdigit() for c in q_times_raw): continue

                    # Чистка мусора (убираем текст в скобках, лишние пробелы)
                    # Например "00:00 - 04:00 (прим. ред)" -> "00:00 - 04:00"
                    q_times_clean = re.sub(r'\(.*?\)', '', q_times_raw) 
                    
                    # Нормализация символов
                    q_times_clean = q_times_clean.replace('–', '-').replace('—', '-').replace(',', ', ')
                    
                    # Оставляем только допустимые символы
                    q_times_clean = re.sub(r'[^\d\:\-\,\s]', '', q_times_clean)
                    
                    # Форматирование пробелов
                    q_times_clean = re.sub(r'\s+', '', q_times_clean) # Сначала удаляем все пробелы
                    q_times_clean = q_times_clean.replace('-', ' - ').replace(',', ', ') # Ставим красивые
                    
                    if q_times_clean:
                        queues[q_id] = q_times_clean.strip()

            if queues:
                # Сортировка ключей
                sorted_queues = dict(sorted(queues.items()))
                
                schedule_data.append({
                    "date": current_date,
                    "queues": sorted_queues
                })
                print(f"   SUCCESS! Parsed {len(queues)} queues.")
                return schedule_data # Нашли свежий - выходим

        # Пагинация
        try:
            oldest_msg = message_wrappers[0].select_one('.tgme_widget_message')
            post_id = int(oldest_msg.get('data-post').split('/')[-1])
            next_url = f"{CHANNEL_URL}?before={post_id}"
        except:
            break

    return schedule_data

if __name__ == "__main__":
    data = parse_telegram()
    if data:
        with open('schedule.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Done.")
    else:
        print("No data.")
