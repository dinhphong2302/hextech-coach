"""Tên tiếng Việt chính thức cho tướng, tộc hệ, trang bị và lõi.

Nguồn: Data Dragon của Riot, bản locale vi_VN. Tải một lần rồi lưu vào data/names_vi.json.
"""
import json
import re

import requests

import config

DDRAGON = "https://ddragon.leagueoflegends.com"
FILES = {"traits": "tft-trait", "items": "tft-item", "units": "tft-champion", "augments": "tft-augments"}

_MAP: dict[str, str] = {}      # ID gốc -> tên tiếng Việt
_EN2VI: dict[str, str] = {}    # tên tiếng Anh -> tên tiếng Việt
_LOADED = False


def _short(key: str) -> str:
    """Bỏ phần đường dẫn trong ID: 'TFTSet18/Set18_Items/DA_AdaptiveHelm' -> 'DA_AdaptiveHelm'."""
    return key.rsplit("/", 1)[-1]


def download(cfg, log=print) -> dict:
    """Tải bảng tên tiếng Việt về data/names_vi.json."""
    version = requests.get(f"{DDRAGON}/api/versions.json", timeout=20).json()[0]
    table, en2vi = {}, {}
    for kind, f in FILES.items():
        data = {}
        for loc in ("vi_VN", "en_US"):
            r = requests.get(f"{DDRAGON}/cdn/{version}/data/{loc}/{f}.json", timeout=30)
            r.raise_for_status()
            data[loc] = r.json().get("data", {})
        table[kind] = {_short(k): v.get("name") for k, v in data["vi_VN"].items() if v.get("name")}
        # bảng tra tên tiếng Anh -> tiếng Việt, dùng để dịch phần meta do AI viết
        for key, en in data["en_US"].items():
            vi_name = data["vi_VN"].get(key, {}).get("name")
            en_name = en.get("name")
            if vi_name and en_name and vi_name != en_name and len(en_name) > 3:
                en2vi.setdefault(en_name.lower(), vi_name)
        log(f"Tên tiếng Việt: {kind} {len(table[kind])} mục")
    out = {"version": version, "tables": table, "en2vi": en2vi}
    config.write_json(cfg["data_path"] / "names_vi.json", out)
    load(cfg, force=True)
    return out


def load(cfg, force=False) -> bool:
    """Nạp bảng tên vào bộ nhớ. Trả về False nếu chưa tải bảng về."""
    global _LOADED
    if _LOADED and not force:
        return True
    path = cfg["data_path"] / "names_vi.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    _MAP.clear()
    _EN2VI.clear()
    _EN2VI.update(data.get("en2vi", {}))
    for kind, table in data.get("tables", {}).items():
        for key, vi in table.items():
            _MAP.setdefault(key, vi)
            _MAP.setdefault(key.lower(), vi)
    _LOADED = True
    return True


def translate_text(text: str) -> str:
    """Đổi tên trang bị / tộc hệ / lõi tiếng Anh trong một câu sang tiếng Việt."""
    if not text or not _EN2VI:
        return text
    for en in sorted(_EN2VI, key=len, reverse=True):
        if en in text.lower():
            # chỉ đổi khi đứng riêng thành từ, tránh "Lunarwood" -> "Mặt Trăngwood"
            pattern = r"(?<![0-9A-Za-zÀ-ỹ])" + re.escape(en) + r"(?![0-9A-Za-zÀ-ỹ])"
            text = re.sub(pattern, _EN2VI[en], text, flags=re.IGNORECASE)
    return text


def translate_obj(obj):
    """Dịch mọi chuỗi trong một cấu trúc JSON (meta do AI viết)."""
    if isinstance(obj, str):
        return translate_text(obj)
    if isinstance(obj, list):
        return [translate_obj(x) for x in obj]
    if isinstance(obj, dict):
        # giữ nguyên tên đội hình (nhãn do trang meta đặt) và các trường kỹ thuật
        keep = {"sources", "url", "source", "matched_name"}
        if "core_units" in obj or "carry_items" in obj:
            keep |= {"name"}
        return {k: (v if k in keep else translate_obj(v)) for k, v in obj.items()}
    return obj


def vi(raw_id: str, fallback: str = "") -> str:
    """Tên tiếng Việt theo ID gốc của Riot; không có thì trả về fallback."""
    if not raw_id:
        return fallback
    key = _short(raw_id)
    hit = _MAP.get(key) or _MAP.get(key.lower())
    if hit:
        return hit
    # ID tộc hệ đôi khi thiếu/thừa số set: DA_18_Blossom <-> DA_Blossom18
    base = re.sub(r"(^DA_|^TFT\d*_)|_?\d+", "", key)
    for k, name in _MAP.items():
        if re.sub(r"(^DA_|^TFT\d*_)|_?\d+", "", k) == base and not k.islower():
            return name
    return fallback
