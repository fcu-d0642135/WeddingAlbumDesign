"""Flask 應用程式的進入點。

用 create_app() 產生 app，而不是在模組層級直接建立：
測試時每個測試都能拿到一個乾淨、設定可以個別調整的 app。
"""

import os

from flask import Flask

from app import config, errors
from app.db import db, upgrade_existing_tables

DEV_EVENT_CODE = "dev"
DEV_ADMIN_CODE = "admin"


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(config.load())
    if overrides:
        app.config.update(overrides)

    if not app.config["EVENT_CODE"]:
        # 正式環境忘了設活動碼，等於任何人輸入 "dev" 都能進來，寧可啟動失敗
        if not (app.debug or app.testing):
            raise RuntimeError(
                "沒有設定環境變數 EVENT_CODE。正式環境一定要設；"
                "開發時請在 backend/ 底下執行 flask 指令（會讀 .flaskenv 進入開發模式）"
            )
        app.config["EVENT_CODE"] = DEV_EVENT_CODE

    # 管理員代碼沒設：開發時用預設值方便測試；正式環境就保持空的（管理員功能關閉，不影響賓客使用）
    if not app.config["ADMIN_CODE"] and (app.debug or app.testing):
        app.config["ADMIN_CODE"] = DEV_ADMIN_CODE

    # 整個請求的大小上限 = 照片與影片上限中較大的（預設影片 200 MB）+ 1 MB 給表單的其他欄位（例如 tag）。
    # 超過這個大小的請求，Flask 在收下之前就直接回 413。
    # 收下的檔案超過 500 KB 時，Werkzeug 會寫到暫存檔而不是放在記憶體，同時有很多人傳影片也不會吃光記憶體
    app.config["MAX_CONTENT_LENGTH"] = (
        max(app.config["MAX_PHOTO_BYTES"], app.config["MAX_VIDEO_BYTES"]) + 1024 * 1024
    )

    # 中文直接輸出，不要轉成 \u 開頭的跳脫字元
    app.json.ensure_ascii = False

    errors.register(app)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)

    from app import import_blessings, import_wedding, models, seed, storage  # noqa: F401  models：讓 create_all 知道有哪些資料表
    from app.api import bp

    app.register_blueprint(bp)
    app.register_blueprint(storage.bp)
    app.cli.add_command(seed.seed_command)
    app.cli.add_command(import_blessings.import_blessings_command)
    app.cli.add_command(import_wedding.import_wedding_command)

    with app.app_context():
        # 只會建立還不存在的資料表，不會動到已有的資料。
        # 改了既有欄位不會自動套用，見 README 的「資料庫」
        db.create_all()
        upgrade_existing_tables()

    return app
