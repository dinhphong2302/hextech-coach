"""Biểu đồ SVG vẽ bằng tay: phân bố hạng 1–8 và đường LP theo thời gian.

Vẽ thẳng ra SVG để báo cáo mở được cả khi không có mạng và không cần thư viện đồ thị.
Mọi con số đều lấy từ dữ liệu thật; không có dữ liệu thì trả về chuỗi rỗng chứ không vẽ khung trống.
"""
import html
import json
from datetime import datetime
from pathlib import Path

import config

GOLD = "#d8a94f"
TEAL = "#43b5a6"
BAD = "#e0685c"
MUTED = "#8ea1a3"
LINE = "#26363d"
SURFACE = "#131d22"

# màu theo hạng: hạng 1 vàng, top 4 xanh, còn lại đỏ
PLACE_COLOR = {1: GOLD, 2: TEAL, 3: TEAL, 4: TEAL}


def _t(x, y, text, fill=MUTED, size=12, anchor="middle", weight="400"):
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" '
            f'font-weight="{weight}" font-family="Segoe UI,system-ui,sans-serif">'
            f'{html.escape(str(text))}</text>')


def placement_bars(placements, width=660, height=250) -> str:
    """Cột: mỗi hạng 1–8 bao nhiêu trận. placements là danh sách hạng của từng trận."""
    places = [int(p) for p in placements if isinstance(p, (int, float)) and 1 <= int(p) <= 8]
    if not places:
        return ""
    counts = {i: places.count(i) for i in range(1, 9)}
    top = max(counts.values()) or 1
    pad_l, pad_r, pad_t, pad_b = 42, 14, 22, 42
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    slot = plot_w / 8
    bar_w = slot * 0.6

    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
           f'aria-label="Phân bố hạng 1 đến 8">']
    out.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{SURFACE}" rx="8"/>')

    # lưới ngang + nhãn trục số trận
    steps = min(top, 5)
    for s in range(steps + 1):
        val = round(top * s / steps)
        y = pad_t + plot_h - plot_h * s / steps
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
                   f'stroke="{LINE}" stroke-width="1"/>')
        out.append(_t(pad_l - 8, y + 4, val, anchor="end", size=11))

    for i in range(1, 9):
        n = counts[i]
        x = pad_l + slot * (i - 1) + (slot - bar_w) / 2
        h = plot_h * n / top
        y = pad_t + plot_h - h
        color = PLACE_COLOR.get(i, BAD)
        if n:
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
                       f'fill="{color}" rx="3" opacity="0.9"/>')
            out.append(_t(x + bar_w / 2, y - 6, n, fill=color, size=12, weight="700"))
        out.append(_t(x + bar_w / 2, pad_t + plot_h + 18, f"#{i}",
                      fill=color if n else MUTED, size=12, weight="600"))

    avg = sum(places) / len(places)
    top4 = 100 * sum(1 for p in places if p <= 4) / len(places)
    out.append(_t(width / 2, height - 8,
                  f"{len(places)} trận · hạng trung bình {avg:.2f} · Top 4 {top4:.0f}%", size=12))
    out.append("</svg>")
    return "".join(out)


