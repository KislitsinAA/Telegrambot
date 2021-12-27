import logging
import os
import sys
import time
import exceptions as exc
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


VERDICTS = {
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
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        logger.error('Не удалось отправить сообщение')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            logger.error(
                f'Сбой в работе программы: эндпоинт {ENDPOINT} недоступен.'
                f'Код ответа API: {response.status_code}'
            )
            raise Exception('Ошибка API ^_^')
    except Exception as error:
        logger.error(f'Ошибка запроса: {error}')
        raise exc.RequestFault('Ошибка запроса')
    if response.status_code != HTTPStatus.OK:
        logger.error(
            f'Сбой в работе программы: эндпоинт {ENDPOINT} недоступен.'
            f'Код ответа API: {response.status_code}'
        )
        raise Exception('Ошибка API ^_^')
    return response.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('API прислал странный ответ :(')
    if len(response) == 0:
        raise Exception('Пришел пустой ответ:(')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет твоей домашки :(')
    if not isinstance(response['homeworks'], list):
        raise Exception(
            'Под ключом `homeworks` домашки приходят не в виде списка'
        )
    return response['homeworks']


def parse_status(homework):
    """Проверка статуса домашней работы."""
    for key in ['homework_name', 'status']:
        if key not in homework:
            logger.error(f'В ответе API отсутствует ожидаемый ключ: {key}')
            raise KeyError(f'В ответе API отсутствует ожидаемый ключ: {key}')
    homework_name = homework['homework_name']
    status = homework['status']
    try:
        verdict = VERDICTS[status]
    except Exception:
        logger.error(f'Полученный статус не поддерживается: {status}')
        raise KeyError(f'Полученный статус не поддерживается: {status}')
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
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    button = ReplyKeyboardMarkup([['/homework']], resize_keyboard=True)
    last_status_message = []
    last_error_message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            for homework in check_response(response):
                message = parse_status(homework)
                if message not in last_status_message:
                    send_message(bot, parse_status(homework))
                    last_status_message.append(message)
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.info(f'Бот отправил сообщение: {message}')
            if last_error_message != message:
                bot.send_message(
                    TELEGRAM_CHAT_ID,
                    message,
                    reply_markup=button
                )
            last_error_message = message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
