"""開發用：在開發資料庫（data/）建立 admin/admin123，並匯入上一層資料夾的舊版專案彙整網頁。"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from zp.biz import Biz  # noqa: E402
from zp.database import DB  # noqa: E402
from zp.dbserver import LocalDatabaseServer  # noqa: E402
from zp.settings import Settings  # noqa: E402

st = Settings.load()
srv = LocalDatabaseServer(st)
srv.start()
try:
    db = DB(st)
    db.prepare()
    st.save()
    b = Biz(db)
    if not b.has_users():
        b.create_first_admin("admin", "系統管理員", "admin123")
    b.login("admin", "admin123")
    b.save_company(name="吳玉柱工作室", github_owner="achir1015")
    html = os.path.join(os.path.dirname(HERE), "Achir1015專案彙整.html")
    if os.path.isfile(html):
        print(b.import_html(html))
        print("自動分類", b.auto_classify())
finally:
    db.close()
    srv.stop()
