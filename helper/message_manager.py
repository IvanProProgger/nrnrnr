from telegram import InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.logging_config import logger
from db import db

from helper.messages import INITIATOR, HEAD, FINANCE, PAYMENT, ALL
from helper.user_data import get_chat_ids, get_department

from asyncio import gather
from pympler.tracker import SummaryTracker
import time

# Настройка трота
import tracemalloc


tracemalloc.start()


class MessageManager:
    """Класс для хранения данных и отправки сообщений по отделам"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MessageManager, cls).__new__(cls)
            cls._instance._initialize()
            logger.info(cls._instance)
        return cls._instance

    def _initialize(self):
        self._data = {}
        self.db = db
        self.messages = {
            "initiator": INITIATOR,
            "head": HEAD,
            "finance": FINANCE,
            "payment": PAYMENT,
            "result": ALL,
        }

    def __del__(self):
        if hasattr(self, '_del_called'):
            return
        self._del_called = True

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

    def __setattr__(self, name, value):
        """Позволяет устанавливать значения в self._data[name] через точечную нотацию."""
        if name in {"_data", "messages", "db"}:
            logger.info(self(130))
            super().__setattr__(name, value)
            logger.info(self._data)
        elif isinstance(value, dict):
            logger.info(self._data)
            self._data.setdefault(name, {}).update(value)
        else:
            logger.info(self._data)
            raise ValueError(f"Значение должно быть словарем для {name}")

    async def __call__(self, row_id: int) -> dict[str, int]:
        """Возвращает данные для указанного row_id."""
        return {"row_id": row_id, **self._data.get(row_id, {})}

    async def add_new_record(self, record_dict: dict):
        if not isinstance(record_dict, dict):
            raise TypeError("record_dict должен быть словарем")

        row_id = next(iter(record_dict))
        if not row_id:
            raise ValueError("В record_dict должен быть указан 'row_id'.")

        self._data.setdefault(row_id, {})
        await self.update_data(
            row_id,
            {
                k: record_dict[row_id].get(k)
                for k in [
                    "initiator_chat_id",
                    "initiator_nickname",
                    "record_data_text",
                    "amount",
                ]
            },
        )
        logger.info(f"After sending messages, _data: {self._data}")

    async def update_data(self, row_id: int, data_dict: dict):
        self._data[row_id].update(data_dict)

    async def get_message(self, department, stage, **kwargs) -> str:
        if department not in self.messages:
            raise ValueError(f"Неправильный департамент: {department}")

        if stage not in self.messages[department].keys():
            raise ValueError(f"Неправильная стадия для {department}: {stage}")

        try:
            return self.messages[department][stage].format(**kwargs)
        except Exception as e:
            raise f"Некорректные аргументы для получения сообщения: {e}"

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
        logger.info(message_text)
        message_ids = []
        actual_chat_ids = []
        if isinstance(chat_ids, (int, str)):
            chat_ids = [chat_ids]
        for chat_id in chat_ids:
            try:
                message = await context.bot.send_message(
                    chat_id=chat_id, text=f"✨{message_text}✨", reply_markup=reply_markup
                )
                message_ids.append(message.message_id)
                actual_chat_ids.append(chat_id)
            except Exception as e:
                logger.info(
                    f"🚨Ошибка при отправке сообщения в chat_id: {chat_id}. Ошибка: {e}"
                )
                pass
        self._data.get(row_id)[f"{department}_messages"] = list(
            zip(actual_chat_ids, message_ids)
        )

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
        if (await self(row_id)).get(key) is None:
            raise RuntimeError(f"Ошибка! По ключу {department}_messages нет данных!")

        actual_chat_ids = []
        message_ids = []
        message_text = await self.get_message(department, stage, **await self(row_id))
        for chat_id, message_id in self._data[row_id].get(key):
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                message = await context.bot.send_message(
                    chat_id=chat_id, text=f"🔄{message_text}"
                )
                message_ids.append(message.message_id)
                actual_chat_ids.append(chat_id)
                # await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception as e:
                logger.error(f"Не удалось обновить сообщение с chat_id: {chat_id}: {e}")
                pass
        logger.info(f"After sending messages, _data: {self._data}")
        self._data.get(row_id)[key] = list(zip(actual_chat_ids, message_ids))
        logger.info(f"After sending messages, _data: {self._data}")

    async def send_department_messages(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        row_id: int,
        department: str,
        chat_ids: list[int] | int | str,
        stage: str,
        reply_markup: InlineKeyboardMarkup = None,
    ):

        logger.info(f"Before sending messages, _data: {self._data}")
        await self.send_messages_with_tracking(
            context, row_id, chat_ids, department, stage, reply_markup=reply_markup
        )
        logger.info(f"After sending messages, _data: {self._data}")

    async def edit_department_messages(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        row_id: int,
        department: str,
        stage: str,
    ):
        await self.resend_messages_with_tracking(
            context, row_id, department, stage, reply_markup=None
        )
        logger.info(f"After sending messages, _data: {self._data}")

    async def command_reply_message(self, update, context, row_id):
        department = await get_department(update.effective_chat.id)
        department_chat_ids = await get_chat_ids(self._data[row_id].get(department))
        await self.send_messages_with_tracking(
            context, row_id, department_chat_ids, department, stage=""
        )


message_manager = MessageManager()
