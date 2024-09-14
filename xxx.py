import asyncio
from typing import Tuple, Dict, Any, Coroutine

from config.logging_config import logger
from helper.messages import INITIATOR, HEAD, FINANCE, PAYMENT, RESULT
from helper.user_data import get_chat_ids


class MessageManager:

    def __init__(self):
        self._data = {}
        self.messages = {
            "initiator": INITIATOR,
            "head": HEAD,
            "finance": FINANCE,
            "payment": PAYMENT,
            "result": RESULT,
        }

    async def add_new_record(self, record_dict: dict):

        if not isinstance(record_dict, dict):
            raise TypeError("record_dict должен быть словарем")

        row_id =  next(iter(record_dict))
        if not row_id:
            raise ValueError("В record_dict должен быть указан 'row_id'.")

        if row_id not in self._data:
            self._data[row_id] = {}

        self._data[row_id].update({
            "initiator_chat_id": record_dict[row_id]["initiator_chat_id"],
            "initiator_nickname": record_dict[row_id]["initiator_nickname"],
            "record_data_text": record_dict[row_id]["record_data_text"]
        })

    def __getitem__(self, row_id):
        """Позволяет обращаться к данным как к словарю."""
        return self._data.get(row_id, {})

    def __getattr__(self, name):
        """Позволяет обращаться к данным через атрибуты."""
        if name.startswith('_'):
            raise AttributeError(f"Нельзя получить доступ к приватному атрибуту {name}")

        value = self._data.get(name)
        if value is not None:
            return value

        raise AttributeError(f"Нет свойства {name} в {self.__class__.__name__}")

    def get(self):
        return self._data

    def __setattr__(self, name, value):
        """Позволяет устанавливать значения в self._data[name] через точечную нотацию."""
        if name in {'_data', 'messages', 'db'}:
            super().__setattr__(name, value)
        elif isinstance(value, dict):
            self._data.setdefault(name, {}).update(value)
        else:
            raise ValueError(f"Значение должно быть словарем для {name}")

    async def __call__(self, row_id: int) -> dict[str, int]:
        """Возвращает данные для указанного row_id."""
        return {"row_id": row_id, ** self._data.get(row_id)}


    # async def get_message(self, department, stage, row_id) -> str:
    #     if department not in self.messages:
    #         raise ValueError(f"Неправильный департамент: {department}")
    #
    #     if stage not in self.messages[department].keys():
    #         raise ValueError(f"Неправильная стадия для {department}: {stage}")
    #
    #     return self.messages[department][stage].format(** await self(row_id))

    async def get_message(self, department, stage, **kwargs) -> str:
        if department not in self.messages:
            raise ValueError(f"Неправильный департамент: {department}")

        if stage not in self.messages[department].keys():
            raise ValueError(f"Неправильная стадия для {department}: {stage}")

        message_template = self.messages[department][stage]
        return message_template.format(**kwargs)

    async def send_initiator_to_head(self, context, row_id):
        message = await self.get_message("initiator", "initiator_to_head", ** await self(row_id))
        logger.info(message)
        # await self.send_messages_with_tracking(
        #     context,
        #     row_id,
        #     await get_chat_ids("head"),
        #     "head",
        #     message,
        #     "initiators",
        # )

"context: ContextTypes.DEFAULT_TYPE,row_id,chat_ids: list[int | str] | int | str,message_text: str,department: str,reply_markup: InlineKeyboardMarkup = None,"


async def main():
    message_manager = MessageManager()
    await message_manager.add_new_record(
        {
            5: {
                "row_id": 5,
                "initiator_chat_id": 123123,
                "initiator_nickname": "@хуй",
                "record_data_text": "хуйхуйхуй",
            }
        }
    )
    row_id = 5
    print(await message_manager(row_id))
    await message_manager.send_initiator_to_head(None, row_id)
    # a = await message_manager.get_message("initiator", "initiator_to_head")
    # print(a)


result = asyncio.run(main())
print(result)