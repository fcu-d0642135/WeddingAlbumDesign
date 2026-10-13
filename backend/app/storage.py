"""照片檔的存放。

其他程式只透過這裡的 save() / url() 碰檔案，不直接讀寫路徑。
現在存本機磁碟；之後換成雲端物件儲存（例如 S3）時，只要換掉這個模組的實作。
"""

import os
import shutil
from typing import BinaryIO

from flask import Blueprint, current_app, send_from_directory


def media_dir() -> str:
    return current_app.config["MEDIA_DIR"] or os.path.join(current_app.instance_path, "media")


def save(key: str, data: bytes) -> None:
    """key 是像 "photos/p_abc/thumb.jpg" 這樣的相對路徑。"""
    path = os.path.join(media_dir(), *key.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def save_stream(key: str, stream: BinaryIO) -> None:
    """跟 save() 一樣，但從檔案串流一段一段複製，影片這種大檔案不必整個讀進記憶體。"""
    path = os.path.join(media_dir(), *key.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    stream.seek(0)
    with open(path, "wb") as f:
        shutil.copyfileobj(stream, f)


def delete(key: str) -> None:
    """刪掉一個檔案。檔案不在也不報錯：--replace 中斷後重跑，部分檔案可能已經刪過了。"""
    path = os.path.join(media_dir(), *key.split("/"))
    if os.path.exists(path):
        os.remove(path)


def url(key: str) -> str:
    """回給前端的網址，前端拿到後直接使用、不自己組。"""
    return current_app.config["MEDIA_BASE_URL"].rstrip("/") + "/" + key


# 開發時由 Flask 自己送出照片檔。正式環境改由網頁伺服器或雲端儲存直接提供，不經過 Flask
bp = Blueprint("media", __name__)


@bp.get("/media/<path:key>")
def serve(key: str):
    # send_from_directory 會擋掉 ../ 之類跳出資料夾的路徑
    return send_from_directory(media_dir(), key, max_age=60 * 60 * 24 * 30)
