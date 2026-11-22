"""專案彙整服務：專案清單、便利貼、平台進度、分類、待辦、彙整 GitHub、匯入匯出、統計。"""
import datetime as dt
import json
import re

from .core import BizError, normalize_owner
from .github import Gateway, RateLimit, extract_links
from .seed import PALETTE, PLATFORM_NAMES, PLATFORMS, PLT_STATUS, PRJ_STATUS

NOTE_FIELDS = ("status", "owner_uid", "apple_url", "apple_note", "play_url", "play_note", "video_url",
               "download_url", "live_url", "memo")
LIST_COLS = ("name, full_name, url, title, description, stars, forks, language, topics, homepage, pushed_at, "
             "is_fork, is_private, archived, rel_tag, rel_url, rel_published, rel_assets, source, gone, "
             "LEFT(readme, 20000) AS readme_head")


def _dt(s):
    """GitHub 時間字串（UTC，Z 結尾）→ 台灣時間 datetime。"""
    if not s:
        return None
    if isinstance(s, dt.datetime):
        return s
    try:
        t = dt.datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S")
        return t + dt.timedelta(hours=8) if str(s).endswith("Z") else t
    except ValueError:
        return None


def readme_heading(text):
    """README 的第一個大標題（# 主題 或 HTML <h1>），沒有就回傳空字串。"""
    for line in (text or "").splitlines()[:60]:
        s = line.strip()
        m = re.match(r"^#{1,2}\s+(.+?)\s*#*$", s) or re.match(r"^<h1[^>]*>(.+?)</h1>", s, re.I)
        if m:
            t = re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)", "", m.group(1))
            t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t).replace("**", "")
            t = re.sub(r"https?://\S+", "", t).strip(" -｜|：:")
            if t:
                return t[:120]
    return ""


def short_title(p):
    """專案主題：手動中文名稱 → README 大標題 → 說明冒號前的字 → 專案名稱。"""
    if p.get("title"):
        return p["title"]
    if p.get("heading"):
        return p["heading"]
    d = (p.get("description") or "").strip()
    m = re.match(r"^([^：:，,。（(]{2,24})[：:]", d)
    return m.group(1).strip() if m else p["name"]


