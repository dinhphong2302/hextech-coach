"""Bảng ảnh chính thức cho tướng, tộc hệ, trang bị, lõi và huy hiệu rank.

Nguồn: Community Dragon (ảnh trích thẳng từ game). Bảng được tải một lần và lưu vào
data/assets.json; ảnh tải về máy khi cần để app dùng được cả khi mạng chậm.
"""
import json
import re
import unicodedata

import requests

import config

CDRAGON_DATA = "https://raw.communitydragon.org/latest/cdragon/tft/{loc}.json"
CDRAGON_GAME = "https://raw.communitydragon.org/latest/game/"
RANK_CREST = ("https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/"
              "global/default/images/ranked-mini-crests/{tier}.svg")

TIERS = {"sắt": "iron", "đồng": "bronze", "bạc": "silver", "vàng": "gold", "bạch kim": "platinum",
         "lục bảo": "emerald", "kim cương": "diamond", "cao thủ": "master",
         "đại cao thủ": "grandmaster", "thách đấu": "challenger"}

_BY_ID: dict[str, str] = {}     # apiName (thường) -> url ảnh
_BY_NAME: dict[str, str] = {}   # tên hiển thị (không dấu, thường) -> url ảnh
_RECIPE: dict[str, list] = {}   # tên đồ -> danh sách mảnh ghép (tiếng Việt)
_VN_OF: dict[str, str] = {}     # tên tiếng Anh -> tên tiếng Việt
_LOADED = False


def _url(tex_path: str) -> str:
    return CDRAGON_GAME + re.sub(r"\.(tex|dds)$", ".png", (tex_path or "").lower())


