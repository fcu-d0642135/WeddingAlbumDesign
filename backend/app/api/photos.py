"""相簿：照片列表、單張照片、首頁統計。"""

import hashlib
from datetime import UTC, datetime, time, timedelta

from flask import current_app, g, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import images, storage, videos
from app.api import bp
from app.auth import require_guest
from app.db import db
from app.errors import ApiError
from app.models import (
    PHOTO_TAGS,
    TAIPEI,
    Blessing,
    Favorite,
    Guest,
    Like,
    Photo,
    new_photo_id,
    now,
    photos_to_json,
)
from app.pagination import paginate


def _today_range_utc() -> tuple[datetime, datetime]:
    """台灣時間「今天」的起訖，換成資料庫裡存的 UTC（不帶時區）。"""
    # now() 是不帶時區的 UTC，不能直接 astimezone（會被當成電腦本地時間），這裡直接取台灣時間
    today = datetime.now(TAIPEI).date()
    start = datetime.combine(today, time.min, tzinfo=TAIPEI).astimezone(UTC).replace(tzinfo=None)
    return start, start + timedelta(days=1)


# --- 路由 -----------------------------------------------------------------


@bp.get("/photos")
@require_guest
def list_photos():
    args = request.args
    query = db.select(Photo)

    if tag := args.get("tag"):
        if tag not in PHOTO_TAGS:
            raise ApiError(400, "invalid_tag", "照片分類不正確")
        query = query.where(Photo.tag == tag)

    if kind := args.get("kind"):
        if kind not in ("photo", "video"):
            raise ApiError(400, "invalid_kind", "kind 只能是 photo 或 video")
        query = query.where(Photo.kind == kind)

    if date := args.get("date"):
        if date != "today":
            raise ApiError(400, "invalid_date", "date 目前只支援 today")
        start, end = _today_range_utc()
        query = query.where(Photo.uploaded_at >= start, Photo.uploaded_at < end)

    if uploader := args.get("uploader"):
        query = query.where(Photo.uploader_id == (g.guest.id if uploader == "me" else uploader))

    if args.get("favorited") == "true":
        # 收藏是私人的，只能看自己的
        query = query.join(
            Favorite, (Favorite.photo_id == Photo.id) & (Favorite.guest_id == g.guest.id)
        )

    items, next_cursor = paginate(query, Photo.uploaded_at, Photo.id)
    return jsonify({"items": photos_to_json(items, g.guest.id), "nextCursor": next_cursor})


def _file_size(stream) -> int:
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    return size


def _too_large(limit: int, what: str) -> ApiError:
    # 跟前端選取頁的提示一致：傳不了的，給賓客一條出路
    mb = limit // (1024 * 1024)
    return ApiError(
        413, "file_too_large", f"{what}太大了，單檔上限 {mb} MB，可以等婚禮過後再分享給新人唷 ♥"
    )


