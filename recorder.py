"""Phát hiện trận đấu và ghi hình màn hình game (720p, fps thấp) + lưu khung hình chính."""
import json
import statistics
import threading
import time
from collections import deque
from pathlib import Path

import cv2
import mss
import numpy as np
import psutil
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TFT_MAPS = {22}   # sa bàn TFT

try:  # pywin32 là tùy chọn: có thì chỉ ghi đúng cửa sổ game
    import win32gui
    import win32process
except ImportError:
    win32gui = win32process = None


def game_process(names):
    """Tiến trình game đang chạy, kèm dòng lệnh. None nếu không có.

    `names` là một tên hoặc danh sách tên; trả về tên khớp đầu tiên theo thứ tự đưa vào.
    """
    wanted = [names] if isinstance(names, str) else list(names)
    running = {}
    for p in psutil.process_iter(["name", "pid", "cmdline"]):
        n = p.info["name"]
        if n in wanted and n not in running:
            cmd = " ".join(p.info.get("cmdline") or [])
            running[n] = {"name": n, "pid": p.info["pid"], "cmdline": cmd,
                          "replay": ".rofl" in cmd.lower()}
    for n in wanted:
        if n in running:
            return running[n]
    return None


def game_running(names) -> bool:
    return game_process(names) is not None


def live_mode(timeout=2.5):
    """Chế độ trận đang chạy, đọc từ API trong game (cổng 2999).

    Liên Minh trả về CLASSIC / ARAM / ... kèm map 11, 12. TFT không phục vụ API này
    nên trả về None — đó chính là dấu hiệu để phân biệt.
    """
    try:
        r = requests.get("https://127.0.0.1:2999/liveclientdata/gamestats",
                         verify=False, timeout=timeout)
        if r.status_code != 200:
            return None
        d = r.json()
        return {"mode": str(d.get("gameMode") or ""), "map": d.get("mapNumber")}
    except (requests.RequestException, ValueError):
        return None


def is_tft(cfg) -> tuple[bool, str]:
    """Có nên ghi hình không, kèm lý do để ghi nhật ký."""
    proc = game_process(cfg.get("game_processes") or cfg["game_process"])
    if not proc:
        return False, "không có game"
    if proc["replay"] and cfg.get("skip_replays", True):
        return False, "đang xem lại replay"
    # TFT chạy client riêng: thấy tiến trình này là chắc chắn TFT
    if "TFT" in proc["name"].upper():
        return True, "trận TFT"
    # còn lại là client cũ dùng chung với Liên Minh, phải hỏi API trong game
    info = live_mode()
    if info:
        mode, mp = info["mode"].upper(), info["map"]
        if "TFT" not in mode and mp not in TFT_MAPS:
            return False, f"trận Liên Minh ({info['mode']}, map {mp})"
    return True, "trận TFT"


def _game_o_truoc(pid) -> bool:
    """Cửa sổ đang ở trước có thuộc tiến trình game không."""
    if not pid or win32process is None:
        return True          # không xác định được thì giữ hành vi cũ
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False
        return win32process.GetWindowThreadProcessId(hwnd)[1] == pid
    except Exception:  # noqa: BLE001 - cửa sổ vừa đóng
        return False


def game_window_region(pid=None, title: str = ""):
    """Vùng cửa sổ game để ghi hình.

    Ưu tiên tìm theo tiến trình (tên cửa sổ TFT là "TFT  " và đổi theo ngôn ngữ),
    nếu không có pid thì mới tìm theo tên cửa sổ.
    """
    if win32gui is None:
        return None
    # mss chụp PIXEL đang hiện trên màn hình ở vùng đó, không phải nội dung riêng của
    # cửa sổ game. Cửa sổ game vẫn "visible" khi bị cửa sổ khác đè lên, nên phải kiểm tra
    # nó có đang ở trước hay không, nếu không sẽ chụp nhầm trình duyệt, tin nhắn, email.
    if not _game_o_truoc(pid):
        return None
    best = None

    def rect_of(hwnd):
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if right - left < 400 or bottom - top < 300:
            return None
        return {"left": left, "top": top, "width": right - left, "height": bottom - top}

    if pid and win32process is not None:
        def cb(hwnd, _):
            nonlocal best
            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return
            try:
                if win32process.GetWindowThreadProcessId(hwnd)[1] != pid:
                    return
            except Exception:  # noqa: BLE001 - cửa sổ vừa đóng
                return
            r = rect_of(hwnd)
            if r and (best is None or r["width"] * r["height"] > best["width"] * best["height"]):
                best = r
        win32gui.EnumWindows(cb, None)
        if best:
            return best
    if title:
        hwnd = win32gui.FindWindow(None, title)
        if hwnd and not win32gui.IsIconic(hwnd):
            return rect_of(hwnd)
    return None


