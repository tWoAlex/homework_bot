"""Homework bot custom exceptions."""


class MinorException(Exception):
    """Небольшие исключения, которые можно пропускать."""


class UnexpectedDatatypes(TypeError, MinorException):
    """Данные приняты в неверной структуре."""


class MissingData(MinorException):
    """В элементе не хватает содержимого."""


class UnexpectedResponse(MinorException):
    """Получен нежелательный ответ."""


class MajorException(Exception):
    """Важные исключения, на которые нельзя закрывать глаза."""


class DataRequestException(MajorException):
    """Исключения при получении данных."""


class TelegramNotificationException(MajorException):
    """Исключения при проталкивании данных в Telegram."""
