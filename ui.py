"""Cửa sổ web cục bộ: tier list đội hình / trang bị / lõi, trạng thái ghi hình, danh sách trận."""
import json
import os
import threading
import webbrowser
from collections import deque
from datetime import datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import assets
import charts
from config import ROOT

ASSETS = ROOT / "assets"          # bộ ảnh nhận diện: icon desktop, icon khay
ICON_FILE = ASSETS / "jc.ico"
TRAY_FILE = ASSETS / "tray.png"

PROGRESS = {"text": None}
WINDOW = {"win": None, "max": False}   # cửa sổ app đang mở, để bản chạy sau nhờ hiện lên
STATE = {"phase": "idle", "session": None, "started_at": None, "busy": None, "engine": "",
         "riot": False, "account": None}
LOG = deque(maxlen=200)


_PLACEMENT_CACHE: dict[str, tuple] = {}


def _session_dir(cfg, name: str):
    """Thư mục trận theo tên, chặn tên vượt ra ngoài thư mục dữ liệu."""
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    base = (cfg["data_path"] / "sessions").resolve()
    folder = (base / name).resolve()
    return folder if folder.parent == base else None


def same_origin(headers, port: int) -> bool:
    """Request này có đến từ chính giao diện của app không.

    Trình duyệt luôn gắn Origin vào POST giữa các trang, nên một trang web bất kỳ người
    dùng mở sẽ bị chặn ở đây. Script cục bộ (curl, python) không gắn Origin, và chúng
    chạy với quyền của chính người dùng nên vẫn cho qua.
    """
    goc = headers.get("Origin") or ""
    if not goc:
        ref = headers.get("Referer") or ""
        if not ref:
            return True
        p = urlparse(ref)
        goc = f"{p.scheme}://{p.netloc}"
    return goc in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")


