"""公司內的線上版：桌面版另外開一個網頁服務，同一個網路的電腦、平板用瀏覽器登入使用。

做法：用同一支程式再開一個「網頁模式」的子程序（ZP_WEB_PORT／ZP_WEB_HOST），畫面與桌面版相同，
資料一樣在本機的 MariaDB（子程序直接連桌面版已經開好的資料庫，不會另外啟動或停止）。
子程序跟著桌面版：桌面版關閉（或關掉開關）就一起停止。
網頁版不提供：備份還原、版本更新與捷徑、資料庫設定（只在這台電腦操作）；檔案改成從瀏覽器上傳、下載。
"""
import logging
import os
import socket
import subprocess
import sys
import time

from .settings import data_dir, program_dir

log = logging.getLogger("zp")
DEFAULT_PORT = 8630
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def is_child():
    """目前是不是線上版子程序。"""
    return bool(os.environ.get("ZP_WEB_CHILD"))


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def local_ips():
    """本機在區網的 IPv4 位址。"""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = a[4][0]
            if not ip.startswith(("127.", "169.254.")):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def _cmd():
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, os.path.join(program_dir(), "main.py")]


class WebService:
    def __init__(self, port):
        self.port = int(port or DEFAULT_PORT)
        self.proc = None
        self.logf = None

    @property
    def running(self):
        return bool(self.proc and self.proc.poll() is None)

    def start(self, wait=45):
        if self.running:
            return
        if not port_free(self.port):
            raise OSError("埠 %d 已被其他程式使用，請換一個" % self.port)
        # 桌面版的 Flet 會把 FLET_SERVER_IP 設成 127.0.0.1，子程序繼承後會蓋掉 host → 明確改成對外
        env = dict(os.environ, ZP_WEB_PORT=str(self.port), ZP_WEB_HOST="0.0.0.0", FLET_SERVER_IP="0.0.0.0",
                   ZP_WEB_CHILD="1", ZP_DATA_DIR=data_dir(), FLET_FORCE_WEB_SERVER="true")
        for k in ("FLET_SERVER_PORT", "FLET_SERVER_UDS_PATH", "FLET_DART_BRIDGE_PORT"):
            env.pop(k, None)                           # 桌面版給自己 Flutter 視窗用的連線設定，子程序不要沿用
        env.pop("ZP_DEV_LOGIN", None)                  # 線上版一律要登入
        self.logf = open(os.path.join(data_dir(), "web.log"), "ab")
        self.proc = subprocess.Popen(_cmd(), env=env, stdout=self.logf, stderr=subprocess.STDOUT,
                                     cwd=program_dir(), creationflags=NO_WINDOW)
        t0 = time.time()
        while time.time() - t0 < wait:
            if self.proc.poll() is not None:
                self.proc = None
                raise RuntimeError("線上版服務啟動失敗，詳見 %s" % os.path.join(data_dir(), "web.log"))
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    log.info("web service on :%d (pid %s)", self.port, self.proc.pid)
                    return
            except OSError:
                time.sleep(0.4)
        self.stop()
        raise RuntimeError("線上版服務啟動逾時")

    def stop(self):
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=8)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        if self.logf:
            try:
                self.logf.close()
            except Exception:
                pass
            self.logf = None

    def urls(self):
        return ["http://%s:%d/" % (ip, self.port) for ip in local_ips()]


def qr_png(text):
    """網址 QR Code（PNG bytes），給平板、手機掃描開啟。"""
    import io

    import qrcode
    q = qrcode.QRCode(border=2, box_size=6, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(text)
    q.make(fit=True)
    buf = io.BytesIO()
    q.make_image(fill_color="#14325C", back_color="white").save(buf, format="PNG")
    return buf.getvalue()
