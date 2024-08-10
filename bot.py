import logging
import telebot
import requests
import sqlite3
import time
from database import Database
from info import SYSTEM_PROMPT, CONTINUE_STORY, END_STORY
from telebot import types
from config import TOKEN, iam_token, f_id, MAX_TOKENS_IN_SESSION, MAX_USERS, MAX_TOKENS
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# Создаем объект бота
bot = telebot.TeleBot(TOKEN)

DB_FILE = "chatbot.db"
db = Database(DB_FILE)

logging.basicConfig(filename='log_file.txt', level=logging.ERROR)

# Определяем словарь для хранения выбранных данных пользователей
user_data = {}
# Словарь для отслеживания активных пользователей
active_users = {}


# Функция ограничения на использование бота в рамках 2-х пользователей
def is_limit_users():
    connection = sqlite3.connect('chatbot.db')
    cursor = connection.cursor()
    result = cursor.execute('SELECT DISTINCT user_id FROM users;')  # Assuming 'users' table exists with 'user_id'
    count = 0
    for _ in result:
        count += 1
    connection.close()
    return count >= MAX_USERS


def is_user_in_db(user_id):
    connection = sqlite3.connect('chatbot.db')
    cursor = connection.cursor()
    result = cursor.execute('SELECT user_id FROM users WHERE user_id = ?;', (user_id,))
    user = result.fetchone()
    connection.close()
    return user is not None


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if is_limit_users() and not is_user_in_db(user_id):
        bot.send_message(message.chat.id, "Извините, Бот в данный момент занят. Пожалуйста, повторите попытку позже.")
        return
    user_name = message.from_user.first_name
    if is_user_in_db(user_id):
        text = 'Приветствую тебя снова! Воспользуйтесь командой /writing чтобы начать составлять новый сюжет.'
    else:
        db.create_user_if_not_exist(user_id)
        text = f"Приветствую тебя 👋, {user_name}!\n Воспользуйтесь командой /writing чтобы начать составлять новый сюжет."
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['info'])  # получение информации о боте
def info(message):
    bot.send_message(message.chat.id,
                     "Бот-сценарист — это телеграмм-бот с функцией YandexGPT, которая позволяет пользователю"
                     "разрабатывать сюжеты с возможностью добавления к ней своей информации.\n"               
                     "\nЖелаю Вам приятного общения!")


@bot.message_handler(commands=['debug'])  # режим отладки бота
def send_logs(message):
    with open("log_file.txt", "rb") as f:
        bot.send_document(message.chat.id, f)


@bot.message_handler(commands=['help'])  # вывод доступных команд
def say_start(message):
    bot.send_message(message.chat.id, " Доступные команды 📋:\n"
                                      "\n/start - начать диалог"
                                      "\n/help - справочная информация"
                                      "\n/info - получить подробную информацию о Боте-сценаристе>"
                                      "\n/writing – начало составление сюжета"
                                      "\n/limits – ваш профиль с потраченными токенами/сессиями"
                                      "\n/debug - режим отладки бота")


# Обработчик команды для старта бота
@bot.message_handler(commands=['writing'])
def handle_writing(message):
    if not is_user_in_db(message.from_user.id):
        bot.send_message(message.chat.id, f"Извините, {message.from_user.first_name}, вы не авторизованы. Используйте команду /start для начала.")
        return
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_fantasy = types.KeyboardButton('Фантастика')
    button_horror = types.KeyboardButton('Хоррор')
    button_comedy = types.KeyboardButton('Комедия')
    keyboard.add(button_fantasy, button_horror, button_comedy)
    bot.send_message(message.chat.id, "Выбери жанр:", reply_markup=keyboard)


# Обработчик для выбора жанра
@bot.message_handler(func=lambda message: message.text in ['Фантастика', 'Хоррор', 'Комедия'])
def handle_genre(message):
    user_id = message.chat.id
    user_data[user_id] = {'genre': message.text}
    # Создаем клавиатуру с выбором персонажа
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_dasha = types.KeyboardButton('Даша путешественница')
    button_pasha = types.KeyboardButton('Виктор Цой')
    button_yulia = types.KeyboardButton('Маша')
    button_kirill = types.KeyboardButton('Райан Гослинг')
    keyboard.add(button_dasha, button_pasha, button_yulia, button_kirill)

    bot.send_message(message.chat.id, "Выбери персонажа:", reply_markup=keyboard)


