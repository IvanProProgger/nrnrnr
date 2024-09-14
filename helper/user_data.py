from config.config import Config
from config.logging_config import logger


async def get_nickname(department: str, chat_id: str | int) -> str:
    """Возвращает nickname с помощью названия департамента и chat_id"""
    chat_ids = Config.NICKNAMES.get(department)
    if chat_ids:
        return chat_ids.get(str(chat_id), "")
    return ""


async def get_department(chat_id: str | int) -> str:
    """Возвращает департамент по chat_id"""
    return Config.DEPARTMENTS.get(str(chat_id)) or None


async def get_chat_ids(department: str) -> list[str]:
    """Возвращает chat_id по названию департамента"""
    return [
        str(chat_id) for chat_id in getattr(Config, f"{department.lower()}_chat_ids")
    ]


async def get_departments(chat_id: str) -> list[str] | None:
    """Возвращает список департаментов по chat_id"""
    try:
        departments = {}
        for department in ["initiator", "head", "finance", "payers"]:
            for chat_id in getattr(Config, f"{department}_chat_ids"):
                if chat_id not in departments:
                    departments[chat_id] = []
                departments[chat_id].append(department)

        user_department = departments.get(chat_id)
        if not user_department:
            raise ValueError(f"Департамент не найден для введённого chat_id: {chat_id}")

        return user_department
    except Exception as e:
        logger.error(f"Ошибка поиска департамента по {chat_id}. Ошибка: {str(e)}")
        return None