class HubMixin:
    # ================================================================ 共用
    def _note_map(self):
        return {r["name"]: r for r in self.db.rows("SELECT * FROM prj_note")}

    def _assign_map(self):
        out = {}
        for r in self.db.rows("SELECT name, cat_id FROM prj_assign"):
            out.setdefault(r["name"], set()).add(r["cat_id"])
        return out

    def _platform_map(self):
        out = {}
        for r in self.db.rows("SELECT * FROM prj_platform"):
            out.setdefault(r["name"], {})[r["platform"]] = r
        return out

    def settings_row(self):
        return self.db.row("SELECT * FROM sys_company WHERE id=1") or {}

    def _decorate(self, p, note, cats, plats, cat_by_id, open_tasks=0):
        note = note or {}
        det = extract_links(p.get("readme_head") or p.get("readme") or "", p.get("description") or "",
                            p.get("homepage") or "")
        p["note"] = note
        p["heading"] = readme_heading(p.get("readme_head") or p.get("readme") or "")
        p["display"] = short_title(p)
        p["apple"] = note.get("apple_url") or (det["apple"][0] if det["apple"] else "")
        p["play"] = note.get("play_url") or (det["play"][0] if det["play"] else "")
        p["video"] = note.get("video_url") or (det["video"][0] if det["video"] else "")
        p["download"] = note.get("download_url") or p.get("rel_url") or (det["download"][0] if det["download"] else "")
        hp = p.get("homepage") or ""
        p["live"] = note.get("live_url") or (hp if re.match(r"^https?://", hp) else "")
        p["detected"] = det
        p["cats"] = [cat_by_id[c] for c in sorted(cats or (), key=lambda c: cat_by_id[c]["sort"] if c in cat_by_id
                                                    else 0) if c in cat_by_id]
        p["platforms"] = plats or {}
        p["status"] = note.get("status") or ""
        p["open_tasks"] = open_tasks
        try:
            p["assets"] = json.loads(p.get("rel_assets") or "[]")
        except ValueError:
            p["assets"] = []
        p.pop("readme_head", None)
        return p

    # ================================================================ 查詢
    def categories(self):
        rows = self.db.rows("SELECT * FROM prj_category ORDER BY sort, id")
        cnt = {r["cat_id"]: r["n"] for r in self.db.rows("SELECT cat_id, COUNT(*) AS n FROM prj_assign GROUP BY cat_id")}
        for r in rows:
            r["count"] = cnt.get(r["id"], 0)
        return rows

    def all_projects(self, include_forks=None, include_gone=False):
        self.need("PRJ", 1)
        if include_forks is None:
            include_forks = bool(self.settings_row().get("include_forks", 1))
        where = []
        if not include_forks:
            where.append("is_fork=0")
        if not include_gone:
            where.append("gone=0")
        rows = self.db.rows("SELECT %s FROM prj_project%s" % (LIST_COLS, (" WHERE " + " AND ".join(where))
                                                                if where else ""))
        notes, assigns, plats = self._note_map(), self._assign_map(), self._platform_map()
        cat_by_id = {c["id"]: c for c in self.categories()}
        tasks = {r["name"]: r["n"] for r in
                 self.db.rows("SELECT name, COUNT(*) AS n FROM prj_task WHERE done=0 GROUP BY name")}
        return [self._decorate(p, notes.get(p["name"]), assigns.get(p["name"]), plats.get(p["name"]), cat_by_id,
                               tasks.get(p["name"], 0)) for p in rows]

    def list_projects(self, tab="all", keyword="", sort="pushed", filters=(), status="", projects=None):
        arr = projects if projects is not None else self.all_projects()
        if tab == "uncategorized":
            arr = [p for p in arr if not p["cats"]]
        elif tab not in ("all", "", None):
            arr = [p for p in arr if any(c["id"] == int(tab) for c in p["cats"])]
        kw = (keyword or "").strip().lower()
        if kw:
            arr = [p for p in arr if kw in " ".join([p["name"], p.get("title") or "", p.get("description") or "",
                                                    p.get("language") or "", p.get("topics") or "",
                                                    (p["note"] or {}).get("memo") or ""]).lower()]
        for f in filters or ():
            arr = [p for p in arr if p.get(f)]
        if status:
            arr = [p for p in arr if p["status"] == status]
        keys = {"pushed": lambda p: (p.get("pushed_at") or dt.datetime.min), "stars": lambda p: (p["stars"], p["name"]),
                "name": lambda p: p["name"].lower(), "release": lambda p: (p.get("rel_published") or dt.datetime.min)}
        arr.sort(key=keys.get(sort, keys["pushed"]), reverse=sort != "name")
        return arr

    def tab_counts(self, projects):
        counts = {"all": len(projects), "uncategorized": 0}
        for p in projects:
            if not p["cats"]:
                counts["uncategorized"] += 1
            for c in p["cats"]:
                counts[c["id"]] = counts.get(c["id"], 0) + 1
        return counts

    def project(self, name):
        self.need("PRJ", 1)
        p = self.db.row("SELECT * FROM prj_project WHERE name=%s", (name,))
        if not p:
            raise BizError("找不到專案 %s" % name)
        cat_by_id = {c["id"]: c for c in self.categories()}
        p = self._decorate(p, self.db.row("SELECT * FROM prj_note WHERE name=%s", (name,)),
                           self._assign_map().get(name), self._platform_map().get(name), cat_by_id)
        p["tasks"] = self.tasks(name=name, show_done=True)
        p["open_tasks"] = sum(1 for t in p["tasks"] if not t["done"])
        return p

    # ================================================================ 專案維護
    def save_note(self, name, **kw):
        self.need("PRJ", 2)
        if not self.db.value("SELECT 1 FROM prj_project WHERE name=%s", (name,)):
            raise BizError("找不到專案 %s" % name)
        old = self.db.row("SELECT * FROM prj_note WHERE name=%s", (name,)) or {}
        vals = {k: ("" if kw[k] is None else str(kw[k]).strip()) for k in NOTE_FIELDS if k in kw}
        for k in ("apple_url", "play_url", "video_url", "download_url", "live_url"):
            if vals.get(k) and not re.match(r"^https?://", vals[k]):
                raise BizError("網址要以 http:// 或 https:// 開頭：%s" % vals[k])
        if "status" in vals and vals["status"] not in PRJ_STATUS:
            raise BizError("專案狀態不正確")
        if "title" in kw:
            self.db.exec("UPDATE prj_project SET title=%s WHERE name=%s", ((kw["title"] or "").strip()[:120], name))
        merged = {k: old.get(k, "") or "" for k in NOTE_FIELDS}
        merged.update(vals)
        self.db.exec("REPLACE INTO prj_note (name, %s, updated_at, updated_by) VALUES (%%s, %s, NOW(), %%s)"
                     % (", ".join(NOTE_FIELDS), ", ".join(["%s"] * len(NOTE_FIELDS))),
                     (name, *[merged[k] for k in NOTE_FIELDS], self.uid))
        diff = {k: "%s → %s" % (old.get(k) or "", merged[k]) for k in NOTE_FIELDS if (old.get(k) or "") != merged[k]}
        if "title" in kw:
            diff["title"] = kw["title"] or ""
        self.log("note_save", name, json.dumps(diff, ensure_ascii=False))

    def add_project(self, name, title="", description="", url="", homepage=""):
        """手動新增（不在 GitHub 上的專案，例如私人或其他平台）。"""
        self.need("PRJ", 2)
        name = (name or "").strip()
        if not re.fullmatch(r"[\w.\-]{1,100}", name):
            raise BizError("專案名稱只能用英文、數字、底線、減號與點（最多 100 字）")
        if self.db.value("SELECT 1 FROM prj_project WHERE name=%s", (name,)):
            raise BizError("專案 %s 已存在" % name)
        self.db.exec("INSERT INTO prj_project (name, title, description, url, homepage, source, pushed_at) "
                     "VALUES (%s, %s, %s, %s, %s, 'manual', NOW())",
                     (name, (title or "").strip(), (description or "").strip(), (url or "").strip(),
                      (homepage or "").strip()))
        self.log("project_add", name, title or "")

    def delete_project(self, name):
        self.need("PRJ", 2)
        p = self.db.row("SELECT source, gone FROM prj_project WHERE name=%s", (name,))
        if not p:
            raise BizError("找不到專案")
        if p["source"] == "github" and not p["gone"]:
            raise BizError("GitHub 上的專案下次彙整會再出現；不想看到請改用分類或篩選，或到 GitHub 封存")
        with self.db.transaction():
            for t in ("prj_note", "prj_platform", "prj_assign", "prj_task", "prj_project"):
                self.db.exec("DELETE FROM %s WHERE name=%%s" % t, (name,))
        self.log("project_delete", name)

    # ================================================================ 平台進度
    def set_platform(self, name, platform, status, version="", note=""):
        self.need("PLT", 2)
        if platform not in PLATFORM_NAMES:
            raise BizError("平台代號不正確")
        status = int(status)
        if status not in PLT_STATUS:
            raise BizError("平台狀態不正確")
        old = self.db.row("SELECT * FROM prj_platform WHERE name=%s AND platform=%s", (name, platform)) or {}
        self.db.exec("REPLACE INTO prj_platform (name, platform, status, version, note, updated_at) "
                     "VALUES (%s, %s, %s, %s, %s, NOW())", (name, platform, status, (version or "").strip()[:30],
                                                            (note or "").strip()[:255]))
        self.log("platform", name, "%s：%s → %s %s" % (PLATFORM_NAMES[platform],
                                                      PLT_STATUS.get(old.get("status", 0))[0],
                                                      PLT_STATUS[status][0], version or ""))

    def matrix(self, tab="all", keyword=""):
        """平台進度總表。"""
        self.need("PLT", 1)
        return self.list_projects(tab, keyword, "name")

    @staticmethod
    def infer_platforms(assets, homepage="", tag=""):
        """依發佈檔名判斷哪些平台已發佈。"""
        found = {}
        for a in assets or []:
            n = (a.get("name") or "").lower()
            if n.endswith((".exe", ".msi")) or "setup" in n or "win" in n and n.endswith(".zip"):
                found["WIN"] = tag
            if n.endswith((".dmg", ".pkg")) or "mac" in n and n.endswith(".zip"):
                found["MAC"] = tag
            if n.endswith((".apk", ".aab")):
                found["AND"] = tag
            if n.endswith(".ipa"):
                found["IOS"] = tag
                found["IPAD"] = tag
        if re.match(r"^https?://", homepage or ""):
            found["WEB"] = ""
        return found

    def _auto_platforms(self, name, assets, homepage, tag):
        cur = {r["platform"]: r for r in self.db.rows("SELECT * FROM prj_platform WHERE name=%s", (name,))}
        n = 0
        for plat, ver in self.infer_platforms(assets, homepage, tag).items():
            row = cur.get(plat)
            if row and (row["status"] == 9 or (row["status"] == 4 and (row["version"] == ver or not ver))):
                continue
            self.db.exec("REPLACE INTO prj_platform (name, platform, status, version, note, updated_at) "
                         "VALUES (%s, %s, 4, %s, %s, NOW())",
                         (name, plat, ver or (row or {}).get("version", ""),
                          (row or {}).get("note") or "依發佈檔自動判斷"))
            n += 1
        return n

    # ================================================================ 分類
    def add_category(self, name, color=None):
        self.need("CAT", 2)
        name = (name or "").strip()
        if not name:
            raise BizError("分類名稱不可空白")
        if self.db.value("SELECT 1 FROM prj_category WHERE name=%s", (name,)):
            raise BizError("已有「%s」這個分類" % name)
        n = self.db.value("SELECT COUNT(*) FROM prj_category") or 0
        cid = self.db.exec("INSERT INTO prj_category (name, color, sort) VALUES (%s, %s, %s)",
                           (name[:40], color or PALETTE[n % len(PALETTE)], n + 1))
        self.log("cat_add", name)
        return cid

    def save_category(self, cid, name, color, rule=""):
        self.need("CAT", 2)
        name = (name or "").strip()
        if not name:
            raise BizError("分類名稱不可空白")
        if self.db.value("SELECT 1 FROM prj_category WHERE name=%s AND id<>%s", (name, cid)):
            raise BizError("已有「%s」這個分類" % name)
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color or ""):
            raise BizError("顏色格式不正確")
        old = self.db.row("SELECT * FROM prj_category WHERE id=%s", (cid,))
        self.db.exec("UPDATE prj_category SET name=%s, color=%s, rule=%s WHERE id=%s",
                     (name[:40], color.upper(), (rule or "").strip()[:160], cid))
        self.log("cat_save", name, "%s → %s" % (old and old["name"], name))

    def move_category(self, cid, delta):
        self.need("CAT", 2)
        cats = self.db.rows("SELECT id FROM prj_category ORDER BY sort, id")
        ids = [c["id"] for c in cats]
        i = ids.index(cid)
        j = i + delta
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            self.db.exec_many("UPDATE prj_category SET sort=%s WHERE id=%s", [(k + 1, x) for k, x in enumerate(ids)])

    def delete_category(self, cid):
        self.need("CAT", 2)
        name = self.db.value("SELECT name FROM prj_category WHERE id=%s", (cid,))
        with self.db.transaction():
            self.db.exec("DELETE FROM prj_assign WHERE cat_id=%s", (cid,))
            self.db.exec("DELETE FROM prj_category WHERE id=%s", (cid,))
        self.log("cat_delete", name or cid)

    def toggle_category(self, name, cid):
        self.need("CAT", 2)
        if self.db.value("SELECT 1 FROM prj_assign WHERE name=%s AND cat_id=%s", (name, cid)):
            self.db.exec("DELETE FROM prj_assign WHERE name=%s AND cat_id=%s", (name, cid))
            return False
        self.db.exec("INSERT IGNORE INTO prj_assign (name, cat_id) VALUES (%s, %s)", (name, cid))
        return True

    def auto_classify(self, only_uncategorized=True):
        """依分類的「自動分類規則」把專案放進分類（名稱、說明、主題含有規則中的字）。"""
        self.need("CAT", 2)
        cats = [c for c in self.categories() if (c["rule"] or "").strip()]
        rules = [(c["id"], [w.strip().lower() for w in c["rule"].split(",") if w.strip()]) for c in cats]
        assigned = self._assign_map()
        n = 0
        for p in self.db.rows("SELECT name, description, topics FROM prj_project WHERE gone=0"):
            if only_uncategorized and assigned.get(p["name"]):
                continue
            hay = " ".join([p["name"], p["description"] or "", p["topics"] or ""]).lower()
            for cid, words in rules:
                if any(_rule_hit(w, p["name"].lower(), hay) for w in words):
                    if cid not in assigned.get(p["name"], set()):
                        self.db.exec("INSERT IGNORE INTO prj_assign (name, cat_id) VALUES (%s, %s)", (p["name"], cid))
                        assigned.setdefault(p["name"], set()).add(cid)
                        n += 1
        self.log("auto_classify", "", "%d 筆" % n)
        return n

    # ================================================================ 待辦
    def tasks(self, name=None, show_done=False, uid=""):
        self.need("TASK", 1) if name is None else self.need("PRJ", 1)
        where, args = [], []
        if name is not None:
            where.append("t.name=%s")
            args.append(name)
        if not show_done:
            where.append("t.done=0")
        if uid:
            where.append("t.uid=%s")
            args.append(uid)
        return self.db.rows("SELECT t.*, u.name AS uname FROM prj_task t LEFT JOIN sys_user u ON u.uid=t.uid%s "
                            "ORDER BY t.done, t.priority, t.due IS NULL, t.due, t.id"
                            % ((" WHERE " + " AND ".join(where)) if where else ""), tuple(args))

    def save_task(self, tid, name, title, platform="", priority=2, due=None, uid=""):
        self.need("TASK", 2)
        title = (title or "").strip()
        if not title:
            raise BizError("請輸入待辦事項")
        if platform and platform not in PLATFORM_NAMES:
            raise BizError("平台代號不正確")
        if due in ("",):
            due = None
        if due is not None and not isinstance(due, dt.date):
            from . import rocdate
            try:
                due = rocdate.read(due)
            except ValueError as e:
                raise BizError(str(e))
        args = (name or "", title[:255], platform or "", int(priority or 2), due, uid or "")
        if tid:
            self.db.exec("UPDATE prj_task SET name=%s, title=%s, platform=%s, priority=%s, due=%s, uid=%s WHERE id=%s",
                         args + (tid,))
        else:
            tid = self.db.exec("INSERT INTO prj_task (name, title, platform, priority, due, uid, created_by) "
                               "VALUES (%s, %s, %s, %s, %s, %s, %s)", args + (self.uid,))
        self.log("task_save", name or "", title)
        return tid

    def toggle_task(self, tid):
        self.need("TASK", 2)
        self.db.exec("UPDATE prj_task SET done=1-done, done_at=IF(done=1, NOW(), NULL) WHERE id=%s", (tid,))
        t = self.db.row("SELECT name, title, done FROM prj_task WHERE id=%s", (tid,))
        if t:
            self.log("task_done" if t["done"] else "task_undo", t["name"], t["title"])

    def delete_task(self, tid):
        self.need("TASK", 2)
        t = self.db.row("SELECT name, title FROM prj_task WHERE id=%s", (tid,))
        self.db.exec("DELETE FROM prj_task WHERE id=%s", (tid,))
        if t:
            self.log("task_delete", t["name"], t["title"])

    # ================================================================ 彙整 GitHub
    def sync_github(self, progress=None, releases="auto", stop=None):
        """① 專案清單 ② README ③ 最新發佈版本（API 次數不夠時改用不扣次數的方式）。回傳統計 dict。"""
        self.need("SYNC", 2)
        say = progress or (lambda text, done=0, total=0: None)
        st = self.settings_row()
        owner = normalize_owner(st.get("github_owner") or "")
        if not owner:
            raise BizError("請先到「GitHub 設定」填寫 GitHub 帳號名稱")
        gw = Gateway(self.db, self.github_token())
        say("① 讀取 %s 的專案清單…" % owner)
        try:
            repos = gw.list_repos(owner)
        except RateLimit as e:
            raise BizError(str(e))
        except OSError as e:
            raise BizError("連不到 GitHub，請確認網路：%s" % e)
        now = dt.datetime.now()
        known = {r["name"]: r for r in self.db.rows("SELECT name, pushed_at, readme IS NOT NULL AS has_readme, "
                                                    "rel_checked, rel_tag, source FROM prj_project")}
        stat = dict(total=len(repos), new=0, readme=0, release=0, release_free=0, platforms=0, gone=0)
        fresh = set()
        for r in repos:
            name = r["name"]
            fresh.add(name)
            vals = (r.get("full_name") or "", r.get("html_url") or "", r.get("description") or "",
                    int(r.get("stargazers_count") or 0), int(r.get("forks_count") or 0), r.get("language") or "",
                    ",".join(r.get("topics") or []), r.get("homepage") or "", r.get("default_branch") or "main",
                    _dt(r.get("pushed_at")), int(bool(r.get("fork"))), int(bool(r.get("private"))),
                    int(bool(r.get("archived"))), now)
            if name in known:
                self.db.exec("UPDATE prj_project SET full_name=%s, url=%s, description=%s, stars=%s, forks=%s, "
                             "language=%s, topics=%s, homepage=%s, default_branch=%s, pushed_at=%s, is_fork=%s, "
                             "is_private=%s, archived=%s, synced_at=%s, source='github', gone=0 WHERE name=%s",
                             vals + (name,))
            else:
                self.db.exec("INSERT INTO prj_project (full_name, url, description, stars, forks, language, topics, "
                             "homepage, default_branch, pushed_at, is_fork, is_private, archived, synced_at, name) "
                             "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", vals + (name,))
                stat["new"] += 1
        # GitHub 上已經不見的專案（刪除或改名）
        for name, k in known.items():
            if k["source"] == "github" and name not in fresh:
                self.db.exec("UPDATE prj_project SET gone=1 WHERE name=%s", (name,))
                stat["gone"] += 1

        # ② README：有更新過（pushed_at 變了）或還沒抓過的才抓
        todo = [r for r in repos if r["name"] not in known or not known[r["name"]]["has_readme"]
                or _dt(r.get("pushed_at")) != known[r["name"]]["pushed_at"]]
        for i, r in enumerate(todo):
            if stop and stop():
                break
            say("② 讀取 README：%s" % r["name"], i + 1, len(todo))
            text = gw.readme(r["full_name"], r.get("default_branch"), r.get("private"))
            self.db.exec("UPDATE prj_project SET readme=%s WHERE name=%s", (text, r["name"]))
            stat["readme"] += 1

        # ③ 最新發佈版本：先查有變動的，再查其他的
        changed = {r["name"] for r in todo}
        order = sorted(repos, key=lambda r: (r["name"] not in changed, not known.get(r["name"], {}).get("rel_checked")))
        for i, r in enumerate(order):
            if stop and stop():
                break
            say("③ 查最新發佈版本：%s" % r["name"], i + 1, len(order))
            rel, free = None, False
            try:
                if releases != "free" and gw.can_spend(reserve=3):
                    rel = gw.latest_release(r["full_name"])
                else:
                    raise RateLimit("")
            except RateLimit:
                free = True
                try:
                    rel = gw.latest_release_free(r["full_name"])
                except Exception:
                    continue
            except Exception:
                continue
            self._save_release(r["name"], rel, r.get("homepage") or "")
            stat["release_free" if free else "release"] += 1
            stat["platforms"] += self._auto_platforms(r["name"], (rel or {}).get("assets") or [],
                                                      r.get("homepage") or "", (rel or {}).get("tag_name") or "")
        # 新專案依規則自動分類
        stat["classified"] = self.auto_classify(only_uncategorized=True) if self.can("CAT", 2) else 0
        note = "共 %(total)d 個專案，新增 %(new)d、README %(readme)d、發佈版本 %(release)d" % stat
        if stat["release_free"]:
            note += "（另 %d 個改用發佈頁查詢）" % stat["release_free"]
        if gw.remaining is not None:
            note += "；GitHub 剩餘次數 %s/%s" % (gw.remaining, gw.limit)
            stat["remaining"], stat["limit"] = gw.remaining, gw.limit
        self.db.exec("UPDATE sys_company SET last_sync_at=NOW(), last_sync_note=%s WHERE id=1", (note[:255],))
        self.log("sync", owner, note)
        stat["note"] = note
        say("完成：" + note, 1, 1)
        return stat

    def _save_release(self, name, rel, homepage=""):
        if not rel:
            self.db.exec("UPDATE prj_project SET rel_tag='', rel_name='', rel_url='', rel_published=NULL, "
                         "rel_assets='[]', rel_checked=1 WHERE name=%s", (name,))
            return
        assets = [dict(name=a.get("name"), url=a.get("browser_download_url") or a.get("url"), size=a.get("size") or 0,
                       downloads=a.get("download_count")) for a in rel.get("assets") or []]
        self.db.exec("UPDATE prj_project SET rel_tag=%s, rel_name=%s, rel_url=%s, rel_published=COALESCE(%s, "
                     "IF(rel_tag=%s, rel_published, NULL)), rel_assets=%s, rel_checked=1 WHERE name=%s",
                     (rel.get("tag_name") or "", rel.get("name") or rel.get("tag_name") or "", rel.get("html_url") or "",
                      _dt(rel.get("published_at")), rel.get("tag_name") or "", json.dumps(assets, ensure_ascii=False),
                      name))

    # ================================================================ 匯入匯出
    def import_html(self, path):
        """匯入舊版「Achir1015專案彙整.html」內附的專案快照（專案清單、README、發佈版本）。"""
        self.need("SYNC", 2)
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        m = re.search(r'<script[^>]*id="bundled-snapshot"[^>]*>(.*?)</script>', text, re.S)
        if not m:
            raise BizError("這個網頁裡找不到專案快照（bundled-snapshot）")
        try:
            snap = json.loads(m.group(1))
        except ValueError:
            raise BizError("專案快照格式不正確")
        return self._import_snapshot(snap)

    def _import_snapshot(self, snap):
        projects = snap.get("projects") or []
        known = {r["name"] for r in self.db.rows("SELECT name FROM prj_project")}
        n_new = n_upd = 0
        with self.db.transaction():
            for p in projects:
                name = p.get("name")
                if not name:
                    continue
                vals = (p.get("fullName") or "", p.get("url") or "", p.get("description") or "", int(p.get("stars") or 0),
                        int(p.get("forks") or 0), p.get("language") or "", ",".join(p.get("topics") or []),
                        p.get("homepage") or "", p.get("defaultBranch") or "main", _dt(p.get("pushedAt")),
                        int(bool(p.get("isFork"))), int(bool(p.get("isPrivate"))), int(bool(p.get("archived"))),
                        p.get("readme"))
                if name in known:
                    self.db.exec("UPDATE prj_project SET full_name=%s, url=%s, description=%s, stars=%s, forks=%s, "
                                 "language=%s, topics=%s, homepage=%s, default_branch=%s, pushed_at=%s, is_fork=%s, "
                                 "is_private=%s, archived=%s, readme=COALESCE(%s, readme), gone=0 WHERE name=%s",
                                 vals + (name,))
                    n_upd += 1
                else:
                    self.db.exec("INSERT INTO prj_project (full_name, url, description, stars, forks, language, topics,"
                                 " homepage, default_branch, pushed_at, is_fork, is_private, archived, readme, name) "
                                 "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", vals + (name,))
                    known.add(name)
                    n_new += 1
                rel = p.get("release")
                if rel:
                    assets = [dict(name=a.get("name"), url=a.get("url"), size=a.get("size") or 0,
                                   downloads=a.get("downloadCount")) for a in rel.get("assets") or []]
                    self.db.exec("UPDATE prj_project SET rel_tag=%s, rel_name=%s, rel_url=%s, rel_published=%s, "
                                 "rel_assets=%s, rel_checked=1 WHERE name=%s",
                                 (rel.get("tagName") or "", rel.get("name") or "", rel.get("htmlUrl") or "",
                                  _dt(rel.get("publishedAt")), json.dumps(assets, ensure_ascii=False), name))
                    self._auto_platforms(name, [{"name": a["name"]} for a in assets], p.get("homepage") or "",
                                         rel.get("tagName") or "")
                elif rel is None and "release" in p:
                    self.db.exec("UPDATE prj_project SET rel_checked=1 WHERE name=%s", (name,))
                if p.get("note"):
                    self._import_note(name, p["note"])
        self.log("import_html", "", "新增 %d、更新 %d" % (n_new, n_upd))
        return dict(new=n_new, updated=n_upd, total=len(projects))

    def _import_note(self, name, n):
        """舊網頁的便利貼（appleUrl…）或本系統的欄位名稱都可以。"""
        m = {"appleUrl": "apple_url", "appleNote": "apple_note", "playUrl": "play_url", "playNote": "play_note",
             "videoUrl": "video_url", "downloadUrl": "download_url", "memo": "memo"}
        vals = {m.get(k, k): v for k, v in n.items() if m.get(k, k) in NOTE_FIELDS and v}
        if not vals:
            return
        old = self.db.row("SELECT * FROM prj_note WHERE name=%s", (name,)) or {}
        merged = {k: old.get(k, "") or "" for k in NOTE_FIELDS}
        merged.update({k: str(v) for k, v in vals.items()})
        self.db.exec("REPLACE INTO prj_note (name, %s, updated_at, updated_by) VALUES (%%s, %s, NOW(), %%s)"
                     % (", ".join(NOTE_FIELDS), ", ".join(["%s"] * len(NOTE_FIELDS))),
                     (name, *[merged[k] for k in NOTE_FIELDS], self.uid))

    def export_backup(self):
        """匯出「手動整理的東西」：分類、對應、便利貼、中文名稱、平台進度、待辦、手動新增的專案。"""
        self.need("PRJ", 1)
        cats = self.db.rows("SELECT id, name, color, sort, rule FROM prj_category ORDER BY sort, id")
        assign = {}
        for r in self.db.rows("SELECT name, cat_id FROM prj_assign"):
            assign.setdefault(r["name"], []).append(r["cat_id"])

        def clean(rows, drop=()):
            out = []
            for r in rows:
                out.append({k: (v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v)
                            for k, v in r.items() if k not in drop})
            return out
        return dict(app="資料助秘專案彙整", version=1, exportedAt=dt.datetime.now().isoformat(timespec="seconds"),
                    categories=clean(cats), assignments=assign,
                    notes={r["name"]: {k: r[k] for k in NOTE_FIELDS} for r in self.db.rows("SELECT * FROM prj_note")},
                    titles={r["name"]: r["title"] for r in self.db.rows("SELECT name, title FROM prj_project "
                                                                        "WHERE title<>''")},
                    platforms=clean(self.db.rows("SELECT name, platform, status, version, note FROM prj_platform")),
                    tasks=clean(self.db.rows("SELECT name, title, platform, priority, due, uid, done FROM prj_task")),
                    manual=clean(self.db.rows("SELECT name, title, description, url, homepage FROM prj_project "
                                              "WHERE source='manual'")))

    def import_backup(self, data):
        """匯入備份：本系統匯出的檔案，或舊版網頁「匯出備份」的 JSON（categories＋notes）。"""
        self.need("SYNC", 2)
        if not isinstance(data, dict):
            raise BizError("備份檔格式不正確")
        stat = dict(categories=0, assigned=0, notes=0, platforms=0, tasks=0)
        with self.db.transaction():
            cats = data.get("categories")
            assign = data.get("assignments")
            if isinstance(cats, dict):                       # 舊網頁：{categories:[…], assignments:{…}}
                assign = cats.get("assignments") or {}
                cats = cats.get("categories") or []
            idmap = {}
            for i, c in enumerate(cats or []):
                name = (c.get("name") or "").strip()
                if not name:
                    continue
                cid = self.db.value("SELECT id FROM prj_category WHERE name=%s", (name,))
                if not cid:
                    n = self.db.value("SELECT COUNT(*) FROM prj_category") or 0
                    cid = self.db.exec("INSERT INTO prj_category (name, color, sort, rule) VALUES (%s, %s, %s, %s)",
                                       (name[:40], (c.get("color") or PALETTE[n % 8]).upper()[:9], n + 1,
                                        c.get("rule") or ""))
                    stat["categories"] += 1
                elif c.get("rule"):
                    self.db.exec("UPDATE prj_category SET rule=%s WHERE id=%s AND rule=''", (c["rule"], cid))
                idmap[str(c.get("id"))] = cid
            names = {r["name"] for r in self.db.rows("SELECT name FROM prj_project")}
            for m in data.get("manual") or []:
                if m.get("name") and m["name"] not in names:
                    self.db.exec("INSERT INTO prj_project (name, title, description, url, homepage, source) "
                                 "VALUES (%s, %s, %s, %s, %s, 'manual')",
                                 (m["name"], m.get("title") or "", m.get("description") or "", m.get("url") or "",
                                  m.get("homepage") or ""))
                    names.add(m["name"])
            for name, ids in (assign or {}).items():
                for old_id in ids or []:
                    cid = idmap.get(str(old_id))
                    if cid and name in names and not self.db.value(
                            "SELECT 1 FROM prj_assign WHERE name=%s AND cat_id=%s", (name, cid)):
                        self.db.exec("INSERT INTO prj_assign (name, cat_id) VALUES (%s, %s)", (name, cid))
                        stat["assigned"] += 1
            for name, n in (data.get("notes") or {}).items():
                if isinstance(n, dict):
                    if name not in names:
                        continue
                    self._import_note(name, n)
                    stat["notes"] += 1
            for name, t in (data.get("titles") or {}).items():
                self.db.exec("UPDATE prj_project SET title=%s WHERE name=%s AND title=''", (t, name))
            for p in data.get("platforms") or []:
                if p.get("platform") in PLATFORM_NAMES:
                    self.db.exec("REPLACE INTO prj_platform (name, platform, status, version, note, updated_at) "
                                 "VALUES (%s, %s, %s, %s, %s, NOW())",
                                 (p["name"], p["platform"], int(p.get("status") or 0), p.get("version") or "",
                                  p.get("note") or ""))
                    stat["platforms"] += 1
            have = {(r["name"], r["title"]) for r in self.db.rows("SELECT name, title FROM prj_task")}
            for t in data.get("tasks") or []:
                if t.get("title") and (t.get("name") or "", t["title"]) not in have:
                    self.db.exec("INSERT INTO prj_task (name, title, platform, priority, due, uid, done, created_by) "
                                 "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                                 (t.get("name") or "", t["title"], t.get("platform") or "", int(t.get("priority") or 2),
                                  (t.get("due") or None), t.get("uid") or "", int(bool(t.get("done"))), self.uid))
                    stat["tasks"] += 1
        self.log("import_backup", "", json.dumps(stat, ensure_ascii=False))
        return stat

    # ================================================================ 首頁與統計
    def dashboard(self):
        ps = self.all_projects()
        st = self.settings_row()
        plat = {code: sum(1 for p in ps if (p["platforms"].get(code) or {}).get("status") == 4)
                for code, *_ in PLATFORMS}
        recent = sorted(ps, key=lambda p: p.get("pushed_at") or dt.datetime.min, reverse=True)[:8]
        week = dt.datetime.now() - dt.timedelta(days=7)
        return dict(
            total=len(ps), active_week=sum(1 for p in ps if p.get("pushed_at") and p["pushed_at"] >= week),
            with_release=sum(1 for p in ps if p.get("rel_tag")), apple=sum(1 for p in ps if p["apple"]),
            play=sum(1 for p in ps if p["play"]), live=sum(1 for p in ps if p["live"]),
            video=sum(1 for p in ps if p["video"]), uncategorized=sum(1 for p in ps if not p["cats"]),
            platforms=plat, recent=recent, open_tasks=self.db.value("SELECT COUNT(*) FROM prj_task WHERE done=0") or 0,
            last_sync=st.get("last_sync_at"), last_note=st.get("last_sync_note") or "", projects=ps,
            cats=[(c, sum(1 for p in ps if any(x["id"] == c["id"] for x in p["cats"]))) for c in self.categories()])

    def stats(self):
        self.need("RPT", 1)
        ps = self.all_projects()
        langs = {}
        for p in ps:
            k = p.get("language") or "（未標示）"
            langs[k] = langs.get(k, 0) + 1
        by_cat = []
        for c in self.categories():
            mine = [p for p in ps if any(x["id"] == c["id"] for x in p["cats"])]
            row = dict(name=c["name"], color=c["color"], total=len(mine),
                       release=sum(1 for p in mine if p.get("rel_tag")), stars=sum(p["stars"] for p in mine))
            for code, *_ in PLATFORMS:
                row[code] = sum(1 for p in mine if (p["platforms"].get(code) or {}).get("status") == 4)
            by_cat.append(row)
        plat = []
        for code, pname, *_ in PLATFORMS:
            row = dict(code=code, name=pname)
            for s in PLT_STATUS:
                row[s] = sum(1 for p in ps if (p["platforms"].get(code) or {}).get("status", 0) == s)
            plat.append(row)
        return dict(langs=sorted(langs.items(), key=lambda x: -x[1]), by_cat=by_cat, platforms=plat, total=len(ps))


def _rule_hit(word, name, hay):
    """規則字很短（例如 go）時只比對專案名稱的一段，避免誤判。"""
    if len(word) <= 3 and word.isascii():
        return word in re.split(r"[-_.]", name)
    return word in hay
