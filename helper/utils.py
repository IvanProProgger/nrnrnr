from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from datetime import datetime
from db import db


async def validate_period_dates(period: str) -> str:
    """Проверяет корректность формата дат."""
    try:
        return " ".join(
            [
                datetime.strptime(f"01.{date}", "%d.%m.%y").strftime("%d.%m.%Y")
                for date in period.split()
            ]
        )
    except Exception as e:
        raise RuntimeError(
            f"Введены неверные даты. Даты вводятся в формате mm.yy. "
            f'строго через пробел(например: "08.22 10.22").\n'
            f"Ошибка: {e}"
        )


async def get_record_by_id(row_id: int) -> dict:
    """
    Получает запись из базы данных по id.
    """
    async with db:
        record_dict = await db.get_row_by_id(row_id)
    return record_dict


async def get_record_info(record_dict: dict) -> str:
    """
    Получает детали конкретного счета из базы данных и форматирует их для бота.
    """
    return (
        f"Данные счета:\n"
        f'1.Сумма: {record_dict["amount"]}₽;\n'
        f'2.Статья: "{record_dict["expense_item"]}"\n'
        f'3.Группа: "{record_dict["expense_group"]}"\n'
        f'4.Партнер: "{record_dict["partner"]}"\n'
        f'5.Комментарий: "{record_dict["comment"]}"\n'
        f'6.Даты начисления: "{", ".join(record_dict["period"].split())}"\n'
        f'7.Форма оплаты: "{record_dict["payment_method"]}"\n'
    )


async def create_approval_keyboard(
    row_id: str | int, department: str
) -> InlineKeyboardMarkup:
    """Создание кнопок "Одобрить" и "Отклонить", создание и отправка сообщения для одобрения заявки."""

    keyboard = [
        [
            InlineKeyboardButton(
                text="Одобрить",
                callback_data=f"approval_approve_{department}_{row_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="Отклонить",
                callback_data=f"approval_reject_{department}_{row_id}",
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def create_payment_keyboard(row_id: int) -> InlineKeyboardMarkup:
    """
    Создание кнопок "Оплачено",
    создание и отправка сообщения для одобрения заявки.
    """

    keyboard = [[InlineKeyboardButton("Оплачено", callback_data=f"payment_{row_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


async def split_long_message(text: str) -> list[str]:
    """Функция для разделения текста свыше 4096 символов"""
    max_length = 4096
    parts = []
    current_part = ""

    for line in text.split("\n"):
        if len(current_part) + len(line) + 1 <= max_length:
            current_part += (current_part and "\n") + line
        else:
            parts.append(current_part)
            current_part = line

    if current_part:
        parts.append(current_part)

    return parts
