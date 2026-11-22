"""首頁：專案數、本週更新、已發佈平台、分類分布、最近更新的專案、待辦、快捷功能。"""
import datetime as dt

import flet as ft

from .. import rocdate
from ..seed import PLATFORMS
from . import theme as T
from .projects import plat_dots, when

I = ft.Icons


def greet():
    h = dt.datetime.now().hour
    return "早安" if h < 11 else "午安" if h < 14 else "下午好" if h < 18 else "晚安"


class Dashboard(ft.Column):
    def __init__(self, ctx, **kw):
        self.ctx = ctx
        b = ctx.books
        app = ctx.app
        d = b.dashboard()
        u = b.user
        comp = b.company()
        hero = ft.Container(ft.Row([
            ft.Column([ft.Text("%s，%s" % (u["name"], greet()), size=24, weight=ft.FontWeight.W_800,
                               color=ft.Colors.WHITE),
                       ft.Text("%s的 GitHub 專案：%s" % (comp.get("name") or "", comp.get("github_owner") or ""),
                               size=14, color="#DCE6F5"),
                       ft.Row([hero_chip(I.CALENDAR_TODAY, rocdate.show(rocdate.today())),
                               hero_chip(I.SYNC, "上次彙整 %s" % (T.show(d["last_sync"]) or "尚未彙整")),
                               hero_chip(I.CHECKLIST, "待辦 %d 項" % d["open_tasks"])], spacing=8, wrap=True)],
                      spacing=6, expand=True),
            ft.Image(src="icon.png", width=96, height=96)]), padding=24, border_radius=20,
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                       colors=[T.SIDEBAR_TOP, "#1E4D8C", "#0F766E"]))
        ks = [T.kpi("專案總數", str(d["total"]), I.APPS, "blue", "未分類 %d" % d["uncategorized"],
                    lambda e: app.go("projects")),
              T.kpi("本週有更新", str(d["active_week"]), I.UPDATE, "teal", "最近 7 天", lambda e: app.go("projects")),
              T.kpi("有發佈版本", str(d["with_release"]), I.NEW_RELEASES, "green", "GitHub Release",
                    lambda e: app.go("matrix")),
              T.kpi("App Store／Play", "%d／%d" % (d["apple"], d["play"]), I.STOREFRONT, "violet", "上架連結",
                    lambda e: app.go("projects")),
              T.kpi("線上版／影片", "%d／%d" % (d["live"], d["video"]), I.LANGUAGE, "sky", "",
                    lambda e: app.go("projects"))]
        plat = T.card(ft.Column([
            ft.Row([T.icon_tile(I.DEVICES, "violet", 34), ft.Text("各平台已發佈", size=16, weight=ft.FontWeight.W_700)]),
            ft.Row([ft.Container(ft.Column([T.icon_tile(getattr(I, icon), tone, 46, radius=14),
                                            ft.Text(str(d["platforms"][code]), size=22, weight=ft.FontWeight.W_800),
                                            T.muted(name, 12)], spacing=4,
                                           horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                 expand=True, on_click=lambda e: app.go("matrix"), ink=True, border_radius=12,
                                 padding=6)
                    for code, name, icon, tone in PLATFORMS])], spacing=12), expand=3)
        top = max([n for _, n in d["cats"]] or [1]) or 1
        cats = T.card(ft.Column([
            ft.Row([T.icon_tile(I.FOLDER_SPECIAL, "amber", 34), ft.Text("分類", size=16, weight=ft.FontWeight.W_700)]),
            ft.Column([ft.Row([ft.Text(c["name"], size=13, width=96, max_lines=1),
                               ft.Container(height=12, width=max(6, 200 * n / top), bgcolor=c["color"], border_radius=6),
                               T.muted(str(n), 12)]) for c, n in d["cats"]], spacing=6)], spacing=12), expand=2)
        recent = T.card(ft.Column([
            ft.Row([T.icon_tile(I.HISTORY, "teal", 34), ft.Text("最近更新的專案", size=16, weight=ft.FontWeight.W_700)]),
            ft.Column([ft.Container(ft.Row([
                ft.Column([ft.Text(p["display"], size=14, weight=ft.FontWeight.W_600, max_lines=1,
                                   overflow=ft.TextOverflow.ELLIPSIS),
                           T.muted("%s · %s" % (p["name"], when(p.get("pushed_at"))), 11)], spacing=0, expand=True),
                plat_dots(p)]), padding=8, border_radius=10, ink=True,
                on_click=lambda e, n=p["name"]: app.go("projects", open=n)) for p in d["recent"]]
                or [T.empty_state(I.CLOUD_SYNC, "還沒有專案", "到「彙整 GitHub」抓取專案")], spacing=2)],
            spacing=10), expand=3)
        tiles = [("專案總覽", I.APPS, "blue", "projects"), ("平台進度", I.GRID_VIEW, "violet", "matrix"),
                 ("待辦事項", I.CHECKLIST, "rose", "tasks"), ("彙整 GitHub", I.SYNC, "teal", "sync"),
                 ("分類管理", I.FOLDER_SPECIAL, "amber", "categories"), ("統計報表", I.INSIGHTS, "orange", "stats"),
                 ("語音教學", I.RECORD_VOICE_OVER, "green", "help")]
        quick = ft.Row([quick_tile(t, i, tone, lambda e, s=s: app.go(s)) for t, i, tone, s in tiles if app.find(s)],
                       wrap=True, spacing=12, run_spacing=12)
        super().__init__([hero, T.kpis(ks), ft.Text("快捷功能", size=17, weight=ft.FontWeight.W_700), quick,
                          T.split(plat, cats, spacing=16), recent], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True)


def hero_chip(icon, text):
    return ft.Container(ft.Row([ft.Icon(icon, size=14, color="#DCE6F5"), ft.Text(text, size=12, color="#DCE6F5")],
                               spacing=4, tight=True), bgcolor="#22FFFFFF", border_radius=20,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4))


def quick_tile(text, icon, tone, on_click):
    return ft.Container(ft.Column([T.icon_tile(icon, tone, 48, radius=14), ft.Text(text, size=13,
                                                                                   weight=ft.FontWeight.W_600)],
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                        width=118, padding=12, bgcolor=T.CARD, border_radius=16, border=ft.Border.all(1, T.LINE),
                        ink=True, on_click=on_click)