def _key(text: str) -> str:
    """Khoá tra cứu theo tên: bỏ dấu, bỏ ký tự đặc biệt."""
    t = unicodedata.normalize("NFD", (text or "").lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def _fetch(loc: str) -> dict:
    return requests.get(CDRAGON_DATA.format(loc=loc), timeout=240).json()


TIER_BY_SUFFIX = {"i": "Bạc", "ii": "Vàng", "iii": "Ngọc"}


def _set_prefix(s: dict) -> str:
    """Tiền tố apiName của set hiện tại, suy từ chính danh sách tướng (Set 18 là DA_)."""
    for c in s.get("champions", []):
        api = c.get("apiName") or ""
        if "_" in api:
            return api.split("_", 1)[0] + "_"
    return "TFT_"


def _aug_tier(icon: str) -> str:
    """Bậc lõi nằm ở đuôi tên file ảnh: _i là Bạc, _ii là Vàng, _iii là Ngọc."""
    stem = re.sub(r"\.(tex|dds|png)$", "", (icon or "").lower()).rsplit("/", 1)[-1]
    m = re.search(r"[-_](i{1,3})$", stem)
    return TIER_BY_SUFFIX.get(m.group(1), "") if m else ""


def _fill_desc(desc: str, effects: dict) -> str:
    """Thay @BienSo@ trong mô tả bằng số thật lấy từ effects."""
    if not desc:
        return ""
    low = {str(k).lower(): v for k, v in effects.items()}

    def repl(m):
        body = m.group(1)
        mult = 1
        if "*" in body:
            body, _, mult_s = body.partition("*")
            try:
                mult = float(mult_s)
            except ValueError:
                mult = 1
        val = low.get(body.strip().lower())
        if val is None:
            return "?"
        try:
            num = float(val) * mult
        except (TypeError, ValueError):
            return str(val)
        return str(int(num)) if abs(num - round(num)) < 0.01 else f"{num:.1f}"

    text = re.sub(r"@([^@]+)@", repl, desc)
    text = re.sub(r"<[^>]+>", "", text)          # bỏ thẻ định dạng của game
    return re.sub(r"\s+", " ", text).strip()


def download(cfg, log=print, set_number=None) -> dict:
    data = _fetch("vi_vn")
    en = _fetch("en_us")            # tên tiếng Anh: dự phòng khi meta do AI viết dùng tên gốc
    sets = data.get("setData") or []
    if set_number:
        s = next((x for x in sets if str(x.get("number")) == str(set_number)), None)
    else:
        s = max(sets, key=lambda x: int(x.get("number") or 0)) if sets else None
    if not s:
        raise ValueError("Không đọc được dữ liệu set từ Community Dragon")

    table = {"units": {}, "traits": {}, "items": {}}
    for c in s.get("champions", []):
        icon = c.get("tileIcon") or c.get("squareIcon") or c.get("icon")
        if c.get("apiName") and icon:
            # "traits" là tên tộc hệ (tiếng Việt) của tướng — web dùng để dựng Team Builder đúng game
            table["units"][c["apiName"]] = {"name": c.get("name"), "url": _url(icon), "cost": c.get("cost"),
                                            "traits": c.get("traits") or []}
    for t in s.get("traits", []):
        if t.get("apiName") and t.get("icon"):
            mocs = sorted({e["minUnits"] for e in (t.get("effects") or []) if e.get("minUnits")})
            table["traits"][t["apiName"]] = {"name": t.get("name"), "url": _url(t["icon"]),
                                             "breakpoints": mocs}
    en_item = {i.get("apiName"): i.get("name") for i in en.get("items", [])}
    en_unit, en_trait = {}, {}
    for s_en in en.get("setData", []):
        for c in s_en.get("champions", []):
            en_unit[c.get("apiName")] = c.get("name")
        for t in s_en.get("traits", []):
            en_trait[t.get("apiName")] = t.get("name")
    for i in data.get("items", []):
        if i.get("apiName") and i.get("icon"):
            table["items"][i["apiName"]] = {
                "name": i.get("name"), "url": _url(i["icon"]),
                "en": en_item.get(i["apiName"]),
                "recipe": [c for c in (i.get("composition") or [])],
                "is_augment": bool(i.get("isAugment")),
            }
    for api, item in table["units"].items():
        item["en"] = en_unit.get(api)
    for api, item in table["traits"].items():
        item["en"] = en_trait.get(api)

    prefix = _set_prefix(s)
    table["augments"] = {}
    for i in data.get("items", []):
        api = i.get("apiName") or ""
        if not i.get("isAugment") or not i.get("icon") or not api.startswith(prefix):
            continue
        table["augments"][api] = {
            "name": i.get("name"), "url": _url(i["icon"]), "en": en_item.get(api),
            "tier": _aug_tier(i["icon"]),
            "desc": _fill_desc(i.get("desc"), i.get("effects") or {}),
            "traits": i.get("associatedTraits") or [],
        }

    out = {"set": s.get("number"), "tables": table}
    config.write_json(cfg["data_path"] / "assets.json", out)
    log(f"Ảnh: {len(table['units'])} tướng · {len(table['traits'])} tộc hệ · "
        f"{len(table['items'])} trang bị/lõi · {len(table['augments'])} lõi của set")
    load(cfg, force=True)
    return out


def load(cfg, force=False) -> bool:
    global _LOADED
    if _LOADED and not force:
        return True
    path = cfg["data_path"] / "assets.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    _BY_ID.clear()
    _BY_NAME.clear()
    _RECIPE.clear()
    _VN_OF.clear()
    id_to_name = {}
    for table in data.get("tables", {}).values():
        for api_name, item in table.items():
            _BY_ID[api_name.lower()] = item["url"]
            _BY_ID[api_name.rsplit("/", 1)[-1].lower()] = item["url"]
            if item.get("name"):
                _BY_NAME.setdefault(_key(item["name"]), item["url"])
                id_to_name[api_name] = item["name"]
            if item.get("en"):
                _BY_NAME.setdefault(_key(item["en"]), item["url"])
                if item.get("name"):
                    _VN_OF.setdefault(_key(item["en"]), item["name"])
    for table in data.get("tables", {}).values():
        for item in table.values():
            if item.get("recipe") and item.get("name"):
                parts = [id_to_name.get(c, c) for c in item["recipe"]]
                _RECIPE[_key(item["name"])] = parts
                if item.get("en"):
                    _RECIPE.setdefault(_key(item["en"]), parts)
    _LOADED = True
    return True


def img(raw_id: str = "", name: str = "") -> str:
    """URL ảnh theo ID gốc của Riot, hoặc theo tên hiển thị. Không có thì trả chuỗi rỗng."""
    if raw_id:
        hit = _BY_ID.get(raw_id.lower()) or _BY_ID.get(raw_id.rsplit("/", 1)[-1].lower())
        if hit:
            return hit
    if name:
        hit = _BY_NAME.get(_key(name))
        if hit:
            return hit
        # tên đội hình kiểu "Nidalee Aphelios": lấy ảnh theo từ đầu tiên khớp
        for word in str(name).split():
            hit = _BY_NAME.get(_key(word))
            if hit:
                return hit
    return ""


def augments(cfg) -> list:
    """Toàn bộ lõi của set hiện tại, sắp theo bậc rồi tên."""
    path = cfg["data_path"] / "assets.json"
    if not path.exists():
        return []
    table = json.loads(path.read_text(encoding="utf-8")).get("tables", {}).get("augments", {})
    order = {"Bạc": 0, "Vàng": 1, "Ngọc": 2, "": 3}
    rows = [{"api": k, **v} for k, v in table.items() if v.get("name")]
    return sorted(rows, key=lambda r: (order.get(r.get("tier", ""), 3), r["name"]))


def match_augment(ten, danh_sach=None, nguong=0.82):
    """Đối chiếu tên lõi AI đọc được với danh sách lõi thật, trả về TÊN TIẾNG VIỆT chuẩn.

    AI đọc thẻ trên màn hình nên có thể ra tên tiếng Anh, sai dấu, hoặc lệch vài ký tự.
    Hàm này ghim nó về đúng một lõi có thật; không đủ giống thì trả None để báo cáo ghi
    "không đọc được" thay vì bịa ra một cái tên.
    """
    import difflib
    if not ten or not str(ten).strip():
        return None
    if danh_sach is None:
        return None
    goc = _key(ten)
    if len(goc) < 6:            # quá ngắn thì mọi so sánh đều thành ngẫu nhiên
        return None
    ung_vien = {}
    for r in danh_sach:
        vn = r.get("name")
        if not vn:
            continue
        for bien_the in (vn, r.get("en")):
            if bien_the:
                ung_vien.setdefault(_key(bien_the), vn)
    if goc in ung_vien:
        return ung_vien[goc]
    gan = difflib.get_close_matches(goc, list(ung_vien), n=1, cutoff=nguong)
    return ung_vien[gan[0]] if gan else None


def recipe(name: str) -> list:
    """Công thức ghép của một món đồ, theo tên tiếng Việt hoặc tiếng Anh."""
    return _RECIPE.get(_key(name), [])


def vn_name(name: str) -> str:
    """Tên tiếng Việt tương ứng với một tên tiếng Anh (nếu có)."""
    return _VN_OF.get(_key(name), name)


def rank_crest(rank_text: str) -> str:
    """Huy hiệu rank từ chuỗi kiểu 'Lục Bảo I · 0 LP · ...'."""
    low = (rank_text or "").lower()
    for vi_name, en in sorted(TIERS.items(), key=lambda kv: -len(kv[0])):
        if low.startswith(vi_name):
            return RANK_CREST.format(tier=en)
    return ""
