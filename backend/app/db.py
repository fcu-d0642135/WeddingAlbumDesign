"""資料庫連線。所有 model 都繼承這裡的 db.Model。"""

import sqlite3

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase

# 婚宴高峰會有很多人同時上傳，正式環境又是多個 worker 共用一個 SQLite 檔
BUSY_TIMEOUT_MS = 15_000


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record) -> None:
    """WAL：有人在寫入時，其他人還是可以讀（滑相簿不會被上傳卡住）。
    busy_timeout：同時有兩個寫入時，後到的等前一個寫完，而不是馬上回 database is locked。"""
    if not isinstance(dbapi_conn, sqlite3.Connection):
        return
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    cursor.close()


def upgrade_existing_tables() -> None:
    """既有的資料表少了「可以是空值」的新欄位或新索引時，自動補上（例如影片長度、檔案雜湊）。

    create_all() 只建新資料表、不改舊的；新增可空欄位與索引很安全，不必為此刪資料庫。
    改欄位型別、刪欄位、新增必填欄位仍然不會自動處理，見 README 的「資料庫」。
    """
    inspector = inspect(db.engine)
    with db.engine.begin() as conn:
        for table in db.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing or not column.nullable:
                    continue
                type_sql = column.type.compile(dialect=db.engine.dialect)
                conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {type_sql}')
            # 索引要在欄位補上之後才建得起來
            for index in table.indexes:
                index.create(conn, checkfirst=True)
