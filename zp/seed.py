"""第一次使用的預設資料：權限功能與角色、預設分類（含自動分類規則）、平台與狀態代碼。"""

# 權限功能：(代號, 名稱, 說明)；等級 0 無、1 查詢、2 維護
FUNCS = [
    ("PRJ", "專案資料", "專案總覽、README、下載版本；等級 2 可修改便利貼（App Store、Play、影片、備忘）"),
    ("PLT", "平台進度", "六個平台（Windows、Mac、線上版、iPhone、iPad、Android）的開發與發佈進度"),
    ("TASK", "待辦事項", "各專案的待辦、負責人與預定完成日"),
    ("CAT", "分類管理", "新增、改名、換顏色、調整頁簽順序、自動分類規則；把專案放進分類"),
    ("SYNC", "彙整 GitHub", "從 GitHub 抓專案清單、README、最新發佈版本；匯入舊版彙整網頁與備份"),
    ("RPT", "統計報表", "分類、語言、平台發佈統計與匯出"),
    ("SYS", "系統管理", "使用者與權限、GitHub 帳號與 Token、備份還原、版本更新、操作紀錄"),
]
FUNC_NAMES = {f[0]: f[1] for f in FUNCS}
LEVEL_NAMES = {0: "無", 1: "查詢", 2: "維護"}


def _r(**kw):
    return {f[0]: kw.get(f[0], 0) for f in FUNCS}


ROLES = {
    "系統管理員": {f[0]: 2 for f in FUNCS},
    "專案主管": _r(PRJ=2, PLT=2, TASK=2, CAT=2, SYNC=2, RPT=2),
    "開發人員": _r(PRJ=2, PLT=2, TASK=2, CAT=1, SYNC=2, RPT=1),
    "測試人員": _r(PRJ=1, PLT=2, TASK=2, CAT=1, RPT=1),
    "查詢人員": _r(PRJ=1, PLT=1, TASK=1, CAT=1, RPT=1),
}

# 平台：(代號, 名稱, 圖示名稱, 色調)
PLATFORMS = [
    ("WIN", "Windows", "DESKTOP_WINDOWS", "blue"),
    ("MAC", "Mac", "LAPTOP_MAC", "slate"),
    ("WEB", "線上版", "LANGUAGE", "teal"),
    ("IOS", "iPhone", "PHONE_IPHONE", "violet"),
    ("IPAD", "iPad", "TABLET_MAC", "pink"),
    ("AND", "Android", "ANDROID", "green"),
]
PLATFORM_NAMES = {p[0]: p[1] for p in PLATFORMS}

# 平台狀態：代碼 → (名稱, 色調)
PLT_STATUS = {0: ("未定", "slate"), 1: ("規劃中", "sky"), 2: ("開發中", "amber"), 3: ("測試中", "violet"),
              4: ("已發佈", "green"), 9: ("不適用", "slate")}

# 專案狀態
PRJ_STATUS = {"": ("未設定", "slate"), "PLAN": ("規劃中", "sky"), "DEV": ("開發中", "amber"),
              "LIVE": ("已上線", "green"), "HOLD": ("暫停", "rose"), "END": ("結束", "slate")}

PRIORITY = {1: ("高", "rose"), 2: ("中", "amber"), 3: ("低", "slate")}

PALETTE = ["#2563EB", "#16A34A", "#D97706", "#DC2626", "#7C3AED", "#0891B2", "#DB2777", "#4B5563"]

# 預設分類（與原本「Achir1015專案彙整」網頁相同）：(名稱, 顏色, 自動分類規則)
CATEGORIES = [
    ("3D列印", "#2563EB", "3d列印,bambu,tray,screw,托盤,螺絲,floorplan"),
    ("ESP32-S3", "#16A34A", "esp32,esp-,sparkbot,box3,lx04"),
    ("長照", "#D97706", "caregiver,care-,照服,居家服務,ward,長照"),
    ("資料助秘", "#DC2626", "zms-,資料助秘"),
    ("遊戲", "#7C3AED", "game,racing,racer,chess,checkers,go,mahjong,bridge,junqi,sanjun,freecell,sanguo,遊戲,棋"),
    ("眼動鼠", "#0891B2", "eyemouse,eye-,眼動"),
    ("小柯機器人", "#DB2777", "xiaoke,小柯"),
    ("其他", "#4B5563", ""),
]


def seed_all(db, first=False):
    """每次開啟都會補上缺的參考資料（INSERT IGNORE，不覆蓋使用者修改過的內容）。"""
    db.exec("INSERT IGNORE INTO sys_company (id, name) VALUES (1, '')")
    if first and not db.value("SELECT COUNT(*) FROM prj_category"):
        db.exec_many("INSERT IGNORE INTO prj_category (name, color, sort, rule) VALUES (%s, %s, %s, %s)",
                     [(n, c, i + 1, r) for i, (n, c, r) in enumerate(CATEGORIES)])
