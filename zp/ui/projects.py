"""專案總覽：搜尋、排序、連結篩選、分類頁簽、專案卡片；右側明細（總覽、README、下載版本、平台進度、便利貼、待辦）。"""
import flet as ft

from .. import rocdate
from ..seed import PLATFORMS, PLT_STATUS, PRIORITY, PRJ_STATUS
from . import theme as T

I = ft.Icons
LINKS = [("apple", "Apple", I.APPLE, "#111827"), ("play", "Play", I.SHOP, "#16A34A"),
         ("video", "影片", I.ONDEMAND_VIDEO, "#DC2626"), ("download", "下載", I.DOWNLOAD, "#2563EB"),
         ("live", "線上版", I.LANGUAGE, "#0891B2")]
SORTS = [("pushed", "最近更新"), ("release", "最近發佈"), ("stars", "星星數"), ("name", "名稱")]
PAGE = 48
STATUS_TONE = {s: v for s, v in PLT_STATUS.items()}
PLAT_COLOR = {"slate": "#CBD5E1", "sky": "#38BDF8", "amber": "#F59E0B", "violet": "#8B5CF6", "green": "#16A34A"}


_ICON_CACHE = {}
_TILE_TONES = ["blue", "teal", "amber", "violet", "green", "rose", "sky", "orange"]


def project_icon(p, size=40):
    """專案的小圖示：有圖示檔用圖示，沒有就用主題第一個字的色塊。"""
    b64 = p.get("icon_png")
    if b64:
        data = _ICON_CACHE.get(b64)
        if data is None:
            import base64
            try:
                data = _ICON_CACHE[b64] = base64.b64decode(b64)
            except Exception:
                data = b""
        if data:
            return ft.Container(ft.Image(src=data, width=size, height=size, fit=ft.BoxFit.CONTAIN),
                                width=size, height=size, border_radius=size * 0.22,
                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS)
    bg, fg = T.TONES[_TILE_TONES[sum(map(ord, p.get("name") or "")) % len(_TILE_TONES)]]
    sym = getattr(I, (p.get("symbol") or "").upper(), None)
    if sym:
        return ft.Container(ft.Icon(sym, size=size * 0.6, color=fg), width=size, height=size,
                            border_radius=size * 0.22, bgcolor=bg, alignment=ft.Alignment.CENTER)
    title = (p.get("display") or p.get("name") or "?").lstrip("#*-_ ·🤖")
    ch = next((c for c in title if c.isalnum()), "?").upper()
    return ft.Container(ft.Text(ch, size=size * 0.45, weight=ft.FontWeight.W_800, color=fg), width=size, height=size,
                        border_radius=size * 0.22, bgcolor=bg, alignment=ft.Alignment.CENTER)


def when(d):
    return rocdate.show(d) if d else ""


def plat_dots(p, size=14):
    """六個平台的小圖示：顏色代表狀態。"""
    out = []
    for code, name, icon, _ in PLATFORMS:
        r = p["platforms"].get(code) or {}
        s = r.get("status", 0)
        label, tone = PLT_STATUS[s]
        col = "#E2E8F0" if s in (0, 9) else PLAT_COLOR.get(tone, "#94A3B8")
        out.append(ft.Icon(getattr(I, icon), size=size, color=col,
                           tooltip="%s：%s%s" % (name, label, (" " + r["version"]) if r.get("version") else "")))
    return ft.Row(out, spacing=3, tight=True)