def log_line(msg: str):
    LOG.append(f"{datetime.now():%H:%M:%S} {msg}")


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *a, cfg=None, actions=None, **kw):
        self.cfg, self.actions = cfg, actions
        super().__init__(*a, **kw)

    def log_message(self, *a):  # không đổ log HTTP ra cửa sổ app
        pass

    def _send(self, body: bytes, ctype="application/json; charset=utf-8", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(json.dumps(obj, ensure_ascii=False).encode(), code=code)

    def _sessions(self):
        folder = self.cfg["data_path"] / "sessions"
        out = []
        for d in sorted(folder.glob("*"), reverse=True)[:40]:
            if not d.is_dir():
                continue
            placement = None
            match = d / "match.json"
            if match.exists():
                # file trận nặng, giao diện hỏi mỗi 2.5 giây nên phải nhớ kết quả
                stamp = match.stat().st_mtime
                cached = _PLACEMENT_CACHE.get(d.name)
                if cached and cached[0] == stamp:
                    placement = cached[1]
                else:
                    try:
                        data = json.loads(match.read_text(encoding="utf-8"))
                        me = next((p for p in data["info"]["participants"]
                                   if p["puuid"] == self.cfg.get("_puuid")), None)
                        placement = me["placement"] if me else None
                    except (json.JSONDecodeError, KeyError, OSError):
                        placement = None
                    _PLACEMENT_CACHE[d.name] = (stamp, placement)
            out.append({"name": d.name,
                        "frames": len(list((d / "keyframes").glob("*.jpg"))) if (d / "keyframes").exists() else 0,
                        "report": (d / "review.html").exists(),
                        "placement": placement})
        return out

    def do_GET(self):
        route = urlparse(self.path)
        path, query = route.path, parse_qs(route.query)
        if path == "/":
            return self._send((ROOT / "ui.html").read_bytes(), "text/html; charset=utf-8")
        if route.path.startswith("/assets/"):
            name = route.path[len("/assets/"):]
            f = ASSETS / name
            if "/" in name or "\\" in name or not f.is_file():
                return self._json({"error": "Không có ảnh này"}, 404)
            kind = "image/png" if f.suffix == ".png" else "image/x-icon"
            return self._send(f.read_bytes(), kind)
        if path == "/api/state":
            s = dict(STATE)
            meta_file = self.cfg["data_path"] / "meta.json"
            s["meta_updated"] = (datetime.fromtimestamp(meta_file.stat().st_mtime).strftime("%d/%m %H:%M")
                                 if meta_file.exists() else None)
            s["sessions"] = self._sessions()
            for name, f in (("global_updated", "global_stats.json"), ("profile_updated", "profile.json")):
                path_f = self.cfg["data_path"] / f
                s[name] = (datetime.fromtimestamp(path_f.stat().st_mtime).strftime("%d/%m %H:%M")
                           if path_f.exists() else None)
            adv = self.cfg["data_path"] / "advice.json"
            s["advice_updated"] = (datetime.fromtimestamp(adv.stat().st_mtime).strftime("%d/%m %H:%M")
                                   if adv.exists() else None)
            s["progress"] = PROGRESS.get("text")
            s["log"] = list(LOG)[-40:]
            return self._json(s)
        if path == "/api/handbook":
            hb = self.cfg["data_path"] / "handbook.md"
            base = (ROOT / "guide_vi.md")
            return self._json({
                "handbook": hb.read_text(encoding="utf-8") if hb.exists() else "",
                "at": (datetime.fromtimestamp(hb.stat().st_mtime).strftime("%d/%m %H:%M")
                       if hb.exists() else None),
                "base": base.read_text(encoding="utf-8") if base.exists() else "",
            })
        if path == "/api/advice":
            f = self.cfg["data_path"] / "advice.json"
            return self._json(json.loads(f.read_text(encoding="utf-8")) if f.exists() else {})
        if path in ("/api/global", "/api/profile"):
            f = self.cfg["data_path"] / ("global_stats.json" if path.endswith("global") else "profile.json")
            data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
            if path == "/api/profile" and data.get("games"):
                data["charts"] = self._profile_charts(data)
                if not data.get("manh_yeu"):
                    # hồ sơ lưu từ bản cũ chưa có trường này, tính ngay để khỏi bắt cập nhật lại
                    import research
                    data["manh_yeu"] = research.strengths_weaknesses(data)
            return self._json(data)
        if path == "/api/meta":
            meta_file = self.cfg["data_path"] / "meta.json"
            if not meta_file.exists():
                return self._json({})
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["images"] = _meta_images(meta)
            self._enrich_items(meta)
            return self._json(meta)
        if path == "/frame":
            folder = _session_dir(self.cfg, (query.get("session") or [""])[0])
            t = (query.get("t") or [""])[0]
            f = (folder / "keyframes" / f"{t}.jpg") if (folder and t.isdigit()) else None
            if f and f.exists():
                return self._send(f.read_bytes(), "image/jpeg")
            return self._send(b"404", "text/plain", 404)
        if path == "/api/augments":
            rows = assets.augments(self.cfg)
            web = {}
            mf = self.cfg["data_path"] / "meta.json"
            if mf.exists():
                try:
                    for a in json.loads(mf.read_text(encoding="utf-8")).get("augments", []):
                        if isinstance(a, dict) and a.get("name"):
                            web[assets._key(a["name"])] = a
                except json.JSONDecodeError:
                    pass
            for r in rows:                       # đánh giá của web chỉ là phần bổ sung
                hit = web.get(assets._key(r["name"])) or web.get(assets._key(r.get("en") or ""))
                if hit:
                    r["web"] = True
                    r["web_tier"] = hit.get("tier")
                    r["best_for"] = hit.get("best_for")
                    r["notes"] = hit.get("notes")
            return self._json({"augments": rows, "rated": sum(1 for r in rows if r.get("web"))})
        if path == "/api/report":
            folder = _session_dir(self.cfg, (query.get("session") or [""])[0])
            f = (folder / "review.md") if folder else None
            if not f or not f.exists():
                return self._json({"error": "Chưa có báo cáo cho trận này"}, 404)
            return self._json({"name": folder.name, "text": f.read_text(encoding="utf-8"),
                               "at": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m %H:%M")})
        if path == "/report":
            folder = _session_dir(self.cfg, (query.get("session") or [""])[0])
            f = (folder / "review.html") if folder else None
            if f and f.exists() and f.is_file():
                return self._send(f.read_bytes(), "text/html; charset=utf-8")
            return self._send(b"Khong tim thay bao cao", "text/plain; charset=utf-8", 404)
        return self._send(b"404", "text/plain", 404)

    def _enrich_items(self, meta: dict):
        """Điền công thức ghép và hạng TB tự tính cho bảng trang bị và lõi."""
        gfile = self.cfg["data_path"] / "global_stats.json"
        stats = {}
        if gfile.exists():
            try:
                data = json.loads(gfile.read_text(encoding="utf-8"))
                stats = {assets._key(i["name"]): i for i in data.get("items", [])}
                meta["item_stats_meta"] = data.get("meta", {})
            except (json.JSONDecodeError, KeyError):
                pass
        # Bảng trang bị lấy TOÀN BỘ món tự tính được, phần AI chỉ bổ sung ghi chú
        notes = {}
        for it in meta.get("items", []):
            it["name"] = assets.vn_name(it.get("name", ""))
            notes[assets._key(it["name"])] = it
        merged = []
        for key, row in stats.items():
            ai = notes.pop(key, {})
            merged.append({
                "name": row["name"], "tier": ai.get("tier"),
                "recipe": " + ".join(assets.recipe(row["name"]) or row.get("recipe") or []),
                "role": ai.get("role"), "best_on": ai.get("best_on"), "notes": ai.get("notes"),
                "stats": {"avg_place": row["avg_place"], "top4": row["top4"],
                          "win": row["win"], "pick_rate": row["pick_rate"], "games": row["games"]},
            })
        for leftover in notes.values():          # món AI nhắc mà dữ liệu mình chưa đủ mẫu
            leftover.setdefault("recipe", " + ".join(assets.recipe(leftover["name"])))
            merged.append(leftover)
        for row in merged:
            avg = (row.get("stats") or {}).get("avg_place")
            if avg and not row.get("tier"):        # tự xếp tier theo hạng trung bình
                row["tier"] = "S" if avg <= 3.8 else "A" if avg <= 4.1 else "B" if avg <= 4.4 else "C"
                row["tier_auto"] = True
        merged.sort(key=lambda x: ((x.get("stats") or {}).get("avg_place") or 99))
        if merged:
            meta["items"] = merged
        for a in meta.get("augments", []):
            a["name"] = assets.vn_name(a.get("name", ""))

        # đội hình nào thiếu số liệu thì lấy theo tướng carry từ dữ liệu tự thu thập
        carries = {}
        if gfile.exists():
            try:
                carries = {assets._key(c["name"]): c
                           for c in json.loads(gfile.read_text(encoding="utf-8")).get("carries", [])}
            except json.JSONDecodeError:
                pass
        for comp in meta.get("comps", []):
            st = comp.get("stats") or {}
            if st.get("avg_place"):
                continue
            for cand in list(comp.get("carry_items") or {}) + (comp.get("core_units") or []):
                hit = carries.get(assets._key(cand))
                if hit:
                    comp["stats"] = {"avg_place": hit["avg_place"], "top4": hit["top4"],
                                     "win": hit["win"], "pick_rate": hit["pick_rate"],
                                     "by_carry": cand, "games": hit["games"]}
                    break
        meta["images"] = _meta_images(meta)

    def _profile_charts(self, prof: dict) -> dict:
        """Biểu đồ SVG cho tab Cá nhân: phân bố hạng và đường LP."""
        places = [r.get("place") for r in prof.get("placements") or []]
        hist = charts.load_history(self.cfg)
        return {
            "bars": charts.placement_bars(places),
            "lp": charts.lp_line(hist),
            "lp_points": len(hist),
        }

    def _window_button(self, action: str):
        """Thu nhỏ, phóng to hoặc ẩn cửa sổ xuống khay theo nút trên thanh tiêu đề."""
        win = WINDOW.get("win")
        if not win:
            return self._json({"error": "Đang chạy trong trình duyệt, không có cửa sổ app"}, 409)
        try:
            if action == "min":
                _minimize(win)
            elif action == "max":
                _toggle_max(win)
            elif action == "close":
                win.hide()          # đóng chỉ ẩn xuống khay, app vẫn ghi hình
            else:
                return self._json({"error": "Lệnh cửa sổ không hợp lệ"}, 400)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e)}, 409)
        return self._json({"ok": True, "max": WINDOW["max"]})

    def do_POST(self):
        route = urlparse(self.path)
        query = parse_qs(route.query)
        if not same_origin(self.headers, self.cfg["ui_port"]):
            # một trang web khác đang cố điều khiển app qua trình duyệt của người dùng
            nguon = self.headers.get("Origin") or self.headers.get("Referer") or "?"
            log_line(f"Chặn yêu cầu POST từ ngoài: {nguon}")
            return self._json({"error": "Yêu cầu không đến từ giao diện của app"}, 403)
        if route.path == "/api/window":
            # nút thu nhỏ / phóng to / đóng của thanh tiêu đề tự vẽ; chạy cả khi app đang bận
            return self._window_button((query.get("do") or [""])[0])
        if STATE["busy"]:
            return self._json({"error": f"Đang bận: {STATE['busy']}"}, 409)
        if route.path == "/api/meta/refresh":
            self._background("Đang cập nhật meta", self.actions["meta"])
            return self._json({"ok": True})
        if route.path in ("/api/research", "/api/profile/refresh"):
            key = "research" if route.path.endswith("research") else "profile"
            label = "Đang thu thập số liệu nhiều server" if key == "research" else "Đang cập nhật hồ sơ cá nhân"
            self._background(label, self.actions[key])
            return self._json({"ok": True})
        if route.path == "/api/advise":
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "Dữ liệu gửi lên không hợp lệ"}, 400)
            situation = str(body.get("situation") or "").strip()
            if len(situation) < 20:
                return self._json({"error": "Mô tả quá ngắn, cần ít nhất stage, máu, vàng và tướng"}, 400)
            self._background("Đang hỏi cố vấn", partial(self.actions["advise"], situation))
            return self._json({"ok": True})
        if route.path == "/api/show":
            win = WINDOW.get("win")
            if not win:
                return self._json({"error": "Bản đang chạy không có cửa sổ"}, 409)
            try:
                win.show()
                win.restore()
            except Exception as e:  # noqa: BLE001 - cửa sổ đã đóng hẳn
                return self._json({"error": str(e)}, 409)
            return self._json({"ok": True})
        if route.path == "/api/handbook/refresh":
            self._background("Đang tra tài liệu Dishsoap", self.actions["handbook"])
            return self._json({"ok": True})
        if route.path == "/api/account":
            riot_id = (query.get("riot_id") or [""])[0].strip()
            detect = (query.get("detect") or ["0"])[0] == "1"
            # lấy hồ sơ mất gần một phút nên chạy nền, giao diện theo dõi qua /api/state
            self._background("Đang lấy hồ sơ tài khoản",
                             partial(self.actions["account"], riot_id or None, detect))
            return self._json({"ok": True})
        if route.path == "/api/review":
            name = (query.get("session") or [""])[0]
            folder = _session_dir(self.cfg, name)
            if not folder or not folder.is_dir():
                return self._json({"error": "Không có trận này"}, 404)
            self._background(f"Đang review {name}", partial(self.actions["review"], folder))
            return self._json({"ok": True})
        return self._send(b"404", "text/plain", 404)

    def _background(self, label, fn):
        def run():
            STATE["busy"] = label
            log_line(label + "...")
            try:
                fn()
            except Exception as e:  # noqa: BLE001 - lỗi hiện trên giao diện, app vẫn chạy
                log_line(f"Lỗi: {e}")
            finally:
                STATE["busy"] = None
        threading.Thread(target=run, daemon=True).start()


