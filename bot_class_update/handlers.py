import textwrap
import tracemalloc

from telegram import Update
from telegram.ext import ContextTypes

from config.config import Config
from config.logging_config import logger

from helper.message_manager import message_manager
from helper.utils import (
    validate_period_dates,
    split_long_message,
    get_record_info,
    create_approval_keyboard,
)
from bot_class_update.sheets import add_record_to_google_sheet

from helper.user_data import get_nickname, get_chat_ids, get_department
from db import db


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in Config.white_list:
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        logger.warning("В бота пытаются зайти посторонние...")
        return


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""

    await update.message.reply_text(
        f"<b>Бот по автоматизации заполнения бюджета</b>\n\n"
        "<i>Отправьте команду /enter_record и укажите:</i>\n"
        "<i>1) Сумма счёта</i>\n"
        "<i>2) Статья расхода</i>\n"
        "<i>3) Группа расхода</i>\n"
        "<i>4) Партнёр</i>\n"
        "<i>5) Дата оплаты и дата начисления платежа через пробел</i>\n"
        "<i>6) Форма оплаты</i>\n"
        "<i>7) Комментарий к платежу</i>\n"
        "<i>Каждый пункт необходимо указывать строго через запятую.</i>\n\n"
        "<i>Вы можете просмотреть необработанные платежи командой /show_not_paid</i>\n\n"
        "<i>Одобрить заявку можно командой /approve_record указав id платежа</i>\n\n"
        "<i>Отклонить заявку можно командой /reject_record указав id платежа</i>\n\n"
        f"<i>Ваш chat_id - {update.message.chat_id}</i>",
        parse_mode="HTML",
    )


async def submit_record_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Обработчик введённого пользователем платежа в соответствии с паттерном:
    Добавление платежа в базу данных 'approvals';
    Отправка данных о платеже для одобрения главой отдела.
    """

    try:
        record_dict = await process_input(update, context)
    except Exception as e:
        raise RuntimeError(
            f"Не удалось получить данные из аргументов submit_record. Ошибка: {e}"
        )
    try:
        row_id = await add_record_to_storage(update, record_dict)
    except Exception as e:
        raise RuntimeError(
            f"Ошибка в процессе добавления данных в бд и класс MessageManager: {e}"
        )

    try:
        department = "initiator"
        initiator_chat_id, stage = (
            # (await message_manager(row_id)).get("initiator_chat_id"),
            update.effective_chat.id,
            # logger.info(message_manager._data),
            "initiator_to_head",
        )
        # amount = (await message_manager(row_id))
        # logger.info(amount)
        if not context.bot_data.get("initiator_message"):
            await message_manager.send_department_messages(
                context, row_id, department, initiator_chat_id, stage
            )

        department = "head"
        head_chat_id, stage = await get_chat_ids(department), "from_initiator"
        # logger.info(message_manager._data)
        await message_manager.send_department_messages(
            context,
            row_id,
            department,
            head_chat_id,
            stage,
            reply_markup=await create_approval_keyboard(row_id, department)
        )
    except Exception as e:
        raise RuntimeError(
            f"Ошибка при отправке сообщений иницитиатору и руководителю отдела маркетинга: {e}"
        )


async def process_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> dict[str, float | str | int]:
    """Обработчик аргументов команды /submit_record."""

    initiator_chat_id = update.effective_chat.id
    if not context.args:
        raise ValueError("Необходимо указать данные счёта.")

    user_args = [x.strip() for x in " ".join(context.args).split(";")]
    try:
        record_dict = {
            "amount": float(user_args[0]),
            "expense_item": user_args[1],
            "expense_group": user_args[2],
            "partner": user_args[3],
            "comment": user_args[4],
            "period": await validate_period_dates(user_args[5]),
            "payment_method": user_args[6],
            "approvals_needed": 1 if float(user_args[0]) < 50000 else 2,
            "approvals_received": 0,
            "status": "Not processed",
            "approved_by": None,
            "initiator_id": initiator_chat_id,
        }
    except Exception as e:
        raise RuntimeError(
            f"Заданы неверные аргументы! Некоторые аргументы "
            f"не удалось преобразовать к ожидаемому виду. Ошибка: {e}"
        )
    return record_dict


async def add_record_to_storage(update: Update, record_dict: dict) -> int:

    initiator_chat_id = update.effective_chat.id
    async with db:
        row_id = await db.insert_record(record_dict)

    record_data_text = await get_record_info(record_dict)
    amount = record_dict.get("amount")
    initiator_nickname = await get_nickname("initiator", initiator_chat_id)
    await message_manager.add_new_record(
        {
            row_id: {
                "initiator_chat_id": initiator_chat_id,
                "initiator_nickname": initiator_nickname,
                "record_data_text": record_data_text,
                "amount": amount,
            }
        }
    )


    return row_id


async def approval_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик нажатий пользователем кнопок "Одобрить" или "Отклонить."
    """
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    print("[ Top 10 ]")
    for stat in top_stats[:10]:
        print(stat)
    try:

        query = update.callback_query
        _, action, department, row_id = query.data.split("_")
        row_id = int(row_id)
        # logger.info(await message_manager(row_id))
        approver = await get_nickname(department, query.from_user.id)
    except Exception as e:
        raise RuntimeError(f'Ошибка обработки кнопок "Одобрить" и "Отклонить". {e}')

    try:
        # распределяем данные платежа по отделам для принятия решения об одобрении
        logger.info(await message_manager(row_id))
        # amount = (await message_manager(row_id))

        amount = message_manager._data[row_id]["amount"]
        await approval_process(
            context, update, action, row_id, approver, department, amount
        )
    except Exception as e:
        raise RuntimeError(f"Не удалось распределить данные по отделам: {e}")