# Обработчик для выбора персонажа
@bot.message_handler(func=lambda message: message.text in ['Даша путешественница', 'Виктор Цой', 'Маша', 'Райан Гослинг'])
def handle_character(message):
    user_id = message.chat.id
    user_data[user_id]['character'] = message.text
    # Создаем клавиатуру с выбором локации
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_city = types.KeyboardButton('Город')
    button_forest = types.KeyboardButton('Лес')
    button_desert = types.KeyboardButton('Пустыня')
    keyboard.add(button_city, button_forest, button_desert)

    bot.send_message(message.chat.id, "Выбери локацию:", reply_markup=keyboard)


# Обработчик для выбора локации
@bot.message_handler(func=lambda message: message.text in ['Город', 'Лес', 'Пустыня'])
def handle_location(message):
    user_id = message.chat.id
    user_data[user_id]['location'] = message.text
    send_prompt_or_additional_info(user_id)


def send_prompt_or_additional_info(user_id):
    prompt_button = KeyboardButton('Отправить сразу')
    info_button = KeyboardButton('Дополнительная информация')
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add(prompt_button, info_button)
    bot.send_message(user_id, "Хотите отправить промпт сразу или добавить дополнительную информацию?", reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text == 'Дополнительная информация')
def handle_additional_info(message):
    user_id = message.chat.id
    bot.send_message(user_id, "Введите дополнительную информацию:")
    bot.register_next_step_handler(message, process_additional_info)


def process_additional_info(message):
    user_id = message.chat.id
    additional_info = message.text
    user_data[user_id]['additional_info'] = additional_info
    send_send_button(user_id)


@bot.message_handler(func=lambda message: message.text == 'Отправить сразу')
def handle_send_prompt(message):
    user_id = message.from_user.id
    prompt = create_prompt(user_data, user_id)
    gpt_response = ask_gpt(prompt, [], mode='continue')
    try:
        bot.send_message(user_id, gpt_response)
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 400 and e.description == 'Bad Request: message text is empty':
            logging.error("Error sending message: Telegram API error: message text is empty")
        else:
            logging.error(f"Telegram API error: {e}")
    user_data[user_id] = {}
    send_restart_button(user_id)


def send_send_button(user_id):
    send_button = KeyboardButton('Отправить')
    send_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    send_keyboard.add(send_button)
    bot.send_message(user_id, "Готово! Теперь нажмите на кнопку 'Отправить', чтобы получить историю.", reply_markup=send_keyboard)
    prompt = create_prompt(user_data, user_id)
    gpt_response = ask_gpt(prompt, [], mode='continue')
    try:
        bot.send_message(user_id, gpt_response)
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 400 and e.description == 'Bad Request: message text is empty':
            logging.error("Error sending message: Telegram API error: message text is empty")
        else:
            logging.error(f"Telegram API error: {e}")
    user_data[user_id] = {}
    send_restart_button(user_id)


def send_restart_button(user_id):
    restart_button = types.KeyboardButton('Заново')
    restart_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    restart_keyboard.add(restart_button)
    time.sleep(5)
    bot.send_message(user_id, text='Если хотите продолжить, выберите "Заново"', reply_markup=restart_keyboard)


@bot.message_handler(func=lambda message: message.text == 'Заново')
def handle_restart_button(message):
    handle_restart(message)  # вызываем функцию handle_restart при нажатии на кнопку "Заново"


@bot.message_handler(commands=['restart'])
def handle_restart(message):
    if not is_user_in_db(message.from_user.id):
        bot.send_message(message.chat.id, f"Извините, {message.from_user.first_name}, вы не авторизованы. Используйте команду /start для начала.")
        return
    handle_writing(message)


# Создание промта на основе выбранной/введенной информации пользователем
def create_prompt(user_data, user_id):
    user_session_count, _ = db.get_session_data(user_id)
    if user_session_count >= 3:
        session_count, session_tokens = db.get_session_data(user_id)
        try:
            bot.send_message(user_id, f"Вы превысили лимит сессий {session_count} из 3.")
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 400 and e.description == 'Bad Request: message text is empty':
                logging.error("Error sending message: Telegram API error: message text is empty")
            else:
                logging.error(f"Telegram API error: {e}")
        return
    prompt = _create_prompt(user_data, user_id)
    return prompt