def _meta_images(meta: dict) -> dict:
    """Tra ảnh cho mọi tên tướng / trang bị / lõi xuất hiện trong meta."""
    out = {}

    def add(name):
        name = (name or "").strip()
        if name and name not in out:
            url = assets.img(name=name)
            if url:
                out[name] = url

    for c in meta.get("comps", []):
        for u in c.get("core_units", []):
            add(u)
        for unit, items in (c.get("carry_items") or {}).items():
            add(unit)
            for i in items or []:
                add(i)
        for a in c.get("augments", []):
            add(a)
    for i in meta.get("items", []):
        add(i.get("name"))
    for a in meta.get("augments", []):
        add(a.get("name"))
    return out


CLEANUP = []          # các việc phải làm trước khi thoát hẳn (dừng ghi hình...)
_CLEANED = threading.Event()


def register_cleanup(fn) -> None:
    """Đăng ký một việc cần làm trước khi tiến trình thoát."""
    CLEANUP.append(fn)


def run_cleanup() -> None:
    """Chạy mọi việc dọn dẹp, đúng một lần. Một việc lỗi không chặn các việc còn lại."""
    if _CLEANED.is_set():
        return
    _CLEANED.set()
    for fn in list(CLEANUP):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - đang thoát, chỉ ghi lại rồi đi tiếp
            log_line(f"Lỗi khi dọn dẹp: {e}")


