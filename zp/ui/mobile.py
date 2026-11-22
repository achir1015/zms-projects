"""手機／平板 App（iPhone、iPad，之後 Android）：連線設定 → 登入 → 畫面。

資料一律透過電腦版專案彙整的「手機 App 連線」服務存取（zp.remote），畫面程式與電腦版共用。
iPhone（直向）：上方工具列＋抽屜選單；iPad（橫向）：電腦版版面（側邊選單）。
"""
import os
import urllib.parse

import flet as ft

from .. import APP_NAME, APP_SHORT, APP_VERSION
from ..core import BizError
from ..remote import Client, RemoteBiz, normalize
from . import theme as T

IOS_INSTALL_PAGE = "https://achir1015.github.io/zms-projects/ios/"
MOBILE_HIDDEN = {"backup", "update"}     # 手機 App 不提供：備份還原、版本更新（電腦版的設定）


def is_mobile(page) -> bool:
    return bool(os.environ.get("ZP_MOBILE")) or page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)


def is_tablet(page) -> bool:
    if os.environ.get("ZP_TABLET"):
        return True
    return page.platform == ft.PagePlatform.IOS and (page.width or 0) >= 900


def link_from_route(route):
    """掃描 QR Code 的深層連結：zmsprojects://connect?u=<網址> → 頁面路由 /connect?u=…"""
    if not route or "u=" not in route:
        return ""
    q = urllib.parse.urlparse(route).query or route.split("?", 1)[-1]
    return urllib.parse.parse_qs(q).get("u", [""])[0]


def gradient():
    return ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                             colors=[T.SIDEBAR_TOP, "#1E4D8C", "#0F766E"])


def _card(controls):
    return ft.Container(ft.Column(controls, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                        bgcolor=T.CARD, border_radius=20, padding=20, width=None if T.MOBILE else 460)


def _screen(app, controls):
    p = app.page
    p.drawer = None
    p.controls.clear()
    p.add(ft.SafeArea(ft.Container(ft.Column(controls, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10,
                                             scroll=ft.ScrollMode.AUTO),
                                   padding=20, expand=True, gradient=gradient()), expand=True))
    p.update()


# ====================================================================== 啟動
def start(app):
    p = app.page
    T.MOBILE = not is_tablet(p)
    T.TABLET = not T.MOBILE
    if T.MOBILE:
        T.install_mobile_hooks()

    def on_route(e):
        """App 已開著時又掃了 QR Code：換連到新的電腦。"""
        link = link_from_route(p.route)
        if link and normalize(link) != (app.client.url if app.client else ""):
            remember(app, link)
            if app.books and getattr(app.books, "user", None):
                app.books.logout()
            connect(app, link)
    p.on_route_change = on_route
    link = link_from_route(p.route)
    url = link or os.environ.get("ZP_DEV_SERVER") or app.st.extra.get("server_url", "")
    if link:
        remember(app, url)
    if url:
        connect(app, url, quiet=True)
    else:
        connect_screen(app)


def connect_screen(app, msg="", url=""):
    p = app.page
    url_f = T.field("電腦的連線網址", url or app.st.extra.get("server_url", ""),
                    hint_text="例：192.168.6.172:8805", prefix_icon=ft.Icons.LINK, keyboard_type=ft.KeyboardType.URL)
    info = ft.Text(msg, color=T.DANGER if msg else T.MUTED, size=13)

    def go(e=None):
        info.value, info.color = "連線中…", T.MUTED
        p.update()
        connect(app, url_f.value)
    url_f.on_submit = go
    _screen(app, [
        ft.Container(height=16),
        ft.Image(src="icon.png", width=88, height=88),
        ft.Text(APP_SHORT, size=26, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
        ft.Text("手機 App 連線設定", size=15, color="#CFE0F7"),
        _card([
            ft.Row([T.icon_tile(ft.Icons.QR_CODE_SCANNER, "teal", 52, radius=16)], alignment=ft.MainAxisAlignment.CENTER),
            ft.Text("連到電腦上的專案彙整", size=18, weight=ft.FontWeight.W_700),
            T.muted("在電腦的專案彙整「系統管理 → 版本更新與捷徑 → 手機 App 連線」打開服務，用相機掃畫面上的 QR Code "
                    "會自動帶入；或把網址輸入下面。手機要和電腦連同一個 Wi-Fi。", 13),
            url_f, info,
            ft.FilledButton("連線", icon=ft.Icons.LINK, height=48, on_click=go, bgcolor=T.PRIMARY,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12))),
            ft.TextButton("不連電腦，只看公開線上版", icon=ft.Icons.PUBLIC,
                          on_click=lambda e: p.run_task(ft.UrlLauncher().launch_url,
                                                        "https://achir1015.github.io/zms-projects/app/"))]),
        T.muted("v%s" % APP_VERSION, 11)])


