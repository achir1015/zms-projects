"""GitHub 個人首頁說明（儲存庫 <帳號>/<帳號> 的 README.md）。

GitHub 個人首頁只能顯示 Markdown（不能跑程式），所以這裡把公開專案資料（public_snapshot）
轉成一份靜態總表：依分類列出每個專案的小圖示、主題、說明、已發佈平台與下載／線上版連結，
並附上專案彙整線上版的連結，要搜尋、看明細就點過去。

build(snap, icon_base) → README 文字；圖示用 icon_files(snap) 另存成 PNG（README 不能內嵌 data: 圖片），
正式版放在 GitHub Pages 的 docs/data/icons/，個人首頁用絕對網址引用。
apply_edits(snap, edits) 把線上版管理者整理的分類（docs/data/edits.json）套到資料上。
這個檔案只用標準函式庫（畫圖示時才用 Pillow），個人首頁儲存庫的 GitHub Actions 也直接下載它來產生 README。
"""
import base64
import io
import re
from datetime import datetime
from urllib.parse import quote

ONLINE = "https://achir1015.github.io/zms-projects/app/"
SITE = "https://achir1015.github.io/zms-projects/"
ICON_BASE = SITE + "data/icons/"

# 每個專案在總表只出現一次：放在它所屬分類中「專案最少（最專門）」的那個；段落順序＝分類順序
CAT_EMOJI = {"未分類": "📦", "資料助秘": "🗂️", "小柯機器人": "🤖", "遊戲": "🎮", "眼動鼠": "👁️", "ESP32-S3": "🔌",
             "3D列印": "🖨️", "長照": "🩺"}
OTHER = "未分類"         # 沒有分類的專案（和線上版的「未分類」頁簽同名）

PLATFORMS = [("WIN", "Windows"), ("MAC", "Mac"), ("WEB", "線上版"), ("IOS", "iPhone"), ("IPAD", "iPad"),
             ("AND", "Android")]

# 沒有圖示檔的專案：Material 圖示名稱 → emoji（畫成彩色方塊小圖）
SYMBOL_EMOJI = {
    "article": "📰", "auto_awesome": "✨", "build": "🔧", "calculate": "🧮", "calendar_month": "📅",
    "description": "📄", "desktop_windows": "🖥️", "developer_board": "🔌", "emoji_emotions": "😊",
    "face": "🙂", "folder": "📁", "health_and_safety": "🛡️", "image": "🖼️", "keyboard": "⌨️",
    "lan": "🔗", "local_library": "📚", "location_on": "📍", "monitor_heart": "🩺", "movie": "🎬",
    "music_note": "🎵", "nfc": "📶", "qr_code_2": "🔳", "quiz": "❓", "record_voice_over": "🗣️",
    "request_quote": "💰", "shield": "🛡️", "slideshow": "📊", "smart_toy": "🤖", "sports_esports": "🎮",
    "timeline": "📈", "view_in_ar": "🧊", "visibility": "👁️", "web": "🌐",
}
TILE_COLORS = ["#2563EB", "#16A34A", "#D97706", "#DC2626", "#7C3AED", "#0891B2", "#DB2777", "#475569"]


def _short(text, n=70):
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"[。．.]?\s*系統開發[:：].*$", "", text)          # 署名不重複出現在每一列
    return text if len(text) <= n else text[:n - 1] + "…"


def _esc(text):
    return (text or "").replace("|", "｜").replace("<", "&lt;").replace(">", "&gt;")


def _primary_cat(p, cats, sizes):
    ids = [c for c in p.get("cats") or [] if c in cats]
    if not ids:
        return None
    return min(ids, key=lambda c: (sizes.get(c, 0), list(cats).index(c)))