def _create_prompt(user_data, user_id):
    prompt = SYSTEM_PROMPT
    try:
        if user_id in user_data:
            if 'genre' in user_data[user_id] and 'character' in user_data[user_id] and 'location' in user_data[user_id]:
                genre = user_data[user_id]['genre']
                character = user_data[user_id]['character']
                location = user_data[user_id]['location']
                additional_info = user_data[user_id].get('additional_info', 'нет дополнительной информации')
                user_session_count, user_session_tokens = db.get_session_data(user_id)
                prompt += f"\nНапиши начало истории в стиле {genre} с главным героем {character}. "
                prompt += f"Вот начальный сеттинг: \n{location}. \n"
                prompt += f"Также пользователь попросил учесть следующую дополнительную информацию: {additional_info} "
                prompt += 'Не пиши никакие подсказки пользователю, что делать дальше. Он сам знает'
                answer = ask_gpt(prompt, [], mode='continue')
                tokens = prompt.split()
                num_tokens = len(tokens)
                db.save_prompt_to_db(user_id, prompt)
                db.update_session_tokens(user_id, user_session_tokens + num_tokens)
                db.update_session_count(user_id, user_session_count + 1)
                db.update_answer(user_id, answer)
    except Exception as ex:
        logging.error(f"Unexpected error: {str(ex)}")
        return "Произошла непредвиденная ошибка."
    return prompt


# Отправка промта на API YandexGPT-lite
def ask_gpt(prompt, collection, mode='continue'):
    try:
        token = iam_token
        folder_id = f_id
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        data = {
            "modelUri": f"gpt://{folder_id}/yandexgpt-lite",
            "completionOptions": {"stream": False, "temperature": 0.6, "maxTokens": MAX_TOKENS},
            "messages": [{
                "role": "user",
                "text": prompt
            }]
        }
        for row in collection:
            if isinstance(row, dict) and 'content' in row:
                content = row['content']
                if mode == 'continue' and row['role'] == 'user':
                    content += '\n' + CONTINUE_STORY
                elif mode == 'end' and row['role'] == 'user':
                    content += '\n' + END_STORY
                data["messages"].append({"role": row["role"], "text": content})
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            logging.error(f"Status code {response.status_code}.")
            return # отправка сообщений при отклонении промта на API
        response_text = response.json()['result']['alternatives'][0]['message']['text']
        tokens = response_text.split()
        if len(tokens) > 500:
            response_text = ' '.join(tokens[:500])
        return response_text
    except KeyError:
        return "Произошла ошибка. Отсутствует ключ 'content' в данных."
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return "Произошла непредвиденная ошибка."


def exist_user(user_id):
    connection = sqlite3.connect('chatbot.db')
    cur = connection.cursor()
    query = f'''SELECT user_id FROM users_data WHERE user_id = {user_id}'''
    results = cur.execute(query)
    try:
        results = results.fetchone()[0]
    except:
        results = None
    connection.close()
    return results == user_id


def count_tokens(message):
    user_id = message.from_user.id
    connection = sqlite3.connect('chatbot.db')
    cur = connection.cursor()
    user_data = cur.execute(f'''SELECT * FROM users_data WHERE User to {user_id}''').fetchone()
    folder_id = f_id
    session_tokens = user_data[4]
    prompt = user_data(1)
    token = iam_token
    headers = {  # заголовок запроса, в котором передается IΑΜ-τοкен
        "Authorization": f"Bearer {token}",  # token - наши ШАМ-токен
        "Content-Type": "appLication/json"
    }
    data = {
        "modellird": f"gpt: //{folder_id}/yandexgpt-lite/latest",  # указываен folder_id
        "maxTokens": MAX_TOKENS_IN_SESSION,
        "text": prompt
    }

    tokens = cur.execute(f'''SELECT session_tokens FROM users_data WHERE user_id = (user_id)''').fetchone()[0]
    int(str(tokens))
    new_tokens = tokens + len(requests.post("https://lln.apis.cloud.yandex.net/foundationfodels/v1/tokenize", json=data, headers=headers).json()['tokens'])

    sql_query = "UPDATE users_data SET session_tokens = ? WHERE user_id = ?;"
    cur.execute(sql_query,  (new_tokens, user_id))
    connection.commit()

    if session_tokens > MAX_TOKENS_IN_SESSION:
        bot.send_message(message.chat.id, text="У вас закончилость доступное кол-во токенов в этой сессии")
    else:
        ask_gpt(message, [], mode='continue')
    connection.close()


@bot.message_handler(commands=['limits'])
def limits(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_limits = types.KeyboardButton('/limits')
    keyboard.add(button_limits)
    user_id = message.from_user.id
    session_count, session_tokens = db.get_session_data(user_id)
    bot.send_message(user_id, f"\nКоличество сессий: {session_count} из 3 \nПотраченные токены на отправку: {session_tokens}")


@bot.message_handler(content_types=['photo', 'video', 'audio', 'document', 'sticker'])
def handle_non_text_message(message):
    bot.send_message(message.chat.id, "❗ Извините, не могу обработать фотографии, видео, аудио, документы или стикеры.")


bot.polling()

