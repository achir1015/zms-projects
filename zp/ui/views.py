"""平台進度總表、待辦事項、彙整 GitHub（含 GitHub 設定、匯入匯出）、分類管理、統計報表。"""
import datetime as dt
import json
import os
import threading
import time

import flet as ft

from .. import rocdate
from ..seed import PALETTE, PLATFORMS, PLT_STATUS, PRIORITY
from . import theme as T
from .projects import PLAT_COLOR, project_icon, when

I = ft.Icons


def tab_dropdown(ctx, on_select, value="all"):
    cats = ctx.books.categories()
    return T.dropdown("分類", [("all", "全部")] + [(c["id"], c["name"]) for c in cats] +
                      [("uncategorized", "未分類")], value, width=170, filterable=False, on_select=on_select)


# ====================================================================== 平台進度總表
class Matrix(ft.Column):
    def __init__(self, ctx, **kw):
        self.ctx = ctx
        self.tab = "all"
        self.can = ctx.books.can("PLT", 2)
        self.kw = T.field("搜尋", "", width=220, prefix_icon=I.SEARCH, on_change=lambda e: self.load())
        self.cat = tab_dropdown(ctx, lambda e: self.set_tab(e.control.value))
        self.body = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self.sum = ft.Row(spacing=10, wrap=True)
        legend = ft.Row([T.chip(v[0], v[1], size=11) for k, v in PLT_STATUS.items()], spacing=6, wrap=True)
        super().__init__([
            T.page_header(I.GRID_VIEW, "平台進度總表", "每個專案在六個平台的狀態；按格子可修改", "violet",
                          [self.kw, self.cat, T.btn("匯出 Excel", I.DOWNLOAD, self.export, kind="outline")]),
            ft.Row([legend, ft.Container(expand=True), self.sum]),
            T.card(self.body, expand=True, padding=0)], spacing=12, expand=True)
        self.load(update=False)

    def set_tab(self, v):
        self.tab = v or "all"
        self.load()

    def load(self, update=True):
        self.rows = self.ctx.books.matrix(self.tab, self.kw.value)
        W = 116
        head = ft.Container(ft.Row([ft.Text("專案主題", size=13, weight=ft.FontWeight.W_700, width=300)] + [
            ft.Row([ft.Icon(getattr(I, icon), size=16, color=T.TONES[tone][1]),
                    ft.Text(name, size=13, weight=ft.FontWeight.W_700)], width=W, spacing=4)
            for code, name, icon, tone in PLATFORMS], spacing=8), bgcolor="#EEF3FA",
            padding=ft.Padding.symmetric(horizontal=14, vertical=10))
        lines = [head]
        done = {c[0]: 0 for c in PLATFORMS}
        for p in self.rows:
            cells = []
            for code, name, icon, tone in PLATFORMS:
                r = p["platforms"].get(code) or {}
                s = r.get("status", 0)
                if s == 4:
                    done[code] += 1
                label, stone = PLT_STATUS[s]
                bg, fg = T.TONES[stone]
                cells.append(ft.Container(
                    ft.Column([ft.Text(label, size=12, color=fg if s not in (0, 9) else "#94A3B8",
                                       weight=ft.FontWeight.W_700),
                               ft.Text(r.get("version") or "", size=10, color=T.MUTED, max_lines=1)],
                              spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    width=W, height=40, border_radius=8, alignment=ft.Alignment.CENTER,
                    bgcolor=bg if s not in (0, 9) else "#F8FAFC", tooltip=r.get("note") or None,
                    ink=self.can, on_click=(lambda e, p=p, c=code: self.edit(p, c)) if self.can else None))
            lines.append(ft.Container(ft.Row([
                ft.Row([project_icon(p, 28),
                        ft.Column([ft.Text(p["display"], size=13, weight=ft.FontWeight.W_600, max_lines=1,
                                           overflow=ft.TextOverflow.ELLIPSIS),
                                   T.muted(p["name"], 11)], spacing=0, expand=True)], spacing=8, width=300)] + cells,
                spacing=8),
                padding=ft.Padding.symmetric(horizontal=14, vertical=5),
                border=ft.Border.only(bottom=ft.BorderSide(1, "#EDF1F6"))))
        if T.MOBILE:                          # 手機：每個專案一張小卡，六個平台排成 3×2
            short = {"WIN": "Windows", "MAC": "Mac", "WEB": "線上版", "IOS": "iPhone", "IPAD": "iPad", "AND": "Android"}
            lines = []
            for p in self.rows:
                cells = []
                for code, name, icon, tone in PLATFORMS:
                    r = p["platforms"].get(code) or {}
                    s = r.get("status", 0)
                    label, stone = PLT_STATUS[s]
                    bg, fg = T.TONES[stone]
                    cells.append(ft.Container(ft.Column([
                        ft.Text(short.get(code, name), size=10, color=T.MUTED, max_lines=1),
                        ft.Text(label + ((" " + r["version"]) if r.get("version") else ""), size=11, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS, weight=ft.FontWeight.W_700,
                                color=fg if s not in (0, 9) else "#94A3B8")], spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        col=4, height=42, border_radius=8, alignment=ft.Alignment.CENTER,
                        bgcolor=bg if s not in (0, 9) else "#F8FAFC", ink=self.can,
                        on_click=(lambda e, p=p, c=code: self.edit(p, c)) if self.can else None))
                lines.append(ft.Container(ft.Column([
                    ft.Row([project_icon(p, 34), ft.Column([
                        ft.Text(p["display"], size=14, weight=ft.FontWeight.W_700, max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        T.muted(p["name"], 11)], spacing=0, expand=True)], spacing=10),
                    ft.ResponsiveRow(cells, spacing=6, run_spacing=6)], spacing=4),
                    padding=12, border=ft.Border.only(bottom=ft.BorderSide(1, "#EDF1F6"))))
            if not self.rows:
                lines.append(T.empty_state(I.GRID_OFF, "沒有專案"))
            self.body.controls = [ft.Column(lines, spacing=0, data=T.READY)]
        else:
            if not self.rows:
                lines.append(T.empty_state(I.GRID_OFF, "沒有專案"))
            self.body.controls = [ft.Row([ft.Column(lines, spacing=0)], scroll=ft.ScrollMode.AUTO)]
        self.sum.controls = [T.muted("已發佈：", 12)] + [T.chip("%s %d" % (n, done[c]), "green", size=11)
                                                       for c, n, *_ in PLATFORMS]
        if update:
            self.update()

    def edit(self, p, code):
        c = self.ctx
        r = p["platforms"].get(code) or {"status": 0, "version": "", "note": ""}
        name = next(x[1] for x in PLATFORMS if x[0] == code)
        st = T.dropdown("狀態", [(k, v[0]) for k, v in PLT_STATUS.items()], r["status"], width=160, filterable=False)
        ver = T.field("版本", r.get("version"), width=140)
        note = T.field("備註", r.get("note"), width=420)

        def save(e):
            if c.guard(c.books.set_platform, p["name"], code, int(st.value or 0), ver.value, note.value, ok="已儲存"):
                c.close()
                self.load()
        c.dialog("%s · %s" % (p["display"], name), ft.Column([ft.Row([st, ver]), note], tight=True, spacing=12),
                 [T.btn("取消", kind="ghost", on_click=lambda e: c.close()), T.btn("儲存", I.SAVE, save)],
                 icon=I.DEVICES, width=460)

    async def export(self, e):
        import csv
        import io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["專案主題", "專案名稱", "分類"] + [n for c, n, *_ in PLATFORMS])
        for p in self.rows:
            w.writerow([p["display"], p["name"], "、".join(c["name"] for c in p["cats"])] +
                       [("%s %s" % (PLT_STATUS[(p["platforms"].get(c) or {}).get("status", 0)][0],
                                    (p["platforms"].get(c) or {}).get("version") or "")).strip()
                        for c, *_ in PLATFORMS])
        path = await self.ctx.save_download("平台進度_%s.csv" % rocdate.today().strftime("%Y%m%d"),
                                            buf.getvalue().encode("utf-8-sig"))
        if not path:
            return
        self.ctx.toast("已匯出：%s" % os.path.basename(path))
        if not self.ctx.web:
            T.open_file(path)


# ====================================================================== 待辦事項
class Tasks(ft.Column):
    def __init__(self, ctx, **kw):
        self.ctx = ctx
        b = ctx.books
        self.can = b.can("TASK", 2)
        self.show_done = T.switch("顯示已完成", False, on_change=lambda e: self.load())
        self.mine = T.switch("只看我的", False, on_change=lambda e: self.load())
        self.list = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        acts = [self.mine, self.show_done]
        if self.can:
            acts.append(T.btn("新增待辦", I.ADD_TASK, lambda e: self.edit(None)))
        super().__init__([T.page_header(I.CHECKLIST, "待辦事項", "依優先順序與預定完成日排列", "rose", acts),
                          T.card(self.list, expand=True, padding=14)], spacing=12, expand=True)
        self.load(update=False)

    def load(self, update=True):
        b = self.ctx.books
        rows = b.tasks(show_done=self.show_done.value, uid=b.uid if self.mine.value else "")
        names = {p["name"]: p["display"] for p in b.all_projects(include_gone=True)}
        today = rocdate.today()
        out = []
        for t in rows:
            pr = PRIORITY.get(t["priority"], ("中", "amber"))
            late = t.get("due") and not t["done"] and t["due"] < today
            plat = next((n for c, n, *_ in PLATFORMS if c == t["platform"]), "")
            out.append(ft.Container(ft.Row([
                ft.Checkbox(value=bool(t["done"]), disabled=not self.can, on_change=lambda e, i=t["id"]: self.toggle(i)),
                T.chip(pr[0], pr[1], size=11),
                ft.Column([ft.Text(t["title"], size=14, weight=ft.FontWeight.W_600,
                                   color=T.MUTED if t["done"] else T.TEXT,
                                   style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if t["done"] else None),
                           T.muted(" · ".join(x for x in (names.get(t["name"], t["name"]) or "（一般）", plat,
                                                          t.get("uname") or "") if x), 12)], spacing=0, expand=True),
                ft.Text(("預定 " + when(t["due"])) if t.get("due") else "", size=12,
                        color=T.DANGER if late else T.MUTED, weight=ft.FontWeight.W_700 if late else None),
                *([ft.IconButton(I.EDIT, on_click=lambda e, t=t: self.edit(t), tooltip="修改"),
                   ft.IconButton(I.DELETE_OUTLINE, icon_color=T.DANGER, on_click=lambda e, t=t: self.delete(t),
                                 tooltip="刪除")] if self.can else []),
                *([ft.IconButton(I.OPEN_IN_NEW, tooltip="開啟專案",
                                 on_click=lambda e, n=t["name"]: self.ctx.app.go("projects", open=n))]
                  if t["name"] else [])]),
                padding=ft.Padding.symmetric(horizontal=10, vertical=4), border_radius=12, bgcolor="#F7F9FC"))
        self.list.controls = out or [T.empty_state(I.TASK_ALT, "沒有待辦事項")]
        if update:
            self.update()

    def toggle(self, tid):
        if self.ctx.guard(self.ctx.books.toggle_task, tid):
            self.load()

    def delete(self, t):
        self.ctx.confirm("刪除待辦", "確定刪除「%s」？" % t["title"],
                         lambda: self.ctx.guard(self.ctx.books.delete_task, t["id"], ok="已刪除") and self.load(),
                         yes="刪除")

    def edit(self, t):
        c = self.ctx
        b = c.books
        t = t or {"id": None, "name": "", "title": "", "platform": "", "priority": 2, "due": None, "uid": b.uid}
        projects = sorted(((p["name"], "%s（%s）" % (p["display"], p["name"])) for p in b.all_projects()),
                          key=lambda x: x[1])
        prj = T.dropdown("專案", projects, t["name"], width=420, blank="（不屬於特定專案）")
        title = T.field("事項", t["title"], width=420, autofocus=True)
        plat = T.dropdown("平台", [(c_, n) for c_, n, *_ in PLATFORMS], t["platform"], width=150, filterable=False,
                          blank="（不限）")
        pri = T.dropdown("優先", [(k, v[0]) for k, v in PRIORITY.items()], t["priority"], width=110, filterable=False)
        due = T.field("預定完成日", rocdate.show(t["due"]) if t.get("due") else "", width=150, hint_text="115/12/31")
        who = T.dropdown("負責人", b.user_options(), t.get("uid") or "", width=150, filterable=False, blank="（未指定）")

        def save(e):
            if c.guard(b.save_task, t["id"], prj.value or "", title.value, plat.value or "", int(pri.value or 2),
                       due.value.strip() or None, who.value or "", ok="已儲存"):
                c.close()
                self.load()
        c.dialog("修改待辦" if t["id"] else "新增待辦", ft.Column([prj, title, ft.Row([plat, pri]), ft.Row([due, who])],
                                                         tight=True, spacing=12),
                 [T.btn("取消", kind="ghost", on_click=lambda e: c.close()), T.btn("儲存", I.SAVE, save)],
                 icon=I.ADD_TASK, tone="rose", width=460)


# ====================================================================== 彙整 GitHub
class Sync(ft.Column):
    running = False

    def __init__(self, ctx, **kw):
        self.ctx = ctx
        b = ctx.books
        st = b.company()
        self.is_sys = b.can("SYS", 2)
        self.cname = T.field("公司或團隊名稱", st.get("name"), width=300, read_only=not self.is_sys,
                             prefix_icon=I.BUSINESS)
        self.owner = T.field("GitHub 帳號", st.get("github_owner"), width=300, hint_text="帳號名稱，不是 email",
                             read_only=not self.is_sys, prefix_icon=I.PERSON)
        self.token = T.field("GitHub Token（選填）", st.get("github_token"), width=380, password=True,
                             can_reveal_password=self.is_sys, read_only=not self.is_sys, prefix_icon=I.KEY)
        self.forks = T.switch("顯示 Fork 來的專案", st.get("include_forks", 1), disabled=not self.is_sys)
        self.auto = T.switch("開程式時自動彙整", st.get("auto_sync", 0), disabled=not self.is_sys)
        self.free = T.switch("不使用 API 查發佈版本（較慢，但不扣次數）", False)
        self.pages = T.field("線上版儲存庫", st.get("pages_repo"), width=300, read_only=not self.is_sys,
                             hint_text="例如 achir1015/zms-projects", prefix_icon=I.LANGUAGE)
        self.pub_msg = T.muted("上次發佈：%s" % (T.show(st.get("pages_at")) or "尚未發佈"), 12)
        self.bar = ft.ProgressBar(value=0, color=T.ACCENT, bgcolor="#E6F4F1", bar_height=8, border_radius=4,
                                  visible=False)
        self.msg = ft.Text("", size=13, color=T.TEXT, selectable=True)
        self.log = ft.ListView(spacing=2, height=200, auto_scroll=True)
        self.go_btn = T.btn("立即彙整 GitHub", I.SYNC, lambda e: self.run(), kind="accent")
        self.stop_flag = False
        self.last = T.muted("", 12)
        last = "上次彙整：%s　%s" % (T.show(st.get("last_sync_at")) or "尚未彙整", st.get("last_sync_note") or "")
        cfg = [ft.Row([self.cname, self.pages], wrap=True), ft.Row([self.owner, self.token], wrap=True),
               ft.Row([self.forks, self.auto], wrap=True, spacing=24),
               T.muted("沒有 Token 時，GitHub 每小時只允許 60 次查詢；專案多時部分發佈版本會改用發佈頁查詢（較慢但不扣次數）。"
                       "Token 可在 GitHub → Settings → Developer settings → Fine-grained tokens 建立，權限選 Contents: "
                       "Read-only（要發佈線上版則選 Read and write）；有 Token 也能看到私人專案。"
                       "Token 只存在本系統的資料庫，只有系統管理權限看得到。", 12)]
        if self.is_sys:
            cfg.append(ft.Row([T.btn("儲存設定", I.SAVE, lambda e: self.save())]))
        self.last.value = last
        can_sync = b.can("SYNC", 2)
        super().__init__([
            T.page_header(I.SYNC, "彙整 GitHub", "抓專案清單、README（專案主題）、最新發佈版本；便利貼與分類不會被覆蓋",
                          "teal"),
            T.card(ft.Column(([ft.Row([T.icon_tile(I.CLOUD_SYNC, "teal", 44),
                                       ft.Column([ft.Text("彙整", size=17, weight=ft.FontWeight.W_700), self.last],
                                                 spacing=0, expand=True)]),
                               ft.Row([self.go_btn if can_sync else T.chip("沒有彙整權限", "slate")], wrap=True)]
                              if T.MOBILE else          # 手機：按鈕放下一列（彙整在電腦上執行，不能中途停止）
                              [ft.Row([T.icon_tile(I.CLOUD_SYNC, "teal", 44),
                                       ft.Column([ft.Text("彙整", size=17, weight=ft.FontWeight.W_700), self.last],
                                                 spacing=0, expand=True),
                                       self.go_btn if can_sync else T.chip("沒有彙整權限", "slate"),
                                       T.btn("停止", I.STOP, lambda e: self.stop(), kind="outline")])]) + [
                              self.free, self.bar, self.msg,
                              ft.Container(self.log, bgcolor="#F7F9FC", border_radius=10, padding=10)], spacing=10),
                   padding=20),
            T.card(ft.Column([ft.Row([T.icon_tile(I.SETTINGS, "blue", 36),
                                      ft.Text("GitHub 設定", size=16, weight=ft.FontWeight.W_700)])] + cfg, spacing=12),
                   padding=20),
            T.card(ft.Column([ft.Row([T.icon_tile(I.PUBLIC, "sky", 44), ft.Column([
                ft.Text("發佈線上版", size=17, weight=ft.FontWeight.W_700),
                T.muted("把公開專案的主題、說明、版本、連結、分類與平台進度送到 GitHub Pages，任何人用瀏覽器就能看；"
                        "私人專案、便利貼備註、待辦與負責人不會送出。", 12), self.pub_msg,
                ft.Row([T.btn("發佈線上版", I.PUBLISH, self.publish, kind="accent", disabled=not can_sync),
                        T.btn("開啟線上版", I.OPEN_IN_NEW, lambda e: self.open_online(), kind="outline")],
                       spacing=10, wrap=True)], spacing=6, expand=True)], spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START)]), padding=20),
            ft.Row([
                io_card(I.HTML, "orange", "匯入舊版彙整網頁", "讀取「Achir1015專案彙整.html」裡的專案快照（含 README）",
                        T.btn("選擇網頁檔", I.UPLOAD_FILE, self.import_html, kind="outline", disabled=not can_sync)),
                io_card(I.UPLOAD, "violet", "匯入備份", "本系統或舊網頁「匯出備份」的 JSON：分類、便利貼、平台進度、待辦",
                        T.btn("選擇備份檔", I.UPLOAD_FILE, self.import_backup, kind="outline", disabled=not can_sync)),
                io_card(I.DOWNLOAD, "green", "匯出備份", "把手動整理的資料存成 JSON，可搬到另一台電腦",
                        T.btn("匯出", I.SAVE_ALT, self.export_backup, kind="outline"))], spacing=14, data="split")],
            spacing=14, expand=True, scroll=ft.ScrollMode.AUTO)

    def save(self, ok="GitHub 設定已儲存"):
        return self.ctx.guard(self.ctx.books.save_company, name=self.cname.value, github_owner=self.owner.value,
                              github_token=self.token.value, include_forks=self.forks.value,
                              auto_sync=self.auto.value, pages_repo=self.pages.value, ok=ok)

    def online_url(self):
        repo = (self.pages.value or "").strip() or "achir1015/zms-projects"
        owner, _, name = repo.partition("/")
        return "https://%s.github.io/%s/app/" % (owner.lower(), name)

    def open_online(self):
        self.ctx.open_url(self.online_url())

    def publish(self, e):
        if self.is_sys and not self.save(ok=None):
            return
        self.pub_msg.value = "發佈中…"
        self.update()

        def work():
            try:
                r = self.ctx.books.publish_online()
            except Exception as ex:
                self.pub_msg.value = "發佈失敗：%s" % ex
                self.ctx.toast(str(ex), True)
            else:
                self.pub_msg.value = "已發佈 %d 個公開專案（約 1 分鐘後線上版更新）：%s" % (r["count"], r["url"] + "app/")
                self.ctx.toast("線上版已發佈")
            try:
                self.update()
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def say(self, text, done=0, total=0):
        self.msg.value = text
        if total:
            self.bar.value = done / total
        if not text.startswith(("②", "③", "④")) or done in (1, total):
            self.log.controls.append(ft.Text(time.strftime("%H:%M:%S ") + text, size=12, color=T.MUTED))
        try:
            self.update()
        except Exception:
            pass

    def stop(self):
        self.stop_flag = True

    def run(self):
        if Sync.running:
            self.ctx.toast("彙整中，請稍候", True)
            return
        if self.is_sys:
            if not self.save(ok=None):
                return
        Sync.running = True
        self.stop_flag = False
        self.bar.visible, self.bar.value = True, None
        self.go_btn.disabled = True
        self.log.controls.clear()
        self.update()

        def work():
            try:
                stat = self.ctx.books.sync_github(self.say, "free" if self.free.value else "auto",
                                                  stop=lambda: self.stop_flag)
                self.ctx.toast("彙整完成：%s" % stat["note"])
                self.last.value = "上次彙整：%s　%s" % (T.show(dt.datetime.now()), stat["note"])
            except Exception as ex:
                self.say("彙整失敗：%s" % ex)
                self.ctx.toast(str(ex), True)
            finally:
                Sync.running = False
                self.bar.visible = False
                self.go_btn.disabled = False
                try:
                    self.update()
                except Exception:
                    pass
        threading.Thread(target=work, daemon=True).start()

    async def import_html(self, e):
        name, data = await self.ctx.pick_bytes("選擇舊版專案彙整網頁", ["html", "htm"])
        if data is None:
            return
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "zp_import_%d.html" % os.getpid())
        with open(tmp, "wb") as f:
            f.write(data)
        r = self.ctx.guard(self.ctx.books.import_html, tmp)
        if isinstance(r, dict):
            n = self.ctx.guard(self.ctx.books.auto_classify) if self.ctx.books.can("CAT", 2) else 0
            self.say("匯入完成：共 %(total)d 個專案，新增 %(new)d、更新 %(updated)d" % r +
                     ("；自動分類 %d 筆" % n if isinstance(n, int) and n is not True else ""))
            self.ctx.toast("匯入完成")

    async def import_backup(self, e):
        name, raw = await self.ctx.pick_bytes("選擇備份檔", ["json"])
        if raw is None:
            return
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except Exception as ex:
            self.ctx.toast("讀不到備份檔：%s" % ex, True)
            return
        r = self.ctx.guard(self.ctx.books.import_backup, data)
        if isinstance(r, dict):
            self.say("備份匯入完成：分類 %(categories)d、分類對應 %(assigned)d、便利貼 %(notes)d、平台 %(platforms)d、"
                     "待辦 %(tasks)d" % r)
            self.ctx.toast("匯入完成")

    async def export_backup(self, e):
        data = self.ctx.guard(self.ctx.books.export_backup)
        if not isinstance(data, dict):
            return
        path = await self.ctx.save_download("專案彙整備份_%s.json" % time.strftime("%Y%m%d_%H%M"),
                                            json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))
        if path:
            self.ctx.books.log("export_backup", os.path.basename(path))
            self.ctx.toast("已匯出：%s" % os.path.basename(path))