def _tray_image():
    """Biểu tượng khay: huy hiệu tròn cắt từ logo JC Coaching."""
    from PIL import Image, ImageDraw
    if TRAY_FILE.exists():
        try:
            return Image.open(TRAY_FILE).convert("RGBA")
        except Exception:  # noqa: BLE001 - file ảnh hỏng thì vẽ tạm
            log_line("Không đọc được assets/tray.png, dùng biểu tượng vẽ tay.")
    img = Image.new("RGBA", (64, 64), (12, 19, 23, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), outline=(216, 169, 79, 255), width=4)
    d.text((18, 22), "JC", fill=(216, 169, 79, 255))
    return img


def _start_tray(window, state):
    """Chạy biểu tượng khay ở luồng nền. Trả về icon, hoặc None nếu máy không hỗ trợ."""
    try:
        import pystray
    except ImportError:
        log_line("Chưa cài pystray nên không có biểu tượng khay; đóng cửa sổ sẽ thoát app.")
        return None

    def show(icon=None, item=None):
        try:
            window.show()
            window.restore()
        except Exception:  # noqa: BLE001 - cửa sổ đã hiện sẵn
            pass

    def quit_app(icon=None, item=None):
        state["quit"] = True
        log_line("Thoát app từ khay hệ thống.")
        try:
            icon.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            window.destroy()
        except Exception:  # noqa: BLE001
            pass
        # Dừng ghi hình tử tế TRƯỚC khi giết tiến trình: os._exit bỏ qua mọi khối
        # finally, nên VideoWriter không được release và game.mp4 mất phần đuôi.
        run_cleanup()
        os._exit(0)          # thoát cả luồng ghi hình đang chạy nền

    menu = pystray.Menu(
        pystray.MenuItem("Mở cửa sổ JC Coaching", show, default=True),
        pystray.MenuItem("Thoát hẳn", quit_app),
    )
    icon = pystray.Icon("jc_coaching", _tray_image(), "JC Coaching — đang chạy nền", menu)
    threading.Thread(target=icon.run, daemon=True).start()
    return icon


