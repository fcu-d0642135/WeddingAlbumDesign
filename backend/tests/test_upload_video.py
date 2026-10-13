"""影片上傳。測試用的影片用 PyAV 當場產生，只有幾 KB。"""

import io
import os

import av
import pytest
from PIL import Image

from app import images
from tests.conftest import auth
from tests.test_upload import make_image, media_path, upload


def make_video(seconds=1, size=(64, 48), container="mp4", rotation=0, metadata=None, rate=10) -> bytes:
    buf = io.BytesIO()
    with av.open(buf, "w", format=container) as out:
        stream = out.add_stream("libx264", rate=rate)
        stream.width, stream.height = size
        stream.pix_fmt = "yuv420p"
        if rotation:
            stream.set_display_rotation(rotation)
        out.metadata.update(metadata or {})
        for i in range(seconds * rate):
            frame = av.VideoFrame.from_image(Image.new("RGB", size, (200, 120, i % 256)))
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return buf.getvalue()


@pytest.fixture
def token(join):
    return join("小慧")[0]


def upload_video(client, token, data, filename="IMG_0001.MOV", mimetype="video/quicktime", **form):
    return upload(client, token, data, filename=filename, mimetype=mimetype, **form)


# --- 正常上傳 -------------------------------------------------------------


def test_upload_mp4(app, client, token):
    data = make_video(seconds=2)

    res = upload_video(client, token, data, filename="v.mp4", mimetype="video/mp4", tag="engagement")

    assert res.status_code == 201, res.get_json()
    video = res.get_json()
    assert video["kind"] == "video"
    assert video["tag"] == "engagement"
    assert video["durationSeconds"] == pytest.approx(2, abs=0.2)
    assert (video["width"], video["height"]) == (64, 48)
    assert video["url"].endswith("original.mp4")
    # 不轉檔：原檔原封不動，直接拿來播
    with open(media_path(app, video["url"]), "rb") as f:
        assert f.read() == data


def test_mov_keeps_its_extension(client, token):
    video = upload_video(client, token, make_video(container="mov")).get_json()
    assert video["url"].endswith("original.mov")


def test_photo_has_no_duration(client, token):
    assert upload(client, token, make_image()).get_json()["durationSeconds"] is None


def test_poster_is_jpeg(app, client, token):
    video = upload_video(client, token, make_video(size=(320, 240))).get_json()

    display = Image.open(media_path(app, video["displayUrl"]))
    thumb = Image.open(media_path(app, video["thumbnailUrl"]))

    assert display.format == thumb.format == "JPEG"
    # 比縮圖規格小的畫面不放大
    assert display.size == thumb.size == (320, 240)


def test_large_poster_is_resized(app, client, token):
    video = upload_video(client, token, make_video(size=(1920, 1080))).get_json()

    thumb = Image.open(media_path(app, video["thumbnailUrl"]))
    assert max(thumb.size) == images.THUMB_LONG_EDGE


def test_portrait_phone_video_is_upright(app, client, token):
    # 手機直拍：畫面存成橫的 64x48，另外記錄「要轉 90 度」
    video = upload_video(client, token, make_video(size=(64, 48), rotation=-90)).get_json()

    assert (video["width"], video["height"]) == (48, 64)
    assert Image.open(media_path(app, video["thumbnailUrl"])).size == (48, 64)


def test_taken_at_from_creation_time(client, token):
    data = make_video(metadata={"creation_time": "2026-10-17T10:40:12.000000Z"})
    assert upload_video(client, token, data).get_json()["takenAt"] == "2026-10-17T18:40:12+08:00"


def test_placeholder_creation_time_is_ignored(client, token):
    data = make_video(metadata={"creation_time": "1970-01-01T00:00:00.000000Z"})
    assert upload_video(client, token, data).get_json()["takenAt"] is None


def test_iphone_creationdate_wins():
    # iPhone 另存一份帶時區的拍攝時間，creation_time 有時是存檔時間
    from app.videos import _taken_at

    taken_at = _taken_at(
        {
            "com.apple.quicktime.creationdate": "2026-10-17T18:40:12+0800",
            "creation_time": "2026-10-17T10:41:00.000000Z",
        }
    )
    assert taken_at.isoformat() == "2026-10-17T10:40:12"


