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

API_ANSWERS_PATTERNS = {
    'correct': (dict, {
        'homeworks': (list, (dict, {
            'status': (str, None),
            'homework_name': (str, None),
        })),
        'current_date': (int, None)
    }),
    'unresolved': (dict, {
        'code': (str, 'UnknownError'),
        'error': (dict, {'error': (str, 'from_date ')}),
    }),
    'broken_token': (dict, {
        'code': (str, 'not_authenticated'),
        'message': (str, None),
        'source': (str, None)
    })
}


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
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            message = (f'Эндпоинт "{ENDPOINT}" недоступен.'
                       f' Код ответа API: {response.status_code}')
            raise LookupError(message)
        else:
            message = ('Эндпоинт сообщил об ошибке.'
                       f' Код ответа API: {response.status_code}')
            raise LookupError(message)
    except Exception as error:
        message = (f'Ошибка при запросе на эндпоинт "{ENDPOINT}".'
                   f' Сообщение об ошибке: "{error}"')
        raise LookupError(message)


def check_pattern(data, datatype, inner):
    """Проверяет данные на соответствие шаблону."""
    if type(data) is not datatype:
        return False
    if datatype is list:
        return all([check_pattern(item, inner[0], inner[1]) for item in data])
    elif datatype is dict:
        if type(inner) is not dict:
            return False
        else:
            if not all([key in data for key in inner.keys()]):
                return False
            return all([check_pattern(data[key], inner[key][0], inner[key][1])
                        for key in inner.keys()])
    elif datatype in [int, float, str, bool]:
        if inner:
            return type(inner) is datatype and data == inner
        return True
    return False


def check_response(response):
    """Проверяет ответ на соответствие документации API."""
    if type(response) != dict:
        raise TypeError('API должен отправлять в ответ словарь')

    for name, pattern in API_ANSWERS_PATTERNS.items():
        if check_pattern(response, pattern[0], pattern[1]):
            return name

    raise TypeError(
        'Содержимое ответа API не соответствует ожидаемым шаблонам'
    )


def parse_status(homework):
    """Получает из словаря с данными о домашней работе её статус."""
    if 'homework_name' in homework and 'status' in homework:
        homework_name = homework['homework_name']
        status = homework['status']

        if status not in HOMEWORK_VERDICTS:
            raise KeyError(f'Неизвестный статус задания: "{status}"')
    else:
        raise LookupError('API вернул ответ не про домашки.')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) * 0

    last_error_message = ''
    ready = check_tokens()
    while ready:
        try:
            api_answer = get_api_answer(timestamp)
            check_response(api_answer)
            homeworks = api_answer['homeworks']
            if not homeworks:
                logging.debug('Новых статусов работ не обнаружено.')
            for homework in homeworks:
                status = parse_status(homework)
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
