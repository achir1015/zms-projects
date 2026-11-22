"""手機與電腦之間傳資料的格式：JSON；日期、時間、Decimal 與「鍵是數字的字典」都要原樣還原。"""
import datetime as dt
import json
from decimal import Decimal


def _prep(o):
    """JSON 會把字典的數字鍵變成字串（例如分類 id、平台狀態碼）→ 這種字典改成 {"$m": [[鍵, 值], …]}。"""
    if isinstance(o, dict):
        if any(not isinstance(k, str) for k in o):
            return {"$m": [[k, _prep(v)] for k, v in o.items()]}
        return {k: _prep(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_prep(x) for x in o]
    if isinstance(o, set):
        return [_prep(x) for x in o]
    return o


def _enc(o):
    if isinstance(o, Decimal):
        return {"$d": str(o)}
    if isinstance(o, dt.datetime):
        return {"$dt": o.isoformat()}
    if isinstance(o, dt.date):
        return {"$date": o.isoformat()}
    if isinstance(o, bytes):
        return o.decode("utf-8", "replace")
    raise TypeError("無法傳送的資料型別：%s" % type(o).__name__)


def _dec(d):
    if len(d) == 1:
        if "$d" in d:
            return Decimal(d["$d"])
        if "$date" in d:
            return dt.date.fromisoformat(d["$date"])
        if "$dt" in d:
            return dt.datetime.fromisoformat(d["$dt"])
        if "$m" in d:
            return {(tuple(k) if isinstance(k, list) else k): v for k, v in d["$m"]}
    return d


def dumps(obj) -> bytes:
    return json.dumps(_prep(obj), default=_enc, ensure_ascii=False).encode("utf-8")


def loads(data):
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data, object_hook=_dec)