def lp_line(history, width=660, height=250) -> str:
    """Đường: LP theo thời gian. history là danh sách {ts, lp, tier_vi}."""
    pts = [h for h in (history or []) if isinstance(h.get("lp"), int)]
    pts.sort(key=lambda h: h.get("ts") or 0)      # luôn vẽ theo chiều thời gian tăng dần
    if len(pts) < 2:
        return ""
    pad_l, pad_r, pad_t, pad_b = 46, 14, 22, 40
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    lps = [p["lp"] for p in pts]
    lo, hi = min(lps), max(lps)
    if hi == lo:
        lo, hi = lo - 5, hi + 5
    span = hi - lo

    def px(i):
        return pad_l + plot_w * i / (len(pts) - 1)

    def py(v):
        return pad_t + plot_h - plot_h * (v - lo) / span

    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="LP theo thời gian">']
    out.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{SURFACE}" rx="8"/>')
    for s in range(5):
        val = lo + span * s / 4
        y = py(val)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
                   f'stroke="{LINE}" stroke-width="1"/>')
        out.append(_t(pad_l - 8, y + 4, f"{val:.0f}", anchor="end", size=11))

    path = " ".join(f"{'M' if i == 0 else 'L'}{px(i):.1f},{py(p['lp']):.1f}" for i, p in enumerate(pts))
    area = path + f" L{px(len(pts) - 1):.1f},{pad_t + plot_h:.1f} L{pad_l:.1f},{pad_t + plot_h:.1f} Z"
    out.append(f'<path d="{area}" fill="{TEAL}" opacity="0.12"/>')
    out.append(f'<path d="{path}" fill="none" stroke="{TEAL}" stroke-width="2.5" '
               f'stroke-linejoin="round" stroke-linecap="round"/>')

    for i, p in enumerate(pts):
        out.append(f'<circle cx="{px(i):.1f}" cy="{py(p["lp"]):.1f}" r="3.5" fill="{TEAL}"/>')
    # chỉ ghi nhãn điểm đầu và điểm cuối, nhiều nhãn quá sẽ chồng nhau
    out.append(_t(px(0), py(pts[0]["lp"]) - 10, f'{pts[0]["lp"]} LP', fill=MUTED, size=11, anchor="start"))
    last = pts[-1]
    out.append(_t(px(len(pts) - 1), py(last["lp"]) - 10, f'{last["lp"]} LP',
                  fill=GOLD, size=12, anchor="end", weight="700"))

    delta = last["lp"] - pts[0]["lp"]
    sign = "+" if delta > 0 else ""
    out.append(_t(pad_l, height - 8, _when(pts[0]), size=11, anchor="start"))
    out.append(_t(width - pad_r, height - 8, _when(last), size=11, anchor="end"))
    out.append(_t(width / 2, height - 8,
                  f'{last.get("tier_vi") or ""} · {sign}{delta} LP qua {len(pts)} mốc'.strip(" ·"),
                  fill=GOLD if delta > 0 else BAD, size=12, weight="600"))
    out.append("</svg>")
    return "".join(out)


def _when(point) -> str:
    try:
        return datetime.fromtimestamp(point["ts"]).strftime("%d/%m %H:%M")
    except (KeyError, TypeError, ValueError, OSError):
        return ""


# ---------- lịch sử LP ----------
def history_path(cfg) -> Path:
    return cfg["data_path"] / "lp_history.json"


def load_history(cfg) -> list:
    p = history_path(cfg)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def record_lp(cfg, rank_raw: dict | None) -> list:
    """Ghi một mốc LP. Riot API không trả lịch sử LP, nên app phải tự tích lại theo thời gian.

    Mốc mới chỉ được ghi khi LP hoặc số trận thắng/thua có đổi, tránh phình file khi mở app nhiều lần.
    """
    if not rank_raw or not isinstance(rank_raw.get("lp"), int):
        return load_history(cfg)
    hist = load_history(cfg)
    point = {"ts": rank_raw.get("ts") or datetime.now().timestamp(), "lp": rank_raw["lp"],
             "tier_vi": rank_raw.get("tier_vi"), "wins": rank_raw.get("wins"),
             "losses": rank_raw.get("losses")}
    if hist:
        prev = hist[-1]
        same = all(prev.get(k) == point.get(k) for k in ("lp", "tier_vi", "wins", "losses"))
        if same:
            return hist
    hist.append(point)
    hist = hist[-400:]
    config.write_json(history_path(cfg), hist)
    return hist


def block(title: str, svg: str, note: str = "") -> str:
    """Bọc SVG thành khối HTML chèn được vào Markdown."""
    if not svg:
        return ""
    foot = f'<div style="color:{MUTED};font-size:12px;margin-top:4px">{html.escape(note)}</div>' if note else ""
    return (f'\n\n<div class="chart">\n<h3>{html.escape(title)}</h3>\n{svg}\n{foot}\n</div>\n\n')
