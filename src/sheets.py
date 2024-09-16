from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import gspread_asyncio
import pandas as pd
import pytz
from google.oauth2.service_account import Credentials

from config.config import Config
from config.logging_config import logger


async def get_today_moscow_time() -> str:
    """Функция для получения текущей даты"""

    moscow_tz = pytz.timezone("Europe/Moscow")
    today = datetime.now(moscow_tz)
    formatted_date = today.strftime("%d.%m.%Y")
    return formatted_date


async def add_record_to_google_sheet(record_dict: dict) -> None:
    """Функция для добавления строки в таблицу Google Sheet."""
    manager = GoogleSheetsManager()
    await manager.initialize_google_sheets()
    await manager.add_payment_to_sheet(record_dict)


def get_credentials() -> Credentials:
    """Функция для получения данных для авторизации в Google Sheets"""

    creds = Credentials.from_service_account_file(Config.google_sheets_credentials_file)
    scoped = creds.with_scopes(
        [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
    )
    return scoped


class GoogleSheetsManager:
    """Класс для обработки Google Sheets таблиц."""

    def __init__(self):
        self.sheets_spreadsheet_id = Config.google_sheets_spreadsheet_id
        self.records_sheet_id = Config.google_sheets_records_sheet_id
        self.categories_sheet_id = Config.google_sheets_categories_sheet_id
        self.options_dict = None
        self.items = None
        self.agc = None

    @staticmethod
    def get_credentials() -> Credentials:
        """Получить учетные данные для доступа к Google Sheets API."""

        creds = Credentials.from_service_account_file(
            Config.google_sheets_credentials_file
        )
        return creds.with_scopes(
            [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
        )

    async def initialize_google_sheets(self) -> gspread_asyncio.AsyncioGspreadClient:
        """Инициализация в Google Sheets"""

        try:
            agcm = gspread_asyncio.AsyncioGspreadClientManager(self.get_credentials)
            self.agc = await agcm.authorize()
            logger.info("Успешная авторизация Google Sheets.")
            return self.agc
        except Exception as e:
            logger.error(f"Авторизация не удалась: {e}")
            raise RuntimeError(f"Авторизация не удалась: {e}")

    async def add_payment_to_sheet(self, payment_info: dict[str, str]) -> None:
        """Добавить информацию о платеже в Google Sheets."""

        try:
            spreadsheet = await self.agc.open_by_key(self.sheets_spreadsheet_id)
            worksheet = await spreadsheet.get_worksheet_by_id(self.records_sheet_id)
            all_data = await worksheet.get_all_values()
            today_date = (
                await get_today_moscow_time()
            )  # Изменение: добавить await для асинхронной функции
            rows_to_update = self.construct_rows(payment_info, today_date)
            start_row = self.detect_start_row(all_data)

            if rows_to_update:
                await self.update_worksheet(worksheet, rows_to_update, start_row)

        except Exception as e:
            logger.error(f"Не удалось добавить платеж в таблицу: {e}")
            raise RuntimeError(f"Не удалось добавить платеж в таблицу: {e}")

    def construct_rows(
        self, payment_info: dict[str, str], today_date: str
    ) -> list[list[str]]:
        """Построить строки для обновления в таблице на основе информации о платеже."""

        period = payment_info["period"].split(" ")
        total_sum = Decimal(payment_info["amount"]) / Decimal(len(period))
        rounded_sum = float(
            total_sum.quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP)
        )

        return [
            [
                today_date,
                rounded_sum,
                payment_info["expense_item"],
                payment_info["expense_group"],
                payment_info["partner"],
                "",
                "",
                payment_info["comment"],
                month,
                payment_info["payment_method"],
            ]
            for month in period
        ]

    async def update_worksheet(
        self, worksheet, rows_to_update: list[list[str]], start_row: int
    ) -> None:
        """Обновить таблицу с новыми данными и применить форматирование."""

        await worksheet.update(
            f"B{start_row}:K{start_row + len(rows_to_update) - 1}",
            rows_to_update,
            value_input_option="USER_ENTERED",
        )
        logger.info(
            f"Добавлено {len(rows_to_update)} row, начиная с строки {start_row}"
        )

        await self.apply_formatting(worksheet)

    async def apply_formatting(self, worksheet) -> None:
        """Применить необходимое форматирование к таблице."""

        text_format = {"textFormat": {"fontFamily": "Lato"}}
        date_format = {"numberFormat": {"type": "DATE", "pattern": "dd.mm.yyyy"}}
        currency_format = {"numberFormat": {"type": "CURRENCY", "pattern": "₽ #,###"}}

        await worksheet.format("B:I", text_format)
        await worksheet.format("B3:B", date_format)
        await worksheet.format("C3:C", currency_format)
        await worksheet.format("J3:J", date_format)

    def detect_start_row(self, all_data: list[list[str]]) -> int:
        """Определить начальную строку для новых данных на основе существующих данных в таблице."""

        return next(
            (
                index + 1
                for index, row in enumerate(all_data)
                if all(cell == "" for cell in row[:10])
            ),
            len(all_data) + 1,
        )

    async def get_data(self) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
        """Получить категории и соответствующих партнеров из Google Sheets."""

        try:
            spreadsheet = await self.agc.open_by_key(self.sheets_spreadsheet_id)
            worksheet = await spreadsheet.get_worksheet_by_id(self.categories_sheet_id)
            records = await worksheet.get_all_records()
            df = pd.DataFrame(records)
            return self.construct_category_data(df)
        except Exception as e:
            logger.error(f"Не удалось прочитать данные категорий: {e}")
            raise RuntimeError(f"Не удалось прочитать данные категорий: {e}")

    def construct_category_data(
        self, df: pd.DataFrame
    ) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
        """Организовать данные о категориях в структурированный словарь и список уникальных элементов."""

        data_structure = {}
        unique_items = df["Статья"].unique().tolist()
        logger.info(unique_items)
        for _, row in df.iterrows():
            category = row["Статья"]
            group = row["Группа"]
            partner = row["Партнер"]

            if category not in data_structure:
                data_structure[category] = {}

            if group not in data_structure[category]:
                data_structure[category][group] = []

            data_structure[category][group].append(partner)

        return data_structure, unique_items

    # async def get_data(self) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    #     """
    #     Получение списка статей и списка словарей данных из таблицы "категории"
    #     """
    #
    #     try:
    #         spreadsheet = await self.agc.open_by_key(self.sheets_spreadsheet_id)
    #         worksheet = await spreadsheet.get_worksheet_by_id(self.categories_sheet_id)
    #     except Exception as e:
    #         raise RuntimeError(
    #             f'Ошибка получения данных с листа "категории". Ошибка: {e}'
    #         )
    #
    #     df = pd.DataFrame(await worksheet.get_all_records())
    #     unique_items = df["Статья"].unique()
    #     data_structure = {}
    #
    #     for _, row in df.iterrows():
    #         category = row["Статья"]
    #         group = row["Группа"]
    #         partner = row["Партнер"]
    #
    #         if category not in data_structure:
    #             data_structure[category] = {}
    #
    #         if group not in data_structure[category]:
    #             data_structure[category][group] = []
    #
    #         data_structure[category][group].append(partner)
    #
    #     self.options_dict, self.items = data_structure, unique_items
    #
    #     return data_structure, unique_items
