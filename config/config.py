from os import getenv

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Класс-конфиг для проекта"""

    telegram_bot_token: str = getenv("TELEGRAM_BOT_TOKEN")
    google_sheets_spreadsheet_id: str = getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
    database_path: str = getenv("DATABASE_PATH")
    google_sheets_credentials_file: str = getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")
    google_sheets_categories_sheet_id: int = getenv("GOOGLE_SHEETS_CATEGORIES_SHEET_ID")
    google_sheets_records_sheet_id: int = getenv("GOOGLE_SHEETS_RECORDS_SHEET_ID")
    head_chat_ids: list[int] = list(map(int, getenv("HEAD_CHAT_IDS").split(",")))
    finance_chat_ids: list[int] = list(map(int, getenv("FINANCE_CHAT_IDS").split(",")))
    payment_chat_ids: list[int] = list(map(int, getenv("PAYMENT_CHAT_IDS").split(",")))
    initiator_chat_ids: list[int] = list(map(int, getenv("INITIATOR_CHAT_IDS").split(",")))
    developer_chat_id: list[int] = getenv("DEVELOPER_CHAT_ID")
    white_list: set[int] = set(map(int, getenv("WHITE_LIST").split(",")))

    DEPARTMENTS = {
        "180543030": "initiator",
        "113382451": "initiator",
        "482546749": "initiator",
        "523986696": "head",
        "236746871": "finance",
        "191096978": "finance",
        "455256941": "payment",
        "427967346": "payment",  # также инициатор
        "939635840": "payment",  # также инициатор
        "5024126966": "payment",
        "594336984": "head"# также инициатор
    }

    NICKNAMES = {
        "initiator": {
            "180543030": "@irina_kuderova",
            "427967346": "Мариной Жихарь",
            "113382451": "@koroldorog",
            "482546749": "@bais_bais",
            "939635840": "@dantanusha",
            "5024126966": "Еленой Фомичёвой",
            "594336984": "@Stilldaywonder",
        },
        "head": {
            "180543030": "@irina_kuderova",
            "523986696": "@bonn_ya",
            "594336984": "@Stilldaywonder",
        },
        "finance": {
            "236746871": "@dizher1",
            "191096978": "@ushattt",
            "594336984": "@Stilldaywonder",
        },
        "payment": {
            "455256941": "@IrishkaKitty",
            "427967346": "Мариной Жихарь",
            "939635840": "@dantanusha",
            "5024126966": "Еленой Фомичёвой",
            "594336984": "@Stilldaywonder",
        },
    }