@bp.post("/photos")
@require_guest
def upload_photo():
    """上傳一張照片或一支影片。multipart/form-data，欄位 file（必填）、tag（選填，預設 banquet）。

    是照片還是影片看檔案內容判斷，副檔名、Content-Type 都不採信。
    同一位賓客傳了一模一樣的檔案，回傳已經有的那張（200），不會變成兩張。
    """
    config = current_app.config
    if not config["UPLOADS_OPEN"]:
        raise ApiError(403, "uploads_closed", "相簿已經截止上傳，謝謝你的參與")

    file = request.files.get("file")
    if file is None or not file.filename:
        raise ApiError(400, "file_required", "請選擇要上傳的照片或影片")

    tag = request.form.get("tag") or "banquet"
    if tag not in PHOTO_TAGS:
        raise ApiError(400, "invalid_tag", "照片分類不正確")

    # 檔案已經在 Werkzeug 的暫存檔裡，先看大小，超過就不必讀進記憶體
    stream = file.stream
    size = _file_size(stream)

    # 逾時後重送、或不小心選了同一張：直接回傳之前那張。放在每小時上限之前，重送不該算成多傳
    content_hash = _sha256(stream)
    if existing := _find_duplicate(content_hash):
        return jsonify(existing.to_json(g.guest.id)), 200

    # 每人每小時的上限（照片影片合計）：正常賓客碰不到，主要防活動碼外流後被灌爆
    recent = db.session.scalar(
        db.select(func.count())
        .select_from(Photo)
        .where(Photo.uploader_id == g.guest.id, Photo.uploaded_at >= now() - timedelta(hours=1))
    )
    if recent >= config["MAX_UPLOADS_PER_HOUR"]:
        raise ApiError(429, "too_many_uploads", "上傳得太快了，請休息一下再繼續")

    head = stream.read(16)
    stream.seek(0)
    if videos.looks_like_video(head):
        if size > config["MAX_VIDEO_BYTES"]:
            raise _too_large(config["MAX_VIDEO_BYTES"], "影片")
        processed = _process_video(stream)

        def save_original(key: str) -> None:
            # 影片不轉檔，原檔直接拿來播
            storage.save_stream(key, stream)

        kind = "video"
    else:
        if size > config["MAX_PHOTO_BYTES"]:
            raise _too_large(config["MAX_PHOTO_BYTES"], "照片")
        data = stream.read()
        processed = _process_photo(data)

        def save_original(key: str) -> None:
            # 原檔原封不動地存，之後匯出給新人時就是原始畫質
            storage.save(key, data)

        kind = "photo"

    photo, created = _store(kind, tag, processed, content_hash, save_original)
    return jsonify(photo.to_json(g.guest.id)), 201 if created else 200


def _sha256(stream) -> str:
    """一段一段讀，影片也不必整個放進記憶體。"""
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    stream.seek(0)
    return digest.hexdigest()


def _find_duplicate(content_hash: str) -> Photo | None:
    return db.session.scalar(
        db.select(Photo).where(Photo.uploader_id == g.guest.id, Photo.content_hash == content_hash)
    )


def _process_photo(data: bytes) -> images.ProcessedImage:
    try:
        return images.process_upload(data)
    except images.UnsupportedImage as e:
        raise ApiError(
            415, "unsupported_format", "看不懂這個檔案，請上傳 JPEG、PNG、HEIC、WebP 照片或 MP4、MOV 影片"
        ) from e


def _process_video(stream) -> videos.ProcessedVideo:
    try:
        processed = videos.process_upload(stream)
    except videos.UnsupportedVideo as e:
        raise ApiError(415, "unsupported_format", "看不懂這支影片，請上傳 MP4 或 MOV 影片") from e

    limit = current_app.config["MAX_VIDEO_SECONDS"]
    # 留一秒誤差：手機顯示 3:00 的影片，檔案裡可能記成 180.4 秒
    if processed.duration_seconds > limit + 1:
        raise ApiError(400, "video_too_long", f"影片太長了，請剪到 {_minutes(limit)}以內再上傳")
    return processed


def _store(kind: str, tag: str, processed, content_hash: str, save_original) -> tuple[Photo, bool]:
    """存檔案、寫資料庫，回傳 (照片, 是不是新建的)。

    先存檔案再寫資料庫：SQLite 寫入時整個資料庫會鎖住，這樣只鎖寫一筆資料的那一下，
    婚宴高峰大家同時上傳時，才不會排隊等別人存完檔案。
    """
    photo_id = new_photo_id()
    folder = f"photos/{photo_id}"
    photo = Photo(
        id=photo_id,
        uploader_id=g.guest.id,
        kind=kind,
        tag=tag,
        width=processed.width,
        height=processed.height,
        taken_at=processed.taken_at,
        duration_seconds=getattr(processed, "duration_seconds", None),
        content_hash=content_hash,
        original_key=f"{folder}/original.{processed.extension}",
        display_key=f"{folder}/display.jpg",
        thumb_key=f"{folder}/thumb.jpg",
    )
    keys = [photo.display_key, photo.thumb_key, photo.original_key]
    storage.save(photo.display_key, processed.display_jpeg)
    storage.save(photo.thumb_key, processed.thumb_jpeg)
    save_original(photo.original_key)

    db.session.add(photo)
    try:
        db.session.commit()
    except IntegrityError:
        # 同一個檔案的另一個請求（例如逾時後的重送）剛好搶先寫進去了：用那一張，這次存的檔案丟掉
        db.session.rollback()
        for key in keys:
            storage.delete(key)
        existing = _find_duplicate(content_hash)
        if existing is None:
            raise
        return existing, False
    return photo, True


