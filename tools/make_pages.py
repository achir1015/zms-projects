"""產生 GitHub Pages 線上版需要的檔案。

  docs/lessons.json、docs/voice/*.mp3、docs/icon.png  ← 語音動態教學（與程式內相同）
  docs/data/projects.json、docs/data/readmes.json     ← 線上專案總覽的資料（只含公開專案，加 --data 才產生）
  docs/data/icons/*.png                              ← 個人首頁總表用的專案圖示（加 --data 才產生）

用法：
  python tools/make_pages.py                 只更新教學與圖示
  python tools/make_pages.py --data          另外從資料庫匯出公開專案（預設用開發資料庫 data/）
  python tools/make_pages.py --data --installed   改用這台電腦已安裝版的資料庫（%LOCALAPPDATA%\\ZMSProjects）

程式內「彙整 GitHub → 發佈線上版」做的是同一件事（直接 commit 到 GitHub），不需要這支工具。
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
DOCS = os.path.join(HERE, "docs")


def lessons():
    from zp import APP_NAME, APP_VERSION, GITHUB_REPO
    from zp.help_text import LESSONS
    os.makedirs(os.path.join(DOCS, "voice"), exist_ok=True)
    out = []
    for g in LESSONS:
        mp3 = os.path.join(HERE, "assets", "voice", g["key"] + ".mp3")
        has = os.path.isfile(mp3)
        if has:
            shutil.copy2(mp3, os.path.join(DOCS, "voice", g["key"] + ".mp3"))
        out.append(dict(key=g["key"], title=g["title"], voice=g["voice"],
                        audio=("voice/%s.mp3" % g["key"]) if has else "",
                        steps=[dict(icon=s[0].lower(), tone=s[1], text=s[2]) for s in g["steps"]]))
    shutil.copy2(os.path.join(HERE, "assets", "icon.png"), os.path.join(DOCS, "icon.png"))
    with open(os.path.join(DOCS, "lessons.json"), "w", encoding="utf-8") as f:
        json.dump(dict(app=APP_NAME, version=APP_VERSION, repo=GITHUB_REPO, lessons=out), f,
                  ensure_ascii=False, indent=1)
    print("lessons:", len(out))


def data(installed=False):
    if installed:
        os.environ["ZP_DATA_DIR"] = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ZMSProjects")
    from zp.biz import Biz
    from zp.database import DB
    from zp.dbserver import LocalDatabaseServer
    from zp.settings import Settings
    st = Settings.load()
    srv = None
    if installed:
        # 安裝版：只連「已經在執行」的資料庫（用安裝版的密碼找埠），絕不另外啟動，免得兩個程式搶同一個資料夾
        import pymysql
        for port in [st.port] + list(range(3438, 3460)):
            try:
                pymysql.connect(host="127.0.0.1", port=port, user=st.user, password=st.password,
                                connect_timeout=2).close()
                st.port = port
                break
            except Exception:
                continue
        else:
            raise SystemExit("找不到執行中的安裝版資料庫：請先打開「資料助秘專案彙整」")
    else:
        srv = LocalDatabaseServer(st)
        srv.start()                   # 開發資料庫：已經在執行就直接連
    db = DB(st)
    try:
        b = Biz(db)
        b.user, b.perms = dict(uid="pages", name="線上版", is_admin=1, role=""), {}
        snap, readmes = b.public_snapshot()
    finally:
        db.close()
        if srv:
            srv.stop()                # 只會停掉這支工具自己開的資料庫
    d = os.path.join(DOCS, "data")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "projects.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(d, "readmes.json"), "w", encoding="utf-8") as f:
        json.dump(readmes, f, ensure_ascii=False, separators=(",", ":"))
    from zp.profile import icon_files                # 個人首頁總表用的專案圖示（docs/data/icons/）
    os.makedirs(os.path.join(d, "icons"), exist_ok=True)
    for name, png in icon_files(snap).items():
        with open(os.path.join(d, "icons", name), "wb") as f:
            f.write(png)
    print("projects:", len(snap["projects"]), "readmes:", len(readmes),
          "size: %d KB / %d KB" % (os.path.getsize(os.path.join(d, "projects.json")) // 1024,
                                   os.path.getsize(os.path.join(d, "readmes.json")) // 1024))


if __name__ == "__main__":
    lessons()
    if "--data" in sys.argv:
        data(installed="--installed" in sys.argv)
