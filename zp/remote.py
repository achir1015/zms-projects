"""手機端：透過電腦版的「手機 App 連線」服務（zp.api）使用專案彙整的資料。

RemoteBiz 和電腦版的 Biz 介面相同，畫面程式不用改：ctx.books.xxx() 會變成一次 API 呼叫。
權限（can／level／need）在手機端先判斷一次（決定按鈕能不能按），電腦端每次呼叫再嚴格檢查一次。
只做篩選、計數的方法（list_projects 傳入 projects、tab_counts）直接在手機上算，不必來回傳資料。
"""
import base64
import os
import urllib.error
import urllib.request

from . import APP_ID, wire
from .core import BizError
from .hub import HubMixin
from .seed import FUNC_NAMES, LEVEL_NAMES

DEFAULT_PORT = 8805


class ConnectionLost(BizError):
    pass


def normalize(url):
    url = (url or "").strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    if url.count(":") == 1 and url.startswith("http://"):
        url += ":%d" % DEFAULT_PORT              # 只輸入 IP 時補上預設連接埠
    return url


class Client:
    def __init__(self, url, alternates=()):
        self.url = normalize(url)
        self.alternates = [normalize(u) for u in alternates if normalize(u) != self.url]
        self.token = ""
        self.on_relogin = None
        self.on_switch = None                    # 自動換網址時通知（手機記住新的優先網址）

    def _switch(self):
        """目前網址連不上：試其他記住的網址。"""
        for alt in list(self.alternates):
            try:
                req = urllib.request.Request(alt + "/api/ping", headers={"User-Agent": APP_ID})
                with urllib.request.urlopen(req, timeout=5) as r:
                    if wire.loads(r.read()).get("app"):
                        self.alternates = [u for u in self.alternates if u != alt] + [self.url]
                        self.url = alt
                        if self.on_switch:
                            self.on_switch(alt)
                        return True
            except Exception:
                continue
        return False

    def post(self, path, body, timeout=30, _retry=True):
        try:
            return self._post_once(path, body, timeout)
        except ConnectionLost:
            if _retry and self._switch():
                return self._post_once(path, body, timeout)
            raise

    def _post_once(self, path, body, timeout=30):
        req = urllib.request.Request(self.url + path, data=wire.dumps(body), method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": APP_ID,
                                              "Authorization": "Bearer " + self.token})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return wire.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                out = wire.loads(e.read())
            except Exception:
                out = {"error": "HTTP %s" % e.code}
            if out.get("relogin") and self.on_relogin:
                self.on_relogin(out.get("error"))
            raise BizError(out.get("error") or "HTTP %s" % e.code)
        except (urllib.error.URLError, OSError) as e:
            raise ConnectionLost("連不到電腦（%s）。請確認電腦已開啟專案彙整，並在「版本更新與捷徑」打開手機 App 連線。"
                                 % getattr(e, "reason", e))

    def ping(self, timeout=6):
        req = urllib.request.Request(self.url + "/api/ping", headers={"User-Agent": APP_ID})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return wire.loads(r.read())
        except Exception as e:
            raise ConnectionLost("連不到 %s：%s" % (self.url, getattr(e, "reason", e)))

    def call(self, method, args=(), kwargs=None, timeout=30):
        out = self.post("/api/call", {"method": method, "args": list(args), "kwargs": kwargs or {}}, timeout=timeout)
        if "biz" in out:
            raise BizError(out["biz"])
        return out


class RemoteBiz:
    # 手機上直接計算的方法（借用 HubMixin 的實作，不經過 API）
    list_projects = HubMixin.list_projects
    tab_counts = HubMixin.tab_counts
    infer_platforms = staticmethod(HubMixin.infer_platforms)

    def __init__(self, client: Client):
        self._c = client
        self.user = None
        self.perms = {}
        self.server = {}

    # ---------------------------------------------------------------- 登入與權限（本地判斷，電腦端會再檢查）
    @property
    def uid(self):
        return (self.user or {}).get("uid", "")

    def login(self, uid, pw):
        out = self._c.post("/api/login", {"uid": (uid or "").strip(), "pw": pw or ""})
        self._c.token = out["token"]
        self.user, self.perms, self.server = out["user"], out["perms"], out.get("server", {})
        return self.user

    def logout(self):
        if self._c.token:
            try:
                self._c.post("/api/logout", {}, timeout=5, _retry=False)
            except Exception:
                pass
        self._c.token = ""
        self.user, self.perms = None, {}

    def level(self, func):
        if not self.user:
            return 0
        if self.user.get("is_admin"):
            return 2
        return int(self.perms.get(func, 0))

    def can(self, func, lvl=1):
        return self.level(func) >= lvl

    def can_doc(self, func, lvl=1):
        return self.can(func, lvl)

    def need(self, func, lvl=2):
        if not self.can(func, lvl):
            raise BizError("您沒有「%s」的%s權限" % (FUNC_NAMES.get(func, func), LEVEL_NAMES.get(lvl, "")))

    def _call(self, method, *args, timeout=30, **kwargs):
        out = self._c.call(method, args, kwargs, timeout=timeout)
        self.user, self.perms = out.get("user", self.user), out.get("perms", self.perms)
        return out["result"]

    # ---------------------------------------------------------------- 特別處理
    def settings_row(self):
        return self.company()                    # 不把 Token 傳到手機（company() 依權限遮蔽）

    def sync_github(self, progress=None, releases="auto", stop=None):
        if progress:
            progress("彙整中，請稍候（在電腦上執行，專案多時要幾分鐘）…", 0, 0)
        r = self._call("sync_github", releases=releases, timeout=900)
        if progress:
            progress("完成：" + r.get("note", ""), 1, 1)
        return r

    def publish_online(self, repo=""):
        return self._call("publish_online", repo, timeout=180)

    def import_html(self, path):
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return self._call("import_html_upload", os.path.basename(path), data, timeout=180)

    def import_backup(self, data):
        return self._call("import_backup", data, timeout=120)

    def auto_classify(self, only_uncategorized=True):
        return self._call("auto_classify", only_uncategorized, timeout=60)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *a, **kw: self._call(name, *a, **kw)
