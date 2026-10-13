"""設定：GET /api/config（前端要遵守的各種上限），以及管理員在 app 裡改的設定。"""

from flask import current_app, g, jsonify, request

from app.api import bp
from app.auth import require_guest
from app.db import db
from app.errors import ApiError
from app.models import Setting

KAHOOT_KEY = "kahoot_url"
KAHOOT_ENABLED_KEY = "kahoot_enabled"
URL_MAX = 500


def _kahoot() -> dict:
    """管理員看到的 Kahoot! 設定：連結可以先存好，開關打開才會出現按鈕。"""
    url = db.session.get(Setting, KAHOOT_KEY)
    enabled = db.session.get(Setting, KAHOOT_ENABLED_KEY)
    return {"url": url.value if url else None, "enabled": bool(url and enabled)}


def _put_setting(key: str, value: str | None) -> None:
    """value 為 None 代表拿掉這筆設定。"""
    existing = db.session.get(Setting, key)
    if value is None:
        if existing:
            db.session.delete(existing)
    elif existing:
        existing.value = value
    else:
        db.session.add(Setting(key=key, value=value))


def _require_admin() -> None:
    if not g.guest.is_admin:
        raise ApiError(403, "not_admin", "只有管理員可以修改")


@bp.get("/config")
def get_config():
    """不需要 token：歡迎頁（還沒加入）也要用到，例如 Kahoot! 連結。"""
    c = current_app.config
    kahoot = _kahoot()
    return jsonify(
        {
            "maxPhotoBytes": c["MAX_PHOTO_BYTES"],
            "maxVideoBytes": c["MAX_VIDEO_BYTES"],
            "maxVideoSeconds": c["MAX_VIDEO_SECONDS"],
            "maxUploadsPerHour": c["MAX_UPLOADS_PER_HOUR"],
            "uploadConcurrency": c["UPLOAD_CONCURRENCY"],
            "videoUploadConcurrency": c["VIDEO_UPLOAD_CONCURRENCY"],
            "maxBlessingLength": c["MAX_BLESSING_LENGTH"],
            "uploadsOpen": c["UPLOADS_OPEN"],
            # 連結由管理員在 app 裡設定；開關沒打開時一律是 null，提早存好的連結不會被看到
            "kahootUrl": kahoot["url"] if kahoot["enabled"] else None,
        }
    )


@bp.get("/settings/kahoot")
@require_guest
def get_kahoot():
    """管理員看目前存的連結與開關（開關關著時 /api/config 不會給連結）。"""
    _require_admin()
    return jsonify(_kahoot())


@bp.put("/settings/kahoot")
@require_guest
def set_kahoot():
    """管理員設定 Kahoot! 連結與開關。url 傳空字串或 null 代表拿掉，開關也會跟著關掉。"""
    _require_admin()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_body", "請求內容必須是 JSON 物件")

    raw = body.get("url")
    url = raw.strip() if isinstance(raw, str) else ""
    enabled = body.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ApiError(400, "invalid_body", "enabled 必須是 true 或 false")

    # 只收網址：這個值會變成所有人都看得到的按鈕連結，不能是 javascript: 之類的東西
    if url and (not url.lower().startswith(("https://", "http://")) or len(url) > URL_MAX):
        raise ApiError(400, "invalid_url", "請貼上以 https:// 開頭的完整連結")
    if enabled and not url:
        raise ApiError(400, "url_required", "要先貼上連結才能打開")

    _put_setting(KAHOOT_KEY, url or None)
    _put_setting(KAHOOT_ENABLED_KEY, "1" if enabled else None)
    db.session.commit()
    return jsonify(_kahoot())
