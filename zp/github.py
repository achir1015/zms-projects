"""GitHub 查詢：專案清單、README、最新發佈版本。

* GitHub API 沒有 Token 時每小時只能查 60 次；有 Token 可到 5000 次。
* 用 ETag 條件查詢（資料沒變時 GitHub 回 304，不扣次數），回應存在 sys_http_cache。
* README 走 raw.githubusercontent.com（不扣次數）。
* 次數用完時，最新發佈版本改從 github.com 發佈頁的轉址＋下載清單頁取得（不扣次數）。
"""
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from . import APP_ID

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
UA = APP_ID + "/1.0"


class RateLimit(Exception):
    pass


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class Gateway:
    def __init__(self, db=None, token=""):
        self.db = db
        self.token = (token or "").strip()
        self.remaining = None
        self.limit = None
        self.reset_at = None
        self.ssl = _ctx()

    # ------------------------------------------------------------ 底層
    def _open(self, url, headers=None, method="GET", timeout=20):
        h = {"User-Agent": UA}
        h.update(headers or {})
        if self.token and url.startswith(API):
            h["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(url, headers=h, method=method)
        return urllib.request.urlopen(req, timeout=timeout, context=self.ssl)

    def _note_rate(self, headers):
        rem = headers.get("X-RateLimit-Remaining")
        if rem is not None:
            self.remaining = int(rem)
            self.limit = int(headers.get("X-RateLimit-Limit") or 0)
            self.reset_at = int(headers.get("X-RateLimit-Reset") or 0)

    def _cache_get(self, url):
        if not self.db:
            return None
        return self.db.row("SELECT etag, data FROM sys_http_cache WHERE url=%s", (url[:400],))

    def _cache_put(self, url, etag, data):
        if self.db and etag:
            self.db.exec("REPLACE INTO sys_http_cache (url, etag, data) VALUES (%s, %s, %s)",
                         (url[:400], etag, json.dumps(data, ensure_ascii=False)))

    def get_json(self, path):
        url = API + path
        cached = self._cache_get(url)
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if cached and cached["etag"]:
            headers["If-None-Match"] = cached["etag"]
        try:
            with self._open(url, headers) as r:
                self._note_rate(r.headers)
                data = json.loads(r.read().decode("utf-8"))
                self._cache_put(url, r.headers.get("ETag") or "", slim(data))
                return data
        except urllib.error.HTTPError as e:
            self._note_rate(e.headers)
            if e.code == 304 and cached:
                return json.loads(cached["data"])
            if e.code in (403, 429) and self.remaining == 0:
                raise RateLimit(self.rate_message())
            if e.code == 404:
                return None
            raise RuntimeError("GitHub 回應 %s：%s" % (e.code, path))

    def rate_message(self):
        import datetime as dt
        t = dt.datetime.fromtimestamp(self.reset_at).strftime("%H:%M") if self.reset_at else "稍後"
        return "GitHub 查詢次數已用完，%s 後恢復。可到「GitHub 設定」填入 Token 提高到每小時 5000 次。" % t

    def can_spend(self, reserve=1):
        return self.remaining is None or self.remaining > reserve

    # ------------------------------------------------------------ 對外
    def list_repos(self, owner):
        out = []
        for page in range(1, 11):
            if self.token:
                path = "/user/repos?per_page=100&page=%d&affiliation=owner&sort=pushed" % page
            else:
                path = "/users/%s/repos?per_page=100&page=%d&type=owner&sort=pushed" % (owner, page)
            lst = self.get_json(path)
            if lst is None:
                raise RuntimeError("GitHub 上找不到帳號「%s」" % owner)
            out += lst
            if len(lst) < 100:
                break
        return [r for r in out if ((r.get("owner") or {}).get("login") or "").lower() == owner.lower()]

    def latest_release(self, full_name):
        lst = self.get_json("/repos/%s/releases?per_page=3" % full_name) or []
        return next((r for r in lst if not r.get("draft")), None)

    def latest_release_free(self, full_name):
        """不扣 API 次數：HEAD /releases/latest 取轉址版號，再讀下載清單頁。沒有發佈回傳 None。"""
        url = "https://github.com/%s/releases/latest" % full_name
        try:
            with self._open(url, method="HEAD", timeout=15) as r:
                final = r.geturl()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        if "/releases/tag/" not in final:
            return None
        tag = urllib.parse.unquote(final.rstrip("/").rsplit("/tag/", 1)[-1])
        assets = []
        try:
            with self._open("https://github.com/%s/releases/expanded_assets/%s" % (full_name, urllib.parse.quote(tag)),
                            timeout=15) as r:
                html = r.read().decode("utf-8", "replace")
            seen = set()
            for href in re.findall(r'href="(/%s/releases/download/[^"]+)"' % re.escape(full_name), html):
                if href in seen:
                    continue
                seen.add(href)
                assets.append(dict(name=urllib.parse.unquote(href.rsplit("/", 1)[-1]),
                                   browser_download_url="https://github.com" + href, size=0, download_count=None))
        except Exception:
            pass
        return dict(tag_name=tag, name=tag, html_url=final, published_at=None, assets=assets)

    def readme(self, full_name, branch, private=False):
        if self.token and private:
            try:
                with self._open("%s/repos/%s/readme" % (API, full_name),
                                {"Accept": "application/vnd.github.raw+json"}) as r:
                    self._note_rate(r.headers)
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError:
                return ""
        for fn in ("README.md", "readme.md", "Readme.md", "README.MD", "README"):
            try:
                with self._open("%s/%s/%s/%s" % (RAW, full_name, urllib.parse.quote(branch or "main"), fn)) as r:
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    return ""
            except Exception:
                return ""
        return ""

    # ------------------------------------------------------------ 寫入（發佈線上版）
    def _send(self, method, path, body=None):
        if not self.token:
            raise RuntimeError("要先在「GitHub 設定」填入 Token（需有該儲存庫的 Contents 寫入權限）")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(API + path, data=data, method=method, headers={
            "User-Agent": UA, "Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120, context=self.ssl) as r:
                self._note_rate(r.headers)
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            self._note_rate(e.headers)
            try:
                msg = json.loads(e.read() or b"{}").get("message") or ""
            except Exception:
                msg = ""
            if e.code in (401, 403):
                raise RuntimeError("GitHub 拒絕寫入（%s）：請確認 Token 有這個儲存庫的 Contents 寫入權限" % (msg or e.code))
            if e.code == 404:
                raise RuntimeError("找不到儲存庫或分支（%s），或 Token 沒有權限" % path.split("/git/")[0])
            raise RuntimeError("GitHub 回應 %s：%s" % (e.code, msg))

    def commit_files(self, repo, files, message, branch=""):
        """把多個文字檔一次 commit 到儲存庫（Git Data API，共 5 次呼叫）。files：{路徑: 文字內容}。"""
        if not branch:
            branch = (self._send("GET", "/repos/%s" % repo) or {}).get("default_branch") or "main"
        ref = self._send("GET", "/repos/%s/git/ref/heads/%s" % (repo, branch))
        head = ref["object"]["sha"]
        base = self._send("GET", "/repos/%s/git/commits/%s" % (repo, head))["tree"]["sha"]
        tree = self._send("POST", "/repos/%s/git/trees" % repo, {"base_tree": base, "tree": [
            {"path": k, "mode": "100644", "type": "blob", "content": v} for k, v in files.items()]})
        if tree["sha"] == base:
            return head                          # 內容沒變
        c = self._send("POST", "/repos/%s/git/commits" % repo, {"message": message, "tree": tree["sha"],
                                                                "parents": [head]})
        self._send("PATCH", "/repos/%s/git/refs/heads/%s" % (repo, branch), {"sha": c["sha"]})
        return c["sha"]


def slim(data):
    """只留下需要的欄位，避免快取太大。"""
    def repo(r):
        return {k: r.get(k) for k in ("name", "full_name", "html_url", "description", "stargazers_count",
                                       "forks_count", "language", "topics", "homepage", "default_branch",
                                       "pushed_at", "fork", "private", "archived")} | {
            "owner": {"login": (r.get("owner") or {}).get("login")}}

    def rel(r):
        return {k: r.get(k) for k in ("tag_name", "name", "html_url", "published_at", "draft")} | {
            "assets": [{k: a.get(k) for k in ("name", "browser_download_url", "size", "download_count")}
                       for a in r.get("assets") or []]}
    if not isinstance(data, list):
        return data
    return [repo(x) if "stargazers_count" in x else rel(x) if "tag_name" in x else x for x in data]


# ================================================================ README 連結偵測
RULES = [
    ("apple", re.compile(r"(apps|itunes|testflight)\.apple\.com/", re.I)),
    ("play", re.compile(r"play\.google\.com/store/apps", re.I)),
    ("video", re.compile(r"(youtube\.com/(watch|shorts|embed|live|playlist|@)|youtu\.be/|vimeo\.com/\d|"
                         r"\.(mp4|webm|mov|m4v|avi|mkv)(\?|#|$))", re.I)),
    ("download", re.compile(r"(/releases/(download|latest|tag)\b|\.(apk|aab|ipa|exe|msi|dmg|pkg|zip|7z|rar|deb|"
                            r"AppImage)(\?|#|$))", re.I)),
]
GH_VIDEO_LINE = re.compile(r"^[ \t]*(https://github\.com/user-attachments/assets/[\w-]+)[ \t]*$", re.M)
VIDEO_TAG = re.compile(r"<(?:video|source)\b[^>]*?\bsrc=[\"']?(https?://[^\"'\s>]+)", re.I)
URL_PATTERN = re.compile(r"https?://[^\s<>\"'`)\]]+", re.I)


def extract_links(*texts):
    """從 README、說明、首頁找出 App Store、Play、影片、下載網址。"""
    out = {"apple": [], "play": [], "video": [], "download": []}
    seen = set()
    for text in texts:
        if not text:
            continue
        # README 裡的影片：單獨一行的 GitHub 影片附件、<video src>／<source src>、.mp4 等影片檔
        for m in list(GH_VIDEO_LINE.finditer(text)) + list(VIDEO_TAG.finditer(text)):
            if m.group(1) not in seen:
                seen.add(m.group(1))
                out["video"].append(m.group(1))
        for raw in URL_PATTERN.findall(text):
            url = re.sub(r"[.,;:!?。，、）]+$", "", raw)
            if url in seen:
                continue
            seen.add(url)
            for kind, rx in RULES:
                if rx.search(url):
                    out[kind].append(url)
                    break
    return out


def youtube_id(url):
    for rx in (r"youtu\.be/([\w-]{11})", r"[?&]v=([\w-]{11})", r"youtube\.com/(?:shorts|embed|live)/([\w-]{11})"):
        m = re.search(rx, url or "")
        if m:
            return m.group(1)
    return None