def remember(app, url):
    """記住連線網址（最多 4 個，最近成功的放最前面）。"""
    url = normalize(url)
    lst = [url] + [u for u in app.st.extra.get("server_urls", []) if u != url]
    app.st.extra["server_urls"] = lst[:4]
    app.st.extra["server_url"] = url
    app.st.save()


def connect(app, url, quiet=False):
    saved = [u for u in app.st.extra.get("server_urls", []) if u != normalize(url)]
    c = Client(url, alternates=saved)
    try:
        try:
            info = c.ping()
        except BizError:
            if not c._switch():
                raise
            info = c.ping()
    except BizError as e:
        msg = str(e) if not quiet else "上次的電腦目前連不上：%s" % e
        if app.page.platform == ft.PagePlatform.IOS and ("No route to host" in msg or "Errno 65" in msg):
            msg += ("\n\niPhone／iPad 第一次連電腦，要允許本 App 使用「區域網路」：請到「設定 → App（或隱私權與安全性）"
                    "→ 區域網路」，打開「%s」，再回來按「連線」。" % APP_NAME)
        connect_screen(app, msg, url)
        return
    if info.get("app") != APP_NAME:
        connect_screen(app, "這個網址不是專案彙整的手機 App 連線服務", url)
        return
    remember(app, c.url)
    c.on_switch = lambda u: remember(app, u)
    app.client = c
    app.books = app.reports = RemoteBiz(c)
    app.server_info = info
    app.ctx = T.Ctx(app)
    c.on_relogin = lambda reason: app.page.run_thread(lambda: login(app, reason))
    login(app)


# ====================================================================== 登入
def login(app, msg=""):
    p = app.page
    info = getattr(app, "server_info", {}) or {}
    uid = T.field("帳號", app.st.last_user, prefix_icon=ft.Icons.PERSON_OUTLINE)
    pw = T.field("密碼", "", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK_OUTLINE,
                 autofocus=bool(app.st.last_user))
    err = ft.Text(msg, color=T.DANGER, size=13)

    def go(e=None):
        try:
            app.books.login(uid.value, pw.value)
        except BizError as ex:
            err.value = str(ex)
            p.update()
            return
        app.st.last_user = app.books.uid
        app.st.save()
        app.main()
    pw.on_submit = go
    dev = os.environ.get("ZP_DEV_LOGIN")          # 開發測試：自動登入
    if dev and not msg:
        u, _, w = dev.partition(":")
        app.books.login(u, w)
        app.main()
        route = (p.route or "").strip("/") or os.environ.get("ZP_DEV_ROUTE", "")
        if route:
            sid, _, arg = route.partition(":")
            app.go(sid, **({"open": arg} if arg else {}))
        return
    _screen(app, [
        ft.Container(height=16),
        ft.Image(src="icon.png", width=80, height=80),
        ft.Text(APP_SHORT, size=26, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
        ft.Text(info.get("company") or "", size=15, color="#CFE0F7"),
        _card([
            ft.Text("歡迎回來", size=22, weight=ft.FontWeight.W_800),
            T.muted("請用專案彙整的帳號登入（與電腦版相同）", 13),
            uid, pw, err,
            ft.FilledButton("登入", icon=ft.Icons.LOGIN, height=48, on_click=go, bgcolor=T.PRIMARY,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12))),
            ft.Row([T.btn("更換電腦", ft.Icons.LINK, lambda e: switch_server(app), kind="ghost")],
                   alignment=ft.MainAxisAlignment.CENTER, wrap=True)]),
        T.muted("已連線：%s　v%s" % (app.client.url, APP_VERSION), 11)])