def apply_edits(snap, edits):
    """線上版管理者的分類整理（edits.json）比這份資料新時，套用上去。回傳 True＝有套用。"""
    if not edits or not edits.get("at") or edits.get("at", "") <= (snap.get("generated") or ""):
        return False
    snap["categories"] = [dict(id=c["id"], name=c["name"], color=c.get("color") or "#2563EB")
                          for c in edits.get("categories") or []]
    valid = {c["id"] for c in snap["categories"]}
    cats = edits.get("cats") or {}
    for p in snap.get("projects") or []:
        if p["name"] in cats:
            p["cats"] = [c for c in cats[p["name"]] if c in valid]
        else:
            p["cats"] = [c for c in p.get("cats") or [] if c in valid]
    return True


def _released(p):
    out = [code for code, _ in PLATFORMS
           if (p.get("platforms") or {}).get(code, {}).get("status") == 4]
    if p.get("live") and "WEB" not in out:
        out.append("WEB")
    return [code for code, _ in PLATFORMS if code in out]


def _tile(name, symbol):
    """沒有圖示檔：彩色圓角方塊＋emoji（或第一個字）。"""
    from PIL import Image, ImageDraw, ImageFont
    size = 96
    color = TILE_COLORS[sum(map(ord, name)) % len(TILE_COLORS)]
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=22, fill=color)
    emoji = SYMBOL_EMOJI.get(symbol or "")
    try:
        if emoji:
            font = ImageFont.truetype("seguiemj.ttf", 54)
            d.text((size / 2, size / 2 + 2), emoji, font=font, anchor="mm", embedded_color=True)
        else:
            font = ImageFont.truetype("msjhbd.ttc", 50)
            d.text((size / 2, size / 2), (name or "?")[0].upper(), font=font, anchor="mm", fill="white")
    except OSError:                       # 沒有字型（非 Windows）：只留色塊
        pass
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _icon_file(p):
    if p.get("icon"):
        return base64.b64decode(p["icon"].split(",")[-1])
    return _tile(p["name"], p.get("symbol"))


def _links(p):
    out = []
    rel = p.get("rel") or {}
    if rel.get("tag") and rel.get("assets"):
        out.append("[⬇️ 下載 %s](%s)" % (rel["tag"], rel.get("url") or p["url"] + "/releases/latest"))
    if p.get("live"):
        out.append("[🌐 線上版](%s)" % p["live"])
    if p.get("apple"):
        out.append("[🍎 App Store](%s)" % p["apple"])
    if p.get("play"):
        out.append("[▶️ Google Play](%s)" % p["play"])
    if p.get("videos"):
        out.append("[🎬 影片](%s)" % p["videos"][0])
    return " ・ ".join(out) or "—"


def _button(text, color, scale=2):
    """自己畫的按鈕圖（不靠外部服務，GitHub 一定顯示得出來）。回傳 PNG bytes；顯示寬度＝圖寬／scale。"""
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("msjhbd.ttc", 17 * scale)
    except OSError:
        font = ImageFont.load_default()
    pad, h = 18 * scale, 40 * scale
    w = int(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=font)) + pad * 2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=10 * scale, fill=color)
    d.text((w / 2, h / 2), text, font=font, anchor="mm", fill="white")
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue(), w // scale, h // scale


BUTTONS = {"online": ("開啟線上專案總覽", "#2563EB"), "download": ("下載專案彙整 App", "#DC2626")}
BUTTON_SIZE = {"online": (172, 40), "download": (176, 40)}     # 顯示大小（icon_files 畫出來的圖會一致）


def _badge(icon_base, key, link):
    text = BUTTONS[key][0]
    w, h = BUTTON_SIZE[key]
    return '<a href="%s"><img src="%sbtn-%s.png" width="%d" height="%d" alt="%s"></a>' % (link, icon_base, key, w, h, text)


def icon_files(snap):
    """{檔名: PNG bytes}：每個專案的圖示＋兩個按鈕（需要 Pillow）。"""
    files = {}
    for p in snap.get("projects") or []:
        files["%s.png" % p["name"]] = _icon_file(p)
    for key, (text, color) in BUTTONS.items():
        png, w, h = _button(text, color)
        BUTTON_SIZE[key] = (w, h)
        files["btn-%s.png" % key] = png
    return files


