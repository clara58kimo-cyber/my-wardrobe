"""
資料儲存層
- Supabase 模式：在 Streamlit Secrets 設定 SUPABASE_URL / SUPABASE_KEY 後自動啟用，資料永久保存。
- 本機模式：未設定時使用 SQLite（圖片一併存進資料庫），
  注意 Streamlit Cloud 重新啟動或重新部署時會清空，請定期「下載備份」。
"""
from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from datetime import date, datetime

LIST_FIELDS = ("styles", "seasons")
ITEM_FIELDS = (
    "name", "category", "color", "styles", "seasons", "notes",
    "favorite", "wear_count", "last_worn", "image_path", "thumb_path", "created_at",
)
OUTFIT_FIELDS = ("name", "item_ids", "note", "created_at")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _split(v) -> list:
    if isinstance(v, list):
        return v
    return [s for s in (v or "").split(",") if s]


def _join(v) -> str:
    return ",".join(v) if isinstance(v, (list, tuple)) else (v or "")


def _decode_item(row: dict) -> dict:
    row = dict(row)
    for f in LIST_FIELDS:
        row[f] = _split(row.get(f))
    row["favorite"] = bool(row.get("favorite"))
    row["wear_count"] = int(row.get("wear_count") or 0)
    lw = row.get("last_worn")
    row["last_worn"] = str(lw)[:10] if lw else None
    return row


