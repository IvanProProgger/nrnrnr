import textwrap

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
    create_payment_keyboard,
)
from src.sheets import add_record_to_google_sheet

from helper.user_data import get_nickname, get_chat_ids, get_department
from db import db


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in Config.white_list:
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        logger.warning("В бота пытаются зайти посторонние...")
        return


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""

    try:
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
            # "<i>Каждый пункт необходимо указывать строго через запятую.</i>\n\n"
            "<i>Узнать о статусе интересующего платежа можно командой /check <b>ID</b></i>\n\n"
            "<i>Вы можете просмотреть необработанные платежи командой /show_not_paid</i>\n\n"
            "<i>Одобрить заявку можно командой /approve_record <b>ID</b> платежа</i>\n\n"
            "<i>Отклонить заявку можно командой /reject_record <b>ID</b> платежа</i>\n\n"
            f"<i>Ваш id чата - {update.message.chat_id}</i>",
            parse_mode="HTML",
        )
    except Exception as e:
        raise RuntimeError(f"Ошибка при отправке команды /start: {e}")


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
            update.effective_chat.id,
            "initiator_to_head",
        )
        if not context.bot_data.get("initiator_message"):
            await message_manager.send_department_messages(
                context, row_id, department, initiator_chat_id, stage
            )

        department = "head"
        head_chat_id, stage = await get_chat_ids(department), "from_initiator"
        await message_manager.send_department_messages(
            context,
            row_id,
            department,
            head_chat_id,
            stage,
            reply_markup=await create_approval_keyboard(row_id, department),
        )
    except Exception as e:
        raise RuntimeError(
            f"Ошибка при отправке сообщений иницитиатору и руководителю отдела маркетинга: {e}"
        )


async def process_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> dict[str, float | str | int]:
    """Обработчик аргументов команды /submit_record."""

    try:
        initiator_chat_id = update.effective_chat.id
        if not context.args:
            raise ValueError("Необходимо указать данные счёта.")
        user_args = [x.strip() for x in " ".join(context.args).split(";")]
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

    try:
        initiator_chat_id = update.effective_chat.id
        async with db:
            row_id = await db.insert_record(record_dict)

        record_data_text = await get_record_info(record_dict)
        amount = record_dict.get("amount")
        initiator_nickname = await get_nickname("initiator", initiator_chat_id)
        message_manager[row_id] = {
            "initiator_chat_id": initiator_chat_id,
            "initiator_nickname": initiator_nickname,
            "record_data_text": record_data_text,
            "amount": amount,
        }
    except Exception as e:
        raise RuntimeError(f"Ошибка при добавлении данных в storages: {e}")

    return row_id


