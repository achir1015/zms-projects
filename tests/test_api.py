"""手機 App 連線服務：真的開 HTTP 服務，用手機端的 RemoteBiz 連線測試。"""
import datetime as dt

import pytest

from zp import wire
from zp.api import ApiServer
from zp.core import BizError
from zp.remote import Client, RemoteBiz, normalize


def test_wire_roundtrip():
    obj = {"t": dt.datetime(2026, 11, 22, 9, 30), "d": dt.date(2026, 1, 2), "m": {1: "a", 4: {"x": 2}}, "s": {"k": 1}}
    back = wire.loads(wire.dumps(obj))
    assert back == obj


def test_normalize():
    assert normalize("192.168.6.172") == "http://192.168.6.172:8805"
    assert normalize("http://10.0.0.2:9000/") == "http://10.0.0.2:9000"


@pytest.fixture()
def api(biz):
    srv = ApiServer(biz.db, port=8899, host="127.0.0.1")
    srv.start()
    yield srv
    srv.stop()


def test_api_end_to_end(biz, api):
    biz.add_project("demo", "示範專案", "示範說明")
    biz.set_platform("demo", "WIN", 4, "1.0.0")
    biz.save_company(github_token="ghp_secret_value")
    c = Client("http://127.0.0.1:8899")
    assert c.ping()["app"] == "資料助秘專案彙整"
    rb = RemoteBiz(c)
    with pytest.raises(BizError):
        rb.login("admin", "wrong")
    rb.login("admin", "admin123")
    assert rb.can("SYS", 2) and rb.uid == "admin"
    ps = rb.all_projects()
    assert ps[0]["display"] == "示範專案" and ps[0]["platforms"]["WIN"]["status"] == 4
    # 手機端直接計算
    assert [p["name"] for p in rb.list_projects(keyword="示範", projects=ps)] == ["demo"]
    assert rb.tab_counts(ps)["all"] == 1
    # 數字鍵字典（平台狀態統計）要原樣還原
    st = rb.stats()
    assert 4 in st["platforms"][0]
    # 寫入
    rb.save_note("demo", memo="手機寫的")
    assert biz.project("demo")["note"]["memo"] == "手機寫的"
    # Token 不能傳到手機
    assert "ghp_secret" not in str(rb.settings_row())
    with pytest.raises(BizError):
        rb.github_token()                  # 不在白名單
    # 停用帳號後立即失效
    biz.save_user("u1", "同仁", "查詢人員", False, True, {"PRJ": 1}, pw="pass1234", is_new=True)
    r2 = RemoteBiz(c)
    r2._c = Client("http://127.0.0.1:8899")
    r2.login("u1", "pass1234")
    with pytest.raises(BizError):
        r2.save_note("demo", memo="沒有權限")
    biz.db.exec("UPDATE sys_user SET active=0 WHERE uid='u1'")
    with pytest.raises(BizError):
        r2.all_projects()
    rb.logout()
