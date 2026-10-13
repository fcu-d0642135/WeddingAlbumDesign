from datetime import timedelta

import pytest

from app.models import now
from tests.conftest import auth


@pytest.fixture
def me(join):
    """目前這位賓客的 (token, guest)。"""
    return join("小慧")


def _list(client, token, **params):
    res = client.get("/api/photos", headers=auth(token), query_string=params)
    assert res.status_code == 200, res.get_json()
    return res.get_json()


def _ids(body):
    return [p["id"] for p in body["items"]]


# --- 列表 -----------------------------------------------------------------


def test_list_requires_token(client):
    assert client.get("/api/photos").status_code == 401


def test_empty_album(client, me):
    assert _list(client, me[0]) == {"items": [], "nextCursor": None}


def test_newest_first(client, me, add_photo):
    token, guest = me
    old = add_photo(guest["id"], uploaded_at=now() - timedelta(hours=1))
    new = add_photo(guest["id"])

    assert _ids(_list(client, token)) == [new, old]


def test_photo_shape(client, me, add_photo):
    token, guest = me
    add_photo(guest["id"], tag="engagement", width=3024, height=4032)

    photo = _list(client, token)["items"][0]

    assert photo["kind"] == "photo"
    assert photo["tag"] == "engagement"
    assert photo["width"] == 3024 and photo["height"] == 4032
    assert photo["uploader"] == guest
    # 網址由後端組好，前端直接使用
    assert photo["url"] == "/media/photos/x/original.jpg"
    assert photo["thumbnailUrl"] == "/media/photos/x/thumb.jpg"
    # 時間一律帶台灣時區
    assert photo["uploadedAt"].endswith("+08:00")


def test_media_base_url_can_point_elsewhere(app, client, me, add_photo):
    # 換成雲端儲存時，只要改設定，前端拿到的就是新網址
    app.config["MEDIA_BASE_URL"] = "https://cdn.example.com/"
    token, guest = me
    add_photo(guest["id"])

    assert _list(client, token)["items"][0]["url"] == "https://cdn.example.com/photos/x/original.jpg"


# --- 分頁 -----------------------------------------------------------------


def test_pagination_walks_every_photo_once(client, me, add_photo):
    token, guest = me
    base = now() - timedelta(hours=1)
    # 有幾張故意放在同一秒，確認不會漏掉或重複
    created = [
        add_photo(guest["id"], uploaded_at=base + timedelta(seconds=i // 2)) for i in range(7)
    ]

    seen = []
    cursor = None
    while True:
        params = {"limit": 3, **({"cursor": cursor} if cursor else {})}
        body = _list(client, token, **params)
        seen += _ids(body)
        cursor = body["nextCursor"]
        if cursor is None:
            break

    assert sorted(seen) == sorted(created)
    assert len(seen) == len(set(seen))


def test_new_uploads_do_not_shift_next_page(client, me, add_photo):
    # 婚禮當下一直有人上傳，第二頁不能因為前面多了新照片就重複出現舊照片
    token, guest = me
    base = now() - timedelta(hours=1)
    for i in range(4):
        add_photo(guest["id"], uploaded_at=base + timedelta(minutes=i))

    first = _list(client, token, limit=2)
    add_photo(guest["id"])  # 看第一頁的時候，有人傳了新照片
    second = _list(client, token, limit=2, cursor=first["nextCursor"])

    assert not set(_ids(first)) & set(_ids(second))


def test_invalid_cursor_is_400(client, me):
    res = client.get("/api/photos", headers=auth(me[0]), query_string={"cursor": "garbage!"})
    assert res.status_code == 400


def test_limit_is_capped(client, me, add_photo):
    token, guest = me
    for _ in range(3):
        add_photo(guest["id"])

    assert len(_list(client, token, limit=0)["items"]) == 1
    assert len(_list(client, token, limit=1000)["items"]) == 3


# --- 篩選 -----------------------------------------------------------------


def test_filter_by_tag(client, me, add_photo):
    token, guest = me
    engagement = add_photo(guest["id"], tag="engagement")
    add_photo(guest["id"], tag="banquet")

    assert _ids(_list(client, token, tag="engagement")) == [engagement]


def test_invalid_tag_is_400(client, me):
    res = client.get("/api/photos", headers=auth(me[0]), query_string={"tag": "party"})
    assert res.get_json()["error"]["code"] == "invalid_tag"


def test_filter_by_uploader(client, join, add_photo):
    token, me = join("小慧")
    _, other = join("阿凱")
    mine = add_photo(me["id"])
    theirs = add_photo(other["id"])

    assert _ids(_list(client, token, uploader="me")) == [mine]
    assert _ids(_list(client, token, uploader=other["id"])) == [theirs]


def test_filter_today(client, me, add_photo):
    token, guest = me
    today = add_photo(guest["id"])
    add_photo(guest["id"], uploaded_at=now() - timedelta(days=2))

    assert _ids(_list(client, token, date="today")) == [today]


def test_today_means_taiwan_date(client, me, add_photo):
    # 「今天」以台灣時間的午夜為界。UTC 與台灣差 8 小時，凌晨時段最容易算錯
    from datetime import UTC, datetime, time

    from app.models import TAIPEI

    token, guest = me
    midnight = datetime.combine(datetime.now(TAIPEI).date(), time.min, tzinfo=TAIPEI)
    midnight_utc = midnight.astimezone(UTC).replace(tzinfo=None)
    just_after = add_photo(guest["id"], uploaded_at=midnight_utc + timedelta(minutes=1))
    add_photo(guest["id"], uploaded_at=midnight_utc - timedelta(minutes=1))

    assert _ids(_list(client, token, date="today")) == [just_after]


def test_filter_by_kind(client, me, add_photo):
    token, guest = me
    photo = add_photo(guest["id"])
    video = add_photo(guest["id"], kind="video")

    assert _ids(_list(client, token, kind="video")) == [video]
    assert _ids(_list(client, token, kind="photo")) == [photo]


# --- 單張 -----------------------------------------------------------------


def test_get_single_photo(client, me, add_photo):
    token, guest = me
    photo_id = add_photo(guest["id"])

    res = client.get(f"/api/photos/{photo_id}", headers=auth(token))

    assert res.status_code == 200
    assert res.get_json()["id"] == photo_id


def test_missing_photo_is_404(client, me):
    res = client.get("/api/photos/p_nope", headers=auth(me[0]))

    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "photo_not_found"


# --- 統計 -----------------------------------------------------------------


def test_stats(client, join, add_photo):
    token, me = join("小慧")
    join("阿凱")
    add_photo(me["id"])
    add_photo(me["id"])

    res = client.get("/api/stats", headers=auth(token))

    assert res.get_json() == {
        "photoCount": 2,
        "guestCount": 2,
        "blessingCount": 0,
        "blessingGuestCount": 0,
    }


# --- 照片檔 ---------------------------------------------------------------


def test_media_files_are_served(app, client):
    from app import storage

    with app.app_context():
        storage.save("photos/p_1/thumb.jpg", b"fake-jpeg")

    res = client.get("/media/photos/p_1/thumb.jpg")

    assert res.status_code == 200
    assert res.data == b"fake-jpeg"


def test_media_cannot_escape_folder(client):
    assert client.get("/media/../wedding.db").status_code == 404