def test_kind_is_judged_by_content(client, token):
    # 影片假裝成 jpg、照片假裝成 mp4，一律看內容
    res = upload_video(client, token, make_video(), filename="a.jpg", mimetype="image/jpeg")
    assert res.get_json()["kind"] == "video"
    res = upload(client, token, make_image(), filename="a.mp4", mimetype="video/mp4")
    assert res.get_json()["kind"] == "photo"


def test_heic_photo_is_not_mistaken_for_video(client, token):
    # HEIC 跟 MP4 的檔頭長得很像（都是 ftyp），要靠品牌分辨
    res = upload(client, token, make_image("HEIF"), filename="p.heic", mimetype="image/heic")
    assert res.get_json()["kind"] == "photo"


def test_video_shows_in_kind_filter(client, token):
    video_id = upload_video(client, token, make_video()).get_json()["id"]
    upload(client, token, make_image())

    items = client.get("/api/photos?kind=video", headers=auth(token)).get_json()["items"]

    assert [p["id"] for p in items] == [video_id]


def test_video_can_be_streamed_with_range(client, token):
    # iPhone 播影片一定用 Range 一段一段要，不支援就播不了
    data = make_video()
    url = upload_video(client, token, data).get_json()["url"]

    res = client.get(url, headers={"Range": "bytes=0-99"})

    assert res.status_code == 206
    assert res.data == data[:100]


def test_delete_video_removes_files(app, client, token):
    video = upload_video(client, token, make_video()).get_json()
    paths = [media_path(app, video[k]) for k in ("url", "displayUrl", "thumbnailUrl")]

    assert client.delete(f"/api/photos/{video['id']}", headers=auth(token)).status_code == 204

    assert not any(os.path.exists(p) for p in paths)


# --- 擋下來的情況 ---------------------------------------------------------


def test_video_too_long(app, client, token):
    app.config["MAX_VIDEO_SECONDS"] = 1

    res = upload_video(client, token, make_video(seconds=3))

    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "video_too_long"
    assert "1 秒" in res.get_json()["error"]["message"]
    assert client.get("/api/photos", headers=auth(token)).get_json()["items"] == []


def test_video_at_limit_is_accepted(app, client, token):
    app.config["MAX_VIDEO_SECONDS"] = 2
    assert upload_video(client, token, make_video(seconds=2)).status_code == 201


def test_too_long_message_in_minutes(app, client, token):
    app.config["MAX_VIDEO_SECONDS"] = 0

    res = upload_video(client, token, make_video(seconds=2))
    assert res.status_code == 400

    from app.api.photos import _minutes

    assert _minutes(180) == "3 分鐘"
    assert _minutes(90) == "1 分 30 秒"


def test_video_too_large(app, client, token):
    data = make_video()
    app.config["MAX_VIDEO_BYTES"] = len(data) - 1

    res = upload_video(client, token, data)

    assert res.status_code == 413
    assert res.get_json()["error"]["code"] == "file_too_large"
    assert res.get_json()["error"]["message"] == "影片太大了，單檔上限 0 MB，可以等婚禮過後再分享給新人唷 ♥"


def test_photo_limit_does_not_apply_to_video(app, client, token):
    data = make_video(size=(320, 240))
    app.config["MAX_PHOTO_BYTES"] = len(data) - 1

    assert upload_video(client, token, data).status_code == 201


@pytest.mark.parametrize(
    "data",
    [
        b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100,  # 只有檔頭
        b"\x00\x00\x00\x18ftypisom" + b"U" * 5000,  # 內容是亂碼
    ],
)
def test_broken_video_is_415(client, token, data):
    res = upload_video(client, token, data)

    assert res.status_code == 415
    assert res.get_json()["error"]["code"] == "unsupported_format"


def test_truncated_video_is_415(client, token):
    data = make_video(seconds=2)

    res = upload_video(client, token, data[: len(data) // 3])

    assert res.status_code == 415
    assert client.get("/api/photos", headers=auth(token)).get_json()["items"] == []


def test_videos_count_toward_hourly_limit(app, client, token):
    app.config["MAX_UPLOADS_PER_HOUR"] = 2

    assert upload_video(client, token, make_video(seconds=1)).status_code == 201
    assert upload(client, token, make_image()).status_code == 201
    assert upload_video(client, token, make_video(seconds=2)).status_code == 429


def test_same_video_twice_returns_existing(client, token):
    data = make_video()
    first = upload_video(client, token, data).get_json()

    again = upload_video(client, token, data)

    assert again.status_code == 200
    assert again.get_json()["id"] == first["id"]
