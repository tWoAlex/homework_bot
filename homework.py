import os
import sys
import time
import logging
from dotenv import load_dotenv

import requests
import telegram


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

EXCEPTION_MESSAGE_PATTERN = 'Сбой в работе программы: "{}"'


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


def check_tokens():
    """Проверяет наличие и корректность переменных окружения."""
    environment_variables = {
        PRACTICUM_TOKEN: 'PRACTICUM_TOKEN',
        TELEGRAM_TOKEN: 'TELEGRAM_TOKEN',
        TELEGRAM_CHAT_ID: 'TELEGRAM_CHAT_ID'
    }
    message_pattern = ('Отсутствует обязательная переменная окружения:'
                       ' {}. Программа принудительно остановлена.')
    result = True
    for variable, name in environment_variables.items():
        if not variable:
            logging.critical(message_pattern.format(name))
            result = False
    return result


def send_message(bot, message):
    """Посылает Telegram-боту bot сообщение message."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.debug('Бот отправил сообщение "{message}"')
    except Exception as error:
        logging.error(
            f'Не удалось отправить сообщение в Telegram. Ошибка: "{error}"'
        )


def get_api_answer(timestamp):
    """Получает ответ API Практикума."""
    payload = {'from_date': {timestamp}}
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=payload
        )
        if response.status_code == 404:
            message = (f'Эндпоинт "{ENDPOINT}" недоступен.'
                       f' Код ответа API: {response.status_code}')
            raise LookupError(message)
        else:
            return response.json()
    except Exception as error:
        message = (f'Ошибка при запросе на эндпоинт "{ENDPOINT}".'
                   f' Сообщение об ошибке: "{error}"')
        logging.error(message)


def check_response(response):
    """Проверяет ответ на соответствие документации API."""
    if not response:
        return False
    expected_keys = ['homeworks', 'current_date']
    for key in expected_keys:
        if key not in response:
            raise KeyError(f'Ключ "{key}" не найден в ответе API')
    return True


def parse_status(homework):
    """Получает из словаря с данными о домашней работе её статус."""
    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неизвестный статус задания: "{status}"')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    last_error_message = ''
    ready = check_tokens()
    while ready:
        try:
            api_answer = get_api_answer(timestamp)
            if check_response(api_answer):
                homeworks = api_answer['homeworks']
                if not homeworks:
                    logging.debug('Новых статусов работ не обнаружено.')
                for data in homeworks:
                    status = parse_status(data)
                    if status:
                        send_message(bot, status)
                timestamp = api_answer['current_date']

        except Exception as error:
            logging.error(error)

            error = str(error)
            if last_error_message != error:
                last_error_message = error
                send_message(bot, error)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