def io_card(icon, tone, title, desc, button):
    return T.card(ft.Column([T.icon_tile(icon, tone, 48, radius=14), ft.Text(title, size=16, weight=ft.FontWeight.W_700),
                             T.muted(desc, 12), button], spacing=8), expand=True, padding=18)


# ====================================================================== 分類管理
class Categories(ft.Column):
    def __init__(self, ctx, **kw):
        self.ctx = ctx
        self.can = ctx.books.can("CAT", 2)
        self.list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self.new = T.field("新分類名稱", "", width=220, on_submit=lambda e: self.add())
        acts = [self.new, T.btn("新增", I.ADD, lambda e: self.add()),
                T.btn("依規則自動分類", I.AUTO_FIX_HIGH, lambda e: self.auto(), kind="accent")] if self.can else []
        super().__init__([
            T.page_header(I.FOLDER_SPECIAL, "分類管理",
                          "新增、改名、換顏色、調整頁簽順序或刪除；刪除分類不會刪除專案，專案會回到「未分類」", "amber", acts),
            T.card(self.list, expand=True, padding=14)], spacing=12, expand=True)
        self.load(update=False)

    def load(self, update=True):
        cats = self.ctx.books.categories()
        out = []
        for i, c in enumerate(cats):
            out.append(ft.Container(ft.Row([
                ft.Container(width=34, height=34, border_radius=10, bgcolor=c["color"]),
                ft.Column([ft.Text(c["name"], size=15, weight=ft.FontWeight.W_700),
                           T.muted("%d 個專案　自動分類規則：%s" % (c["count"], c["rule"] or "（無）"), 12)],
                          spacing=0, expand=True),
                *([ft.IconButton(I.ARROW_UPWARD, tooltip="往前", disabled=i == 0,
                                 on_click=lambda e, c=c: self.move(c, -1)),
                   ft.IconButton(I.ARROW_DOWNWARD, tooltip="往後", disabled=i == len(cats) - 1,
                                 on_click=lambda e, c=c: self.move(c, 1)),
                   ft.IconButton(I.EDIT, tooltip="修改", on_click=lambda e, c=c: self.edit(c)),
                   ft.IconButton(I.DELETE_OUTLINE, icon_color=T.DANGER, tooltip="刪除",
                                 on_click=lambda e, c=c: self.delete(c))] if self.can else [])]),
                padding=10, border_radius=12, bgcolor="#F7F9FC"))
        self.list.controls = out or [T.empty_state(I.FOLDER_OFF, "還沒有分類")]
        if update:
            self.update()

    def add(self):
        if self.ctx.guard(self.ctx.books.add_category, self.new.value, ok="已新增"):
            self.new.value = ""
            self.load()

    def move(self, c, d):
        self.ctx.guard(self.ctx.books.move_category, c["id"], d)
        self.load()

    def auto(self):
        n = self.ctx.guard(self.ctx.books.auto_classify)
        if n is not None:
            self.ctx.toast("自動分類完成：放入 %d 筆（只處理還沒分類的專案）" % (0 if n is True else n))
            self.load()

    def delete(self, c):
        self.ctx.confirm("刪除分類", "確定刪除「%s」？裡面的 %d 個專案不會被刪除。" % (c["name"], c["count"]),
                         lambda: self.ctx.guard(self.ctx.books.delete_category, c["id"], ok="已刪除") and self.load(),
                         yes="刪除")

    def edit(self, cat):
        c = self.ctx
        name = T.field("分類名稱", cat["name"], width=300)
        color = T.field("顏色", cat["color"], width=140)
        rule = T.field("自動分類規則（專案名稱或說明含有的字，以逗號分隔）", cat["rule"], width=440)
        swatch = ft.Row([ft.Container(width=30, height=30, border_radius=8, bgcolor=x, ink=True,
                                      on_click=lambda e, x=x: set_color(x)) for x in PALETTE + ["#0F766E", "#B45309"]],
                        spacing=6, wrap=True)

        def set_color(x):
            color.value = x
            color.update()

        def save(e):
            if c.guard(c.books.save_category, cat["id"], name.value, color.value.strip(), rule.value, ok="已儲存"):
                c.close()
                self.load()
        c.dialog("修改分類", ft.Column([name, ft.Row([color, swatch]), rule], tight=True, spacing=12),
                 [T.btn("取消", kind="ghost", on_click=lambda e: c.close()), T.btn("儲存", I.SAVE, save)],
                 icon=I.FOLDER_SPECIAL, tone="amber", width=520)


