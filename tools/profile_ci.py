"""個人首頁儲存庫（achir1015/achir1015）的 GitHub Actions 用：產生 README.md。

讀 zms-projects 的 docs/data/projects.json，再套用線上版管理者整理的 docs/data/edits.json，
用 zp/profile.py 產生總表（圖示用 GitHub Pages 上的 docs/data/icons/）。只用標準函式庫。

用法：python profile_ci.py <zms-projects 目錄> <輸出 README.md>
"""
import importlib.util
import json
import os
import sys


def main(src, out):
    spec = importlib.util.spec_from_file_location("profile", os.path.join(src, "zp", "profile.py"))
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    data = os.path.join(src, "docs", "data")
    with open(os.path.join(data, "projects.json"), encoding="utf-8") as f:
        snap = json.load(f)
    edits = None
    if os.path.isfile(os.path.join(data, "edits.json")):
        with open(os.path.join(data, "edits.json"), encoding="utf-8") as f:
            edits = json.load(f)
    profile.apply_edits(snap, edits)
    md = profile.build(snap)
    old = open(out, encoding="utf-8").read() if os.path.isfile(out) else ""
    # 只有日期不同時不要重寫（免得每天多一個沒意義的 commit）
    strip = lambda t: "\n".join(l for l in t.splitlines() if "自動產生" not in l)
    if strip(old) == strip(md):
        print("README 沒有變化")
        return
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print("README 已更新：%d 字" % len(md))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
