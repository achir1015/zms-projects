"""手機 App 連線服務：電腦版開啟後，iPhone／iPad（之後 Android）App 透過這個 API 使用專案彙整的資料。

* 手機不直接連資料庫；每個請求都在電腦端用該使用者的帳號與權限執行 Biz 的方法（方法內有 need() 權限檢查）。
* 只開放白名單內的方法。GitHub Token 不會傳到手機（company() 會依權限遮蔽；settings_row／github_token 不開放）。
* 檔案類操作改走專用方法：匯入舊版網頁（import_html_upload）。
* 登入：POST /api/login {uid, pw} → token；之後 POST /api/call {method, args, kwargs}，標頭 Authorization: Bearer token
* 每次呼叫都重新讀取使用者狀態與權限（停用帳號或改權限立即生效）；登入失敗太多次暫時封鎖；閒置 12 小時失效。
"""
import base64
import logging
import os
import secrets
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import APP_NAME, APP_VERSION, wire
from .biz import Biz
from .core import BizError
from .webserve import local_ips

log = logging.getLogger("zp")
DEFAULT_PORT = 8805
SESSION_IDLE = 12 * 3600
FAIL_LIMIT, FAIL_WINDOW = 8, 15 * 60
API_VERSION = 1
MAX_BODY = 30 * 1024 * 1024
DEEP_LINK = "zmsprojects://connect?u=%s"

BIZ_METHODS = {
    # 查詢
    "has_users", "users", "user_options", "audit", "company", "categories", "all_projects", "project", "matrix",
    "tasks", "dashboard", "stats", "export_backup",
    # 維護（方法內檢查權限）
    "log", "change_password", "save_user", "delete_user", "save_company", "save_note", "add_project",
    "delete_project", "set_platform", "add_category", "save_category", "move_category", "delete_category",
    "toggle_category", "auto_classify", "save_task", "toggle_task", "delete_task", "sync_github", "import_backup",
    "publish_online",
}


def public_user(u):
    return {k: v for k, v in (u or {}).items() if k != "pw_hash"}


def import_html_upload(biz, name, data_b64):
    """手機上傳的舊版專案彙整網頁：存成暫存檔後照一般匯入。"""
    biz.need("SYNC", 2)
    data = base64.b64decode(data_b64 or "")
    if not data:
        raise BizError("檔案是空的")
    d = tempfile.mkdtemp(prefix="zp_m_")
    p = os.path.join(d, os.path.basename(str(name or "upload.html"))[:120] or "upload.html")
    try:
        with open(p, "wb") as f:
            f.write(data)
        return biz.import_html(p)
    finally:
        shutil.rmtree(d, ignore_errors=True)


EXTRA = {"import_html_upload": import_html_upload}


class Session:
    def __init__(self, biz):
        self.biz = biz
        self.seen = time.time()