def _encode_item(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if k not in ITEM_FIELDS:
            continue
        out[k] = _join(v) if k in LIST_FIELDS else v
    if "favorite" in out:
        out["favorite"] = bool(out["favorite"])
    return out


def _decode_outfit(row: dict) -> dict:
    row = dict(row)
    row["item_ids"] = [int(x) for x in _split(str(row.get("item_ids") or ""))]
    return row


# ---------------------------------------------------------------------------
# 本機 SQLite
# ---------------------------------------------------------------------------
class SQLiteStore:
    mode = "local"
    label = "本機暫存（SQLite）"

    def __init__(self, path: str = "wardrobe.db"):
        self.path = path
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS clothing (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT, style TEXT, season TEXT,
                    image_path TEXT, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS images (path TEXT PRIMARY KEY, data BLOB);
                CREATE TABLE IF NOT EXISTS outfits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, item_ids TEXT, note TEXT, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS wear_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worn_on TEXT, item_ids TEXT
                );
                """
            )
            # 舊版資料表升級：補齊新欄位
            cols = {r["name"] for r in c.execute("PRAGMA table_info(clothing)")}
            for col, typ in [
                ("name", "TEXT"), ("color", "TEXT"), ("styles", "TEXT"), ("seasons", "TEXT"),
                ("notes", "TEXT"), ("favorite", "INTEGER DEFAULT 0"),
                ("wear_count", "INTEGER DEFAULT 0"), ("last_worn", "TEXT"), ("thumb_path", "TEXT"),
            ]:
                if col not in cols:
                    c.execute(f"ALTER TABLE clothing ADD COLUMN {col} {typ}")
            # 舊版單選欄位轉成新版多選欄位
            c.execute("UPDATE clothing SET styles = style WHERE styles IS NULL AND style IS NOT NULL")
            c.execute("UPDATE clothing SET seasons = season WHERE seasons IS NULL AND season IS NOT NULL")

    # 衣物 ------------------------------------------------------------
    def list_items(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id," + ",".join(ITEM_FIELDS) + " FROM clothing ORDER BY id DESC"
            ).fetchall()
        return [_decode_item(dict(r)) for r in rows]

    def add_item(self, data: dict) -> int:
        d = _encode_item({**data, "created_at": data.get("created_at") or _now()})
        keys = list(d)
        with self._conn() as c:
            cur = c.execute(
                f"INSERT INTO clothing ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})",
                [d[k] for k in keys],
            )
            return cur.lastrowid

    def update_item(self, item_id: int, data: dict):
        d = _encode_item(data)
        if not d:
            return
        with self._conn() as c:
            c.execute(
                f"UPDATE clothing SET {','.join(k + '=?' for k in d)} WHERE id=?",
                [*d.values(), item_id],
            )

    def delete_item(self, item: dict):
        with self._conn() as c:
            c.execute("DELETE FROM clothing WHERE id=?", (item["id"],))
            for p in (item.get("image_path"), item.get("thumb_path")):
                if p:
                    c.execute("DELETE FROM images WHERE path=?", (p,))

    # 圖片 ------------------------------------------------------------
    def put_image(self, path: str, data: bytes):
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO images (path, data) VALUES (?, ?)", (path, data))

    def get_image(self, path: str) -> bytes | None:
        if not path:
            return None
        with self._conn() as c:
            r = c.execute("SELECT data FROM images WHERE path=?", (path,)).fetchone()
        if r:
            return r["data"]
        # 相容舊版：圖片放在 uploads/ 資料夾
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError:
            return None

    # 收藏穿搭 --------------------------------------------------------
    def list_outfits(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM outfits ORDER BY id DESC").fetchall()
        return [_decode_outfit(dict(r)) for r in rows]

    def add_outfit(self, name: str, item_ids: list[int], note: str = "") -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO outfits (name, item_ids, note, created_at) VALUES (?,?,?,?)",
                (name, ",".join(map(str, item_ids)), note, _now()),
            )
            return cur.lastrowid

    def delete_outfit(self, outfit_id: int):
        with self._conn() as c:
            c.execute("DELETE FROM outfits WHERE id=?", (outfit_id,))

    # 穿著紀錄 --------------------------------------------------------
    def list_wear_log(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM wear_log ORDER BY worn_on DESC, id DESC").fetchall()
        return [_decode_outfit(dict(r)) for r in rows]

    def log_wear(self, item_ids: list[int], worn_on: str | None = None):
        worn_on = worn_on or date.today().isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO wear_log (worn_on, item_ids) VALUES (?, ?)",
                (worn_on, ",".join(map(str, item_ids))),
            )
            for i in item_ids:
                c.execute(
                    "UPDATE clothing SET wear_count = COALESCE(wear_count,0)+1, last_worn=? WHERE id=?",
                    (worn_on, i),
                )


# ---------------------------------------------------------------------------
# Supabase（永久保存）
# ---------------------------------------------------------------------------
class SupabaseStore:
    mode = "cloud"
    label = "Supabase 雲端（永久保存）"

    def __init__(self, url: str, key: str, bucket: str = "wardrobe"):
        from supabase import create_client  # 延遲載入，本機模式不需要

        self.client = create_client(url, key)
        self.bucket = bucket

    def _t(self, name):
        return self.client.table(name)

    def list_items(self) -> list[dict]:
        res = self._t("clothing").select("*").order("id", desc=True).execute()
        return [_decode_item(r) for r in res.data]

    def add_item(self, data: dict) -> int:
        d = _encode_item({**data, "created_at": data.get("created_at") or _now()})
        res = self._t("clothing").insert(d).execute()
        return res.data[0]["id"]

    def update_item(self, item_id: int, data: dict):
        d = _encode_item(data)
        if d:
            self._t("clothing").update(d).eq("id", item_id).execute()

    def delete_item(self, item: dict):
        self._t("clothing").delete().eq("id", item["id"]).execute()
        paths = [p for p in (item.get("image_path"), item.get("thumb_path")) if p]
        if paths:
            try:
                self.client.storage.from_(self.bucket).remove(paths)
            except Exception:
                pass

    def put_image(self, path: str, data: bytes):
        self.client.storage.from_(self.bucket).upload(
            path, data, {"content-type": "image/jpeg", "upsert": "true"}
        )

    def get_image(self, path: str) -> bytes | None:
        if not path:
            return None
        try:
            return self.client.storage.from_(self.bucket).download(path)
        except Exception:
            return None

    def list_outfits(self) -> list[dict]:
        res = self._t("outfits").select("*").order("id", desc=True).execute()
        return [_decode_outfit(r) for r in res.data]

    def add_outfit(self, name: str, item_ids: list[int], note: str = "") -> int:
        res = self._t("outfits").insert(
            {"name": name, "item_ids": ",".join(map(str, item_ids)), "note": note, "created_at": _now()}
        ).execute()
        return res.data[0]["id"]

    def delete_outfit(self, outfit_id: int):
        self._t("outfits").delete().eq("id", outfit_id).execute()

    def list_wear_log(self) -> list[dict]:
        res = self._t("wear_log").select("*").order("worn_on", desc=True).execute()
        return [_decode_outfit(r) for r in res.data]

    def log_wear(self, item_ids: list[int], worn_on: str | None = None):
        worn_on = worn_on or date.today().isoformat()
        self._t("wear_log").insert({"worn_on": worn_on, "item_ids": ",".join(map(str, item_ids))}).execute()
        items = {i["id"]: i for i in self.list_items()}
        for i in item_ids:
            if i in items:
                self._t("clothing").update(
                    {"wear_count": items[i]["wear_count"] + 1, "last_worn": worn_on}
                ).eq("id", i).execute()


# ---------------------------------------------------------------------------
# 備份 / 還原（兩種模式通用）
# ---------------------------------------------------------------------------
def export_backup(store) -> bytes:
    items = store.list_items()
    payload = {
        "version": 2,
        "exported_at": _now(),
        "items": items,
        "outfits": store.list_outfits(),
        "wear_log": store.list_wear_log(),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("data.json", json.dumps(payload, ensure_ascii=False, indent=2))
        for it in items:
            for key in ("image_path", "thumb_path"):
                p = it.get(key)
                data = store.get_image(p) if p else None
                if data:
                    z.writestr(f"images/{p.replace('/', '_')}", data)
    return buf.getvalue()


def import_backup(store, file_bytes: bytes) -> tuple[int, int]:
    """合併匯入：衣物取得新編號，收藏穿搭與穿著紀錄會自動對應新編號。"""
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        payload = json.loads(z.read("data.json"))
        names = set(z.namelist())
        id_map: dict[int, int] = {}
        for it in payload.get("items", []):
            for key in ("image_path", "thumb_path"):
                p = it.get(key)
                zp = f"images/{p.replace('/', '_')}" if p else None
                if zp and zp in names:
                    store.put_image(p, z.read(zp))
            new_id = store.add_item({k: it.get(k) for k in ITEM_FIELDS})
            id_map[int(it["id"])] = new_id
    n_outfits = 0
    for o in payload.get("outfits", []):
        ids = [id_map[i] for i in o.get("item_ids", []) if i in id_map]
        if ids:
            store.add_outfit(o.get("name") or "未命名穿搭", ids, o.get("note") or "")
            n_outfits += 1
    for w in payload.get("wear_log", []):
        ids = [id_map[i] for i in w.get("item_ids", []) if i in id_map]
        if ids and isinstance(store, SQLiteStore):
            with store._conn() as c:
                c.execute("INSERT INTO wear_log (worn_on, item_ids) VALUES (?,?)",
                          (w.get("worn_on"), ",".join(map(str, ids))))
        elif ids:
            store._t("wear_log").insert({"worn_on": w.get("worn_on"), "item_ids": ",".join(map(str, ids))}).execute()
    return len(id_map), n_outfits