# ====================================================================== 統計
class Stats(ft.Column):
    def __init__(self, ctx, **kw):
        self.ctx = ctx
        s = ctx.books.stats()
        top = max([n for _, n in s["langs"]] or [1])
        langs = T.card(ft.Column([ft.Text("程式語言", size=16, weight=ft.FontWeight.W_700)] + [
            ft.Row([ft.Text(k, size=13, width=120), ft.Container(height=14, width=max(6, 260 * n / top),
                                                                   bgcolor=T.ACCENT, border_radius=7),
                    ft.Text(str(n), size=12, color=T.MUTED)]) for k, n in s["langs"][:14]], spacing=6),
            expand=2, padding=18)
        self.grid = T.Grid([("name", "分類", "s", 110), ("total", "專案數", "n", 60), ("release", "有發佈", "n", 60),
                            ("stars", "星星", "n", 50)] + [(c, n, "n", 62) for c, n, *_ in PLATFORMS], height=380)
        self.grid.set_rows(s["by_cat"])
        plat = T.card(ft.Column([ft.Text("各平台狀態", size=16, weight=ft.FontWeight.W_700)] + [
            ft.Row([ft.Text(r["name"], size=13, width=80)] + [
                T.chip("%s %d" % (PLT_STATUS[k][0], r[k]), PLT_STATUS[k][1], size=11) for k in (4, 3, 2, 1) if r[k]],
                wrap=True, spacing=6) for r in s["platforms"]], spacing=8), expand=3, padding=18)
        super().__init__([
            T.page_header(I.INSIGHTS, "統計報表", "共 %d 個專案" % s["total"], "orange",
                          [ctx.export_button(self.grid, "分類統計")]),
            ft.Text("各分類發佈情形（平台欄位＝已發佈數）", size=15, weight=ft.FontWeight.W_700), self.grid,
            T.split(plat, langs, spacing=16)], spacing=14, expand=True, scroll=ft.ScrollMode.AUTO)


_ = PLAT_COLOR
