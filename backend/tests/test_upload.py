import io
import os

import pytest
from PIL import Image

from app import images
from tests.conftest import auth

ORIENTATION = 0x0112
EXIF_IFD = 0x8769
DATETIME_ORIGINAL = 36867


def make_image(fmt="JPEG", size=(400, 300), orientation=None, taken_at=None) -> bytes:
    image = Image.new("RGB", size, "#C9A48E")
    exif = Image.Exif()
    if orientation:
        exif[ORIENTATION] = orientation
    if taken_at:
        exif.get_ifd(EXIF_IFD)[DATETIME_ORIGINAL] = taken_at
    buf = io.BytesIO()
    image.save(buf, fmt, **({"exif": exif.tobytes()} if len(exif) or taken_at else {}))
    return buf.getvalue()


@pytest.fixture
def token(join):
    return join("小慧")[0]


def upload(client, token, data, filename="photo.jpg", mimetype="image/jpeg", **form):
    return client.post(
        "/api/photos",
        headers=auth(token),
        data={"file": (io.BytesIO(data), filename, mimetype), **form},
        content_type="multipart/form-data",
    )


def media_path(app, url: str) -> str:
    return os.path.join(app.config["MEDIA_DIR"], *url.removeprefix("/media/").split("/"))


# --- 正常上傳 -------------------------------------------------------------


def test_upload_jpeg(app, client, token):
    data = make_image()

    res = upload(client, token, data)

    assert res.status_code == 201, res.get_json()
    photo = res.get_json()
    assert photo["kind"] == "photo"
    assert photo["tag"] == "banquet"  # 沒帶分類時預設宴客
    assert (photo["width"], photo["height"]) == (400, 300)
    assert photo["uploader"]["nickname"] == "小慧"

    # 原檔原封不動，之後匯出才是原始畫質
    with open(media_path(app, photo["url"]), "rb") as f:
        assert f.read() == data


def test_uploaded_photo_shows_in_album(client, token):
    photo_id = upload(client, token, make_image()).get_json()["id"]

    items = client.get("/api/photos", headers=auth(token)).get_json()["items"]

    assert [p["id"] for p in items] == [photo_id]


def test_upload_with_tag(client, token):
    res = upload(client, token, make_image(), tag="engagement")
    assert res.get_json()["tag"] == "engagement"


def test_display_and_thumbnail_are_resized_jpegs(app, client, token):
    photo = upload(client, token, make_image(size=(4000, 3000))).get_json()

    display = Image.open(media_path(app, photo["displayUrl"]))
    thumb = Image.open(media_path(app, photo["thumbnailUrl"]))

    assert display.format == thumb.format == "JPEG"
    assert max(display.size) == images.DISPLAY_LONG_EDGE
    assert max(thumb.size) == images.THUMB_LONG_EDGE
    # 原圖尺寸照實回報，前端用來算比例
    assert (photo["width"], photo["height"]) == (4000, 3000)


def test_small_photo_is_not_enlarged(app, client, token):
    photo = upload(client, token, make_image(size=(200, 100))).get_json()
    assert Image.open(media_path(app, photo["thumbnailUrl"])).size == (200, 100)


def test_rotated_phone_photo_is_upright(app, client, token):
    # 手機直拍：像素存成橫的 400x300，EXIF 記錄「要轉 90 度」
    photo = upload(client, token, make_image(size=(400, 300), orientation=6)).get_json()

    assert (photo["width"], photo["height"]) == (300, 400)
    assert Image.open(media_path(app, photo["thumbnailUrl"])).size == (300, 400)


def test_taken_at_from_exif(client, token):
    photo = upload(client, token, make_image(taken_at="2026:10:17 18:40:12")).get_json()
    # EXIF 沒寫時區，當作台灣時間
    assert photo["takenAt"] == "2026-10-17T18:40:12+08:00"


def test_taken_at_missing_is_null(client, token):
    assert upload(client, token, make_image()).get_json()["takenAt"] is None


@pytest.mark.parametrize(
    "fmt, mimetype, ext",
    [("PNG", "image/png", "png"), ("WEBP", "image/webp", "webp"), ("HEIF", "image/heic", "heic")],
)
def test_other_formats(app, client, token, fmt, mimetype, ext):
    res = upload(client, token, make_image(fmt=fmt), filename=f"p.{ext}", mimetype=mimetype)

    assert res.status_code == 201, res.get_json()
    photo = res.get_json()
    assert photo["url"].endswith(f"original.{ext}")
    # iPhone 的 HEIC 很多瀏覽器看不懂，畫面用的一律是 JPEG
    assert Image.open(media_path(app, photo["thumbnailUrl"])).format == "JPEG"


# --- 擋下來的情況 ---------------------------------------------------------