def _taskbar_identity():
    """Cho Windows gom cửa sổ theo app này và lấy icon của app, không lấy icon Python."""
    try:
        from ctypes import windll
        windll.shell32.SetCurrentProcessExplicitAppUserModelID("JordiChau.JCCoaching")
    except Exception:  # noqa: BLE001 - không đặt được thì chỉ mất icon đẹp trên thanh tác vụ
        pass


WS_THICKFRAME, WS_MINIMIZEBOX, WS_MAXIMIZEBOX = 0x00040000, 0x00020000, 0x00010000
GWL_STYLE = -16
SWP_FRAMECHANGED, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER = 0x0020, 0x0002, 0x0001, 0x0004


def _minimize(win):
    """Thu nhỏ xuống thanh tác vụ. Dùng ShowWindow vì cửa sổ không viền không nhận
    WindowState = Minimized của WinForms."""
    try:
        from ctypes import windll
        windll.user32.ShowWindow(win.native.Handle.ToInt32(), 6)      # SW_MINIMIZE
    except Exception:  # noqa: BLE001
        win.minimize()


def _work_area():
    """Vùng màn hình trừ thanh tác vụ: (trái, trên, rộng, cao)."""
    from ctypes import windll, wintypes, byref
    r = wintypes.RECT()
    windll.user32.SystemParametersInfoW(0x0030, 0, byref(r), 0)   # SPI_GETWORKAREA
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def _toggle_max(win):
    """Phóng to vừa vùng làm việc rồi thu lại. Tự căn thay vì dùng maximize của Windows,
    vì cửa sổ không viền khi maximize hay tràn ra ngoài mép màn hình."""
    if WINDOW["max"]:
        x, y, w, h = WINDOW.get("geom") or (100, 60, 1280, 840)
        win.move(x, y)
        win.resize(w, h)
        WINDOW["max"] = False
        return
    WINDOW["geom"] = (win.x, win.y, win.width, win.height)
    x, y, w, h = _work_area()
    win.move(x, y)
    win.resize(w, h)
    WINDOW["max"] = True


