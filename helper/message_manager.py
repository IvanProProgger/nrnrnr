from telegram import InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.logging_config import logger
from db import db

from helper.messages import INITIATOR, HEAD, FINANCE, PAYMENT
from helper.user_data import get_chat_ids, get_department


class MessageManager:
    """Класс для хранения данных и отправки сообщений по отделам"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MessageManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self._data = {}
        self.db = db
        self.messages = {
            "initiator": INITIATOR,
            "head": HEAD,
            "finance": FINANCE,
            "payment": PAYMENT,
        }

    def __getitem__(self, row_id):
        """Позволяет обращаться к данным как к словарю."""
        return self._data.get(row_id, {})

    def __getattr__(self, name: str):
        """Позволяет обращаться к данным через атрибуты."""
        if name.startswith("_"):
            raise AttributeError(f"Нельзя получить доступ к приватному атрибуту {name}")
        return self._data.get(
            name, AttributeError(f"Нет свойства {name} в {self.__class__.__name__}")
        )

    def __setitem__(self, row_id: int, value: dict):
        """Добавляет или обновляет значение по ID ячейки."""
        if not isinstance(value, dict):
            raise ValueError("Значение должно быть словарем.")
        self._data[row_id] = value

    def __delitem__(self, row_id: int):
        """Удаляет элемент по ID ячейки."""
        if row_id in self._data:
            del self._data[row_id]
        else:
            raise KeyError("ID ячейки не найден.")

    async def __call__(self, row_id: int) -> dict[str, int]:
        """Возвращает данные для указанного row_id."""
        return {"row_id": row_id, **self._data.get(row_id, {})}

    async def update_data(self, row_id: int, data_dict: dict):
        """Обновляет данные ячейки по ID."""
        self._data.setdefault(row_id, {}).update(data_dict)

    async def get_message(self, department, stage, **kwargs) -> str:
        if department not in self.messages:
            raise ValueError(f"Неправильный департамент: {department}")

        if stage not in self.messages[department].keys():
            raise ValueError(f"Неправильная стадия для {department}: {stage}")

        try:
            return self.messages[department][stage].format(**kwargs)
        except Exception as e:
            logger.error(f"Ошибка при форматировании сообщения: {e}")
            raise ValueError(f"Ошибка при форматировании сообщения: {e}")


    async def send_messages_with_tracking(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        row_id,
        chat_ids: list[int | str] | int | str,
        department: str,
        stage: str,
        reply_markup: InlineKeyboardMarkup = None,
    ) -> None:
        """Отправка сообщения в выбранные телеграм-чаты с сохранением message_id и user_id."""

        message_text = await self.get_message(department, stage, **await self(row_id))
        message_ids = []
        actual_chat_ids = []
        logger.info(chat_ids)
        if isinstance(chat_ids, (int, str)):
            chat_ids = [chat_ids]
        for chat_id in chat_ids:
            try:
                message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✨{message_text}✨",
                    reply_markup=reply_markup,
                )
                message_ids.append(message.message_id)
                actual_chat_ids.append(chat_id)
            except Exception as e:
                logger.info(
                    f"🚨Ошибка при отправке сообщения в chat_id: {chat_id}. Ошибка: {e}"
                )
                pass
        self[row_id][f"{department}_messages"] = list(zip(actual_chat_ids, message_ids))

    async def resend_messages_with_tracking(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        row_id: int,
        department: str,
        stage: str,
        reply_markup: InlineKeyboardMarkup = None,
    ) -> None:
        """Отправляет новое и удаляет старое сообщение."""

        key = f"{department}_messages"
        if self[row_id].get(key) is None:
            raise RuntimeError(f"Ошибка! По ключу {department}_messages нет данных!")

        actual_chat_ids = []
        message_ids = []
        message_text = await self.get_message(department, stage, **await self(row_id))
        for chat_id, message_id in self[row_id].get(key):
            try:
                message = await context.bot.send_message(
                    chat_id=chat_id, text=f"🔄{message_text}", reply_markup=reply_markup
                )
                message_ids.append(message.message_id)
                actual_chat_ids.append(chat_id)
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception as e:
                logger.error(f"Не удалось обновить сообщение с chat_id: {chat_id}: {e}")
                pass
        self[row_id][key] = list(zip(actual_chat_ids, message_ids))

    async def send_department_messages(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        row_id: int,
        department: str,
        chat_ids: list[int] | int | str,
        stage: str,
        reply_markup: InlineKeyboardMarkup = None,
    ):
        await self.send_messages_with_tracking(
            context, row_id, chat_ids, department, stage, reply_markup=reply_markup
        )

    async def edit_department_messages(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        row_id: int,
        department: str,
        stage: str,
        reply_markup: InlineKeyboardMarkup = None,
    ):
        await self.resend_messages_with_tracking(
            context, row_id, department, stage, reply_markup=reply_markup
        )

    async def command_reply_message(self, update, context, row_id):
        try:
            department = await get_department(update.effective_chat.id)
            department_chat_ids = await get_chat_ids(department)
            await self.send_messages_with_tracking(
                context, row_id, department_chat_ids, department, stage=""
            )
        except Exception as e:
            logger.error(f"Ошибка в команде reply_message: {e}")

    async def get_all_messages(self, row_id: int) -> list[tuple]:
        all_messages = []

        # Получаем данные для каждого типа сообщений
        for message_type in [
            "initiator_messages",
            "head_messages",
            "finance_messages",
            "payment_messages",
        ]:
            messages = self[row_id].get(message_type, [])
            all_messages.extend(messages)

        if "all_messages" not in self[row_id]:
            self[row_id]["all_messages"] = []

        self[row_id]["all_messages"] = all_messages

        return self[row_id]["all_messages"]


message_manager = MessageManager()