class DarkWatch:
    """Nhận ra màn hình tối đi so với mức nền, để bắn ảnh dày hơn lúc chọn lõi.

    Hai điểm khác bản trước, đều cần thiết:
    - Mức nền lấy mẫu theo THỜI GIAN (mỗi giây một mẫu, giữ 60 giây) chứ không theo
      khung hình. Lấy theo khung hình ở 8 fps thì lịch sử chỉ dài 5 giây.
    - Chỉ lấy mẫu khi màn hình đang sáng. Nếu không, một màn chọn lõi dài 30 giây
      sẽ tự kéo mức nền xuống rồi tắt chính nó sau vài giây.
    """

    def __init__(self, sample_sec=1.0, history_sec=60.0, ratio=0.78, min_samples=8,
                 bam_them_sec=8.0):
        self.sample_sec, self.history_sec = sample_sec, history_sec
        self.ratio, self.min_samples = ratio, min_samples
        self.bam_them_sec = bam_them_sec
        self.samples = deque()        # (thời điểm, độ sáng) của những lúc màn hình sáng
        self.last_sample = -1e9
        self.toi_lan_cuoi = -1e9

    def update(self, brightness: float, now: float) -> bool:
        """Trả về True nếu lúc này màn hình đang tối bất thường."""
        while self.samples and now - self.samples[0][0] > self.history_sec:
            self.samples.popleft()
        if len(self.samples) < self.min_samples:
            dark = False
        else:
            base = statistics.median(v for _, v in self.samples)
            dark = brightness < base * self.ratio
        if dark:
            self.toi_lan_cuoi = now
        elif now - self.last_sample >= self.sample_sec:
            self.samples.append((now, brightness))
            self.last_sample = now
        # Bám thêm vài giây sau khi màn sáng lại: người chơi vừa bấm chọn lõi thì lõi mới
        # hiện ở cột trái, và đó là khung hình DUY NHẤT xác nhận họ chọn cái nào.
        return dark or (now - self.toi_lan_cuoi) <= self.bam_them_sec


class Recorder:
    def __init__(self, cfg: dict, session_dir: Path):
        self.cfg = cfg
        self.dir = session_dir
        self.keyframes = session_dir / "keyframes"
        self.keyframes.mkdir(parents=True, exist_ok=True)
        self.dark_seconds = []        # giây của các khung hình chụp lúc màn hình tối (vòng chọn lõi)
        self.video_path = session_dir / "game.mp4"
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.started_at = None
        proc = game_process(cfg.get("game_processes") or cfg["game_process"])
        self.pid = proc["pid"] if proc else None
        self.frames_written = 0
        self.real_fps = None
        self.skipped_frames = 0
        self.error = None

    def start(self):
        self.started_at = time.time()
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=10)

    def _run(self):
        c = self.cfg
        w, h, fps = c["record_width"], c["record_height"], c["record_fps"]
        writer = None
        if c["keep_video"]:
            writer = cv2.VideoWriter(str(self.video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        frame_dt = 1.0 / fps
        next_t = time.perf_counter()
        last_key = -1e9
        last_small = None
        # Màn chọn lõi chỉ hiện vài giây rồi tắt. Với nhịp 12 giây thì gần như luôn chụp trượt,
        # nên phải nhận ra lúc màn hình tối đi rồi bắn ảnh dày hơn.
        dark_gap = float(c.get("keyframe_interval_dark_sec", 2.0))
        watch = DarkWatch()
        try:
            with mss.mss() as sct:
                fallback = sct.monitors[min(c["monitor"], len(sct.monitors) - 1)]
                skipped = 0
                while not self._stop.is_set():
                    region = game_window_region(self.pid, c.get("game_window_title", ""))
                    if region is None:
                        # cửa sổ game không ở trước: bỏ qua, tránh chụp nhầm desktop của người dùng
                        if c.get("record_only_game_window", True):
                            skipped += 1
                            self.skipped_frames = skipped
                            time.sleep(frame_dt)
                            next_t = time.perf_counter()
                            continue
                        region = fallback
                    raw = np.array(sct.grab(region))
                    frame = cv2.resize(cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR), (w, h), interpolation=cv2.INTER_AREA)
                    if writer is not None:
                        writer.write(frame)
                    self.frames_written += 1

                    elapsed = time.time() - self.started_at
                    small = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY)
                    center = float(np.mean(small[22:72, 32:128]))
                    dark = watch.update(center, elapsed)
                    gap = dark_gap if dark else c["keyframe_interval_sec"]
                    if elapsed - last_key >= gap:
                        changed = last_small is None or                             float(np.mean(cv2.absdiff(small, last_small))) >= c["keyframe_min_diff"]
                        if changed or dark:   # màn chọn lõi đứng yên nhưng vẫn phải lưu
                            # lưu ở độ phân giải gốc của cửa sổ game: biểu tượng lõi và tên tướng
                            # ở bản 720p quá nhỏ để đọc được
                            full = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
                            cv2.imwrite(str(self.keyframes / f"{int(elapsed):05d}.jpg"), full,
                                        [cv2.IMWRITE_JPEG_QUALITY, 88])
                            if dark:
                                self.dark_seconds.append(int(elapsed))
                            last_small = small
                        last_key = elapsed

                    next_t += frame_dt
                    delay = next_t - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
                    else:  # máy chậm: bỏ nhịp thay vì dồn khung
                        next_t = time.perf_counter()
        except Exception as e:  # noqa: BLE001 - báo lỗi ra ngoài thay vì chết im lặng
            self.error = e
        finally:
            if writer is not None:
                writer.release()
            # Danh sách này là thông tin duy nhất đáng tin để biết khung hình nào ở vòng
            # chọn lõi: lúc ghi mới có mức nền độ sáng của chính trận đó để so.
            try:
                (self.dir / "dark_frames.json").write_text(
                    json.dumps(sorted(set(self.dark_seconds))), encoding="utf-8")
            except OSError:
                pass
            elapsed = time.time() - (self.started_at or time.time())
            if elapsed > 30 and self.frames_written:
                self.real_fps = round(self.frames_written / elapsed, 1)