async def approval_process(
    context: ContextTypes.DEFAULT_TYPE,
    update: Update,
    action: str,
    row_id: str,
    approver: str,
    department: str,
    amount: float,
) -> None:
    """Обработчик платежей для одобрения или отклонения."""

    if action == "approve":
        if department == "head" and amount >= 50000:
            await approve_to_financial_department(context, update, row_id, approver)

        else:
            await approve_to_payment_department(
                context, update, row_id, approver, department
            )

    else:
        await reject_record(context, row_id, approver)


async def approve_to_financial_department(
    context: ContextTypes.DEFAULT_TYPE, update: Update, row_id: str, approver: str
) -> None:
    """
    Изменение количества апрувов и статуса платежа.
    Отправка сообщения о платеже свыше 50.000 в финансовый отдел на согласование платежа.
    Изменение сообщения от бота в чатах участников департамента "head"
    """
    # Добавляем
    approvals_received, status = 1, "Pending"
    await update_storage_data(row_id, status, approver, approvals_received=None)

    # меняем сообщение инициатору
    department, stage = "initiator", "head_to_finance"
    initiator_chat_id = (await message_manager(row_id))["initiator_chat_id"]
    message_manager.edit_department_messages(
        context, row_id, department, initiator_chat_id, stage, reply_markup=None
    )

    # меняем сообщение руководителю департамента или создаём
    # ответное новое сообщение на команду руководителя департамента
    if message_manager(row_id).get("head_message_id"):
        message_manager.edit_department_messages(
            context, row_id, department, initiator_chat_id, stage, reply_markup=None
        )
    else:
        await message_manager.command_reply_message(update, context, row_id)

    # отправляем сообщение сотрудникам финансового отдела

    await message_manager.edit_department_messages(
        context, row_id, department, initiator_chat_id, stage, reply_markup=None
    )


async def update_storage_data(
    row_id: str, status: str, approver: str = None, approvals_received: str = None
):
    # logger.info(message_manager._data)
    try:
        async with db:
            is_approver_exist = await db.get_column_by_id("approved_by", row_id)
            if is_approver_exist:
                approver = f"{is_approver_exist} и {approver}"
            await db.update_row_by_id(
                row_id,
                {
                    "approvals_received": approvals_received,
                    "status": status,
                    "approved_by": approver,
                },
            )
    except Exception as e:
        raise RuntimeError(f"Не удалось обновить данные в базе данных: {e}")


async def approve_to_payment_department(
    context: ContextTypes.DEFAULT_TYPE,
    update: Update,
    row_id: str,
    approver: str,
    department: str,
) -> None:
    """
    Изменение количество апрувов и статус платежа. При сумме более 50.000 апрувит "finance" иначе "head" департамент
    Отправка сообщения об одобрении платежа для отдела оплаты.
    Изменение сообщения от бота в чатах участников департамента "head" или "finance"
    """
    approvals_received, status = 2 if department == "finance" else 1, "Approved"
    await update_storage_data(row_id, status, approver, approvals_received=None)

    chat_id, stage = message_manager(row_id).get("initiator_chat_id"), (
        "head_finance_to_payment" if department == "finance" else "head_to_payment"
    )
    await message_manager.edit_department_messages(
        context, row_id, department, chat_id, stage
    )

    department = "head"
    chat_id, stage = get_chat_ids(department), (
        "head_to_payment" if department == "finance" else "head_to_finance"
    )
    await message_manager.edit_department_messages(
        context, row_id, department, chat_id, stage
    )

    department = "finance"
    chat_id, stage = get_chat_ids(department), (
        "to_payment" if department == "finance" else "from_head"
    )
    await message_manager.edit_department_messages(
        context, row_id, department, chat_id, stage
    )

    department = "payment"
    chat_id, stage = get_chat_ids(department), (
        "finance_to_payment" if department == "finance" else "head_to_payment"
    )
    await message_manager.send_department_messages(
        context, row_id, department, chat_id, stage
    )


