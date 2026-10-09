"""JC Coaching: tự ghi hình trận TFT, review sau trận bằng Claude, cập nhật meta từ web.

Lệnh:
  python main.py watch            Chạy nền: tự ghi mỗi trận và review khi trận kết thúc
  python main.py review <thư mục> Review lại một trận đã ghi (data/sessions/...)
  python main.py meta             Tìm meta mới nhất trên web (TFTAcademy + trang thống kê)
  python main.py stats            Thống kê 20 trận gần nhất từ Riot API
  python main.py guide            Giáo án leo rank cá nhân hóa theo số liệu của bạn
"""
import argparse
import json
import re
import shutil
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

import assets
import charts
import config
import names
import report
import research
import riot_client
import ui
from coach import Coach, CoachError
from recorder import Recorder, game_running, is_tft
from riot import Riot, RiotError, lobby_summary, me_in, stats as riot_stats, summarize_player

if sys.stdout is None or sys.stderr is None:
    # pythonw.exe không có console: mọi print sẽ lỗi nếu không thay thế luồng ra
    _null = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = sys.stdout or _null
    sys.stderr = sys.stderr or _null
elif sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def ensure_names(cfg):
    """Bảng tên tiếng Việt và bảng ảnh: tải một lần, sau đó dùng lại."""
    if not names.load(cfg):
        try:
            log("Đang tải bảng tên tiếng Việt từ Riot...")
            names.download(cfg, log=log)
        except requests.RequestException as e:
            log(f"Không tải được bảng tên tiếng Việt ({e}), tạm dùng tên tiếng Anh.")
    if not assets.load(cfg):
        try:
            log("Đang tải bảng ảnh từ Community Dragon (khoảng 25 MB, chỉ một lần)...")
            assets.download(cfg, log=log)
        except (requests.RequestException, ValueError) as e:
            log(f"Không tải được bảng ảnh ({e}), giao diện sẽ chỉ có chữ.")


def make_coach(cfg, required=True):
    """Tạo Coach; thiếu Claude API key thì báo rõ thay vì làm sập app."""
    try:
        return Coach(cfg)
    except CoachError as e:
        if required:
            sys.exit(str(e))
        log(str(e))
        return None


LOG_FILE = None


def log(msg):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    ui.log_line(str(msg))
    if LOG_FILE:  # pythonw không có cửa sổ console nên ghi ra file để còn dò lỗi
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def meta_md(cfg, coach=None, force=False) -> str:
    meta, age = report.load_meta(cfg)
    if coach and (force or meta is None or age > cfg["meta_max_age_hours"]):
        log("Đang tìm meta mới trên web (1–3 phút)...")
        try:
            fresh = coach.fetch_meta()
            fresh = names.translate_obj(fresh) if names.load(cfg) else fresh
            meta = merge_meta(meta, fresh)
            report.save_meta(cfg, meta)
            print()
            n_c, n_i, n_a = (len(meta.get(k, [])) for k in ("comps", "items", "augments"))
            log(f"Đã lưu meta: patch {meta.get('patch')} · {n_c} đội hình · {n_i} trang bị · {n_a} lõi")
            if n_c < 12 or n_a < 12:
                log("Nguồn web lần này trả về ít mục. Bấm cập nhật lại nếu muốn đầy đủ hơn.")
        except CoachError as e:
            log(f"Không cập nhật được meta: {e}. Dùng bản đã lưu (nếu có).")
    return report.meta_markdown(meta)


def merge_meta(old: dict | None, fresh: dict) -> dict:
    """Gộp bản meta mới với bản cũ khi cùng patch.

    Nguồn web trả về không đều giữa các lần; giữ lại mục cũ cùng patch để bảng
    không bị hụt, mục trùng tên thì ưu tiên bản mới.
    """
    if not old or old.get("patch") != fresh.get("patch"):
        return fresh
    for key in ("comps", "items", "augments"):
        seen = {str(x.get("name", "")).lower() for x in fresh.get(key, []) if isinstance(x, dict)}
        kept = [x for x in (old.get(key) or [])
                if isinstance(x, dict) and str(x.get("name", "")).lower() not in seen]
        if kept:
            fresh[key] = (fresh.get(key) or []) + kept
    return fresh