class ApiServer:
    def __init__(self, db, port=DEFAULT_PORT, host="0.0.0.0"):
        self.db = db
        self.port = int(port or DEFAULT_PORT)
        self.host = host
        self.sessions = {}
        self.fails = {}
        self.lock = threading.Lock()
        self.httpd = None
        self.thread = None
        self.requests = 0

    # ---------------------------------------------------------------- 啟停
    def start(self):
        if self.httpd:
            return
        api = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "ZMSProjects"

            def log_message(self, fmt, *a):
                pass

            def _send(self, code, obj):
                body = wire.dumps(obj)
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = self.path.split("?")[0].rstrip("/")
                if path in ("", "/api/ping"):
                    return self._send(200, api.ping())
                self._send(404, {"error": "not found"})

            def do_POST(self):
                tok = (self.headers.get("Authorization") or "").replace("Bearer ", "").strip()
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    if n > MAX_BODY:
                        return self._send(413, {"error": "資料太大（上限 30MB）"})
                    body = wire.loads(self.rfile.read(n) or b"{}")
                    ip = self.client_address[0]
                    if self.path == "/api/login":
                        code, out = api.login(body, ip)
                    elif self.path == "/api/call":
                        code, out = api.call(tok, body)
                    elif self.path == "/api/logout":
                        code, out = api.logout(tok)
                    else:
                        code, out = 404, {"error": "not found"}
                except Exception as e:
                    log.exception("api")
                    code, out = 500, {"error": "伺服器錯誤：%s" % e}
                finally:
                    api.db.close()           # 每個請求用完就關閉此執行緒的資料庫連線
                self._send(code, out)

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        log.info("api: listening on %s:%s", self.host, self.port)

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            self.sessions.clear()
            log.info("api: stopped")

    @property
    def running(self):
        return self.httpd is not None

    def urls(self):
        ips = sorted(local_ips(), key=lambda x: (not x.startswith("192.168."), x))
        return ["http://%s:%d" % (ip, self.port) for ip in ips]

    # ---------------------------------------------------------------- 處理
    def ping(self):
        team = ""
        try:
            team = (self.db.row("SELECT name FROM sys_company WHERE id=1") or {}).get("name") or ""
        except Exception:
            pass
        finally:
            self.db.close()
        return {"app": APP_NAME, "version": APP_VERSION, "api": API_VERSION, "company": team}

    def _blocked(self, key, limit=FAIL_LIMIT):
        now = time.time()
        with self.lock:
            lst = [t for t in self.fails.get(key, []) if now - t < FAIL_WINDOW]
            self.fails[key] = lst
            return len(lst) >= limit

    def login(self, body, ip):
        uid_key = "uid:" + str(body.get("uid", "")).strip().lower()
        if self._blocked(ip) or self._blocked(uid_key, FAIL_LIMIT + 4):
            return 429, {"error": "登入失敗次數太多，請 15 分鐘後再試"}
        b = Biz(self.db)
        try:
            b.login(body.get("uid", ""), body.get("pw", ""))
        except BizError as e:
            with self.lock:
                now = time.time()
                self.fails.setdefault(ip, []).append(now)
                self.fails.setdefault(uid_key, []).append(now)
            return 401, {"error": str(e)}
        b.log("mobile_login", b.uid, ip)
        tok = secrets.token_urlsafe(32)
        with self.lock:
            self._expire()
            self.sessions[tok] = Session(b)
        return 200, {"token": tok, "user": public_user(b.user), "perms": b.perms, "server": self.ping()}

    def logout(self, tok):
        with self.lock:
            s = self.sessions.pop(tok, None)
        if s:
            s.biz.log("logout", s.biz.uid, "手機")
        return 200, {"ok": True}

    def _expire(self):
        now = time.time()
        for t in [t for t, s in self.sessions.items() if now - s.seen > SESSION_IDLE]:
            self.sessions.pop(t, None)

    def call(self, tok, body):
        with self.lock:
            s = self.sessions.get(tok)
            if s and time.time() - s.seen > SESSION_IDLE:
                self.sessions.pop(tok, None)
                s = None
        if not s:
            return 401, {"error": "連線已逾時，請重新登入", "relogin": True}
        s.seen = time.time()
        b = s.biz
        u = self.db.row("SELECT * FROM sys_user WHERE uid=%s", (b.uid,))
        if not u or not u["active"]:
            with self.lock:
                self.sessions.pop(tok, None)
            return 401, {"error": "帳號已停用", "relogin": True}
        b.user = u
        b.perms = {r["func"]: r["lvl"] for r in self.db.rows("SELECT func, lvl FROM sys_user_perm WHERE uid=%s",
                                                              (u["uid"],))}
        method = str(body.get("method", ""))
        args, kwargs = list(body.get("args", [])), dict(body.get("kwargs", {}))
        if method in BIZ_METHODS:
            fn = getattr(b, method)
        elif method in EXTRA:
            fn = lambda *a, **kw: EXTRA[method](b, *a, **kw)          # noqa: E731
        else:
            return 403, {"error": "不允許的操作：%s" % method}
        kwargs.pop("progress", None)
        kwargs.pop("stop", None)
        self.requests += 1
        try:
            result = fn(*args, **kwargs)
            if method == "company" and isinstance(result, dict) and result.get("github_token"):
                result = dict(result, github_token="●●●●")      # Token 一律不傳到手機（存檔時 ●●●● 表示不變）
            return 200, {"result": result, "user": public_user(b.user), "perms": b.perms}
        except (BizError, ValueError) as e:
            return 200, {"biz": str(e)}