# ====================================================================== 主畫面（iPhone 直向）
def main(app):
    p = app.page
    u = app.books.user
    app.title = ft.Text("", size=17, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE, expand=True,
                        no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)
    app.sidebar = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, expand=True)

    async def open_menu(e):
        await p.show_drawer()

    top = ft.Container(ft.Row([
        ft.IconButton(ft.Icons.MENU, icon_color=ft.Colors.WHITE, on_click=open_menu, tooltip="選單"),
        app.title,
        ft.IconButton(ft.Icons.RECORD_VOICE_OVER, icon_color=ft.Colors.WHITE, tooltip="語音教學",
                      on_click=lambda e: app.go("help")),
        ft.IconButton(ft.Icons.HOME_ROUNDED, icon_color=ft.Colors.WHITE, tooltip="首頁",
                      on_click=lambda e: app.go("home"))], spacing=0),
        gradient=ft.LinearGradient(begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT,
                                   colors=[T.SIDEBAR_TOP, T.PRIMARY]),
        padding=ft.Padding.only(left=4, right=4, top=4, bottom=4))
    avatar = ft.Container(ft.Text((u.get("name") or "?")[:1], color=ft.Colors.WHITE, weight=ft.FontWeight.W_700),
                          width=40, height=40, border_radius=20, bgcolor=T.ACCENT, alignment=ft.Alignment.CENTER)
    p.drawer = ft.NavigationDrawer(bgcolor=T.SIDEBAR_TOP, controls=[
        ft.Container(ft.Column([
            ft.Row([ft.Image(src="icon.png", width=40, height=40),
                    ft.Column([ft.Text("資料助秘", size=11, color="#9FB6D8"),
                               ft.Text(APP_SHORT, size=17, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE)],
                              spacing=0)], spacing=10),
            ft.Row([avatar, ft.Column([ft.Text(u.get("name") or "", color=ft.Colors.WHITE, size=14,
                                               weight=ft.FontWeight.W_600),
                                       ft.Text((app.server_info or {}).get("company", ""), color="#9FB6D8", size=11)],
                                      spacing=0, expand=True)], spacing=10)], spacing=14),
            padding=ft.Padding.only(left=18, right=12, top=20, bottom=10)),
        ft.Divider(color="#2A4A78", height=1),
        ft.Container(app.sidebar, padding=ft.Padding.symmetric(horizontal=8, vertical=6)),
        ft.Divider(color="#2A4A78", height=1),
        ft.Container(ft.Column([
            ft.TextButton("變更密碼", icon=ft.Icons.KEY, on_click=lambda e: app.change_password(),
                          style=ft.ButtonStyle(color="#D5E0F0")),
            ft.TextButton("登出", icon=ft.Icons.LOGOUT, on_click=lambda e: app.logout(),
                          style=ft.ButtonStyle(color="#D5E0F0")),
            ft.TextButton("更換電腦", icon=ft.Icons.LINK, on_click=lambda e: switch_server(app),
                          style=ft.ButtonStyle(color="#D5E0F0")),
            ft.Text("v%s　已連線 %s" % (APP_VERSION, app.client.url), size=10, color="#7F98BF")], spacing=0),
            padding=ft.Padding.only(left=12, bottom=16))])
    app.body = ft.Container(expand=True, padding=ft.Padding.only(left=12, right=12, top=12, bottom=8))
    p.controls.clear()
    p.add(ft.SafeArea(ft.Column([top, app.body], expand=True, spacing=0), expand=True))
    app.go("home")
    p.run_thread(check_update, app)


def check_update(app):
    """有新版時提示，點一下開啟安裝頁（iPhone／iPad）或下載 APK（Android）。"""
    from .. import maintenance
    ios = app.page.platform == ft.PagePlatform.IOS or os.environ.get("ZP_MOBILE")
    try:
        info = maintenance.check_update(platform="ios" if ios else "android")
    except Exception:
        return
    if not info:
        return
    if ios:
        info["url"] = IOS_INSTALL_PAGE

    async def open_dl(e):
        await ft.UrlLauncher().launch_url(info["url"] or info["page"])
    try:
        if app.page.drawer is not None:
            app.page.drawer.controls.insert(1, ft.Container(
                ft.Row([ft.Icon(ft.Icons.SYSTEM_UPDATE, color=ft.Colors.WHITE),
                        ft.Text("有新版本 v%s，點這裡更新" % info["version"], color=ft.Colors.WHITE,
                                weight=ft.FontWeight.W_600, expand=True)]),
                bgcolor=T.ACCENT, border_radius=12, padding=12, margin=ft.Margin.symmetric(horizontal=10),
                on_click=open_dl, ink=True))
        else:
            app.update_banner.content = ft.Container(
                ft.Row([ft.Icon(ft.Icons.SYSTEM_UPDATE, color=ft.Colors.WHITE, size=16),
                        ft.Text("有新版本 v%s" % info["version"], color=ft.Colors.WHITE, size=13,
                                weight=ft.FontWeight.W_600)], spacing=6, tight=True),
                bgcolor=T.ACCENT, border_radius=20, padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                on_click=open_dl, tooltip="開啟安裝頁")
            app.update_banner.visible = True
        app.ctx.toast("有新版本 v%s，請更新" % info["version"])
        app.page.update()
    except Exception:
        pass


def switch_server(app):
    if app.books and getattr(app.books, "user", None):
        app.books.logout()
    app.st.extra.pop("server_url", None)
    app.st.extra.pop("server_urls", None)
    app.st.save()
    connect_screen(app)


async def close_drawer(page):
    try:
        await page.close_drawer()
    except Exception:
        pass
