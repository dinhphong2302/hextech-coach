"""Lưu meta, xuất báo cáo Markdown/HTML và mở trên trình duyệt."""
import html
import json
import re
import time
import webbrowser
from pathlib import Path

import markdown

import config

CSS = """
:root{color-scheme:dark}
body{background:#0c1317;color:#e4ebe8;font:15px/1.6 "Segoe UI",system-ui,sans-serif;margin:0}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}
h1,h2,h3{color:#d8a94f;line-height:1.25}
h1{font-size:26px;border-bottom:1px solid #26363d;padding-bottom:10px}
h2{font-size:19px;margin-top:32px}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px;display:block;overflow-x:auto}
th,td{border:1px solid #26363d;padding:7px 10px;text-align:left;vertical-align:top}
th{background:#1a272d;color:#8ea1a3;font-weight:600}
tr:nth-child(even) td{background:#111b20}
code{background:#1a272d;padding:1px 5px;border-radius:3px}
a{color:#43b5a6}
.meta{color:#8ea1a3;font-size:13px}
img{max-width:100%;border-radius:8px;border:1px solid #26363d;margin:8px 0}
"""


def to_html(title: str, md_text: str, subtitle: str = "") -> str:
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    return (f"<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>"
            f"<h1>{html.escape(title)}</h1><p class='meta'>{html.escape(subtitle)}</p>{body}</main></body></html>")


def save_report(folder: Path, name: str, title: str, md_text: str, subtitle: str = "", open_it=True) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text(md_text, encoding="utf-8")
    path = folder / f"{name}.html"
    # file HTML mở độc lập nên đổi đường dẫn ảnh của app thành đường dẫn tương đối
    standalone = re.sub(r"/frame\?session=[^&]+&t=(\d+)", r"keyframes/\1.jpg", md_text)
    path.write_text(to_html(title, standalone, subtitle), encoding="utf-8")
    if open_it:
        webbrowser.open(path.as_uri())
    return path


# ---------- meta ----------
def meta_path(cfg) -> Path:
    return cfg["data_path"] / "meta.json"


def load_meta(cfg):
    """Meta đã lưu kèm tuổi tính bằng giờ. File hỏng thì coi như chưa có."""
    p = meta_path(cfg)
    if not p.exists():
        return None, None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None, None
    return data, (time.time() - p.stat().st_mtime) / 3600


def save_meta(cfg, meta: dict):
    config.write_json(meta_path(cfg), meta)


def _fmt(v, suffix=""):
    return "—" if v is None else f"{v}{suffix}"


def meta_markdown(meta) -> str:
    if not meta:
        return ""
    lines = [f"Patch {meta.get('patch', '?')} · {meta.get('set', '')} · cập nhật {meta.get('fetched_at', '?')}", "",
             "| Tier | Đội hình | Kiểu | Hạng TB | Top4 | Top1 | Tỉ lệ chọn | Độ khó |",
             "|---|---|---|---|---|---|---|---|"]
    order = {"S": 0, "A": 1, "B": 2, "C": 3}
    comps = sorted(meta.get("comps", []), key=lambda c: (order.get(c.get("tier"), 9),
                                                         (c.get("stats") or {}).get("avg_place") or 9))
    for c in comps:
        s = c.get("stats") or {}
        lines.append(f"| {c.get('tier')} | **{c.get('name')}** | {c.get('style', '')} | {_fmt(s.get('avg_place'))} | "
                     f"{_fmt(s.get('top4'), '%')} | {_fmt(s.get('win'), '%')} | {_fmt(s.get('pick_rate'), '%')} | "
                     f"{c.get('difficulty', '')} |")
    for c in comps:
        items = "; ".join(f"{u}: {', '.join(str(x) for x in (i or []) if x)}"
                          for u, i in (c.get("carry_items") or {}).items() if u)
        lines += ["", f"### {c.get('tier') or '?'} · {c.get('name')}",
                  f"- **Tướng lõi:** {', '.join(str(x) for x in (c.get('core_units') or []) if x)}",
                  f"- **Đồ carry:** {items or '—'}",
                  f"- **Lõi mạnh:** {', '.join(str(x) for x in (c.get('augments') or []) if x) or '—'}",
                  f"- **Ấn / tướng đặc biệt:** {c.get('emblems_or_special') or '—'}",
                  f"- **Điều kiện đánh:** {c.get('conditions', '—')}",
                  f"- **Kế hoạch roll:** {c.get('roll_plan', '—')}",
                  f"- **Nguồn:** {', '.join(c.get('sources', [])) or '—'}"]
    if meta.get("general_notes"):
        lines += ["", "### Ghi chú patch"] + [f"- {n}" for n in meta["general_notes"]]
    return "\n".join(lines)
