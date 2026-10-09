"""Lấy số liệu thống kê thật từ trang cộng đồng, không qua AI.

Nguồn: seemeta.com — trang dựng sẵn HTML nên đọc được bằng máy, có ghi rõ cỡ mẫu
và khoảng thời gian thống kê. Số liệu lấy nguyên văn, không suy đoán.
"""
import html
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
SEEMETA_URL = "https://seemeta.com/en/tft/set-{set}/stats"

# Từ chung trong tên đội hình, không dùng để ghép cặp
STOP = {"tft", "comp", "reroll", "flex", "fast", "vertical", "the", "and", "set",
        "bài", "hyper", "roll", "carry"}


def _text_lines(url: str, timeout=25) -> list[str]:
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    body = r.text[r.text.find("TftStatsPage"):] or r.text
    txt = html.unescape(re.sub(r"<[^>]+>", "\n", body)).replace("\xa0", " ")
    return [l.strip() for l in txt.split("\n") if l.strip()]


def _num(s: str):
    s = s.replace("%", "").replace(" ", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def fetch_seemeta(set_number: int = 18) -> dict:
    """Trả về bảng số liệu comps kèm thông tin nguồn. Ném requests.RequestException nếu hỏng."""
    url = SEEMETA_URL.format(set=set_number)
    lines = _text_lines(url)
    info = {"source": "seemeta.com", "url": url, "comps": []}

    for i, l in enumerate(lines):
        if l == "Last Updated" and i + 1 < len(lines):
            info["updated"] = lines[i + 1]
        elif l == "Matches analyzed" and i + 1 < len(lines):
            info["matches_analyzed"] = int(lines[i + 1].replace(" ", "").replace(",", "") or 0)
        elif l == "Data period" and i + 1 < len(lines):
            info["period"] = lines[i + 1]
        elif l.startswith("TFT Stats with"):
            m = re.search(r"Patch\s+([\d.]+[a-z]?)", l)
            if m:
                info["patch"] = m.group(1)

    # Mỗi đội hình là một khối: tên, Tier, <tier>, Avg place, <số>, Top 4 %, ... , Games, <số>
    i = 0
    while i < len(lines) - 12:
        if (lines[i + 1] == "Tier" and lines[i + 3] == "Avg place"
                and lines[i + 5] == "Top 4 %" and lines[i + 7] == "Win rate"
                and lines[i + 9] == "Pick rate" and lines[i + 11] == "Games"):
            info["comps"].append({
                "name": lines[i], "tier": lines[i + 2],
                "avg_place": _num(lines[i + 4]), "top4": _num(lines[i + 6]),
                "win": _num(lines[i + 8]), "pick_rate": _num(lines[i + 10]),
                "games": int(lines[i + 12].replace(" ", "").replace(",", "") or 0),
            })
            i += 13
        else:
            i += 1
    return info


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _champion_of(seemeta_name: str) -> str:
    """seemeta đặt tên kiểu '<tính từ> <Tướng>': 'Spectral Master Yi' -> 'masteryi'."""
    parts = (seemeta_name or "").split()
    return _norm(" ".join(parts[1:])) if len(parts) > 1 else _norm(seemeta_name)


def _carries_of(comp: dict) -> list[str]:
    """Tướng carry của một đội hình meta: ưu tiên tướng đang cầm đồ, rồi tới tướng lõi."""
    out = [_norm(u) for u in (comp.get("carry_items") or {})]
    out += [_norm(u) for u in (comp.get("core_units") or [])[:2]]
    return [c for c in out if c]


def merge_into_meta(meta: dict, stats: dict) -> dict:
    """Gắn số liệu thật vào đội hình khi CHẮC CHẮN cùng một tướng carry.

    Không ghép mò: hai nguồn đặt tên khác nhau, nên chỉ nhận khi tên tướng trùng khớp.
    Một carry có thể có nhiều biến thể; khi đó lấy biến thể nhiều trận nhất và ghi rõ
    còn bao nhiêu biến thể khác để không hiểu nhầm là số liệu của đúng bài đó.
    """
    rows = stats.get("comps", [])
    matched = 0
    for comp in meta.get("comps", []):
        comp.setdefault("stats", {})
        hits = []
        for carry in _carries_of(comp):
            same = [r for r in rows if _champion_of(r["name"]) == carry]
            if same:
                hits = same
                break
        if not hits:
            comp["stats"] = {"avg_place": None, "top4": None, "win": None, "pick_rate": None,
                             "note": "không ghép được với nguồn số liệu"}
            continue
        best = max(hits, key=lambda r: r["games"])
        comp["stats"] = {
            "avg_place": best["avg_place"], "top4": best["top4"], "win": best["win"],
            "pick_rate": best["pick_rate"], "games": best["games"],
            "sample_rank": "mọi rank", "source": stats["source"],
            "matched_name": best["name"],
            "variants": len(hits),
            "note": (f"số liệu của biến thể nhiều trận nhất trong {len(hits)} biến thể cùng carry"
                     if len(hits) > 1 else "cùng carry, tên đội hình khác nguồn"),
        }
        matched += 1
    meta["stats_table"] = stats
    meta["stats_matched"] = f"{matched}/{len(meta.get('comps', []))}"
    return meta
