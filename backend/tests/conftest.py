import pytest

from app import create_app

EVENT_CODE = "test-code"


@pytest.fixture
def app(tmp_path):
    # 每個測試一個全新的記憶體資料庫與照片資料夾，互不影響
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "EVENT_CODE": EVENT_CODE,
            "MEDIA_DIR": str(tmp_path / "media"),
        }
    )


@pytest.fixture
def client(app):
    """模擬前端打 API 的測試用 client，不必真的啟動伺服器。"""
    return app.test_client()


@pytest.fixture
def join(client):
    """以賓客身分加入相簿，回傳 (token, guest)。"""

    def _join(nickname="小慧", **extra):
        res = client.post(
            "/api/guests", json={"eventCode": EVENT_CODE, "nickname": nickname, **extra}
        )
        assert res.status_code == 201, res.get_json()
        body = res.get_json()
        return body["token"], body["guest"]

    return _join


@pytest.fixture
def add_photo(app):
    """直接在資料庫建一張照片（不經過上傳 API），回傳 photo id。"""
    from app.db import db
    from app.models import Photo, now

    def _add(guest_id, tag="banquet", uploaded_at=None, width=300, height=400, kind="photo"):
        with app.app_context():
            photo = Photo(
                uploader_id=guest_id,
                kind=kind,
                tag=tag,
                width=width,
                height=height,
                uploaded_at=uploaded_at or now(),
                original_key="photos/x/original.jpg",
                display_key="photos/x/display.jpg",
                thumb_key="photos/x/thumb.jpg",
            )
            db.session.add(photo)
            db.session.commit()
            return photo.id

    return _add


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
