from telegram import Update
from telegram.ext import ContextTypes

from helper.message_manager import message_manager
from helper.user_data import get_chat_ids, get_chat_id_by_nickname
from helper.utils import create_approval_keyboard, create_payment_keyboard
from src.handlers import get_record_by_id


async def initiator_to_head_start_message(
    context: ContextTypes.DEFAULT_TYPE, update: Update, row_id
) -> None:
    try:
        initiator_chat_id = update.effective_chat.id
        if not context.bot_data.get("initiator_message"):
            department = "initiator"
            stage = "initiator_to_head"
            await message_manager.send_department_messages(
                context, row_id, department, initiator_chat_id, stage
            )
        else:
            await message_manager.update_data(
                row_id,
                {"initiator_messages": context.bot_data.get("initiator_message")},
            )
            del context.bot_data["initiator_message"]
    except Exception as e:
        raise RuntimeError(f"Ошибка при отправке стартового сообщения инициатору: {e}")


async def head_from_initiator_approval_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int
) -> None:
    try:
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
            f"Ошибка при отправке сообщения на одобрения счёта от инициатора руководителю отдела маркетинга: {e}"
        )


async def initiator_head_to_finance_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int, record_dict
) -> None:
    department, stage = "initiator", "head_to_finance"
    if message_manager[row_id].get("initiator_messages"):
        await message_manager.edit_department_messages(
            context, row_id, department, stage, reply_markup=None
        )
    else:
        initiator_chat_id = record_dict.get("initiator_id")
        await message_manager.send_department_messages(
            context, row_id, "initiator", initiator_chat_id, "head_to_finance"
        )


async def head_to_finance_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int
) -> None:
    department, stage = "head", "head_to_finance"
    if message_manager[row_id].get("head_messages"):
        await message_manager.edit_department_messages(
            context, row_id, department, stage, reply_markup=None
        )
    else:
        head_chat_id = await get_chat_ids("head")
        await message_manager.send_department_messages(
            context, row_id, "head", head_chat_id, "head_to_finance"
        )


async def finance_from_head_approval_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int
) -> None:
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


async def initiator_head_and_finance_to_payment_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int
) -> None:
    record_dict = await get_record_by_id(row_id)
    stage = "head_finance_to_payment"
    department = "initiator"
    if message_manager[row_id].get("initiator_messages"):
        await message_manager.edit_department_messages(
            context, row_id, department, stage
        )
    else:
        initiator_chat_id = record_dict.get("initiator_id")
        await message_manager.send_department_messages(
            context, row_id, "initiator", initiator_chat_id, "head_finance_to_payment"
        )


async def initiator_head_to_payment_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int, record_dict: dict
) -> None:

    stage = "head_to_payment"
    department = "initiator"
    if message_manager[row_id].get("initiator_messages"):
        await message_manager.edit_department_messages(
            context, row_id, department, stage
        )
    else:
        initiator_chat_id = record_dict.get("initiator_id")
        await message_manager.send_department_messages(
            context, row_id, "initiator", initiator_chat_id, "head_to_payment"
        )


async def head_and_finance_to_payment_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int
) -> None:
    department = "head"
    stage = "head_finance_to_payment"
    if message_manager[row_id].get("head_messages"):
        await message_manager.edit_department_messages(
            context, row_id, department, stage
        )
    else:
        head_chat_id = await get_chat_ids("head")
        await message_manager.send_department_messages(
            context, row_id, "head", head_chat_id, "head_finance_to_payment"
        )


async def head_to_payment_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int
) -> None:
    department = "head"
    stage = "head_to_payment"
    if message_manager[row_id].get("head_messages"):
        await message_manager.edit_department_messages(
            context, row_id, department, stage
        )
    else:
        head_chat_id = await get_chat_ids("head")
        await message_manager.send_department_messages(
            context, row_id, "head", head_chat_id, "head_to_payment"
        )


async def finance_and_head_to_payment_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int, approver: str | int
) -> None:
    department = "finance"
    stage = "to_payment"
    if message_manager[row_id].get("finance_messages"):
        await message_manager.edit_department_messages(
            context, row_id, department, stage
        )
    else:
        approver_id = await get_chat_id_by_nickname(approver)
        await message_manager.send_department_messages(
            context, row_id, "finance", approver_id, "to_payment"
        )


