"""開發用：以網頁模式預覽手機 App（http://127.0.0.1:8621）。
先在電腦端開手機連線服務（埠 8805）；ZP_TABLET=1 預覽 iPad 版面。"""
import os
import runpy
import sys

os.environ.setdefault("ZP_WEB_PORT", "8621")
os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")
os.environ.setdefault("ZP_MOBILE", "1")
os.environ.setdefault("ZP_DEV_SERVER", "http://127.0.0.1:8805")
os.environ.setdefault("ZP_DEV_LOGIN", "admin:admin123")
here = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("ZP_DATA_DIR", os.path.join(here, "data_mobile"))
os.chdir(here)
sys.path.insert(0, here)
runpy.run_path(os.path.join(here, "main.py"), run_name="__main__")