def test_upload_requires_token(client):
    res = client.post(
        "/api/photos",
        data={"file": (io.BytesIO(make_image()), "p.jpg")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 401


def test_missing_file_is_400(client, token):
    res = client.post(
        "/api/photos", headers=auth(token), data={}, content_type="multipart/form-data"
    )
    assert res.get_json()["error"]["code"] == "file_required"


def test_not_an_image_is_415(client, token):
    res = upload(client, token, b"hello", filename="notes.txt", mimetype="text/plain")

    assert res.status_code == 415
    assert res.get_json()["error"]["code"] == "unsupported_format"


def _broken_heic(cut_image_data: bool) -> bytes:
    data = make_image("HEIF")
    mdat = data.find(b"mdat") + 4
    if cut_image_data:
        return data[: mdat + 16]  # 檔頭說有影像資料，檔案卻提早結束
    return data[:mdat] + b"U" * (len(data) - mdat)  # 影像資料被寫壞


@pytest.mark.parametrize("cut_image_data", [True, False])
def test_broken_heic_is_415(client, token, cut_image_data):
    # pillow-heif 這兩種情況丟的是 ValueError／EOFError，以前會變成 500
    data = _broken_heic(cut_image_data)
    res = upload(client, token, data, filename="IMG_0001.HEIC", mimetype="image/heic")

    assert res.status_code == 415
    assert res.get_json()["error"]["code"] == "unsupported_format"


def test_image_with_fake_extension_is_checked_by_content(client, token):
    # 副檔名和 Content-Type 都可以亂填，一律看檔案內容判斷
    res = upload(client, token, b"not really a jpeg", filename="photo.jpg", mimetype="image/jpeg")
    assert res.status_code == 415


def test_invalid_tag_is_400(client, token):
    res = upload(client, token, make_image(), tag="party")
    assert res.get_json()["error"]["code"] == "invalid_tag"


def test_file_too_large(app, client, token):
    app.config["MAX_PHOTO_BYTES"] = 1000

    res = upload(client, token, make_image(size=(800, 800)))

    assert res.status_code == 413
    assert res.get_json()["error"]["code"] == "file_too_large"


def test_huge_request_is_rejected_before_reading(app, client, token):
    # 超過整個請求的上限時，Flask 在讀進記憶體前就擋掉
    app.config["MAX_CONTENT_LENGTH"] = 2000

    res = upload(client, token, b"x" * 5000)

    assert res.status_code == 413
    assert res.get_json()["error"]["code"] == "file_too_large"


def test_uploads_closed(app, client, token):
    app.config["UPLOADS_OPEN"] = False

    res = upload(client, token, make_image())

    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "uploads_closed"


def test_hourly_upload_limit(app, client, join):
    app.config["MAX_UPLOADS_PER_HOUR"] = 2
    token, _ = join("小慧")
    other, _ = join("阿凱")

    # 尺寸不同才是不同的檔案；一模一樣的檔案會被當成重送，不算次數
    assert upload(client, token, make_image(size=(400, 300))).status_code == 201
    assert upload(client, token, make_image(size=(401, 300))).status_code == 201
    res = upload(client, token, make_image(size=(402, 300)))
    assert res.status_code == 429
    assert res.get_json()["error"]["code"] == "too_many_uploads"

    # 每個人各自計算
    assert upload(client, other, make_image()).status_code == 201


def test_failed_upload_leaves_nothing_behind(app, client, token):
    upload(client, token, b"broken", filename="p.jpg")

    assert client.get("/api/photos", headers=auth(token)).get_json()["items"] == []



# --- 重送同一個檔案 -------------------------------------------------------


def test_same_file_twice_returns_existing_photo(app, client, token):
    # 逾時後手機自動重送：後端其實已經存好了，不能變成兩張
    data = make_image()
    first = upload(client, token, data)
    again = upload(client, token, data, filename="IMG_0001 (1).jpg")

    assert first.status_code == 201
    assert again.status_code == 200
    assert again.get_json()["id"] == first.get_json()["id"]
    assert len(client.get("/api/photos", headers=auth(token)).get_json()["items"]) == 1


def test_resend_does_not_count_toward_hourly_limit(app, client, token):
    app.config["MAX_UPLOADS_PER_HOUR"] = 1
    data = make_image()

    assert upload(client, token, data).status_code == 201
    assert upload(client, token, data).status_code == 200


def test_same_file_from_different_guests_is_kept_twice(client, join):
    # 照片在 LINE 群組轉傳，兩個人都上傳：各算各的
    data = make_image()
    a, _ = join("小慧")
    b, _ = join("阿凱")

    assert upload(client, a, data).status_code == 201
    assert upload(client, b, data).status_code == 201


def test_resend_racing_the_first_request_keeps_one(app, client, token, monkeypatch):
    # 第一個請求還在處理時重送就到了：兩邊都查不到重複，各自處理，寫入時才撞上。
    # 模擬法：讓「找重複」第一次查不到，第二個請求寫入時撞到唯一索引
    from app.api import photos as photos_api

    data = make_image()
    first = upload(client, token, data).get_json()

    real = photos_api._find_duplicate
    calls = {"n": 0}

    def miss_once(content_hash):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(content_hash)

    monkeypatch.setattr(photos_api, "_find_duplicate", miss_once)
    res = upload(client, token, data)

    assert res.status_code == 200
    assert res.get_json()["id"] == first["id"]
    assert len(client.get("/api/photos", headers=auth(token)).get_json()["items"]) == 1
    # 輸掉的那次存下的檔案要清掉，不留孤兒檔
    root = os.path.join(app.config["MEDIA_DIR"], "photos")
    leftovers = [d for d in os.listdir(root) if d != first["id"] and os.listdir(os.path.join(root, d))]
    assert leftovers == []