class Projects(ft.Row):
    def __init__(self, ctx, open=None, **kw):
        self.ctx = ctx
        b = ctx.books
        self.tab = "all"
        self.sort = "pushed"
        self.filters = set()
        self.status = ""
        self.limit = PAGE
        self.sel = None
        self.can_note = b.can("PRJ", 2)
        self.can_cat = b.can("CAT", 2)
        self.can_plt = b.can("PLT", 2)
        self.can_task = b.can("TASK", 2)
        self.search = T.field("搜尋主題、名稱、說明…" if T.MOBILE else "搜尋專案主題、名稱、說明、語言、備忘…", "", prefix_icon=I.SEARCH, expand=True,
                              on_change=lambda e: self.refresh(reset=True))
        self.sort_dd = T.dropdown("排序", SORTS, "pushed", width=150, filterable=False,
                                  on_select=lambda e: self.set_sort(e.control.value))
        self.status_dd = T.dropdown("專案狀態", [(k, v[0]) for k, v in PRJ_STATUS.items() if k], "", width=140,
                                    filterable=False, blank="全部", on_select=lambda e: self.set_status(e.control.value))
        self.filter_row = ft.Row(spacing=6, wrap=True)
        self.tabs = ft.Row(spacing=8, run_spacing=8, wrap=True)
        self.grid = ft.ResponsiveRow(spacing=12, run_spacing=12)
        self.more = ft.Container()
        self.count = T.muted("", 12)
        self.detail = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        self.replace = T.MOBILE or T.TABLET   # 手機、iPad：明細取代清單（寬度不夠並排）
        self.detail_box = T.card(self.detail, width=None if self.replace else 520, padding=14 if T.MOBILE else 18,
                                 visible=False, expand=bool(T.TABLET))
        head = [T.btn("新增專案", I.ADD, lambda e: self.add_dialog(), kind="outline")] if self.can_note else []
        if b.can("SYNC", 2):
            head.append(T.btn("彙整 GitHub", I.SYNC, lambda e: ctx.app.go("sync")))
        if T.MOBILE:                          # 手機：搜尋自己一列，排序與狀態在下一列
            self.search.expand = False
            tools = ft.Column([self.search, ft.Row([self.sort_dd, self.status_dd], spacing=8, wrap=True)], spacing=8)
        else:
            tools = ft.Row([self.search, self.sort_dd, self.status_dd], spacing=10)
        self.list_col = left = ft.Column([
            T.page_header(I.APPS, "專案總覽", "按卡片看詳細內容；README 大標題就是專案主題", "blue", head),
            tools,
            self.filter_row, self.tabs,
            ft.Container(ft.Column([self.grid, self.more, self.count], spacing=12, scroll=ft.ScrollMode.AUTO,
                                   expand=True), expand=True)], spacing=12, expand=True)
        super().__init__([left, self.detail_box], expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.START,
                         data="split" if T.MOBILE else None)
        self.reload(update=False)
        if open:
            self.show(open, update=False)

    # ------------------------------------------------------------ 清單
    def reload(self, update=True):
        self.all = self.ctx.books.all_projects()
        self.cats = self.ctx.books.categories()
        self.refresh(update=update)

    def set_sort(self, v):
        self.sort = v or "pushed"
        self.refresh(reset=True)

    def set_status(self, v):
        self.status = v or ""
        self.refresh(reset=True)

    def toggle_filter(self, k):
        self.filters ^= {k}
        self.refresh(reset=True)

    def set_tab(self, t):
        self.tab = t
        self.refresh(reset=True)

    def refresh(self, reset=False, update=True):
        b = self.ctx.books
        if reset:
            self.limit = PAGE
        counts = b.tab_counts(self.all)
        self.filter_row.controls = [T.muted("只看有：", 12)] + [
            T.color_chip(name, col, 12, k in self.filters, lambda e, k=k: self.toggle_filter(k), icon)
            for k, name, icon, col in LINKS]

        def tab(key, name, color, n, icon=None):
            sel = str(self.tab) == str(key)
            return ft.Container(ft.Row(([ft.Icon(icon, size=16, color=ft.Colors.WHITE if sel else color)] if icon else
                                        [ft.Container(width=10, height=10, border_radius=5, bgcolor=color)]) + [
                ft.Text(name, size=14, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE if sel else T.TEXT),
                ft.Container(ft.Text(str(n), size=11, color=color if sel else ft.Colors.WHITE,
                                     weight=ft.FontWeight.W_700), bgcolor=ft.Colors.WHITE if sel else color,
                             border_radius=10, padding=ft.Padding.symmetric(horizontal=7, vertical=1))],
                spacing=8, tight=True), padding=ft.Padding.symmetric(horizontal=14, vertical=8), border_radius=12,
                bgcolor=color if sel else T.CARD, border=ft.Border.all(1, color if sel else T.LINE), ink=True,
                on_click=lambda e, k=key: self.set_tab(k))
        self.tabs.controls = ([tab("all", "全部", T.PRIMARY, counts["all"], I.APPS)] +
                              [tab(c["id"], c["name"], c["color"], counts.get(c["id"], 0)) for c in self.cats] +
                              [tab("uncategorized", "未分類", "#64748B", counts["uncategorized"], I.INBOX)])
        if self.can_cat:
            self.tabs.controls.append(ft.Container(
                ft.Row([ft.Icon(I.ADD, size=16, color=T.PRIMARY), ft.Text("分類", size=14, color=T.PRIMARY)],
                       tight=True, spacing=4), padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=12, border=ft.Border.all(1, "#93C5FD"), ink=True,
                on_click=lambda e: self.ctx.app.go("categories")))
        rows = b.list_projects(self.tab, self.search.value, self.sort, sorted(self.filters), self.status, list(self.all))
        self.rows = rows
        self.grid.controls = [self.card(p) for p in rows[:self.limit]] or [
            ft.Container(T.empty_state(I.FOLDER_OFF, "沒有符合的專案",
                                       "到「彙整 GitHub」抓取專案，或匯入原本的專案彙整網頁" if not self.all else
                                       "換個關鍵字或篩選條件試試"), col=12)]
        self.more.content = T.btn("再顯示 %d 個（共 %d 個）" % (min(PAGE, len(rows) - self.limit), len(rows)),
                                  I.EXPAND_MORE, lambda e: self.show_more(), kind="outline") \
            if len(rows) > self.limit else None
        self.count.value = "顯示 %d／%d 個專案" % (min(len(rows), self.limit), len(rows))
        if update:
            self.update()

    def show_more(self):
        self.limit += PAGE
        self.refresh()

    def card(self, p):
        sel = self.sel == p["name"]
        icons = []
        for k, name, icon, col in LINKS:
            on = bool(p.get(k))
            icons.append(ft.Container(ft.Icon(icon, size=15, color=col if on else "#CBD5E1"), width=28, height=28,
                                      border_radius=14, alignment=ft.Alignment.CENTER,
                                      bgcolor="#F1F5F9" if on else "#F8FAFC", tooltip=name if on else "沒有" + name,
                                      on_click=(lambda e, u=p[k]: self.ctx.open_url(u)) if on else None))
        st = PRJ_STATUS.get(p["status"])
        top = [project_icon(p, 40),
               ft.Text(p["display"], size=16, weight=ft.FontWeight.W_800, color=T.TEXT, max_lines=2,
                       overflow=ft.TextOverflow.ELLIPSIS, expand=True)]
        if p["status"]:
            top.append(T.chip(st[0], st[1], size=11))
        return ft.Container(ft.Column([
            ft.Row(top, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([ft.Icon(I.FOLDER_OUTLINED, size=13, color=T.MUTED),
                    ft.Text(p["name"], size=12, color=T.MUTED, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text("★ %d" % p["stars"], size=12, color="#D97706"),
                    *([T.chip(p["rel_tag"], "green", size=10)] if p.get("rel_tag") else [])], spacing=4),
            ft.Text(p.get("description") or "（沒有說明）", size=12, color="#475569", max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS, height=None if T.MOBILE else 34),
            ft.Row([ft.Row(icons, spacing=4, tight=True), plat_dots(p)], wrap=True, run_spacing=6,
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([T.color_chip(c["name"], c["color"], 10) for c in p["cats"][:4]] +
                   ([T.chip("待辦 %d" % p["open_tasks"], "rose", size=10)] if p["open_tasks"] else []),
                   spacing=4, run_spacing=4, wrap=True),
            ft.Text("%s · %s" % (p.get("language") or "—", when(p.get("pushed_at"))), size=11, color=T.MUTED,
                    text_align=ft.TextAlign.RIGHT)], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            padding=14, border_radius=14, bgcolor="#F5F9FF" if sel else T.CARD,
            border=ft.Border.all(2 if sel else 1, T.PRIMARY if sel else T.LINE), ink=True,
            col={"xs": 12, "md": 12 if self.sel else 6, "xl": 6 if self.sel else 4, "xxl": 6 if self.sel else 3},
            on_click=lambda e, n=p["name"]: self.show(n),
            shadow=ft.BoxShadow(blur_radius=12, spread_radius=-6, color="#1A1E3A5F", offset=ft.Offset(0, 4)))

    # ------------------------------------------------------------ 明細
    def show(self, name, section="總覽", update=True):
        p = self.ctx.guard(self.ctx.books.project, name)
        if not isinstance(p, dict):
            return
        self.sel = name
        self.cur = p
        self.section = section
        self.detail_box.visible = True
        if self.replace:                      # 手機、iPad：明細取代清單，按「返回」回到清單
            self.list_col.visible = False
        self.render_detail()
        self.refresh(update=False)
        if update:
            self.update()

    def close_detail(self):
        self.sel = None
        self.detail_box.visible = False
        self.list_col.visible = True
        self.refresh()

    def render_detail(self):
        p = self.cur
        tabs = ["總覽", "README", "下載版本", "平台進度", "便利貼", "待辦"]
        bar = ft.Row([ft.Container(ft.Text(t + (" ●" if self._has(t) else ""), size=14,
                                           weight=ft.FontWeight.W_700 if t == self.section else ft.FontWeight.W_500,
                                           color=T.PRIMARY if t == self.section else T.MUTED),
                                   padding=ft.Padding.symmetric(horizontal=10, vertical=8), ink=True,
                                   border=ft.Border.only(bottom=ft.BorderSide(3, T.PRIMARY if t == self.section
                                                                              else "#00000000")),
                                   on_click=lambda e, t=t: self.switch(t)) for t in tabs], spacing=0,
                     scroll=ft.ScrollMode.AUTO)
        cat_row = ft.Row([T.color_chip(("✓ " if any(x["id"] == c["id"] for x in p["cats"]) else "") + c["name"],
                                       c["color"], 12, any(x["id"] == c["id"] for x in p["cats"]),
                                       (lambda e, cid=c["id"]: self.toggle_cat(cid)) if self.can_cat else None)
                          for c in self.cats], wrap=True, spacing=6, run_spacing=6)
        meta = "★ %d · %s · 最後更新 %s" % (p["stars"], p.get("language") or "—", when(p.get("pushed_at")))
        flags = [T.chip(x, "slate", size=11) for x, on in (("Fork", p.get("is_fork")), ("私人", p.get("is_private")),
                                                           ("已封存", p.get("archived")), ("手動新增", p.get("source") == "manual"),
                                                           ("GitHub 已找不到", p.get("gone"))) if on]
        self.detail.controls = [
            ft.Row([ft.Container(project_icon(p, 52), on_click=(lambda e: self.icon_dialog()) if self.can_note else None,
                                 tooltip="更換圖示" if self.can_note else None, ink=self.can_note, border_radius=12),
                    ft.Column([ft.Text(p["display"], size=21, weight=ft.FontWeight.W_800, color=T.TEXT, selectable=True),
                               ft.TextButton(p["name"], icon=I.LINK, on_click=lambda e: self.ctx.open_url(p["url"]),
                                             disabled=not p.get("url"), style=ft.ButtonStyle(padding=0))],
                              spacing=0, expand=True),
                    ft.IconButton(I.ARROW_BACK if self.replace else I.CLOSE, on_click=lambda e: self.close_detail(),
                                  tooltip="返回清單" if self.replace else "關閉")],
                   vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Row([T.muted(meta, 12)] + flags, wrap=True, spacing=6),
            cat_row, bar, self.section_body()]

    def icon_dialog(self):
        c = self.ctx
        p = self.cur
        manual = (p.get("icon_path") or "").startswith("manual:")
        src = "手動指定的圖示" if manual else ("自動找到：%s" % p["icon_path"]) if p.get("icon_path") else             "儲存庫裡沒有找到圖示檔，目前用文字色塊"

        async def pick(e):
            name, data = await c.pick_bytes("選擇圖示圖檔", ["png", "jpg", "jpeg", "ico", "webp"])
            if data is None:
                return
            import base64
            if c.guard(c.books.set_icon, p["name"], base64.b64encode(data).decode("ascii"), ok="圖示已更換") is not None:
                c.close()
                self.after_icon()

        def auto(e):
            if c.guard(c.books.clear_icon, p["name"], ok="已改回自動，下次彙整 GitHub 時重新尋找") is not None:
                c.close()
                self.after_icon()
        c.dialog("專案圖示", ft.Column([ft.Row([project_icon(p, 72), T.muted(src, 13)], spacing=14),
                                        T.muted("可選 PNG、JPG、ICO 或 WebP 圖檔，系統會縮成小圖示；手動指定後彙整不會覆蓋。", 12)],
                                       tight=True, spacing=12),
                 [T.btn("取消", kind="ghost", on_click=lambda e: c.close())] +
                 ([T.btn("改回自動", I.AUTO_FIX_HIGH, auto, kind="outline")] if manual else []) +
                 [T.btn("選擇圖檔", I.IMAGE, pick)], icon=I.IMAGE, width=460)

    def after_icon(self):
        self.all = self.ctx.books.all_projects()
        self.show(self.cur["name"], self.section)

    def _has(self, t):
        p = self.cur
        return {"README": bool(p.get("readme")), "下載版本": bool(p.get("rel_tag")),
                "便利貼": any((p["note"] or {}).get(k) for k in ("apple_url", "play_url", "video_url", "memo")),
                "待辦": p["open_tasks"] > 0, "平台進度": bool(p["platforms"])}.get(t, False)

    def switch(self, t):
        self.section = t
        self.render_detail()
        self.detail_box.update()

    def toggle_cat(self, cid):
        if self.ctx.guard(self.ctx.books.toggle_category, self.cur["name"], cid) is not None:
            self.all = self.ctx.books.all_projects()
            self.show(self.cur["name"], self.section)

    def section_body(self):
        return getattr(self, "sec_" + {"總覽": "overview", "README": "readme", "下載版本": "release",
                                       "平台進度": "platforms", "便利貼": "note", "待辦": "tasks"}[self.section])()

    def kv(self, k, v, url=None):
        val = ft.TextButton(v, on_click=lambda e: self.ctx.open_url(url), style=ft.ButtonStyle(padding=0)) if url \
            else ft.Text(v or "—", size=13, selectable=True, expand=True)
        return ft.Row([T.muted(k, 13, width=96), val], vertical_alignment=ft.CrossAxisAlignment.START)

    def sec_overview(self):
        p = self.cur
        rows = [ft.Text(p.get("description") or "（沒有說明）", size=14, selectable=True),
                self.kv("專案主題", p["display"]), self.kv("專案名稱", p["name"]),
                self.kv("專案網址", p.get("url") or "", p.get("url")),
                self.kv("狀態", PRJ_STATUS.get(p["status"])[0])]
        for k, name, icon, col in LINKS:
            if p.get(k):
                rows.append(self.kv(name, p[k][:60] + ("…" if len(p[k]) > 60 else ""), p[k]))
        if p.get("rel_tag"):
            rows.append(self.kv("最新版本", "%s（%s）" % (p["rel_tag"], when(p.get("rel_published")) or "日期未知")))
        if p.get("topics"):
            rows.append(ft.Row([T.chip(t, "sky", size=11) for t in p["topics"].split(",") if t], wrap=True))
        rows.append(ft.Row([T.muted("平台", 13, width=96), plat_dots(p, 20)]))
        vids = self.videos()
        if vids:
            rows.append(vids)
        memo = (p["note"] or {}).get("memo")
        if memo:
            rows.append(ft.Container(ft.Text(memo, size=13, selectable=True), bgcolor="#FFFBEB", border_radius=10,
                                     padding=12, border=ft.Border.all(1, "#FDE68A")))
        return ft.Column(rows, spacing=8)

    def videos(self):
        """README 裡的影片（mp4 等播放媒體）：每支一個播放鈕，用瀏覽器播放。"""
        p = self.cur
        urls = list(dict.fromkeys(([p["note"]["video_url"]] if (p["note"] or {}).get("video_url") else []) +
                                  p["detected"]["video"]))
        if not urls:
            return None
        rows = []
        for i, u in enumerate(urls):
            name = u.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
            if "user-attachments" in u:
                name = "README 影片 %d" % (i + 1)
            rows.append(ft.Container(ft.Row([
                ft.Container(ft.Icon(I.PLAY_ARROW_ROUNDED, color=ft.Colors.WHITE, size=26), width=44, height=44,
                             border_radius=22, bgcolor="#DC2626", alignment=ft.Alignment.CENTER),
                ft.Column([ft.Text(name, size=13, weight=ft.FontWeight.W_700, max_lines=1,
                                   overflow=ft.TextOverflow.ELLIPSIS),
                           T.muted("播放媒體 · 按一下用瀏覽器播放", 11)], spacing=0, expand=True)]),
                padding=8, border_radius=12, bgcolor="#FEF2F2", border=ft.Border.all(1, "#FECACA"), ink=True,
                on_click=lambda e, u=u: self.ctx.open_url(u), tooltip=u))
        return ft.Column([ft.Row([ft.Icon(I.ONDEMAND_VIDEO, color="#DC2626", size=18),
                                  ft.Text("影片（%d）" % len(urls), size=14, weight=ft.FontWeight.W_700)])] + rows,
                         spacing=6)

    def sec_readme(self):
        text = self.cur.get("readme") or ""
        if not text:
            return T.empty_state(I.ARTICLE, "還沒有 README", "按「彙整 GitHub」就會抓下來")
        vids = self.videos()
        md = ft.Markdown(text, selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                           on_tap_link=lambda e: self.ctx.open_url(e.data),
                           image_error_content=ft.Text("（圖片）", size=12, color=T.MUTED))
        return ft.Column([vids, ft.Divider()] + [md], spacing=8) if vids else md

    def sec_release(self):
        p = self.cur
        if not p.get("rel_tag"):
            return ft.Column([T.empty_state(I.NEW_RELEASES, "沒有發佈版本",
                                            "GitHub 上還沒有 Release，或尚未彙整"),
                              T.btn("開啟發佈頁", I.OPEN_IN_NEW, lambda e: self.ctx.open_url(p["url"] + "/releases"),
                                    kind="outline")], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        rows = [ft.Row([T.icon_tile(I.NEW_RELEASES, "green", 40),
                        ft.Column([ft.Text(p.get("rel_name") or p["rel_tag"], size=16, weight=ft.FontWeight.W_700),
                                   T.muted("%s · %s" % (p["rel_tag"], when(p.get("rel_published")) or "日期未知"), 12)],
                                  spacing=0, expand=True),
                        T.btn("發佈頁", I.OPEN_IN_NEW, lambda e: self.ctx.open_url(p["rel_url"]), kind="outline")])]
        for a in p["assets"]:
            size = ("%.1f MB" % (a["size"] / 1e6)) if a.get("size") else ""
            dl = "下載 %s 次" % a["downloads"] if a.get("downloads") is not None else ""
            rows.append(ft.Container(ft.Row([
                ft.Icon(file_icon(a["name"]), size=20, color=T.PRIMARY),
                ft.Column([ft.Text(a["name"], size=13, weight=ft.FontWeight.W_600, max_lines=1,
                                   overflow=ft.TextOverflow.ELLIPSIS),
                           T.muted(" · ".join(x for x in (size, dl) if x) or " ", 11)], spacing=0, expand=True),
                ft.IconButton(I.DOWNLOAD, tooltip="下載", on_click=lambda e, u=a["url"]: self.ctx.open_url(u))]),
                padding=8, border_radius=10, bgcolor="#F7F9FC"))
        if not p["assets"]:
            rows.append(T.muted("這個版本沒有附加檔案", 12))
        return ft.Column(rows, spacing=8)

    def sec_platforms(self):
        p = self.cur
        rows = []
        for code, name, icon, tone in PLATFORMS:
            r = p["platforms"].get(code) or {"status": 0, "version": "", "note": ""}
            label, stone = PLT_STATUS[r["status"]]
            rows.append(ft.Container(ft.Row([
                T.icon_tile(getattr(I, icon), tone, 38),
                ft.Column([ft.Text(name, size=14, weight=ft.FontWeight.W_700),
                           T.muted(" · ".join(x for x in (r.get("version"), r.get("note")) if x) or " ", 11)],
                          spacing=0, expand=True),
                T.chip(label, stone),
                *([ft.IconButton(I.EDIT, tooltip="修改", on_click=lambda e, c=code: self.edit_platform(c))]
                  if self.can_plt else [])]), padding=8, border_radius=12, bgcolor="#F7F9FC"))
        rows.append(T.muted("彙整 GitHub 時會依發佈檔（.exe、.dmg、.apk、.ipa）與線上網址自動標成「已發佈」。", 11))
        return ft.Column(rows, spacing=6)

    def edit_platform(self, code):
        c = self.ctx
        p = self.cur
        r = p["platforms"].get(code) or {"status": 0, "version": "", "note": ""}
        name = next(x[1] for x in PLATFORMS if x[0] == code)
        st = T.dropdown("狀態", [(k, v[0]) for k, v in PLT_STATUS.items()], r["status"], width=160, filterable=False)
        ver = T.field("版本", r.get("version"), width=140)
        note = T.field("備註（例如：App Store 審核中）", r.get("note"), width=420)

        def save(e):
            if c.guard(c.books.set_platform, p["name"], code, int(st.value or 0), ver.value, note.value, ok="已儲存"):
                c.close()
                self.reload(update=False)
                self.show(p["name"], "平台進度")
        c.dialog("%s · %s" % (p["display"], name), ft.Column([ft.Row([st, ver]), note], tight=True, spacing=12),
                 [T.btn("取消", kind="ghost", on_click=lambda e: c.close()), T.btn("儲存", I.SAVE, save)],
                 icon=I.DEVICES, width=460)

    def sec_note(self):
        p = self.cur
        n = p["note"] or {}
        ro = not self.can_note
        d = p["detected"]
        self.nf = {}

        def F(k, label, hint="", **kw):
            self.nf[k] = T.field(label, n.get(k), read_only=ro, hint_text=hint, **kw)
            return self.nf[k]
        self.title_f = T.field("專案主題（空白＝用 README 大標題）", p.get("title"), read_only=ro,
                               hint_text=p.get("heading") or "")
        self.status_f = T.dropdown("專案狀態", [(k, v[0]) for k, v in PRJ_STATUS.items()], n.get("status") or "",
                                   width=160, filterable=False, disabled=ro)
        self.owner_f = T.dropdown("負責人", self.ctx.books.user_options(), n.get("owner_uid") or "", width=180,
                                  filterable=False, blank="（未指定）", disabled=ro)
        auto = lambda k: ("自動偵測：" + d[k][0]) if d.get(k) else ""  # noqa: E731
        items = [self.title_f, ft.Row([self.status_f, self.owner_f], wrap=True),
                 F("apple_url", "App Store／TestFlight 網址", auto("apple")), F("apple_note", "Apple 備註（審核狀態等）"),
                 F("play_url", "Google Play 網址", auto("play")), F("play_note", "Play 商店備註"),
                 F("video_url", "示範影片網址", auto("video")),
                 F("download_url", "下載網址", p.get("rel_url") or auto("download")),
                 F("live_url", "線上版網址", p.get("homepage") or ""),
                 F("memo", "備忘", multiline=True, min_lines=3, max_lines=8)]
        if not ro:
            acts = [T.btn("儲存便利貼", I.SAVE, lambda e: self.save_note())]
            if p.get("source") == "manual" or p.get("gone"):
                acts.append(T.btn("刪除專案", I.DELETE_OUTLINE, lambda e: self.delete_project(), kind="danger"))
            items.append(ft.Row(acts, spacing=8))
        items.append(T.muted("便利貼是手動補充的資料，彙整 GitHub 時不會被覆蓋；網址留空時用自動偵測到的。", 11))
        return ft.Column(items, spacing=10)

    def save_note(self):
        p = self.cur
        vals = {k: f.value for k, f in self.nf.items()}
        if self.ctx.guard(self.ctx.books.save_note, p["name"], title=self.title_f.value, status=self.status_f.value or "",
                          owner_uid=self.owner_f.value or "", ok="便利貼已儲存", **vals):
            self.reload(update=False)
            self.show(p["name"], "便利貼")

    def delete_project(self):
        p = self.cur

        def go():
            if self.ctx.guard(self.ctx.books.delete_project, p["name"], ok="已刪除"):
                self.sel = None
                self.detail_box.visible = False
                self.reload()
        self.ctx.confirm("刪除專案", "確定刪除「%s」？便利貼、平台進度與待辦都會一起刪除。" % p["display"], go, yes="刪除")

    def sec_tasks(self):
        p = self.cur
        rows = []
        if self.can_task:
            self.task_f = T.field("新增待辦，按 Enter", "", expand=True, on_submit=lambda e: self.add_task())
            rows.append(ft.Row([self.task_f, T.btn("新增", I.ADD, lambda e: self.add_task())]))
        for t in p["tasks"]:
            pr = PRIORITY.get(t["priority"], ("中", "amber"))
            rows.append(ft.Container(ft.Row([
                ft.Checkbox(value=bool(t["done"]), disabled=not self.can_task,
                            on_change=lambda e, i=t["id"]: self.toggle_task(i)),
                ft.Column([ft.Text(t["title"], size=13, color=T.MUTED if t["done"] else T.TEXT,
                                   style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if t["done"] else None),
                           T.muted(" · ".join(x for x in (t.get("uname") or "", ("預定 " + when(t["due"])) if t.get("due")
                                                          else "") if x) or " ", 11)], spacing=0, expand=True),
                T.chip(pr[0], pr[1], size=10)]), padding=4, border_radius=10, bgcolor="#F7F9FC"))
        if not p["tasks"]:
            rows.append(T.muted("沒有待辦事項", 12))
        rows.append(T.btn("全部待辦", I.CHECKLIST, lambda e: self.ctx.app.go("tasks"), kind="ghost"))
        return ft.Column(rows, spacing=6)

    def add_task(self):
        if self.ctx.guard(self.ctx.books.save_task, None, self.cur["name"], self.task_f.value):
            self.reload(update=False)
            self.show(self.cur["name"], "待辦")

    def toggle_task(self, tid):
        if self.ctx.guard(self.ctx.books.toggle_task, tid):
            self.reload(update=False)
            self.show(self.cur["name"], "待辦")

    # ------------------------------------------------------------ 新增
    def add_dialog(self):
        c = self.ctx
        name = T.field("專案名稱（英文，例如 my-tool）", "")
        title = T.field("專案主題（中文名稱）", "")
        desc = T.field("說明", "", multiline=True, min_lines=2)
        url = T.field("專案網址（選填）", "")

        def save(e):
            if c.guard(c.books.add_project, name.value, title.value, desc.value, url.value, ok="已新增"):
                c.close()
                self.reload(update=False)
                self.show(name.value.strip())
        c.dialog("新增專案", ft.Column([name, title, desc, url], tight=True, spacing=12),
                 [T.btn("取消", kind="ghost", on_click=lambda e: c.close()), T.btn("新增", I.ADD, save)],
                 icon=I.CREATE_NEW_FOLDER, width=460)


def file_icon(name):
    n = (name or "").lower()
    if n.endswith((".exe", ".msi")):
        return I.DESKTOP_WINDOWS
    if n.endswith((".dmg", ".pkg")):
        return I.LAPTOP_MAC
    if n.endswith((".apk", ".aab")):
        return I.ANDROID
    if n.endswith(".ipa"):
        return I.PHONE_IPHONE
    if n.endswith((".zip", ".7z", ".rar", ".gz")):
        return I.FOLDER_ZIP
    return I.INSERT_DRIVE_FILE
