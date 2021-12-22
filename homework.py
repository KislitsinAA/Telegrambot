import logging
import os
import sys

import requests
import time
import telegram
from dotenv import load_dotenv
from http import HTTPStatus
from telegram.ext import Updater
from telegram import ReplyKeyboardMarkup
from telegram.ext.commandhandler import CommandHandler

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)

handler = logging.StreamHandler(sys.stdout)


formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def send_message(bot, message):
    """Отправка сообщения в телеграм-чат."""
    logger.info('Отправка сообщения')
    bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code is not HTTPStatus.OK:
        logger.error(
            f'Сбой в работе программы: эндпоинт {ENDPOINT} недоступен.'
            'Код ответа API: {response.status_code}'
        )
        raise Exception('Ошибка API ^_^')
    return response.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    if type(response) is not dict:
        raise TypeError('API прислал странный ответ :(')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет твоей домашки :(')
    if type(response['homeworks']) is not list:
        raise Exception(
            'Под ключом `homeworks` домашки приходят не в виде списка'
        )
    return response['homeworks']


def parse_status(homework):
    """Проверка статуса домашней работы."""
    for key in ['homework_name', 'status']:
        if key not in homework:
            logger.error(f'В ответе API отсутствует ожидаемый ключ: {key}')
    homework_name = homework['homework_name']
    status = homework['status']
    verdict = HOMEWORK_STATUSES[status]
    return f'Изменился статус проверки работы "{homework_name}": {verdict}'


def check_tokens():
    """Проверка обязательных переменных окружения, где хранятся токены."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    for name in tokens:
        if name is None:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: {name}'
            )
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise Exception('Отсутствуют обязательные переменные окружения')
    updater = Updater(token=TELEGRAM_TOKEN)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    button = ReplyKeyboardMarkup([['/homework']], resize_keyboard=True)
    last_message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            for homework in check_response(response):
                send_message(bot, parse_status(homework))
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.info(f'Бот отправил сообщение: {message}')
            if last_message != message:
                bot.send_message(
                    TELEGRAM_CHAT_ID,
                    message,
                    replymarkup=button
                )
            last_message = message
            time.sleep(RETRY_TIME)

        updater.dispatcher.add_handler(
            CommandHandler('start', send_message)
        )
        updater.dispatcher.add_handler(
            CommandHandler('homework', parse_status)
        )
        updater.start_polling()


if __name__ == '__main__':
    main()