def dark_ui_frames(frames: list[Path], max_keep=5) -> list[Path]:
    """Các ảnh là màn hình giao diện chứ không phải cảnh bàn cờ.

    Màn hình chọn lõi và chuẩn bị đội hình làm tối hẳn vùng giữa (độ sáng ~35 so với ~90),
    nên nhận ra được bằng độ sáng mà không cần AI. Đây là những ảnh quan trọng nhất
    để biết người chơi đã chọn lõi nào.
    """
    import cv2
    scored = []
    for f in frames:
        img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        h, w = img.shape
        center = img[int(h * .25):int(h * .8), int(w * .2):int(w * .8)]
        scored.append((float(center.mean()), f))
    if not scored:
        return []
    bright = sorted(v for v, _ in scored)
    median = bright[len(bright) // 2]
    dark = [f for v, f in scored if v < median * 0.55]
    return sorted(dark, key=lambda f: int(f.stem))[:max_keep]


def pick_frames(folder: Path, limit: int, early_share=0.72) -> list[Path]:
    """Chọn ảnh để review, ưu tiên nửa đầu trận.

    Các mốc phải chấm (2-6, 3-2, 3-7, 4-1, 4-2) dồn vào khoảng 60% đầu của trận,
    nên phần này được chia nhiều ảnh hơn; 3 ảnh cuối luôn giữ để thấy kết quả.
    """
    frames = sorted(folder.glob("*.jpg"))
    if len(frames) <= limit:
        return frames
    # bỏ phần chờ vào trận và chọn tướng nhỏ ở đầu, không có gì để chấm
    playable = [f for f in frames if int(f.stem) >= 90] or frames
    ui_frames = dark_ui_frames(playable)          # màn hình chọn lõi, chuẩn bị đội hình
    playable = [f for f in playable if f not in ui_frames]
    tail, body = playable[-3:], playable[:-3]
    budget = max(3, limit - 3 - len(ui_frames))    # chừa chỗ cho ảnh giao diện
    cut = max(1, int(len(body) * 0.6))
    early, late = body[:cut], body[cut:]
    n_early = max(1, round(budget * early_share))
    n_late = max(1, budget - n_early)

    def spread(seq, n):
        if not seq:
            return []
        n = min(n, len(seq))
        step = len(seq) / n
        return [seq[int(i * step)] for i in range(n)]

    picked = spread(early, n_early) + spread(late, n_late) + tail
    ra = sorted(set(picked) | set(ui_frames), key=lambda f: int(f.stem))
    if len(ra) > limit:
        # `budget` có sàn max(3, ...) nên khi limit nhỏ, tổng vẫn có thể vượt. Cắt lại,
        # ưu tiên giữ ảnh giao diện và 3 ảnh cuối vì đó là phần không thay thế được.
        giu = set(ui_frames) | set(tail)
        bo = [f for f in ra if f not in giu]
        while len(ra) > limit and bo:
            ra.remove(bo.pop(len(bo) // 2))     # bỏ từ giữa ra, giữ hai đầu trận
        if len(ra) > limit:
            ra = ra[:limit]
    return ra


_REVIEW_LOCK = threading.Lock()
_REVIEWING: set[str] = set()


def review_session(cfg, session: Path, open_it=True, force=False):
    # chặn hai bản review cùng chạy cho một trận: tốn gấp đôi hạn mức và chậm gấp đôi
    with _REVIEW_LOCK:
        if session.name in _REVIEWING:
            log(f"Trận {session.name} đang được review rồi, bỏ qua lần gọi này.")
            return
        _REVIEWING.add(session.name)
    try:
        return _review_session(cfg, session, open_it, force)
    finally:
        with _REVIEW_LOCK:
            _REVIEWING.discard(session.name)


def embed_frames(text: str, session: Path, frames: list[Path]) -> str:
    """Đổi dấu [[anh:mm:ss]] thành ảnh thật, và thêm dải ảnh ở cuối báo cáo."""
    by_sec = {int(f.stem): f for f in frames}

    def repl(m):
        mm, ss = int(m.group(1)), int(m.group(2))
        want = mm * 60 + ss
        if not by_sec:
            return ""
        sec = min(by_sec, key=lambda t: abs(t - want))       # ảnh gần thời điểm đó nhất
        if abs(sec - want) > 90:
            return ""
        return f"\n![{mm:02d}:{ss:02d}](/frame?session={session.name}&t={sec:05d})\n"

    out = re.sub(r"\[\[anh:(\d{1,2}):(\d{2})\]\]", repl, text)
    rest = [f for f in frames if f"&t={f.stem}" not in out]     # bỏ ảnh đã chèn ở trên
    if not rest:
        return out
    strip = "\n\n## Các ảnh còn lại của trận\n\n" + " ".join(
        f"![{int(f.stem) // 60:02d}:{int(f.stem) % 60:02d}]"
        f"(/frame?session={session.name}&t={f.stem})" for f in rest)
    return out + strip


def embed_charts(cfg, text: str) -> str:
    """Đổi dấu [[bieudo]] thành biểu đồ SVG dựng từ dữ liệu thật của người chơi.

    Hồ sơ chưa có thì bỏ luôn dấu này, thà thiếu biểu đồ còn hơn vẽ khung rỗng.
    """
    prof_path = cfg["data_path"] / "profile.json"
    places, blocks = [], []
    if prof_path.exists():
        try:
            prof = json.loads(prof_path.read_text(encoding="utf-8"))
            places = [p.get("place") for p in prof.get("placements") or []]
        except (json.JSONDecodeError, OSError):
            places = []
    bars = charts.placement_bars(places)
    if bars:
        blocks.append(charts.block(
            f"Phân bố hạng {len(places)} trận gần nhất", bars,
            "Cột vàng là hạng 1, cột xanh là Top 4, cột đỏ là ngoài Top 4."))
    hist = charts.load_history(cfg)
    lp = charts.lp_line(hist)
    if lp:
        blocks.append(charts.block(
            "LP theo thời gian", lp,
            "Riot API không trả lịch sử LP, nên đường này dựng từ các mốc app tự ghi lại "
            "kể từ lần đầu chạy; càng chơi lâu đường càng dài."))
    elif hist:
        blocks.append("\n\n*Mới có một mốc LP nên chưa vẽ được đường; "
                      "sau vài trận nữa biểu đồ sẽ hiện.*\n\n")
    body = "".join(blocks)
    if "[[bieudo]]" in text:
        return text.replace("[[bieudo]]", body)
    return text + body if body else text


def _review_session(cfg, session: Path, open_it=True, force=False):
    coach = make_coach(cfg, required=False)
    meta_file = session / "session.json"
    if not meta_file.exists():
        log(f'"{session}" không phải thư mục trận (thiếu session.json).')
        return
    try:
        info = json.loads(meta_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log(f"Không đọc được session.json của trận này: {e}")
        return
    riot = Riot(cfg)
    match_info, recent = None, None
    if riot.enabled:
        try:
            log("Đang lấy dữ liệu trận từ Riot API...")
            m = riot.find_match_near(info.get("end") or time.time(), info.get("start") or 0)
            if m:
                match_info = {
                    "me": summarize_player(me_in(m, riot.puuid())),
                    "lobby": lobby_summary(m),
                    "set": m["info"].get("tft_set_number"),
                    "patch": m["info"].get("game_version"),
                    "rank": riot.rank(),
                }
                config.write_json(session / "match.json", m)
            elif not force:
                log("Riot API không có trận TFT nào khớp (có thể là trận Liên Minh), bỏ qua review. "
                    f"Nếu đúng là TFT, chạy: python main.py review \"{session}\"")
                return
            else:
                log("Chưa thấy trận trên Riot API, review chỉ bằng ảnh.")
            recent = riot_stats(riot)
        except (RiotError, requests.RequestException, KeyError, ValueError) as e:
            log(f"Riot API: {e}")   # thiếu số liệu Riot không được chặn review bằng ảnh

    if match_info and 0 < cfg["skip_review_if_top"] >= match_info["me"]["placement"] and not force:
        log(f'Hạng {match_info["me"]["placement"]} (trong nhóm bỏ qua), không review để tiết kiệm hạn mức. '
            f'Muốn review vẫn chạy được: python main.py review "{session}"')
        return
    if coach is None:
        log(f'Đã lưu ảnh trận. Sau khi thiết lập xong AI, chạy: python main.py review "{session}"')
        return
    limit = cfg["max_frames_with_match_data"] if match_info else cfg["max_frames_for_review"]
    frames = pick_frames(session / "keyframes", limit, cfg.get("frames_early_share", 0.6))
    if not frames:
        log("Không có khung hình nào để phân tích.")
        return
    log(f"Gửi {len(frames)} khung hình cho Claude phân tích...\n")
    try:
        manh_yeu = None
        pf = cfg["data_path"] / "profile.json"
        if pf.exists():
            try:
                manh_yeu = research.strengths_weaknesses(
                    json.loads(pf.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                manh_yeu = None
        text = coach.review(frames, match_info, meta_md(cfg), recent, assets.augments(cfg),
                            manh_yeu=manh_yeu)
    except CoachError as e:
        log(f"Review thất bại: {e}")
        return
    text = embed_frames(text, session, frames)
    text = embed_charts(cfg, text)
    place = f"Hạng {match_info['me']['placement']} · " if match_info else ""
    when = datetime.fromtimestamp(info.get("start") or time.time())
    path = report.save_report(session, "review", "Review trận TFT", text,
                              f"{place}{when:%d/%m/%Y %H:%M}", open_it)
    print()
    log(f"Đã lưu báo cáo: {path}")


def watch_loop(cfg):
    """Vòng lặp: chờ trận, ghi hình, review. Chạy ở luồng nền."""
    sessions = cfg["data_path"] / "sessions"
    last_skip = None
    while True:
        # Một ngoại lệ bất kỳ ở đây từng giết cả luồng ghi hình, trong khi giao diện
        # vẫn hiện 'Đang chờ trận'. Bắt hết, ghi nhật ký, rồi chạy tiếp vòng sau.
        try:
            ok, why = is_tft(cfg)
            while not ok:
                if why not in ("không có game", last_skip):   # chỉ báo một lần mỗi tình huống
                    log(f"Bỏ qua: {why}.")
                    last_skip = why
                time.sleep(3)
                ok, why = is_tft(cfg)
            last_skip = None
            start = time.time()
            session = sessions / datetime.now().strftime("%Y%m%d-%H%M%S")
            rec = Recorder(cfg, session)
            rec.start()
            # để nút "Thoát hẳn" ở khay dừng ghi hình tử tế thay vì giết ngang
            ui.CLEANUP.clear()
            ui.register_cleanup(rec.stop)
            # ghi mốc thời gian ngay, để app tắt giữa chừng vẫn review lại được
            session.mkdir(parents=True, exist_ok=True)
            config.write_json(session / "session.json", {"start": start, "end": None})
            ui.STATE.update(phase="recording", session=session.name, started_at=start)
            log(f"Phát hiện trận đấu, đang ghi → {session.name}")
            aborted = None
            while game_running(cfg.get("game_processes") or cfg["game_process"]):
                time.sleep(3)
                if rec.error:
                    break
                # API trong game chỉ lên sau vài chục giây; kiểm tra lại suốt 3 phút đầu
                if time.time() - start < 180:
                    still_ok, reason = is_tft(cfg)
                    if not still_ok and reason != "không có game":
                        aborted = reason
                        break
            rec.stop()
            ui.CLEANUP.clear()
            if aborted:
                shutil.rmtree(session, ignore_errors=True)
                ui.STATE.update(phase="idle", session=None, started_at=None)
                log(f"Không phải trận TFT ({aborted}), đã hủy bản ghi.")
                while game_running(cfg.get("game_processes") or cfg["game_process"]):
                    time.sleep(5)
                continue
            ui.STATE.update(phase="idle", session=None, started_at=None)
            end = time.time()
            if rec.error:
                log(f"Lỗi ghi hình: {rec.error}")
            minutes = (end - start) / 60
            config.write_json(session / "session.json", {"start": start, "end": end})
            drift = ""
            if rec.real_fps and abs(rec.real_fps - cfg["record_fps"]) / cfg["record_fps"] > 0.2:
                drift = f" · tốc độ ghi thực tế {rec.real_fps} fps so với {cfg['record_fps']} đặt trước, video sẽ lệch nhịp"
            log(f"Trận kết thúc sau {minutes:.1f} phút, {rec.frames_written} khung hình.{drift}")
            if minutes < cfg["min_game_minutes"]:
                log("Trận quá ngắn (remake hoặc thoát sớm), bỏ qua review.")
                continue
            ui.STATE["busy"] = f"Đang review {session.name}"
            try:
                review_session(cfg, session, open_it=False)
            finally:
                ui.STATE["busy"] = None
            log("Chờ trận tiếp theo...")
        except Exception as e:  # noqa: BLE001 - thà lặp tiếp còn hơn chết im lặng
            log(f'Lỗi trong vòng theo dõi trận: {type(e).__name__}: {e}')
            ui.STATE.update(phase='idle', session=None, started_at=None, busy=None)
            time.sleep(5)


def cmd_watch(cfg, window=True):
    global LOG_FILE
    LOG_FILE = cfg["data_path"] / "app.log"
    if ui.already_running(cfg["ui_port"]):
        # hai bản cùng chạy sẽ ghi hai bản ghi và review hai lần cho cùng một trận
        try:
            r = requests.post(f"http://127.0.0.1:{cfg['ui_port']}/api/show", timeout=4)
            ok = r.status_code == 200
        except requests.RequestException:
            ok = False
        if ok:
            log("Đã có một bản JC Coaching đang chạy, đã hiện cửa sổ của bản đó lên.")
        else:
            log("Đã có một bản đang chạy nhưng không hiện được cửa sổ. "
                "Bấm biểu tượng JC ở khay hệ thống để mở, hoặc thoát bản đó rồi bật lại.")
        return
    if getattr(sys.stdout, "name", "") == os.devnull:
        # không có console: dồn cả nhật ký lẫn nội dung Claude trả về vào app.log
        sys.stdout = sys.stderr = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    ensure_names(cfg)
    engine = "Claude Code (gói thuê bao)" if cfg.get("engine", "claude_cli") == "claude_cli" else "Claude API"
    log(f"JC Coaching khởi động · chế độ AI: {engine}")
    riot = Riot(cfg)
    if riot.enabled:
        try:
            cfg["_puuid"] = riot.puuid()
        except Exception as e:  # noqa: BLE001 - chỉ dùng để hiện hạng trong danh sách trận
            log(f"Riot API: {e}")
    ui.STATE.update(engine=engine, riot=riot.enabled,
                    account=f"{cfg['riot_game_name']}#{cfg['riot_tag_line']}" if riot.enabled else None)
    url = ui.start(cfg, {
        "meta": lambda: meta_md(cfg, make_coach(cfg, required=False), force=True),
        "review": lambda folder: review_session(cfg, folder, open_it=False, force=True),
        "research": lambda: cmd_research(cfg),
        "account": lambda riot_id=None, detect=False: set_account(cfg, riot_id, detect),
        "advise": lambda situation: cmd_advise(cfg, situation, open_report=False),
        "handbook": lambda: cmd_handbook(cfg),
        "profile": lambda: cmd_profile(cfg),
    }, open_browser=False)

    threading.Thread(target=lambda: meta_md(cfg, make_coach(cfg, required=False)), daemon=True).start()
    threading.Thread(target=watch_loop, args=(cfg,), daemon=True).start()

    if window and cfg["open_ui"] and ui.open_window(url, cfg):
        log("Cửa sổ đã đóng. Thoát app.")
        return
    if cfg["open_ui"]:  # không mở được cửa sổ ứng dụng thì đành dùng trình duyệt
        log("KHÔNG mở được cửa sổ app nên phải mở bằng trình duyệt. "
            "Lý do ghi ở dòng nhật ký ngay phía trên; thường là thiếu pywebview "
            "hoặc thiếu WebView2 Runtime của Windows.")
        import webbrowser
        webbrowser.open(url)
    log(f"Giao diện: {url} · Ctrl+C để thoát.")
    while True:
        time.sleep(1)


def set_account(cfg, riot_id=None, detect=False) -> dict:
    """Chọn tài khoản Riot: tự nhận từ Riot Client, hoặc nhập tay dạng Tên#TAG."""
    if detect:
        acc = riot_client.current_account()          # ném NotLoggedIn nếu chưa mở client
        name, tag = acc["game_name"], acc["tag_line"]
        log(f"Nhận diện tài khoản đang đăng nhập: {name}#{tag}")
    else:
        if "#" not in (riot_id or ""):
            raise ValueError("Riot ID phải có dạng Tên#TAG, ví dụ Jordi#2302")
        name, tag = riot_id.rsplit("#", 1)
        name, tag = name.strip(), tag.strip()

    cfg["riot_game_name"], cfg["riot_tag_line"] = name, tag
    cfg.pop("_puuid", None)
    riot = Riot(cfg)
    cfg["_puuid"] = riot.puuid()                      # xác nhận tài khoản có thật
    config.save({"riot_game_name": name, "riot_tag_line": tag})
    ui.STATE.update(riot=True, account=f"{name}#{tag}")
    log(f"Đã lưu tài khoản {name}#{tag}")
    cmd_profile(cfg)
    return {"game_name": name, "tag_line": tag}


def cmd_research(cfg, rebuild=False):
    """Thu thập trận từ nhiều server rồi tự tính bảng theo carry."""
    ensure_names(cfg)
    out = cfg["data_path"] / "global_stats.json"
    if rebuild:
        data = research.aggregate_from_cache(cfg, log=log)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"Xong: {len(data['carries'])} carry có đủ mẫu")
        return data
    if not cfg["riot_api_key"]:
        log("Cần riot_api_key trong config.json.")
        return
    old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    if old and old["meta"].get("key_fingerprint") != research.key_fingerprint(cfg["riot_api_key"]):
        log("Phát hiện key Riot mới, sẽ thu thập lại từ đầu.")
    col = research.Collector(cfg, log=log)

    def progress(done, target):
        ui.PROGRESS["text"] = f"{done}/{target} trận"
        log(f"Đã tải {done}/{target} trận")

    try:
        data = col.run(on_progress=progress)
    except PermissionError as e:
        log(str(e))
        return
    except KeyboardInterrupt:
        log("Đã dừng thu thập.")
        return
    finally:
        ui.PROGRESS["text"] = None
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    m = data["meta"]
    log(f"Xong: {m['matches']} trận · {m['participants']} lượt chơi · {len(data['carries'])} carry có đủ mẫu")
    return data


def cmd_names(cfg):
    """Tải lại bảng tên tiếng Việt và dịch luôn phần meta đã lưu."""
    names.download(cfg, log=log)
    assets.download(cfg, log=log)
    path = cfg["data_path"] / "meta.json"
    if path.exists():
        meta = names.translate_obj(json.loads(path.read_text(encoding="utf-8")))
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        log("Đã dịch phần meta đang lưu sang tiếng Việt.")


def cmd_profile(cfg):
    """Hồ sơ cá nhân: rank, 20 trận gần nhất, bài hay chơi, Top 4, Top 1."""
    ensure_names(cfg)
    riot = Riot(cfg)
    if not riot.enabled:
        log("Cần riot_api_key, riot_game_name và riot_tag_line trong config.json.")
        return
    try:
        prof = research.personal_profile(riot, cfg["profile_games"])
    except (RiotError, PermissionError) as e:
        log(f"Riot API: {e}")
        return
    if not prof.get("games"):
        log("Không tìm thấy trận xếp hạng thường nào gần đây.")
        return
    try:
        charts.record_lp(cfg, riot.rank_raw())     # tích dần lịch sử LP để vẽ biểu đồ đường
    except (RiotError, requests.RequestException) as e:
        log(f"Không ghi được mốc LP: {e}")
    gpath = cfg["data_path"] / "global_stats.json"
    if gpath.exists():
        glob = json.loads(gpath.read_text(encoding="utf-8"))
        prof["vs_global"] = research.compare_with_global(prof, glob)
        prof["suggestions"] = research.suggestions(prof, glob)
    # điểm mạnh/yếu tính được cả khi chưa có bảng số liệu chung
    prof["manh_yeu"] = research.strengths_weaknesses(prof, glob if gpath.exists() else None)
    config.write_json(cfg["data_path"] / "profile.json", prof)
    log(f"Hồ sơ: {prof.get('rank') or 'chưa có rank'} · {prof['games']} trận · hạng TB {prof['avg_place']} · "
        f"Top 4 {prof['top4']}% · Top 1 {prof['win']}%")
    return prof


def cmd_handbook(cfg):
    """Tra tài liệu Dishsoap trên web rồi lưu thành cẩm nang."""
    coach = make_coach(cfg)
    src = cfg["data_path"] / "sources"
    files = [f for f in sorted(src.glob("*.txt")) if f.name != "list.txt"] if src.exists() else []
    batches, cur = [], ""
    for f in files:
        t = f.read_text(encoding="utf-8", errors="ignore")   # phụ đề tự động đôi khi lẫn ký tự lạ
        if len(cur) + len(t) > cfg.get("handbook_batch_chars", 90000) and cur:
            batches.append(cur)
            cur = ""
        cur += t + "\n\n=====\n\n"
    if cur:
        batches.append(cur)
    if batches:
        log(f"Đọc {len(files)} transcript, chia {len(batches)} đợt, tổng "
            f"{sum(len(b) for b in batches) // 1000} KB. Mất khoảng {len(batches) * 2 + 2} phút.")
    else:
        log("Chưa có transcript trong data/sources, sẽ tra trên web.")

    def step(done, total):
        ui.PROGRESS["text"] = f"đợt {done}/{total}"
        log(f"Xong đợt {done}/{total}")

    try:
        text = coach.fetch_handbook(batches, on_step=step,
                                    cache_dir=cfg["data_path"] / "handbook_parts")
    except CoachError as e:
        log(f"Không tra được: {e}")
        return
    finally:
        ui.PROGRESS["text"] = None
    out = cfg["data_path"] / "handbook.md"
    out.write_text(text, encoding="utf-8")
    print()
    log(f"Đã lưu cẩm nang: {len(text)} ký tự · {text.count(chr(10) + '#')} mục")
    return text


def cmd_advise(cfg, situation: str, open_report=True):
    """Hệ 4 agent tư vấn tình huống, dùng đúng dữ liệu app đang có."""
    ensure_names(cfg)
    coach = make_coach(cfg)
    blocks = {}
    g = cfg["data_path"] / "global_stats.json"
    if g.exists():
        data = json.loads(g.read_text(encoding="utf-8"))
        blocks["Số liệu app tự thu thập (rút gọn)"] = json.dumps({
            "meta": data.get("meta"),
            "carries": data.get("carries", [])[:20],
            "traits": data.get("traits", [])[:12],
            "items": data.get("items", [])[:20],
        }, ensure_ascii=False)
    pr = cfg["data_path"] / "profile.json"
    if pr.exists():
        prof = json.loads(pr.read_text(encoding="utf-8"))
        blocks["Hồ sơ người chơi"] = json.dumps({
            k: prof.get(k) for k in ("riot_id", "rank", "games", "avg_place", "top4", "win",
                                     "by_carry", "vs_global", "suggestions")}, ensure_ascii=False)
    blocks["Meta từ web"] = report.meta_markdown(report.load_meta(cfg)[0])[:6000]

    log("Đang chạy hệ 4 agent...\n")
    try:
        text = coach.advise(situation, blocks)
    except CoachError as e:
        sys.exit(str(e))
    path = report.save_report(cfg["data_path"] / "reports", f"tu-van-{datetime.now():%Y%m%d-%H%M%S}",
                              "Tư vấn tình huống", text, situation[:120], open_it=open_report)
    config.write_json(cfg["data_path"] / "advice.json",
                      {"situation": situation, "text": text,
                       "at": datetime.now().strftime("%d/%m %H:%M")})
    print()
    log(f"Đã lưu: {path}")
    return text


def cmd_stats(cfg):
    riot = Riot(cfg)
    if not riot.enabled:
        sys.exit("Cần điền riot_api_key, riot_game_name, riot_tag_line trong config.json.")
    s = riot_stats(riot)
    if not s.get("games"):
        sys.exit("Không có trận xếp hạng thường nào gần đây.")
    rank = riot.rank()
    print(f"\nRank: {rank or cfg['rank']}")
    print(f"{s['games']} trận · hạng TB {s['avg_place']} · Top 4 {s['top4_rate']}% · Top 1 {s['win_rate']}%")
    print("Gần nhất → cũ nhất:", " ".join(map(str, s["recent"])))
    print("\nTộc/hệ chính      Trận  Hạng TB")
    for t in s["by_main_trait"]:
        print(f"{t['trait'][:16]:<17}{t['games']:>4}  {t['avg']:>6}")
    print("\nLõi hay chọn:", ", ".join(f"{a} ×{n}" for a, n in s["top_augments"]))


def cmd_guide(cfg):
    coach, riot = make_coach(cfg), Riot(cfg)
    s, rank = None, cfg["rank"]
    if riot.enabled:
        try:
            s, rank = riot_stats(riot), riot.rank() or rank
        except RiotError as e:
            log(f"Riot API: {e}")
    try:
        text = coach.rank_plan(rank, s, meta_md(cfg, coach))
    except CoachError as e:
        sys.exit(str(e))
    path = report.save_report(cfg["data_path"] / "reports", f"giao-an-{datetime.now():%Y%m%d}",
                              "Giáo án leo rank", text, rank)
    print()
    log(f"Đã lưu: {path}")


def main():
    ap = argparse.ArgumentParser(description="JC Coaching cho TFT")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch")
    w.add_argument("--no-window", action="store_true", help="chạy trong terminal, không mở cửa sổ ứng dụng")
    r = sub.add_parser("review")
    r.add_argument("session", type=Path)
    sub.add_parser("meta")
    sub.add_parser("stats")
    rs = sub.add_parser("research")
    rs.add_argument("--rebuild", action="store_true", help="tính lại từ dữ liệu đã tải, không gọi API")
    sub.add_parser("profile")
    a = sub.add_parser("account")
    a.add_argument("riot_id", nargs="?", help="Tên#TAG; bỏ trống để tự nhận từ Riot Client")
    sub.add_parser("guide")
    sub.add_parser("names")
    sub.add_parser("handbook", help="tra tài liệu Dishsoap thành cẩm nang")
    ad = sub.add_parser("advise", help="hệ 4 agent tư vấn một tình huống")
    ad.add_argument("situation", help="mô tả tình huống: stage, máu, vàng, đồ, tướng, lõi")
    args = ap.parse_args()
    cfg = config.load()

    if args.cmd == "watch":
        try:
            cmd_watch(cfg, window=not args.no_window)
        except KeyboardInterrupt:
            log("Đã thoát.")
    elif args.cmd == "review":
        review_session(cfg, args.session, open_it=False, force=True)
    elif args.cmd == "meta":
        md = meta_md(cfg, make_coach(cfg), force=True)
        if md:
            path = report.save_report(cfg["data_path"] / "reports", "meta", "Meta TFT", md)
            log(f"Đã lưu: {path}")
    elif args.cmd == "stats":
        cmd_stats(cfg)
    elif args.cmd == "research":
        cmd_research(cfg, rebuild=args.rebuild)
    elif args.cmd == "profile":
        cmd_profile(cfg)
    elif args.cmd == "account":
        try:
            set_account(cfg, args.riot_id, detect=not args.riot_id)
        except (riot_client.NotLoggedIn, ValueError, RiotError) as e:
            sys.exit(str(e))
    elif args.cmd == "guide":
        cmd_guide(cfg)
    elif args.cmd == "names":
        cmd_names(cfg)
    elif args.cmd == "handbook":
        cmd_handbook(cfg)
    elif args.cmd == "advise":
        cmd_advise(cfg, args.situation)


if __name__ == "__main__":
    main()
