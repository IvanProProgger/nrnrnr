# from telegram import InlineKeyboardMarkup
# from telegram.ext import ContextTypes
#
# from config.logging_config import logger
# from db import db
# from helper.message_manager import MessageManager
# from helper.user_data import get_chat_ids
# from helper.utils import create_approval_keyboard
#
#
# class Initiator(MessageManager):
#
#     def __init__(self, row_id, chat_id, nickname):
#         self.row_id = row_id
#         self.chat_id = chat_id
#         self.nickname = nickname
#         self.initiators_messages_dict = {}
#
#     async def messages(self):
#         STAGE_1 = f"Вы добавили новый счёт №{self.row_id}.\nСчёт передан на согласование руководителю департамента.\n{self.record_data_text}"
#
