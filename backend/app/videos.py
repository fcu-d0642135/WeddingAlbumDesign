"""影片處理：讀長度、尺寸、拍攝時間，抓一格當封面。

影片不轉檔，原檔直接拿來播（轉檔很吃 CPU，婚宴高峰會塞車，見 docs/api.md 的「上傳」）。
封面跟照片一樣產生顯示用與縮圖兩份 JPEG，列表與詳情頁沿用照片的做法。
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO

import av

from app import images

# MP4 與 MOV 檔頭第 4～8 個位元組是 "ftyp"，後面接品牌。iPhone 的 HEIC 照片也是同一種格式，
# 要靠品牌分辨：這些品牌是照片，其餘的 ftyp 都當影片
_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1", b"mif2", b"avif", b"avis"}

# PyAV 認出的容器格式名稱是一串用逗號隔開的別名，例如 "mov,mp4,m4a,3gp,3g2,mj2"
_ACCEPTED_CONTAINERS = {"mov", "mp4"}

# 手機的影片有時沒有拍攝時間，或寫成 1904、1970 這種預設值
_EARLIEST_TAKEN_AT = datetime(2000, 1, 1)


class UnsupportedVideo(Exception):
    """不是影片、壞掉的檔案，或不支援的格式。"""


@dataclass
class ProcessedVideo:
    extension: str
    # 已依拍攝方向轉正
    width: int
    height: int
    duration_seconds: float
    # 不帶時區的 UTC，讀不到就是 None
    taken_at: datetime | None
    display_jpeg: bytes
    thumb_jpeg: bytes


def looks_like_video(head: bytes) -> bool:
    """看檔頭判斷是不是 MP4／MOV 影片。副檔名、Content-Type 都可以亂填，不能拿來判斷。"""
    return head[4:8] == b"ftyp" and head[8:12] not in _HEIF_BRANDS


def _parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    # creation_time 一律是 UTC；沒帶時區的也照 UTC 算
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt if dt >= _EARLIEST_TAKEN_AT else None


def _taken_at(metadata: dict) -> datetime | None:
    # iPhone 另外存一份帶時區的拍攝時間，比 creation_time（有時是存檔時間）準
    return _parse_time(metadata.get("com.apple.quicktime.creationdate")) or _parse_time(
        metadata.get("creation_time")
    )


def process_upload(file: BinaryIO) -> ProcessedVideo:
    """file 要能 seek。只讀檔頭和第一格畫面，不會把整支影片讀進記憶體。"""
    try:
        with av.open(file) as container:
            if not _ACCEPTED_CONTAINERS & set(container.format.name.split(",")):
                raise UnsupportedVideo(container.format.name)
            if not container.streams.video:
                raise UnsupportedVideo("沒有影像")
            stream = container.streams.video[0]

            if container.duration:
                duration = container.duration / av.time_base
            elif stream.duration and stream.time_base:
                duration = float(stream.duration * stream.time_base)
            else:
                raise UnsupportedVideo("讀不到長度")

            frame = next(container.decode(stream), None)
            if frame is None:
                raise UnsupportedVideo("沒有畫面")
            poster = frame.to_image()
            # 手機直拍的影片，畫面其實是橫的，靠 rotation 記錄要轉幾度（逆時針，跟 PIL 的 rotate 一樣）
            if frame.rotation:
                poster = poster.rotate(frame.rotation, expand=True)
            taken_at = _taken_at(dict(container.metadata))
            extension = "mov" if container.metadata.get("major_brand", "").strip() == "qt" else "mp4"
    except (av.FFmpegError, ValueError, OSError) as e:
        raise UnsupportedVideo(str(e)) from e

    return ProcessedVideo(
        extension=extension,
        width=poster.width,
        height=poster.height,
        duration_seconds=round(duration, 1),
        taken_at=taken_at,
        display_jpeg=images.make_display(poster),
        thumb_jpeg=images.make_thumbnail(poster),
    )

