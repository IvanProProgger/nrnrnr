import aiosqlite

from config.config import Config
from config.logging_config import logger


class ApprovalDB:
    """База данных для хранения данных о заявке"""

    def __init__(self):
        self.db_file = Config.database_path

    async def __aenter__(self) -> "ApprovalDB":
        self._conn = await aiosqlite.connect(self.db_file)
        self._cursor = await self._conn.cursor()
        logger.info("Соединение установлено.")
        return self

    async def __aexit__(self, exc_type: any, exc_val: any, exc_tb: any) -> bool:
        if exc_type:
            logger.error(f"Произошла ошибка: {exc_type}; {exc_val}; {exc_tb}")
        if self._conn:
            await self._conn.close()
            logger.info("Соединение разъединено.")
        return True

    async def create_table(self) -> None:
        """Создает таблицу 'approvals', если она еще не существует."""
        async with self:
            await self._cursor.execute(
                'SELECT name FROM sqlite_master WHERE type="table" AND name="approvals";'
            )
            table_exists = await self._cursor.fetchone()

            if not table_exists:
                try:
                    await self._cursor.execute(
                        """CREATE TABLE IF NOT EXISTS approvals
                                                  (id INTEGER PRIMARY KEY, 
                                                   amount REAL, 
                                                   expense_item TEXT, 
                                                   expense_group TEXT, 
                                                   partner TEXT, 
                                                   comment TEXT,
                                                   period TEXT, 
                                                   payment_method TEXT, 
                                                   approvals_needed INTEGER, 
                                                   approvals_received INTEGER,
                                                   status TEXT,
                                                   approved_by TEXT,
                                                   initiator_id INTEGER)"""
                    )
                    await self._conn.commit()
                    logger.info('Таблица "approvals" создана.')
                except Exception as e:
                    raise RuntimeError(e)
            else:
                logger.info('Таблица "approvals" уже существует.')

    async def insert_record(self, record_dict: dict[str, any]) -> int:
        """
        Добавляет новую запись в таблицу 'approvals'.
        """

        try:
            await self._cursor.execute(
                "INSERT INTO approvals (amount, expense_item, expense_group, partner, comment, period, payment_method,"
                "approvals_needed, approvals_received, status, approved_by, initiator_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                list(record_dict.values()),
            )
            await self._conn.commit()
            logger.info("Информация о счёте успешно добавлена.")
            return self._cursor.lastrowid
        except Exception as e:
            raise RuntimeError(f"Не удалось добавить информацию о счёте: {e}")

    async def get_row_by_id(self, row_id: int) -> dict[str, any] | None:
        """Получаем словарь из названий и значений столбцов по id"""
        try:
            result = await self._cursor.execute(
                "SELECT * FROM approvals WHERE id=?", (row_id,)
            )
            row = await result.fetchone()
            if row is None:
                raise RuntimeError(f"По заданному id: {row_id} данных не найдено!")
            logger.info("Данные строки получены успешно.")
            return dict(
                zip(
                    (
                        "id",
                        "amount",
                        "expense_item",
                        "expense_group",
                        "partner",
                        "comment",
                        "period",
                        "payment_method",
                        "approvals_needed",
                        "approvals_received",
                        "status",
                        "approved_by",
                        "initiator_id",
                    ),
                    row,
                )
            )
        except Exception as e:
            raise RuntimeError(f"Не удалось получить запись: {e}")

    async def get_column_by_id(self, column_name: str, row_id: int) -> any:
        """Получает значение указанного столбца по id"""
        try:
            result = await self._cursor.execute(
                f"SELECT [{column_name}] FROM approvals WHERE id=?", (row_id,)
            )
            value = await result.fetchone()
            if value is None:
                return None
            logger.info(f"Значение столбца '{column_name}' получено успешно.")
            return value[0]
        except Exception as e:
            raise RuntimeError(f"Не удалось получить значение столбца: {e}")

    async def update_row_by_id(self, row_id: int, updates: dict[str, any]) -> None:
        """Функция меняет значения столбцов.
        :param принимает id строки row_id и словарь updates из названий и значений столбцов
        """
        try:
            await self._cursor.execute(
                "UPDATE approvals SET {} WHERE id = ?".format(
                    ", ".join([f"{key} = ?" for key in updates.keys()])
                ),
                list(updates.values()) + [row_id],
            )
            await self._conn.commit()
            logger.info("Информация о счёте успешно обновлена.")
        except Exception as e:
            raise RuntimeError(
                f"Не удалось обновить информацию о счёте: {e}. ID заявки: {row_id}, "
                f"Обновления: {updates}"
            )

    async def get_record_info(self, row_id: int) -> str:
        """
        Получает детали конкретного счета из базы данных и форматирует их для бота.
        """
        try:

            record_dict = await self.get_row_by_id(row_id)

            if record_dict:
                return (
                    f"Данные счета:\n"
                    f'1.Сумма: {record_dict["amount"]}₽;\n'
                    f'2.Статья: "{record_dict["expense_item"]}"\n'
                    f'3.Группа: "{record_dict["expense_group"]}"\n'
                    f'4.Партнер: "{record_dict["partner"]}"\n'
                    f'5.Комментарий: "{record_dict["comment"]}"\n'
                    f'6.Даты начисления: "{", ".join(record_dict["period"].split())}"\n'
                    f'7.Форма оплаты: "{record_dict["payment_method"]}"\n'
                )
            else:
                raise RuntimeError("Данного счёта не существует в базе данных.")
        except Exception as e:
            logger.error(f"Ошибка при получении деталей счета: {str(e)}")
            raise RuntimeError(f"Произошла ошибка: {str(e)}")

    async def find_not_paid(self) -> list[dict[str, str]]:
        """Функция возвращает все данные по всем неоплаченным заявкам на платёж"""
        try:
            result = await self._cursor.execute(
                "SELECT * FROM approvals WHERE status != ? AND status != ?",
                ("Paid", "Rejected"),
            )
            rows = await result.fetchall()
            if not rows:
                return []
            logger.info("Неоплаченные счета найдены успешно.")

            return [
                dict(
                    zip(
                        (
                            "id заявки",
                            "сумма",
                            "статья",
                            "группа",
                            "партнёр",
                            "комментарий",
                            "период дат",
                            "способ оплаты",
                            "апрувов требуется",
                            "апрувов получено",
                            "статус",
                            "кто апрувил",
                        ),
                        row,
                    )
                )
                for row in rows
            ]
        except Exception as e:
            raise RuntimeError(f"Не удалось получить неоплаченные счета: {e}")