def _minutes(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    if not m:
        return f"{s} 秒"
    return f"{m} 分鐘" if not s else f"{m} 分 {s} 秒"


def _get_photo_or_404(photo_id: str) -> Photo:
    photo = db.session.get(Photo, photo_id)
    if photo is None:
        raise ApiError(404, "photo_not_found", "找不到這張照片")
    return photo


@bp.get("/photos/<photo_id>")
@require_guest
def get_photo(photo_id: str):
    return jsonify(_get_photo_or_404(photo_id).to_json(g.guest.id))


@bp.delete("/photos/<photo_id>")
@require_guest
def delete_photo(photo_id: str):
    """刪除照片。上傳者可以刪自己的；管理員可以刪任何一張（例如不適當的照片）。

    讚、收藏一併刪掉。照片上的祝福留在留言牆，只是不再掛在照片上：照片不當不代表祝福也有問題。
    """
    photo = _get_photo_or_404(photo_id)
    if photo.uploader_id != g.guest.id and not g.guest.is_admin:
        raise ApiError(403, "not_your_photo", "只能刪除自己上傳的照片")

    keys = [photo.original_key, photo.display_key, photo.thumb_key]
    db.session.execute(db.delete(Like).where(Like.photo_id == photo.id))
    db.session.execute(db.delete(Favorite).where(Favorite.photo_id == photo.id))
    db.session.execute(
        db.update(Blessing).where(Blessing.photo_id == photo.id).values(photo_id=None)
    )
    db.session.delete(photo)
    db.session.commit()
    # 資料庫刪成功之後才刪檔案；反過來的話，萬一資料庫失敗會留下一張打不開的照片
    for key in keys:
        storage.delete(key)
    return "", 204


# --- 按讚、收藏 -----------------------------------------------------------
# 用 PUT / DELETE 而不是「切換」：重複按、網路不穩重送，結果都一樣，不會讚了又被收回。
# 回應是更新後的照片，前端直接拿來換掉畫面上的那張。


def _set_mark(model, photo_id: str, on: bool):
    photo = _get_photo_or_404(photo_id)
    existing = db.session.get(model, (g.guest.id, photo.id))
    if on and existing is None:
        db.session.add(model(guest_id=g.guest.id, photo_id=photo.id))
    elif not on and existing is not None:
        db.session.delete(existing)
    db.session.commit()
    return jsonify(photo.to_json(g.guest.id))


@bp.put("/photos/<photo_id>/like")
@require_guest
def like_photo(photo_id: str):
    return _set_mark(Like, photo_id, True)


@bp.delete("/photos/<photo_id>/like")
@require_guest
def unlike_photo(photo_id: str):
    return _set_mark(Like, photo_id, False)


@bp.put("/photos/<photo_id>/favorite")
@require_guest
def favorite_photo(photo_id: str):
    return _set_mark(Favorite, photo_id, True)


@bp.delete("/photos/<photo_id>/favorite")
@require_guest
def unfavorite_photo(photo_id: str):
    return _set_mark(Favorite, photo_id, False)


@bp.get("/stats")
@require_guest
def get_stats():
    def count(query):
        return db.session.scalar(query)

    return jsonify(
        {
            "photoCount": count(db.select(func.count()).select_from(Photo)),
            # 透過 app 加入相簿的賓客人數，不含預先匯入的祝福作者
            "guestCount": count(
                db.select(func.count()).select_from(Guest).where(Guest.imported.is_(False))
            ),
            "blessingCount": count(db.select(func.count()).select_from(Blessing)),
            # 留言牆標題「32 位賓客留下了 47 則祝福」的 32：留過祝福的人數，含預先匯入的
            "blessingGuestCount": count(db.select(func.count(func.distinct(Blessing.guest_id)))),
        }
    )
