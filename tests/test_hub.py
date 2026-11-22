import json
import os

import pytest

from zp.core import BizError, normalize_owner
from zp.github import extract_links, youtube_id

HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "Achir1015專案彙整.html")


def test_normalize_owner():
    assert normalize_owner("https://github.com/achir1015/xiaoke") == "achir1015"
    assert normalize_owner("@achir1015") == "achir1015"
    assert normalize_owner("achir1015@users.noreply.github.com") == "achir1015"
    assert normalize_owner("不合法!") == ""


def test_extract_links():
    text = ("下載 https://github.com/a/b/releases/latest 、App https://apps.apple.com/tw/app/x/id1。\n"
            "https://github.com/user-attachments/assets/5b4cd40d-3b73\n"
            "影片 https://youtu.be/abcdefghijk Play https://play.google.com/store/apps/details?id=x")
    d = extract_links(text)
    assert d["apple"] == ["https://apps.apple.com/tw/app/x/id1"]
    assert d["download"] == ["https://github.com/a/b/releases/latest"]
    assert d["video"][0].startswith("https://github.com/user-attachments/")
    assert "https://youtu.be/abcdefghijk" in d["video"]
    assert d["play"]
    assert youtube_id("https://youtu.be/abcdefghijk") == "abcdefghijk"


def _add(biz, name, **kw):
    biz.add_project(name, kw.get("title", ""), kw.get("description", ""))


def test_categories_and_auto_classify(biz):
    names = [c["name"] for c in biz.categories()]
    assert names[:3] == ["3D列印", "ESP32-S3", "長照"]
    _add(biz, "xiaoke-go", description="小柯機器人圍棋")
    _add(biz, "zms-exim", description="資料助秘之進出口貿易系統")
    _add(biz, "cargo-tool", description="cargo")              # 規則「go」很短，只比對名稱片段，不可誤判
    n = biz.auto_classify()
    assert n >= 3
    cats = {p["name"]: {c["name"] for c in p["cats"]} for p in biz.all_projects()}
    assert {"小柯機器人", "遊戲"} <= cats["xiaoke-go"]
    assert cats["zms-exim"] == {"資料助秘"}
    assert "遊戲" not in cats["cargo-tool"]
    # 分類新增、改名、排序、刪除
    cid = biz.add_category("工具")
    with pytest.raises(BizError):
        biz.add_category("工具")
    biz.save_category(cid, "小工具", "#123456", "tool")
    biz.move_category(cid, -1)
    order = [c["name"] for c in biz.categories()]
    assert order.index("小工具") == len(order) - 2
    assert biz.toggle_category("cargo-tool", cid) is True
    biz.delete_category(cid)
    assert all(c["name"] != "小工具" for c in biz.categories())


def test_note_platform_task(biz):
    _add(biz, "demo", title="示範")
    with pytest.raises(BizError):
        biz.save_note("demo", apple_url="apps.apple.com/x")
    biz.save_note("demo", apple_url="https://apps.apple.com/tw/app/x/id1", status="DEV", memo="備忘")
    p = biz.project("demo")
    assert p["apple"] and p["status"] == "DEV" and p["display"] == "示範"
    biz.set_platform("demo", "WIN", 4, "1.0.0")
    assert biz.project("demo")["platforms"]["WIN"]["status"] == 4
    tid = biz.save_task(None, "demo", "做 Mac 版", "MAC", 1, "115/12/01", "admin")
    assert biz.project("demo")["open_tasks"] == 1
    biz.toggle_task(tid)
    assert biz.tasks() == []
    assert len(biz.tasks(show_done=True)) == 1
    # 篩選
    assert [x["name"] for x in biz.list_projects(filters=["apple"])] == ["demo"]
    assert biz.list_projects(keyword="備忘")[0]["name"] == "demo"


def test_infer_platforms(biz):
    f = biz.infer_platforms([{"name": "ZMSExim-Setup-1.0.0.exe"}, {"name": "X-1.0-mac.dmg"},
                             {"name": "X-1.0-android.apk"}, {"name": "X-ios.ipa"}],
                            "https://achir1015.github.io/x/", "v1.0")
    assert set(f) == {"WIN", "MAC", "AND", "IOS", "IPAD", "WEB"}


def test_permissions(biz):
    biz.save_user("viewer", "查詢者", "查詢人員", False, True, None, "123456", True)
    from zp.biz import Biz
    v = Biz(biz.db)
    v.login("viewer", "123456")
    from zp.seed import ROLES
    v.perms = ROLES["查詢人員"]
    v.all_projects()
    with pytest.raises(BizError):
        v.save_note("x", memo="y")
    with pytest.raises(BizError):
        v.sync_github()
    assert v.company().get("github_token", "") in ("", "●●●●")


@pytest.mark.skipif(not os.path.isfile(HTML), reason="沒有舊版彙整網頁")
def test_import_html_and_backup(biz):
    r = biz.import_html(HTML)
    assert r["total"] > 50 and r["new"] == r["total"]
    p = biz.project("xiaoke-checkers")
    assert p["readme"] and "跳棋" in p["readme"]
    biz.auto_classify()
    data = biz.export_backup()
    s = json.dumps(data, ensure_ascii=False)
    assert "小柯機器人" in s
    # 舊網頁匯出備份格式
    old = {"app": "Achir1015專案彙整", "version": 1,
           "categories": {"categories": [{"id": "c1", "name": "新分類", "color": "#112233"}],
                          "assignments": {"xiaoke-checkers": ["c1"]}},
           "notes": {"xiaoke-checkers": {"playUrl": "https://play.google.com/store/apps/details?id=a", "memo": "m"}}}
    st = biz.import_backup(old)
    assert st["categories"] == 1 and st["assigned"] == 1 and st["notes"] == 1
    p = biz.project("xiaoke-checkers")
    assert "新分類" in [c["name"] for c in p["cats"]]
    assert p["play"].startswith("https://play.google.com")
    d = biz.dashboard()
    assert d["total"] == r["total"]
    assert biz.stats()["total"] == r["total"]


def test_readme_heading():
    from zp.hub import readme_heading, short_title
    assert readme_heading("# A13input A13輸入資料\n內容") == "A13input A13輸入資料"
    assert readme_heading('<p>x</p>\n<h1 align="center">小柯 <b>機器人</b></h1>') == "小柯 機器人"
    assert readme_heading("## [眼動鼠](https://x)  \n") == "眼動鼠"
    assert short_title({"name": "a13", "heading": "A13input A13輸入資料"}) == "A13input A13輸入資料"
    assert short_title({"name": "a13", "title": "手動", "heading": "H"}) == "手動"


def test_video_media():
    text = ('<video src="https://github.com/user-attachments/assets/abc-123" controls></video>\n'
            "示範 https://example.com/files/REC_20261112_63.mp4\n"
            "https://github.com/user-attachments/assets/5b4cd40d-3b73\n"
            '<img src="https://github.com/user-attachments/assets/img-1" />')
    v = extract_links(text)["video"]
    assert "https://github.com/user-attachments/assets/abc-123" in v
    assert "https://example.com/files/REC_20261112_63.mp4" in v
    assert "https://github.com/user-attachments/assets/5b4cd40d-3b73" in v
    assert "https://github.com/user-attachments/assets/img-1" not in v