async def reject_record(
    context: ContextTypes.DEFAULT_TYPE,
    row_id: str,
    approver: str,
) -> None:
    """Отправка сообщения об отклонении платежа и изменении статуса платежа."""

    status, approver = "Rejected", approver
    await update_storage_data(row_id, status, approver, approvals_received=None)

    department, stage = "all", "rejected"
    # logger.info(message_manager._data)
    # logger.info(await message_manager(row_id))
    message_manager(row_id)["all_messages"] = (
        (await message_manager(row_id)).get("initiator_messages")
        + (await message_manager(row_id)).get("head_messages")
        + (await message_manager(row_id)).get("finance_messages")
        + (await message_manager(row_id)).get("payment_messages")
    )
    await message_manager.edit_department_messages(context, row_id, department, stage)

    await message_manager[row_id].remove()


async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик нажатий пользователем кнопки "Оплачено"
    """

    try:
        query = update.callback_query
        response_list = query.data.split("_")
        row_id = response_list[1]
        approver = await get_nickname("payment", query.from_user.id)

    except Exception as e:
        raise RuntimeError(f'Ошибка считывания данных с кнопки "Оплачено". Ошибка: {e}')

    await make_payment_and_add_record_to_google_sheet(update, context, row_id)


async def make_payment_and_add_record_to_google_sheet(
    update: Update, context: ContextTypes.DEFAULT_TYPE, row_id
) -> None:
    await update_storage_data(row_id, "Paid")

    message_manager(row_id)["all_messages"] = (
        await message_manager(row_id).get("initiator_messages")
        + await message_manager(row_id).get("head_messages")
        + await message_manager(row_id).get("finance_messages")
        + await message_manager(row_id).get("payment_messages")
    )
    department, stage = "all", "paid"
    await message_manager.edit_department_messages(context, row_id, department, stage)

    await message_manager(row_id).remove()
    # await add_record_to_google_sheet(record_dict)


# async def check_department(approver_id: str) -> str | None:
#     """Возвращает название департамента, к которому принадлежит approver_id."""
#     departments = {  # Если у approver_id возможен только 1 департамент
#         **{str(k): "head" for k in Config.head_chat_ids},
#         **{str(k): "finance" for k in Config.finance_chat_ids},
#         **{str(k): "payment" for k in Config.payers_chat_ids},
#     }
#     user_department = departments.get(approver_id)
#     if user_department not in ("head", "finance", "payment"):
#         return None
#     return user_department

# departments = {}  #  Если пользователи могут состоять более чем в 1 департаменте
# for department in ["head", "finance", "payers"]:
#     for chat_id in getattr(Config, f"{department}_chat_ids"):
#         if chat_id not in departments:
#             departments[chat_id] = []
#         departments[chat_id].append(department)
# user_department = departments.get(approver_id)
# if not any(department in user_department for department in ("head", "finance", "payers")):
#     return None
# return user_department


async def reject_record_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Меняет в базе данных статус платежа на отклонён('Rejected'),
    и отправляет сообщение об отмене ранее одобренного платежа.
    """

    row_id = context.args
    if not row_id:
        raise ValueError("Пожалуйста, укажите id счёта!")
    if len(row_id) > 1:
        raise ValueError("Можно указать только 1 счёт!")

    approver_id = str(update.effective_chat.id)
    department = await get_department(approver_id)
    if department not in ("head", "finance"):
        raise PermissionError("Вы не можете менять статус счёта!")

    row_id = row_id[0]

    approver = await get_nickname(department, approver_id)
    async with db:
        record = await db.get_row_by_id(row_id)
    if not record:
        raise RuntimeError(f"Счёт с id: {row_id} не найден.")

    status = record.get("status")
    if status in ("Rejected", "Paid"):
        raise RuntimeError(f"Счёт №{row_id} уже обработан")

    approvals_received = record.get("approvals_received")
    if department == "head":
        if not (
            approvals_received == 0
            and status == "Not processed"
            or approvals_received == 1
            and status in ("Approved", "Pending")
        ):
            raise RuntimeError(
                "Вы не можете отклонить данный счет! Обратитесь к сотруднику финансового отдела"
            )

    elif department == "finance":
        if not (
            approvals_received == 1
            and status == "Pending"
            or approvals_received == 2
            and status == "Approved"
        ):
            raise RuntimeError(
                "Вы не можете отклонить данный счет! Обратитесь к руководителю департамента"
            )

    await update.message.reply_text(f"Счёт {row_id} отклонён!")
    await reject_record(context, row_id, approver)


