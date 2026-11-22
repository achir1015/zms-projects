# 資料助秘專案彙整

把 GitHub 上的所有專案集中管理：專案主題（README 大標題）、說明、最新發佈版本與下載檔、App Store／Play／影片／線上版連結、
自訂分類頁簽、六個平台（Windows、Mac、線上版、iPhone、iPad、Android）的開發進度與待辦事項。

**系統開發：吳玉柱 先生 與 Claude AI Opus 5.5**

## 功能

| 功能 | 說明 |
|---|---|
| 彙整 GitHub | 一鍵抓專案清單、README、最新 Release；用 ETag 快取，次數用完時改從發佈頁查詢（不扣次數） |
| 專案總覽 | 卡片顯示 README 大標題當主題；搜尋、排序、連結篩選、分類頁簽；明細有總覽、README、下載版本、平台進度、便利貼、待辦 |
| 播放媒體 | README 裡的 mp4／GitHub 上傳影片／`<video>` 自動列成「播放」按鈕 |
| 分類管理 | 新增、改名、顏色、順序，自動分類規則 |
| 平台進度總表 | 六平台狀態（未定、規劃中、開發中、測試中、已發佈、不適用），依發佈檔自動標示已發佈 |
| 待辦事項 | 專案、平台、優先、預定日、負責人 |
| 匯入匯出 | 匯入舊版「專案彙整」網頁快照與備份 JSON；匯出備份 |
| 發佈線上版 | 公開專案送到 GitHub Pages（私人專案、便利貼備註、待辦不會送出） |
| 使用者權限 | 七項功能 × 無／查詢／維護，角色範本；操作紀錄含異動前後 |
| 其他 | 內建 MariaDB（埠 3438，自動啟停）、備份還原、程式內更新、桌面捷徑、語音動態教學 |

## 平台

| 平台 | 狀態 |
|---|---|
| Windows 11、macOS | 安裝檔在 [Releases](https://github.com/achir1015/zms-projects/releases/latest)（macOS 已公證） |
| 線上版（公開） | https://achir1015.github.io/zms-projects/app/ — 不用安裝，瀏覽器看所有公開專案；資料由桌面版「發佈線上版」更新 |
| 線上版（公司內） | 桌面版「版本更新與捷徑」打開「公司內的線上版」，同一個網路的電腦、平板用瀏覽器登入，資料與權限和桌面版相同 |
| iPhone／iPad、Android | 陸續推出 |

## 開發

```powershell
.venv\Scripts\python -m pytest -q tests        # 測試（測試資料庫埠 3448）
.venv\Scripts\python run_web.py                # 網頁預覽 http://127.0.0.1:8620
.venv\Scripts\python tools\build_windows.py    # 建 Windows 安裝檔 → dist-installer\
.venv\Scripts\python tools\make_pages.py --data  # 更新 docs/（Pages 線上版的教學與資料）
```

資料表說明見 [docs/資料表欄位明細.md](docs/資料表欄位明細.md)。
