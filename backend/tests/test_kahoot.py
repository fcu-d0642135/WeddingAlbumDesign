import pytest

from tests.conftest import auth

URL = "https://kahoot.it/?pin=1234567"


@pytest.fixture
def admin(client, join):
    token, _ = join("婷婷")
    client.post("/api/me/admin", headers=auth(token), json={"adminCode": "admin"})
    return token


def _config(client):
    return client.get("/api/config").get_json()


def _put(client, token, **body):
    return client.put("/api/settings/kahoot", headers=auth(token), json=body)


def test_no_link_by_default(client, admin):
    assert _config(client)["kahootUrl"] is None
    assert client.get("/api/settings/kahoot", headers=auth(admin)).get_json() == {
        "url": None,
        "enabled": False,
    }


def test_link_saved_early_stays_hidden_until_enabled(client, admin):
    res = _put(client, admin, url=f"  {URL} ")

    assert res.status_code == 200
    assert res.get_json() == {"url": URL, "enabled": False}
    # 提早存好的連結，賓客還拿不到
    assert _config(client)["kahootUrl"] is None
    # 管理員自己看得到存了什麼
    assert client.get("/api/settings/kahoot", headers=auth(admin)).get_json() == {
        "url": URL,
        "enabled": False,
    }


def test_enable_shows_link_to_everyone_without_login(client, admin):
    _put(client, admin, url=URL)

    res = _put(client, admin, url=URL, enabled=True)

    assert res.get_json() == {"url": URL, "enabled": True}
    # 歡迎頁還沒加入也看得到
    assert _config(client)["kahootUrl"] == URL


def test_disable_hides_link_but_keeps_it(client, admin):
    _put(client, admin, url=URL, enabled=True)

    res = _put(client, admin, url=URL, enabled=False)

    assert res.get_json() == {"url": URL, "enabled": False}
    assert _config(client)["kahootUrl"] is None


def test_change_link_while_enabled(client, admin):
    _put(client, admin, url=URL, enabled=True)
    _put(client, admin, url="https://kahoot.it/?pin=7654321", enabled=True)

    assert _config(client)["kahootUrl"] == "https://kahoot.it/?pin=7654321"


@pytest.mark.parametrize("empty", ["", "   ", None])
def test_clear_link_also_turns_off(client, admin, empty):
    _put(client, admin, url=URL, enabled=True)

    res = _put(client, admin, url=empty)

    assert res.get_json() == {"url": None, "enabled": False}
    assert _config(client)["kahootUrl"] is None


def test_cannot_enable_without_link(client, admin):
    res = _put(client, admin, url="", enabled=True)

    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "url_required"


def test_enabled_must_be_bool(client, admin):
    res = _put(client, admin, url=URL, enabled="yes")

    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_body"


@pytest.mark.parametrize("bad", ["kahoot.it/123", "javascript:alert(1)", "https://" + "a" * 600])
def test_rejects_non_links(client, admin, bad):
    res = _put(client, admin, url=bad, enabled=True)

    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_url"
    assert _config(client)["kahootUrl"] is None


def test_only_admin(client, join):
    token, _ = join("阿凱")

    for res in (
        _put(client, token, url=URL),
        client.get("/api/settings/kahoot", headers=auth(token)),
    ):
        assert res.status_code == 403
        assert res.get_json()["error"]["code"] == "not_admin"


def test_requires_token(client):
    assert client.put("/api/settings/kahoot", json={"url": URL}).status_code == 401
    assert client.get("/api/settings/kahoot").status_code == 401
