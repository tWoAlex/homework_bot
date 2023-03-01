import os
import sys
import time
import logging
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (MinorException, MajorException, DataRequestException,
                        UnexpectedResponse, UnexpectedDatatypes, MissingData)


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 60 * 10
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
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('homework.log', mode='w'),
    ]
)


def check_tokens() -> bool:
    """Проверяет наличие и корректность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,))


def send_message(bot: telegram.Bot, message: str) -> None:
    """Посылает Telegram-боту bot сообщение message."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
    except telegram.error.NetworkError as network_error:
        logging.error(
            'Не удалось установить соединение с сетью Telegram.',
            exc_info=network_error
        )
        logging.error(f'Неотправленное сообщение: "{message}"')
    except telegram.error.TelegramError as error:
        logging.error(
            'Не удалось отправить сообщение в Telegram.',
            exc_info=error
        )
        logging.error(f'Неотправленное сообщение: "{message}"')
    else:
        logging.debug(f'Бот отправил сообщение "{message}"')


def get_api_answer(timestamp: int) -> dict:
    """Получает ответ API Практикума."""
    payload = {'from_date': {timestamp}}
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=payload
        )
        if response.status_code == HTTPStatus.OK:
            return response.json()
        elif response.status_code == HTTPStatus.NOT_FOUND:
            message = (f'Эндпоинт "{ENDPOINT}" недоступен.'
                       f' Код ответа API: {response.status_code}')
            raise DataRequestException(message)
        else:
            message = ('Эндпоинт сообщил об ошибке.'
                       f' Код ответа API: {response.status_code}')
            raise DataRequestException(message)
    except Exception as error:
        message = (f'Ошибка при запросе на эндпоинт "{ENDPOINT}".'
                   f' Сообщение об ошибке: "{error}"')
        raise DataRequestException(message)


def check_response(response: dict) -> None:
    """Проверяет ответ на соответствие документации API."""
    if not isinstance(response, dict):
        raise UnexpectedDatatypes('API ответил не словарём.')
    if ('homeworks' not in response
       or 'current_date' not in response):
        raise UnexpectedResponse(
            'API не дал удовлетворительный ответ. Не хватает ключей.'
        )
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise UnexpectedDatatypes('API прислал домашки не списком.')


def parse_status(homework: dict) -> str:
    """Получает из словаря с данными о домашней работе её статус."""
    if ('homework_name' not in homework
       or 'status' not in homework):
        raise MissingData('В данных о домашке не хватает ключей.')

    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise UnexpectedResponse(f'Неизвестный статус задания: "{status}"')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    is_ready = check_tokens()
    if not is_ready:
        logging.critical(
            ('Отсутствуют обязательные переменные окружения.'
             'Программа принудительно остановлена.')
        )

    last_error_message = ''
    while is_ready:
        try:
            api_answer = get_api_answer(timestamp)
            check_response(api_answer)
            homeworks = api_answer['homeworks']
            if not homeworks:
                logging.debug('Новых статусов работ не обнаружено.')
            for homework in homeworks:
                status = parse_status(homework)
                send_message(bot, status)
                time.sleep(0.5)
            timestamp = api_answer['current_date']

        except MajorException as error:
            logging.error(error, exc_info=error)
            error = str(error)
            if last_error_message != error:
                last_error_message = error
                send_message(bot, error)

        except MinorException as minor:
            logging.warning(minor, exc_info=minor)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
