"""資料助秘專案彙整 — 程式進入點。

桌面版：python main.py
網頁預覽（測試用）：python run_web.py（http://127.0.0.1:8620）。
"""
import os
import sys

import flet as ft  # noqa: E402

from zp.settings import resource_dir  # noqa: E402
from zp.ui.shell import main  # noqa: E402

if __name__ == "__main__":
    if getattr(sys, "frozen", False) and os.name == "nt":
        # 讓工作列顯示本程式的圖示（而不是 Python／Flet 的）
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ZMS.Projects")
        except Exception:
            pass
    assets = os.path.join(resource_dir(), "assets")
    port = os.environ.get("ZP_WEB_PORT")
    if port:
        ft.run(main, view=None, port=int(port), host="127.0.0.1", assets_dir=assets)
    else:
        ft.run(main, assets_dir=assets)
