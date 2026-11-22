"""共用基礎：錯誤類別、登入與權限、使用者、公司與 GitHub 設定、操作紀錄。

所有規則都在服務層檢查（畫面只負責顯示），日後手機版透過 API 也共用同一套。
"""
import json

from . import passwords
from .seed import FUNC_NAMES, FUNCS, LEVEL_NAMES, ROLES


class BizError(Exception):
    """可以直接顯示給使用者看的錯誤。"""


class Base:
    def __init__(self, db):
        self.db = db
        self.user = None
        self.perms = {}

    # ================================================================ 登入、權限、紀錄
    @property
    def uid(self):
        return self.user["uid"] if self.user else ""

    def has_users(self) -> bool:
        return bool(self.db.value("SELECT COUNT(*) FROM sys_user"))

    def login(self, uid, pw):
        u = self.db.row("SELECT * FROM sys_user WHERE uid=%s", ((uid or "").strip(),))
        if not u or not passwords.verify(pw, u["pw_hash"]):
            self.db.exec("INSERT INTO sys_audit_log (uid, action, detail) VALUES (%s, 'login_fail', '')", (uid or "",))
            raise BizError("帳號或密碼錯誤")
        if not u["active"]:
            raise BizError("此帳號已停用，請洽系統管理員")
        self.user = u
        self.perms = {r["func"]: r["lvl"] for r in self.db.rows("SELECT func, lvl FROM sys_user_perm WHERE uid=%s",
                                                                 (u["uid"],))}
        self.db.exec("UPDATE sys_user SET last_login=NOW() WHERE uid=%s", (u["uid"],))
        self.log("login", u["uid"])
        return u

    def logout(self):
        if self.user:
            self.log("logout", self.uid)
        self.user, self.perms = None, {}

    def level(self, func) -> int:
        if not self.user:
            return 0
        if self.user["is_admin"]:
            return 2
        return int(self.perms.get(func, 0))

    def can(self, func, lvl=1) -> bool:
        return self.level(func) >= lvl

    def need(self, func, lvl=2):
        if not self.can(func, lvl):
            raise BizError("您沒有「%s」的%s權限" % (FUNC_NAMES.get(func, func), LEVEL_NAMES.get(lvl, "")))

    def log(self, action, target="", detail=""):
        try:
            self.db.exec("INSERT INTO sys_audit_log (uid, action, target, detail) VALUES (%s, %s, %s, %s)",
                         (self.uid, action, str(target)[:80], str(detail)[:1000]))
        except Exception:
            pass

    # ================================================================ 使用者
    def users(self):
        rows = self.db.rows("SELECT uid, name, role, dept, is_admin, active, last_login FROM sys_user ORDER BY uid")
        perms = self.db.rows("SELECT uid, func, lvl FROM sys_user_perm")
        for u in rows:
            u["perms"] = {p["func"]: p["lvl"] for p in perms if p["uid"] == u["uid"]}
        return rows

    def user_options(self):
        return [(r["uid"], r["name"]) for r in
                self.db.rows("SELECT uid, name FROM sys_user WHERE active=1 ORDER BY uid")]

    def create_first_admin(self, uid, name, pw):
        if self.has_users():
            raise BizError("系統已有使用者")
        self._check_new_password(pw)
        self._insert_user(uid, name, pw, "系統管理員", True)

    def save_user(self, uid, name, role, is_admin, active, perms, pw=None, is_new=False, dept=""):
        self.need("SYS")
        uid = (uid or "").strip()
        if not uid or not (name or "").strip():
            raise BizError("帳號與姓名必填")
        if is_new:
            if self.db.value("SELECT 1 FROM sys_user WHERE uid=%s", (uid,)):
                raise BizError("帳號 %s 已存在" % uid)
            self._check_new_password(pw)
            self._insert_user(uid, name, pw, role, is_admin, perms, dept)
        else:
            if uid == self.uid and (not is_admin or not active) and self.user["is_admin"]:
                raise BizError("不能取消自己的管理員身分或停用自己")
            if (not is_admin or not active) and not self.db.value(
                    "SELECT COUNT(*) FROM sys_user WHERE is_admin=1 AND active=1 AND uid<>%s", (uid,)):
                raise BizError("至少要保留一位啟用中的系統管理員")
            self.db.exec("UPDATE sys_user SET name=%s, role=%s, dept=%s, is_admin=%s, active=%s WHERE uid=%s",
                         (name.strip(), role, dept or "", int(bool(is_admin)), int(bool(active)), uid))
            self._write_perms(uid, perms)
            if pw:
                self._check_new_password(pw)
                self.db.exec("UPDATE sys_user SET pw_hash=%s WHERE uid=%s", (passwords.make(pw), uid))
        self.log("user_save", uid, json.dumps({"role": role, "admin": bool(is_admin), "perms": perms},
                                               ensure_ascii=False))

    def _insert_user(self, uid, name, pw, role, is_admin, perms=None, dept=""):
        uid = (uid or "").strip()
        if not uid:
            raise BizError("請輸入帳號")
        self.db.exec("INSERT INTO sys_user (uid, name, pw_hash, role, dept, is_admin) VALUES (%s, %s, %s, %s, %s, %s)",
                     (uid, (name or uid).strip(), passwords.make(pw), role, dept or "", int(bool(is_admin))))
        self._write_perms(uid, perms if perms is not None else ROLES.get(role, {}))

    def _write_perms(self, uid, perms):
        self.db.exec("DELETE FROM sys_user_perm WHERE uid=%s", (uid,))
        self.db.exec_many("INSERT INTO sys_user_perm (uid, func, lvl) VALUES (%s, %s, %s)",
                          [(uid, f, int((perms or {}).get(f, 0))) for f, _, _ in FUNCS])

    @staticmethod
    def _check_new_password(pw):
        if len(pw or "") < 6:
            raise BizError("密碼至少 6 個字")

    def change_password(self, old, new):
        if not passwords.verify(old, self.db.value("SELECT pw_hash FROM sys_user WHERE uid=%s", (self.uid,))):
            raise BizError("舊密碼不正確")
        self._check_new_password(new)
        self.db.exec("UPDATE sys_user SET pw_hash=%s WHERE uid=%s", (passwords.make(new), self.uid))
        self.log("password", self.uid)

    def delete_user(self, uid):
        self.need("SYS")
        if uid == self.uid:
            raise BizError("不能刪除自己")
        if self.db.value("SELECT 1 FROM sys_audit_log WHERE uid=%s AND action NOT IN ('login','logout','login_fail') "
                         "LIMIT 1", (uid,)):
            raise BizError("此帳號已有操作紀錄，請改為「停用」以保留稽核軌跡")
        self.db.exec("DELETE FROM sys_user_perm WHERE uid=%s", (uid,))
        self.db.exec("DELETE FROM sys_user WHERE uid=%s", (uid,))
        self.log("user_delete", uid)

    def audit(self, limit=500, uid="", target=""):
        where, args = [], []
        if uid:
            where.append("uid=%s")
            args.append(uid)
        if target:
            where.append("target LIKE %s")
            args.append("%" + target + "%")
        sql = "SELECT * FROM sys_audit_log%s ORDER BY id DESC LIMIT %%s" % (
            (" WHERE " + " AND ".join(where)) if where else "")
        return self.db.rows(sql, tuple(args) + (limit,))

    # ================================================================ 公司與 GitHub 設定
    def company(self):
        c = self.db.row("SELECT * FROM sys_company WHERE id=1") or {}
        if c and not self.can("SYS", 2):
            c = dict(c, github_token="●●●●" if c.get("github_token") else "")
        return c

    def github_token(self):
        """內部使用（彙整時），不經過權限遮蔽。"""
        return self.db.value("SELECT github_token FROM sys_company WHERE id=1") or ""

    def save_company(self, name=None, github_owner=None, github_token=None, include_forks=None, auto_sync=None):
        self.need("SYS")
        vals = {}
        if name is not None:
            vals["name"] = (name or "").strip()[:120]
        if github_owner is not None:
            owner = normalize_owner(github_owner)
            if not owner:
                raise BizError("GitHub 帳號名稱不正確（只能是英文、數字與減號，不是 email）")
            vals["github_owner"] = owner
        if github_token is not None and github_token != "●●●●":
            vals["github_token"] = (github_token or "").strip()
        if include_forks is not None:
            vals["include_forks"] = int(bool(include_forks))
        if auto_sync is not None:
            vals["auto_sync"] = int(bool(auto_sync))
        if vals:
            self.db.exec("UPDATE sys_company SET %s WHERE id=1" % ", ".join("%s=%%s" % k for k in vals),
                         tuple(vals.values()))
        shown = {k: ("（已變更）" if k == "github_token" else v) for k, v in vals.items()}
        self.log("company", "", json.dumps(shown, ensure_ascii=False))


def normalize_owner(text):
    """接受帳號、@帳號、https://github.com/帳號、帳號@users.noreply…，取出 GitHub 帳號名稱。"""
    import re
    v = (text or "").strip()
    v = re.sub(r"^https?://github\.com/", "", v, flags=re.I).lstrip("@")
    v = re.split(r"[/?#]", v)[0]
    if "@" in v:
        v = v.split("@")[0]
    return v if re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", v or "") else ""
