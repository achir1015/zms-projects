"""產生 GitHub 個人首頁說明草稿（<帳號>/<帳號> 儲存庫的 README.md＋icons/）。

用法：
  python tools/make_profile.py                  從開發資料庫（data/）匯出公開專案
  python tools/make_profile.py --snap 檔案.json  改用已匯出的 public_snapshot
  加 --preview：另外產生 preview.html（用 GitHub 的 Markdown 轉換，外觀與個人首頁相同）

輸出在 build-profile/（不進 git）。正式的首頁由個人首頁儲存庫的 GitHub Actions（tools/profile_ci.py）產生，
圖示放在 GitHub Pages；這支工具是本機預覽用，圖示放 build-profile/icons/。
"""
import json
import os
import shutil
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "build-profile")


def snapshot():
    if "--snap" in sys.argv:
        with open(sys.argv[sys.argv.index("--snap") + 1], encoding="utf-8") as f:
            return json.load(f)
    from zp.biz import Biz
    from zp.database import DB
    from zp.dbserver import LocalDatabaseServer
    from zp.settings import Settings
    st = Settings.load()
    srv = LocalDatabaseServer(st)
    srv.start()
    db = DB(st)
    try:
        b = Biz(db)
        b.user, b.perms = dict(uid="profile", name="個人首頁", is_admin=1, role=""), {}
        return b.public_snapshot()[0]
    finally:
        db.close()
        srv.stop()


def preview(md):
    token = os.environ.get("GH_TOKEN", "")
    req = urllib.request.Request("https://api.github.com/markdown", method="POST",
                                 data=json.dumps({"text": md, "mode": "markdown"}).encode("utf-8"),
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "zp-profile",
                                          **({"Authorization": "Bearer " + token} if token else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode("utf-8")
    html = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>個人首頁預覽</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown-light.min.css">
<style>body{background:#f6f8fa;margin:0;font-family:-apple-system,"Microsoft JhengHei",sans-serif}
.frame{max-width:900px;margin:24px auto;background:#fff;border:1px solid #d0d7de;border-radius:6px;padding:24px 32px}
.hint{max-width:900px;margin:16px auto 0;color:#57606a;font-size:13px}</style></head><body>
<div class="hint">預覽：個人首頁 Overview 上方會顯示這一塊（下面才是 Popular repositories）。</div>
<div class="frame"><div class="markdown-body">%s</div></div></body></html>""" % body
    with open(os.path.join(OUT, "preview.html"), "w", encoding="utf-8") as f:
        f.write(html)


def main():
    from zp import profile
    snap = snapshot()
    if "--edits" in sys.argv:
        with open(sys.argv[sys.argv.index("--edits") + 1], encoding="utf-8") as f:
            profile.apply_edits(snap, json.load(f))
    files = profile.icon_files(snap)
    md = profile.build(snap, icon_base="icons/")
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(os.path.join(OUT, "icons"))
    for name, data in files.items():
        with open(os.path.join(OUT, "icons", name), "wb") as f:
            f.write(data)
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print("README.md %d KB、圖示 %d 個" % (len(md.encode("utf-8")) // 1024, len(files)))
    if "--preview" in sys.argv:
        preview(md)
        print("preview.html")


if __name__ == "__main__":
    main()