def _restore_resize(win):
    """Cửa sổ không viền vẫn kéo cạnh để đổi kích thước, và thu nhỏ xuống thanh tác vụ được."""
    try:
        from ctypes import windll
        hwnd = win.native.Handle.ToInt32()
        style = windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
        windll.user32.SetWindowLongW(hwnd, GWL_STYLE,
                                     style | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
        windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                   SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER)
    except Exception as e:  # noqa: BLE001 - mất tính năng kéo viền, cửa sổ vẫn dùng được
        log_line(f"Không bật được kéo viền đổi kích thước: {e}")


def open_window(url: str, cfg) -> bool:
    """Mở giao diện trong cửa sổ ứng dụng (WebView2). False nếu máy không hỗ trợ.

    Đóng cửa sổ chỉ ẩn đi, app vẫn ghi hình; muốn thoát hẳn thì dùng biểu tượng khay.
    """
    try:
        import webview
    except ImportError as e:
        log_line(f"Không nạp được pywebview: {e}")
        return False
    _taskbar_identity()
    try:
        # frameless: bỏ thanh tiêu đề trắng của Windows, thay bằng thanh tự vẽ trong ui.html.
        # easy_drag=False để chỉ kéo được ở thanh tiêu đề, không kéo nhầm khi bấm trong nội dung.
        win = webview.create_window("JC Coaching", url, width=1280, height=840,
                                    min_size=(900, 600), background_color="#0c1317",
                                    frameless=True, easy_drag=False)
        WINDOW["win"] = win
        state = {"quit": False}

        def on_closing():
            if state["quit"]:
                return True
            win.hide()
            log_line("Đã ẩn cửa sổ xuống khay hệ thống. App vẫn ghi hình; "
                     "bấm chuột phải biểu tượng khay để mở lại hoặc thoát hẳn.")
            return False        # huỷ việc đóng, chỉ ẩn

        win.events.closing += on_closing

        def force_show():
            # Launcher chạy tiến trình ở chế độ ẩn, nên cửa sổ đầu tiên thừa hưởng trạng thái ẩn
            try:
                win.show()
                win.restore()
                win.on_top = True
                win.on_top = False
            except Exception:  # noqa: BLE001 - cửa sổ đã hiện sẵn
                pass
            _restore_resize(win)
            _start_tray(win, state)

        icon = str(ICON_FILE) if ICON_FILE.exists() else None
        webview.start(force_show, gui=cfg.get("ui_backend") or None, icon=icon)
        return True
    except Exception as e:  # noqa: BLE001 - không mở được cửa sổ thì quay lại dùng trình duyệt
        import traceback
        log_line(f"Không mở được cửa sổ ứng dụng: {e}")
        print("open_window traceback:\n" + traceback.format_exc(), flush=True)
        return False


def already_running(port: int) -> bool:
    """Có bản app nào đang chạy ở cổng này không."""
    import socket
    with socket.socket() as s:
        s.settimeout(0.6)
        return s.connect_ex(("127.0.0.1", port)) == 0


class _Server(ThreadingHTTPServer):
    # mặc định của Python cho phép hai tiến trình cùng chiếm một cổng trên Windows,
    # khiến app chạy hai bản mà không ai báo lỗi
    allow_reuse_address = False


def start(cfg, actions, open_browser=True):
    """Chạy web server nền, trả về địa chỉ."""
    server = _Server(("127.0.0.1", cfg["ui_port"]),
                     partial(Handler, cfg=cfg, actions=actions))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{cfg['ui_port']}/"
    if open_browser:
        webbrowser.open(url)
    return url
