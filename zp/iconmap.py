"""儲存庫裡沒有圖示檔的專案：依名稱、主題與說明挑一個代表的圖示（Material Symbols 名稱，電腦版、手機、線上版共用）。

規則由上往下比對，第一個符合的就用；都不符合回傳 ""（畫面改用主題第一個字的色塊）。
"""
import re

RULES = [
    (r"esp32|arduino|sparkbot|box3|lafvin|開發板", "developer_board"),
    (r"nfc", "nfc"),
    (r"suno|song|歌曲|音樂", "music_note"),
    (r"tts|語音|voice|speech|transcript|srt|字幕", "record_voice_over"),
    (r"mp3|audio", "music_note"),
    (r"video|影片|youtube|youtubo|yt-|錄影|剪輯|cut", "movie"),
    (r"facefusion|face", "face"),
    (r"quiz|測驗|考試|subject-test|練習|術科", "quiz"),
    (r"game|遊戲|guess|猜", "sports_esports"),
    (r"排班|shift|schedule|calendar|calender|月曆|行事曆|monthly", "calendar_month"),
    (r"勞保|勞退|insurance|retirement|計算|calculat|combined", "calculate"),
    (r"prompt|nano-banana|skill", "auto_awesome"),
    (r"長照|照護|照服|care", "health_and_safety"),
    (r"qr", "qr_code_2"),
    (r"pptx|ppt|簡報|slide", "slideshow"),
    (r"pdf|文件|file|converter|轉檔", "description"),
    (r"glb|3d|viewer", "view_in_ar"),
    (r"image|圖片|圖像|splitter|photo", "image"),
    (r"scam|詐騙|guard", "shield"),
    (r"repair|quote|報價", "request_quote"),
    (r"address|地址|gps|arrival|map", "location_on"),
    (r"windows|wsa|wpf|xreal|magisk", "desktop_windows"),
    (r"error|ngrok|flask|修復", "build"),
    (r"input|輸入", "keyboard"),
    (r"客服|chat|gpt|assistant|(^|[^a-z])ai([^a-z]|$)", "smart_toy"),
    (r"network|scan|網路", "lan"),
    (r"library|書", "local_library"),
    (r"markdown|world|article", "article"),
    (r"monitor|bot-", "monitor_heart"),
    (r"timeline|project|專案", "timeline"),
    (r"emoji", "emoji_emotions"),
    (r"optikey|眼動|eye", "visibility"),
    (r"resources|資源", "folder"),
    (r"web|html|網頁", "web"),
]
_COMPILED = [(re.compile(p, re.I), s) for p, s in RULES]


def symbol_for(name, title="", description="", topics=""):
    hay = " ".join([name or "", title or "", description or "", topics or ""])
    for rx, sym in _COMPILED:
        if rx.search(hay):
            return sym
    return ""