def build(snap, icon_base=ICON_BASE, today=None):
    owner = snap.get("owner") or "achir1015"
    cats = {c["id"]: c["name"] for c in snap.get("categories") or []}
    ps = [p for p in snap.get("projects") or [] if not p.get("fork") and not p.get("archived")]
    sizes = {}
    for p in ps:
        for c in p.get("cats") or []:
            sizes[c] = sizes.get(c, 0) + 1
    groups = {}
    for p in ps:
        cid = _primary_cat(p, cats, sizes)
        groups.setdefault(cats[cid] if cid else OTHER, []).append(p)
    order = [n for n in cats.values() if n in groups]
    if OTHER in groups and OTHER not in order:
        order.append(OTHER)

    released = sum(1 for p in ps if _released(p))
    online = sum(1 for p in ps if "WEB" in _released(p))
    today = today or datetime.now().strftime("%Y-%m-%d")

    L = []
    L.append('<div align="center">')
    L.append("")
    L.append("# 吳玉柱的專案總覽")
    L.append("")
    L.append("小柯機器人 ・ 資料助秘 ・ 眼動鼠 ・ ESP32 AI 機器人 ・ 3D 列印 ・ 長照")
    L.append("")
    L.append("**%d** 個公開專案 ・ **%d** 個已發佈 ・ **%d** 個可直接線上使用" % (len(ps), released, online))
    L.append("")
    L.append(" ".join([
        _badge(icon_base, "online", ONLINE),
        _badge(icon_base, "download", "https://github.com/%s/zms-projects/releases/latest" % owner),
    ]))
    L.append("")
    L.append("</div>")
    L.append("")
    L.append("> 想找某個專案、看 README、播放影片，請開 **[線上專案總覽](%s)**（可搜尋、依分類與平台篩選）。" % ONLINE)
    L.append("")
    # 分類目錄
    toc = []
    for c in order:
        toc.append("[%s %s（%d）](#%s)" % (CAT_EMOJI.get(c, "📁"), c, len(groups[c]), _anchor(c)))
    L.append("**分類：** " + " ・ ".join(toc))
    L.append("")

    for i, c in enumerate(order):
        items = sorted(groups[c], key=lambda p: (not _released(p), -_ts(p.get("pushed"))))
        L.append('<a id="%s"></a>' % _anchor(c))
        L.append("")
        L.append("## %s %s（%d）" % (CAT_EMOJI.get(c, "📁"), c, len(items)))
        L.append("")
        if c == OTHER:
            L.append("<details><summary>展開 %d 個專案</summary>" % len(items))
            L.append("")
        L.append("| 專案 | 已發佈平台 | 取得 |")
        L.append("|---|---|---|")
        for p in items:
            title = p.get("title") or p["name"]
            desc = _short(p.get("description"))
            if desc and desc.startswith(title):
                desc = desc[len(title):].lstrip("：: ")
            icon = '<img src="%s%s.png" width="44" height="44" align="left" alt="">' % (icon_base, quote(p["name"]))
            cell = icon + "**[%s](%s)**" % (_esc(title), p["url"])
            if desc:
                cell += "<br><sub>%s</sub>" % _esc(desc)
            plats = " ".join("`%s`" % dict(PLATFORMS)[x] for x in _released(p)) or "—"
            L.append("| %s | %s | %s |" % (cell, plats, _links(p)))
        if c == OTHER:
            L.append("")
            L.append("</details>")
        L.append("")
    L.append("---")
    L.append("")
    L.append('<sub>這份總表由 <a href="https://github.com/%s/zms-projects">資料助秘專案彙整</a> 自動產生（%s 更新）。'
             '系統開發：吳玉柱 先生 與 Claude AI Opus 5.5</sub>' % (owner, today))
    L.append("")
    return "\n".join(L)


def _anchor(cat):
    return "cat-" + quote(cat.lower().replace(" ", "-"), safe="").replace("%", "")


def _ts(s):
    try:
        return datetime.fromisoformat((s or "")[:16]).timestamp()
    except ValueError:
        return 0
