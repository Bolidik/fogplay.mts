import requests
from bs4 import BeautifulSoup
import telebot
from dotenv import load_dotenv
import os
from collections import Counter
import json
import google.generativeai as genai
import logging
import asyncio

load_dotenv()

BOT_TOKEN = os.getenv("ТОКЕН БОТА")
if not BOT_TOKEN:
    BOT_TOKEN = 'ТОКЕН БОТА'

bot = telebot.TeleBot(BOT_TOKEN)

GEMINI_API_KEY = os.getenv("ТУТ АПИ")
if not GEMINI_API_KEY:
    GEMINI_API_KEY = 'ТУТ АПИ'

genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.9,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    generation_config=generation_config
)

chat_sessions = {}

def load_html_from_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        print(f"Файл не найден: {filepath}")
        return None
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        return None

def parse_html_cards_simplified(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    cards = soup.find_all('div', class_=lambda x: x and 'card card-outside computer-' in x)
    print(f"Найдено карточек: {len(cards)}")

    card_data_list = []
    for card in cards:
        try:
            card_data = {}
            
            system_items = card.find_all('li', class_='card__system__item')
            for item in system_items:
                title = item.find('span', class_='card__system__title')
                value = item.find('span', class_='card__system__value')
                if title and value:
                    key = title.text.replace(':', '').strip()
                    val = value.text.strip()
                    if 'Процессор' in key:
                        card_data['cpu'] = val
                    elif 'Видеокарта' in key:
                        card_data['gpu'] = val
                    elif 'Оперативная память' in key:
                        card_data['ram'] = val

            price_element = card.find('div', class_='card__price')
            if price_element:
                price_text = price_element.text.strip()
                price_digits = ''.join(c for c in price_text if c.isdigit())
                if price_digits:
                    card_data['price'] = f"{int(price_digits)} ₽"
                else:
                    card_data['price'] = "Цена не указана"
            else:
                alt_price = card.find('div', class_='price')
                if alt_price:
                    price_text = alt_price.text.strip()
                    price_digits = ''.join(c for c in price_text if c.isdigit())
                    if price_digits:
                        card_data['price'] = f"{int(price_digits)} ₽"
                    else:
                        card_data['price'] = "Цена не указана"
                else:
                    card_data['price'] = "Цена не указана"

            card_data_list.append(card_data)
            print(f"Обработана карточка: {card_data}")  
            
        except Exception as e:
            print(f"Ошибка при обработке карточки: {e}")
            continue

    return card_data_list

def get_price_stats(card_data_list):
    try:
        prices = []
        for card in card_data_list:
            price_str = card['price'].replace('₽', '').replace(' ', '')
            if price_str.isdigit():
                prices.append(int(price_str))
        
        if not prices:
            return "❌ <b>Нет данных о ценах</b>"
        
        avg_price = sum(prices) / len(prices)
        median_price = sorted(prices)[len(prices)//2]
        
        return (
            "💰 <b>АНАЛИЗ ЦЕН</b>\n"
            f"└ Всего с ценами: <b>{len(prices)}</b> из {len(card_data_list)}\n"
            f"└ Средняя: <b>{int(avg_price):,} ₽</b>\n"
            f"└ Минимальная: <b>{min(prices):,} ₽</b>\n"
            f"└ Максимальная: <b>{max(prices):,} ₽</b>\n"
            f"└ Медианная: <b>{median_price:,} ₽</b>"
        )
    except Exception as e:
        print(f"Ошибка в get_price_stats: {e}")
        return "❌ <b>Ошибка при анализе цен</b>"

def get_cpu_stats(card_data_list):
    cpu_counts = Counter(card['cpu'] for card in card_data_list)
    total = len(card_data_list)
    
    output = "🔧 <b>СТАТИСТИКА ПРОЦЕССОРОВ</b>\n"
    for cpu, count in cpu_counts.most_common(5):
        percentage = (count / total) * 100
        output += f"└ {cpu}: {count} шт ({percentage:.1f}%)\n"
    return output

def get_gpu_stats(card_data_list):
    gpu_counts = Counter(card['gpu'] for card in card_data_list)
    total = len(card_data_list)
    
    output = "🎮 <b>СТАТИСТИКА ВИДЕОКАРТ</b>\n"
    for gpu, count in gpu_counts.most_common(5):
        percentage = (count / total) * 100
        output += f"└ {gpu}: {count} шт ({percentage:.1f}%)\n"
    return output

def get_ram_stats(card_data_list):
    ram_counts = Counter(card['ram'] for card in card_data_list)
    total = len(card_data_list)
    
    output = "💾 <b>СТАТИСТИКА ОЗУ</b>\n"
    for ram, count in ram_counts.most_common():
        percentage = (count / total) * 100
        output += f"└ {ram}: {count} шт ({percentage:.1f}%)\n"
    return output

def get_quick_overview(card_data_list):
    total = len(card_data_list)
    prices = [int(card['price'].replace('₽', '').replace(' ', '')) for card in card_data_list if card['price'].replace('₽', '').replace(' ', '').isdigit()]
    avg_price = sum(prices) / len(prices) if prices else 0
    
    return (
        "📊 <b>КРАТКИЙ ОБЗОР</b>\n"
        f"└ Всего компьютеров: <b>{total}</b>\n"
        f"└ Средняя цена: <b>{int(avg_price):,} ₽</b>\n"
        f"└ Моделей CPU: <b>{len(set(card['cpu'] for card in card_data_list))}</b>\n"
        f"└ Моделей GPU: <b>{len(set(card['gpu'] for card in card_data_list))}</b>"
    )

def generate_statistics(card_data_list):
    stats = {
        'total_cards': len(card_data_list),
        'prices': [],
        'ram_sizes': [],
        'cpu_counts': Counter(),
        'gpu_counts': Counter()
    }

    for card in card_data_list:
        stats['cpu_counts'][card['cpu']] += 1
        stats['gpu_counts'][card['gpu']] += 1
        stats['ram_sizes'].append(card['ram'])
        
        try:
            price_str = card['price'].replace('₽', '').replace(' ', '')
            price = int(price_str) if price_str.isdigit() else 0
            if price > 0:
                stats['prices'].append(price)
        except:
            continue

    if stats['prices']:
        stats['avg_price'] = sum(stats['prices']) / len(stats['prices'])
        stats['min_price'] = min(stats['prices'])
        stats['max_price'] = max(stats['prices'])

    return stats

def format_stats_for_telegram(stats, card_data_list):
    top_cpu = stats['cpu_counts'].most_common(1)[0] if stats['cpu_counts'] else ('Нет данных', 0)
    top_gpu = stats['gpu_counts'].most_common(1)[0] if stats['gpu_counts'] else ('Нет данных', 0)

    output = "📊 <b>СТАТИСТИКА ПО КОМПЬЮТЕРАМ</b>\n\n"
    
    output += f"📦 Всего компьютеров: <b>{stats['total_cards']}</b>\n\n"
    
    output += "🔥 <b>ПОПУЛЯРНОЕ ЖЕЛЕЗО</b>\n"
    output += f"└ CPU: <b>{top_cpu[0]}</b> ({top_cpu[1]} шт)\n"
    output += f"└ GPU: <b>{top_gpu[0]}</b> ({top_gpu[1]} шт)\n\n"

    if 'avg_price' in stats:
        output += "💰 <b>ЦЕНЫ</b>\n"
        output += f"└ Средняя: <b>{int(stats['avg_price']):,} ₽</b>\n"
        output += f"└ Минимальная: <b>{stats['min_price']:,} ₽</b>\n"
        output += f"└ Максимальная: <b>{stats['max_price']:,} ₽</б>\n\n"

    output += "🔋 <b>ТОП-3 ПРОЦЕССОРОВ</b>\н"
    for cpu, count in stats['cpu_counts'].most_common(3):
        percentage = (count / stats['total_cards']) * 100
        output += f"└ {cpu}: <b>{count}</b> шт ({percentage:.1f}%)\n"
    
    output += "\n📺 <b>ТОП-3 ВИДЕОКАРТ</б>\н"
    for gpu, count in stats['gpu_counts'].most_common(3):
        percentage = (count / stats['total_cards']) * 100
        output += f"└ {gpu}: <b>{count}</b> шт ({percentage:.1f}%)\н"

    return output

def search_by_component(card_data_list, component_type, query):
    results = []
    query = query.lower()
    
    for card in card_data_list:
        if component_type in card and query in card[component_type].lower():
            results.append(card)
    
    return results

def format_config_results(results):
    if not results:
        return "❌ Конфигурации не найдены"
    
    output = f"🔍 Найдено конфигураций: {len(results)}\n\n"
    for i, config in enumerate(results, 1):
        output += (f"📌 Конфигурация #{i}\n"
                  f"└ CPU: {config['cpu']}\n"
                  f"└ GPU: {config['gpu']}\n"
                  f"└ RAM: {config['ram']}\n"
                  f"└ Цена: {config['price']}\n\n")
        
        if len(output) > 3000:
            output += "... и ещё несколько конфигураций"
            break
            
    return output

def search_by_full_config(card_data_list, query):
    results = []
    query_parts = query.lower().split()
    
    for card in card_data_list:
        card_text = (f"{card['cpu']} {card['gpu']} {card['ram']}").lower()
        matches = sum(1 for part in query_parts if part in card_text)
        if matches >= len(query_parts) / 2:
            score = matches / len(query_parts)
            results.append((score, card))
    
    return [card for score, card in sorted(results, key=lambda x: x[0], reverse=True)]

def generate_card_key(card):
    cpu = card.get('cpu', '').lower().strip()
    gpu = card.get('gpu', '').lower().strip()
    ram = card.get('ram', '').lower().strip()
    cpu = ' '.join(cpu.split())
    gpu = ' '.join(gpu.split())
    ram = ' '.join(ram.split())
    return f"{cpu}|{gpu}|{ram}"

def load_cards_data():
    json_file = 'cards_data.json'
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            print(f"Загружено {len(existing_data)} карточек из JSON")
    except FileNotFoundError:
        existing_data = []
        print("JSON файл не найден, создаем новый")
    
    html_content = load_html_from_file('cards.txt')
    if not html_content:
        print("HTML файл не найден или пуст")
        return existing_data
        
    new_cards = parse_html_cards_simplified(html_content)
    if not new_cards:
        print("Нет новых карточек для обработки")
        return existing_data

    existing_configs = {generate_card_key(card) for card in existing_data}
    
    added_count = 0
    duplicate_count = 0
    
    for card in new_cards:
        card_key = generate_card_key(card)
        if card_key not in existing_configs:
            existing_data.append(card)
            existing_configs.add(card_key)
            added_count += 1
        else:
            duplicate_count += 1
    
    if added_count > 0:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        print(f"Добавлено {added_count} новых карточек")
    
    print(f"Пропущено {duplicate_count} дубликатов")
    return existing_data

async def analyze_with_ai(card_data_list):
    try:
        data_summary = {
            'total_computers': len(card_data_list),
            'price_range': [],
            'components': {
                'cpu': [],
                'gpu': [],
                'ram': []
            }
        }

        for card in card_data_list:
            if card['price'].replace('₽', '').replace(' ', '').isdigit():
                data_summary['price_range'].append(int(card['price'].replace('₽', '').replace(' ', '')))
            data_summary['components']['cpu'].append(card['cpu'])
            data_summary['components']['gpu'].append(card['gpu'])
            data_summary['components']['ram'].append(card['ram'])

        prompt = f"""
        Проанализируй данные о {len(card_data_list)} компьютерах:
        
        Ценовой диапазон: от {min(data_summary['price_range']):,}₽ до {max(data_summary['price_range']):,}₽
        
        Топ CPU: {', '.join(list(set(data_summary['components']['cpu']))[:5])}
        Топ GPU: {', '.join(list(set(data_summary['components']['gpu']))[:5])}
        
        Предоставь:
        1. Анализ соотношения цена/производительность
        2. Рекомендации по оптимальным конфигурациям
        3. Тренды и интересные наблюдения
        """

        chat = model.start_chat(history=[])
        response = chat.send_message(prompt)
        
        return response.text if response and response.text else "AI анализ недоступен"

    except Exception as e:
        logging.error(f"Error in AI analysis: {e}")
        return "Ошибка при выполнении AI анализа"

def split_long_message(text, max_length=4096):
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while len(text) > 0:
        if len(text) <= max_length:
            parts.append(text)
            break
        
        split_point = text[:max_length].rfind('.')
        if split_point == -1:
            split_point = text[:max_length].rfind('\n')
        if split_point == -1:
            split_point = max_length
        
        parts.append(text[:split_point + 1])
        text = text[split_point + 1:].lstrip()
    
    return parts

async def ask_ai_custom_question(data_summary, question):
    try:
        prompt = f"""
        На основе следующих данных о компьютерах ответь на вопрос:
        
        Данные:
        - Всего компьютеров: {data_summary['total_computers']}
        - Ценовой диапазон: от {min(data_summary['price_range']):,}₽ до {max(data_summary['price_range']):,}₽
        - CPU: {', '.join(list(set(data_summary['components']['cpu']))[:5])}
        - GPU: {', '.join(list(set(data_summary['components']['gpu']))[:5])}
        
        Вопрос: {question}
        """

        chat = model.start_chat(history=[])
        response = chat.send_message(prompt)
        return response.text if response and response.text else "AI не смог ответить на вопрос"

    except Exception as e:
        logging.error(f"Error in custom AI question: {e}")
        return "Ошибка при обработке вопроса"

def process_ai_question(message, data_summary):
    try:
        question = message.text.strip()
        if len(question) < 5:
            bot.reply_to(message, "⚠️ Вопрос слишком короткий. Опишите подробнее, что вы хотите узнать.")
            return

        processing_msg = bot.reply_to(message, "🤖 Обрабатываю ваш вопрос...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(ask_ai_custom_question(data_summary, question))
        loop.close()

        response_parts = split_long_message(response)
        
        bot.delete_message(message.chat.id, processing_msg.message_id)

        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(telebot.types.InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu"))
        
        for i, part in enumerate(response_parts):
            if i == len(response_parts) - 1:
                bot.send_message(message.chat.id, part, parse_mode='HTML', reply_markup=markup)
            else:
                bot.send_message(message.chat.id, part, parse_mode='HTML')

    except Exception as e:
        logging.error(f"Error processing AI question: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при обработке вопроса")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup = create_main_menu_markup()
    welcome_text = (
        "🤖 <b>Статистика и поиск компьютеров</b>\n\n"
        "Выберите действие:\n"
        "- Просмотр статистики\n"
        "- Поиск по компонентам\n"
        "- Поиск по полной конфигурации\n"
        "- Просмотр всех конфигураций"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        if call.data == "back_to_menu":
            markup = create_main_menu_markup()
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Вы вернулись в главное меню.",
                parse_mode='HTML',
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
            return

        card_data_list = load_cards_data()
        if not card_data_list:
            bot.answer_callback_query(call.id, "Ошибка: нет данных для анализа")
            return

        if call.data == "search_full":
            msg = bot.send_message(
                call.message.chat.id,
                "Введите параметры конфигурации (процессор, видеокарта, память):\n"
                "Например: i5-12400F RTX 4060 16GB",
                reply_markup=telebot.types.ForceReply()
            )
            bot.register_next_step_handler(msg, lambda m: process_full_search(m, card_data_list))
            return

        if call.data in ["search_cpu", "search_gpu", "search_ram"]:
            component_type = call.data.split('_')[1]
            msg = bot.send_message(
                call.message.chat.id,
                f"Введите параметры поиска для {component_type.upper()}:",
                reply_markup=telebot.types.ForceReply()
            )
            bot.register_next_step_handler(msg, lambda m: process_search(m, component_type, card_data_list))
            return
        
        if call.data == "all_configs":
            text = format_config_results(card_data_list)
        elif call.data == "ai_analysis":
            handle_ai_analysis(call)
            return
        elif call.data == "ask_ai":
            handle_ask_ai(call)
            return
        else:
            if call.data == "overview":
                text = get_quick_overview(card_data_list)
            elif call.data == "prices":
                text = get_price_stats(card_data_list)
            elif call.data == "cpu":
                text = get_cpu_stats(card_data_list)
            elif call.data == "gpu":
                text = get_gpu_stats(card_data_list)
            elif call.data == "ram":
                text = get_ram_stats(card_data_list)
        
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode='HTML',
                reply_markup=call.message.reply_markup
            )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"Error in callback_query: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка при обработке запроса")

def process_search(message, component_type, card_data_list):
    query = message.text.strip()
    if len(query) < 2:
        bot.reply_to(message, "⚠️ Слишком короткий запрос. Минимум 2 символа.")
        return
    
    results = search_by_component(card_data_list, component_type, query)
    response = format_config_results(results)
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(telebot.types.InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu"))
    
    bot.reply_to(message, response, parse_mode='HTML', reply_markup=markup)

def process_full_search(message, card_data_list):
    query = message.text.strip()
    if len(query) < 3:
        bot.reply_to(message, "⚠️ Слишком короткий запрос. Опишите конфигурацию подробнее.")
        return
    
    results = search_by_full_config(card_data_list, query)
    response = format_config_results(results)
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(telebot.types.InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu"))
    
    bot.reply_to(message, response, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    send_welcome(message)

def get_stats(message):
    card_data_list = load_cards_data()
    if card_data_list:
        stats = generate_statistics(card_data_list)
        formatted_text = format_stats_for_telegram(stats, card_data_list)
        if formatted_text:
            bot.send_message(message.chat.id, formatted_text, parse_mode='HTML', disable_web_page_preview=True)
        else:
            bot.reply_to(message, "⚠️ Не удалось сформировать статистику.")
    else:
        bot.reply_to(message, "⚠️ Не удалось получить данные")

def create_main_menu_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    
    markup.row(
        telebot.types.InlineKeyboardButton("📊 Краткий обзор", callback_data="overview"),
        telebot.types.InlineKeyboardButton("💰 Цены", callback_data="prices")
    )
    
    markup.row(
        telebot.types.InlineKeyboardButton("🔧 Процессоры", callback_data="cpu"),
        telebot.types.InlineKeyboardButton("🎮 Видеокарты", callback_data="gpu")
    )
    
    markup.row(
        telebot.types.InlineKeyboardButton("🔍 Поиск по CPU", callback_data="search_cpu"),
        telebot.types.InlineKeyboardButton("🔍 Поиск по GPU", callback_data="search_gpu")
    )
    
    markup.row(
        telebot.types.InlineKeyboardButton("💾 Память", callback_data="ram"),
        telebot.types.InlineKeyboardButton("🔍 Поиск по RAM", callback_data="search_ram")
    )
    
    markup.row(
        telebot.types.InlineKeyboardButton("🔍 Поиск по полной конфигурации", callback_data="search_full")
    )
    
    markup.row(
        telebot.types.InlineKeyboardButton("🖥️ Все конфигурации", callback_data="all_configs")
    )
    
    markup.row(
        telebot.types.InlineKeyboardButton("🤖 AI Анализ", callback_data="ai_analysis")
    )
    
    markup.row(
        telebot.types.InlineKeyboardButton("❓ Задать вопрос AI", callback_data="ask_ai")
    )
    
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "ai_analysis")
def handle_ai_analysis(call):
    try:
        card_data_list = load_cards_data()
        if not card_data_list:
            bot.answer_callback_query(call.id, "Нет данных для анализа")
            return

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🤖 Выполняю AI анализ данных...",
            parse_mode='HTML'
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ai_response = loop.run_until_complete(analyze_with_ai(card_data_list))
        loop.close()

        response_parts = split_long_message(ai_response)
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(telebot.types.InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu"))

        for i, part in enumerate(response_parts):
            if i == 0:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"🤖 <b>AI Анализ данных</b>\n\n{part}",
                    parse_mode='HTML',
                    reply_markup=markup if len(response_parts) == 1 else None
                )
            else:
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=part,
                    parse_mode='HTML',
                    reply_markup=markup if i == len(response_parts)-1 else None
                )

    except Exception as e:
        logging.error(f"Error in AI analysis handler: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка при выполнении AI анализа")

@bot.callback_query_handler(func=lambda call: call.data == "ask_ai")
def handle_ask_ai(call):
    try:
        card_data_list = load_cards_data()
        if not card_data_list:
            bot.answer_callback_query(call.id, "Нет данных для анализа")
            return

        data_summary = {
            'total_computers': len(card_data_list),
            'price_range': [],
            'components': {'cpu': [], 'gpu': [], 'ram': []}
        }
        
        for card in card_data_list:
            if card['price'].replace('₽', '').replace(' ', '').isdigit():
                data_summary['price_range'].append(int(card['price'].replace('₽', '').replace(' ', '')))
            data_summary['components']['cpu'].append(card['cpu'])
            data_summary['components']['gpu'].append(card['gpu'])
            data_summary['components']['ram'].append(card['ram'])

        msg = bot.send_message(
            call.message.chat.id,
            "🤖 Задайте ваш вопрос о компьютерах, например:\n"
            "- Какие конфигурации лучше всего подходят для игр?\n"
            "- В чём разница между разными видеокартами?\n"
            "- Какое соотношение цена/качество оптимально?",
            reply_markup=telebot.types.ForceReply()
        )
        
        bot.register_next_step_handler(msg, lambda m: process_ai_question(m, data_summary))
        
    except Exception as e:
        logging.error(f"Error in ask_ai handler: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")

if __name__ == '__main__':
    print("Бот запущен...")
    initial_data = load_cards_data()
    print(f"Загружено {len(initial_data)} карточек")
    print(f"Gemini AI интегрирован: {'успешно' if GEMINI_API_KEY else 'ошибка'}")
    bot.polling(none_stop=True)