async def approve_record_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Меняет в базе данных статус платежа на отклонён('Rejected'),
    и отправляет сообщение об отмене ранее одобренного платежа.
    """

    row_id = context.args
    if not row_id:
        raise ValueError("Пожалуйста, укажите id счёта!")
    if len(row_id) > 1:
        raise ValueError("Можно указать только 1 счёт!")

    row_id = row_id[0]
    async with db:
        record = await db.get_row_by_id(row_id)
    if not record:
        raise RuntimeError(f"Счёт с id: {row_id} не найден.")

    status = record.get("status")
    if status in ("Paid", "Rejected", "Approved"):
        raise RuntimeError("Счёт уже обработан")

    approver_id = str(update.effective_chat.id)
    department = await get_department(approver_id)

    if department not in ("head", "finance", "payment"):
        raise PermissionError("Вы не можете менять статус счёта!")

    if status == "Paid":
        raise PermissionError("Заявка уже оплачена")

    if department == "payment" and status != "Approved":
        raise PermissionError("Вы можете оплачивать только подтверждённые счета!")

    if department == "finance" and status != "Pending":
        raise PermissionError(
            "Вы можете одобрять только согласованные главой департамента счета!"
        )

    if department == "head" and status != "Not processed":
        raise PermissionError("Вы можете одобрять только несогласованные счета!")

    action = "approve"
    approver = f"@{update.message.from_user.username}"
    amount = record.get("amount")

    await approval_process(
        context, update, action, row_id, approver, department, amount
    )


async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row_id = context.args
    if not row_id:
        raise ValueError("Пожалуйста, укажите id счёта!")
    if len(row_id) > 1:
        raise ValueError("Можно указать только 1 счёт!")

    row_id = row_id[0]
    async with db:
        record_dict = await db.get_row_by_id(row_id)
    if not record_dict:
        raise RuntimeError(f"Счёт с id: {row_id} не найден.")

    status = record_dict.get("status")
    approved_by = record_dict.get("approved_by")
    status_messages = {
        "Rejected": f"Счёт №{row_id} отклонён {approved_by}.",
        "Pending": f"Счёт №{row_id} одобрен {approved_by} и ожидает согласования финансового отдела.",
        "Approved": f"Счёт №{row_id} одобрен {approved_by} и ожидает оплаты.",
        "Paid": f"Счёт №{row_id} оплачен.",
        "Not processed": f"Счёт №{row_id} ожидает согласования руководителя департамента.",
    }
    status_message = status_messages.get(
        status, "Ожидается информация по статусу счёта."
    )

    await update.message.reply_text(status_message)


async def show_not_paid_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Возвращает инициатору в тг-чат неоплаченные заявки на платежи из таблицы "approvals" в удобном формате
    """

    async with db:
        rows = await db.find_not_paid()
    messages = []

    for i, record in enumerate(rows, start=1):
        line = ", ".join([f"{key}: {value}" for key, value in record.items()])
        message_line = f"{i}. {line}"
        wrapped_message = textwrap.fill(message_line, width=4096)
        messages.append(wrapped_message)

    final_text = "\n\n".join(messages)
    if not final_text:
        await update.message.reply_text("Заявок не обнаружено")

    if len(final_text) >= 4096:  # Максимальная длина сообщения в Telegram
        parts = await split_long_message(final_text)
        for part in parts:
            await update.message.reply_text(part)
    if final_text:
        await update.message.reply_text(final_text)

    return


import traceback


async def error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок для логирования и уведомления пользователя с детальной информацией об ошибке."""

    try:
        error_traceback = traceback.format_exc()
        message_text = f"{str(context.error)}"
        await context.bot.send_message(update.effective_chat.id, message_text)
        # await context.bot.send_message(Config.developer_chat_id, f"{message_text} {error_traceback}")
        logger.error(f"{message_text}\n{error_traceback}")

    except Exception as e:
        message_text = f"Ошибка при отправке уведомления об ошибке: {e}."
        logger.error(message_text, exc_info=True)
        await context.bot.send_message(Config.developer_chat_id, message_text)