async def payment_from_head_approval_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int
) -> None:
    department = "payment"
    chat_id = await get_chat_ids(department)
    stage = "head_to_payment"
    await message_manager.send_department_messages(
        context,
        row_id,
        department,
        chat_id,
        stage,
        reply_markup=await create_payment_keyboard(row_id),
    )


async def payment_from_head_and_finance_approval_message(
    context: ContextTypes.DEFAULT_TYPE, row_id: int
) -> None:
    department = "payment"
    chat_id = await get_chat_ids(department)
    stage = "finance_to_payment"
    await message_manager.send_department_messages(
        context,
        row_id,
        department,
        chat_id,
        stage,
        reply_markup=await create_payment_keyboard(row_id),
    )


async def initiator_paid_message(
    context: ContextTypes.DEFAULT_TYPE, row_id, record_dict
):
    if message_manager[row_id].get("initiator_messages"):
        await message_manager.edit_department_messages(
            context, row_id, "initiator", "paid"
        )
    else:
        initiator_chat_id = record_dict.get("initiator_id")
        await message_manager.send_department_messages(
            context, row_id, "initiator", initiator_chat_id, "paid"
        )


async def head_paid_message(context: ContextTypes.DEFAULT_TYPE, row_id):
    if message_manager[row_id].get("head_messages"):
        await message_manager.edit_department_messages(context, row_id, "head", "paid")
    else:
        head_chat_id = await get_chat_ids("head")
        await message_manager.send_department_messages(
            context, row_id, "head", head_chat_id, "paid"
        )


async def finance_paid_message(
    context: ContextTypes.DEFAULT_TYPE, row_id, record_dict: dict
):
    if message_manager[row_id].get("finance_messages"):
        await message_manager.edit_department_messages(
            context, row_id, "finance", "paid"
        )
    else:
        finance_approver = record_dict["approved_by"].split(" и ")[1]
        finance_chat_id = await get_chat_id_by_nickname(finance_approver)
        await message_manager.send_department_messages(
            context, row_id, "finance", finance_chat_id, "paid"
        )


async def payment_paid_message(
    context: ContextTypes.DEFAULT_TYPE, row_id, payment_chat_id: int | str
):
    if message_manager[row_id].get("payment_messages"):
        await message_manager.edit_department_messages(
            context, row_id, "payment", "paid"
        )
    else:
        await message_manager.send_department_messages(
            context, row_id, "payment", payment_chat_id, "paid"
        )


async def initiator_reject_message(
    context: ContextTypes.DEFAULT_TYPE, row_id, record_dict
):
    if message_manager[row_id].get("initiator_messages"):
        await message_manager.edit_department_messages(
            context, row_id, "initiator", "rejected"
        )
    else:
        initiator_chat_id = record_dict.get("initiator_id")
        await message_manager.send_department_messages(
            context, row_id, "initiator", initiator_chat_id, "rejected"
        )


async def head_reject_message(context: ContextTypes.DEFAULT_TYPE, row_id):
    if message_manager[row_id].get("head_messages"):
        await message_manager.edit_department_messages(
            context, row_id, "head", "rejected"
        )
    else:
        head_chat_id = await get_chat_ids("rejected")
        await message_manager.send_department_messages(
            context, row_id, "head", head_chat_id, "rejected"
        )


async def finance_reject_message(
    context: ContextTypes.DEFAULT_TYPE, row_id, record_dict: dict
):
    if message_manager[row_id].get("finance_messages"):
        await message_manager.edit_department_messages(
            context, row_id, "finance", "rejected"
        )
    else:
        finance_approver = record_dict["approved_by"].split(" и ")[1]
        finance_chat_id = await get_chat_id_by_nickname(finance_approver)
        await message_manager.send_department_messages(
            context, row_id, "finance", finance_chat_id, "rejected"
        )


async def payment_reject_message(
    context: ContextTypes.DEFAULT_TYPE, row_id, payment_chat_id: int | str
):
    if message_manager[row_id].get("payment_messages"):
        await message_manager.edit_department_messages(
            context, row_id, "payment", "rejected"
        )
    else:
        await message_manager.send_department_messages(
            context, row_id, "payment", payment_chat_id, "rejected"
        )