async def approval_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик нажатий пользователем кнопок "Одобрить" или "Отклонить."
    """
    try:
        query = update.callback_query
        _, action, department, row_id = query.data.split("_")
        row_id = int(row_id)
        approver = await get_nickname(department, query.from_user.id)
        await message_manager.update_data(row_id, {"approver": approver})
        amount = (await message_manager(row_id)).get("amount")
    except Exception as e:
        raise RuntimeError(f'Ошибка обработки кнопок "Одобрить" и "Отклонить". {e}')

    try:
        # распределяем данные платежа по отделам для принятия решения об одобрении
        await approval_process(
            context, update, action, row_id, approver, department, amount
        )
    except Exception as e:
        raise RuntimeError(f"Не удалось распределить данные по отделам: {e}")


async def approval_process(
    context: ContextTypes.DEFAULT_TYPE,
    update: Update,
    action: str,
    row_id: int,
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
    context: ContextTypes.DEFAULT_TYPE,
    update: Update,
    row_id: int,
    approver: str,
) -> None:
    """
    Изменение количества апрувов и статуса платежа.
    Отправка сообщения о платеже свыше 50.000 в финансовый отдел на согласование платежа.
    Изменение сообщения от бота в чатах участников департамента "head"
    """

    # меняем статус и добавляем апрув в базу данных
    await update_storage_data(
        row_id, approved_by=approver, status="Pending", approvals_received=1
    )

    # меняем сообщение инициатору
    department, stage = "initiator", "head_to_finance"
    await message_manager.edit_department_messages(
        context, row_id, department, stage, reply_markup=None
    )

    # меняем сообщение руководителю департамента или создаём
    # ответное новое сообщение на команду руководителя департамента
    department, stage = "head", "head_to_finance"
    if (await message_manager(row_id)).get("head_messages"):
        await message_manager.edit_department_messages(
            context, row_id, department, stage, reply_markup=None
        )
    else:
        await message_manager.command_reply_message(update, context, row_id)

    # отправляем сообщение сотрудникам финансового отдела
    department, stage = "finance", "from_head"
    finance_chat_ids = await get_chat_ids("finance")
    await message_manager.send_department_messages(
        context,
        row_id,
        department,
        finance_chat_ids,
        stage,
        reply_markup=await create_approval_keyboard(row_id, department),
    )


async def update_storage_data(row_id, **kwargs: int | str | None):
    try:
        async with db:
            is_approver_exist = await db.get_column_by_id("approved_by", row_id)
            if is_approver_exist and kwargs.get("approved_by"):
                kwargs["approved_by"] = f"{is_approver_exist} и {kwargs['approved_by']}"
                await message_manager.update_data(row_id, {"approver": kwargs.get("approved_by")})
            update_data = {
                key: value for key, value in kwargs.items() if value is not None
            }
            await db.update_row_by_id(row_id, update_data)

    except Exception as e:
        raise RuntimeError(f"Не удалось обновить данные в базе данных: {e}")


async def approve_to_payment_department(
    context: ContextTypes.DEFAULT_TYPE,
    update: Update,
    row_id: int,
    approver: str,
    department_approved: str,
) -> None:
    """
    Изменение количество апрувов и статус платежа. При сумме более 50.000 апрувит "finance" иначе "head" департамент
    Отправка сообщения об одобрении платежа для отдела оплаты.
    Изменение сообщения от бота в чатах участников департамента "head" или "finance"
    """

    await update_storage_data(
        row_id,
        approved_by=approver,
        status="Approved",
        approvals_received=2 if department_approved == "finance" else 1,
    )

    # Меняем сообщение инициатору в зависимости от того кто одобрил счёт (руководитель или финансист)
    stage = (
        "head_finance_to_payment"
        if department_approved == "finance"
        else "head_to_payment"
    )
    department = "initiator"
    await message_manager.edit_department_messages(context, row_id, department, stage)

    # Меняем сообщение руководителю отдела маркетинга (в финансовый отдел или на оплату)
    department = "head"
    stage = "head_to_payment" if department_approved == "finance" else "head_to_finance"
    await message_manager.edit_department_messages(context, row_id, department, stage)

    # Если одобрил финансовый отдел - меняем им сообщение (счёт отправлен на оплату)
    if department_approved == "finance":
        department = "finance"
        stage = "to_payment" if department_approved == "finance" else "from_head"
        await message_manager.edit_department_messages(
            context, row_id, department, stage
        )

        # Отправляем сообщение плательщикам от руководителя маркетингового отдела или финансиста
    department = "payment"
    chat_id = await get_chat_ids(department)
    stage = (
        "finance_to_payment" if department_approved == "finance" else "head_to_payment"
    )
    await message_manager.send_department_messages(
        context,
        row_id,
        department,
        chat_id,
        stage,
        reply_markup=await create_payment_keyboard(row_id),
    )


async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик нажатий пользователем кнопки "Оплачено"
    """

    try:
        query = update.callback_query
        response_list = query.data.split("_")
        row_id = int(response_list[1])
        approver = await get_nickname("payment", query.from_user.id)
        await message_manager.update_data(row_id, {"approver": approver})
    except Exception as e:
        raise RuntimeError(f'Ошибка считывания данных с кнопки "Оплачено". Ошибка: {e}')

    await make_payment(update, context, row_id)


async def reject_record(
    context: ContextTypes.DEFAULT_TYPE, row_id: int, approver: str
) -> None:
    """Отправка сообщения об отклонении платежа и изменении статуса платежа."""

    await message_manager.update_data(row_id, {"approver": approver})
    await update_storage_data(row_id, status="Rejected")
    await message_manager.get_all_messages(row_id)
    await message_manager.edit_department_messages(context, row_id, "all", "rejected")
    del message_manager[row_id]


async def make_payment(
    update: Update, context: ContextTypes.DEFAULT_TYPE, row_id: int
) -> None:
    """Добавление записи в Google Sheets после успешного платежа."""
    await update_storage_data(row_id, status="Paid")
    await message_manager.get_all_messages(row_id)
    await message_manager.edit_department_messages(context, row_id, "all", "paid")
    del message_manager[row_id]


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
    logger.info(approver_id)
    logger.info(department)
    if department not in ("head", "finance", "payment"):
        raise PermissionError("Вы не можете менять статус счёта!")

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
        await context.bot.send_message(
            Config.developer_chat_id, f"{message_text} {error_traceback}"
        )
        logger.error(f"{message_text}\n{error_traceback}")

    except Exception as e:
        message_text = f"Ошибка при отправке уведомления об ошибке: {e}."
        logger.error(message_text, exc_info=True)
        await context.bot.send_message(Config.developer_chat_id, message_text)
