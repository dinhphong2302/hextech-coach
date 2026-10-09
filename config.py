"""Đọc cấu hình từ config.json (ghi đè lên giá trị mặc định)."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DEFAULTS = {
    # "claude_cli": dùng Claude Code với gói Pro/Max (không tốn tiền API)
    # "api": gọi Claude API, tính tiền theo lượt dùng
    "engine": "claude_cli",
    "claude_cli_path": "claude",
    "cli_model": "",           # để trống thì dùng model mặc định của Claude Code
    "cli_timeout_sec": 1200,

    # Chỉ dùng khi engine = "api". Để trống thì SDK đọc biến ANTHROPIC_API_KEY
    "anthropic_api_key": "",
    "model": "claude-opus-5",

    # Riot API (developer.riotgames.com). Để trống thì app vẫn chạy, chỉ thiếu số liệu trận.
    "riot_api_key": "",
    "riot_game_name": "",
    "riot_tag_line": "",
    "account_region": "asia",   # account-v1: americas | asia | europe
    "match_region": "sea",      # tft-match-v1: VN/SEA dùng "sea"
    "platform": "vn2",          # tft-league-v1: vn2, kr, na1, euw1...

    # Rank hiện tại, để coach nói đúng trình độ
    "rank": "Lục Bảo",

    # Ghi hình
    # TFT nay chay client rieng (Unreal); League of Legends.exe chi con cho ban cu
    "game_processes": ["TFTClient-Win64-Shipping.exe", "TFTClient.exe", "League of Legends.exe"],
    "legacy_process": "League of Legends.exe",
    "game_process": "TFTClient-Win64-Shipping.exe",
    "skip_replays": True,      # không ghi khi đang xem lại replay (.rofl)
    "monitor": 1,
    "record_width": 1280,
    "record_height": 720,
    "record_fps": 8,
    "keyframe_interval_sec": 12,
    "keyframe_interval_dark_sec": 2.0,   # màn chọn lõi chỉ hiện vài giây, phải chụp dày hơn
    "record_only_game_window": True,   # khong chup khi cua so game khong o truoc
    "keyframe_min_diff": 4.0,      # bỏ qua ảnh gần giống ảnh trước (màn hình chờ, đứng yên)
    "min_game_minutes": 5,
    "keep_video": True,

    # Phân tích
    "max_frames_for_review": 20,          # khi KHÔNG có dữ liệu Riot
    "max_frames_with_match_data": 18,     # đủ ảnh để chấm 8 mốc giai đoạn
    "frames_early_share": 0.72,            # tỉ lệ ảnh dành cho nửa đầu trận (nơi có nhiều mốc)
    "use_ui_crops": True,          # cắt và phóng to vùng giao diện trước khi cho AI đọc ảnh
    "review_parallel": 6,                 # số nhóm ảnh đọc song song ở giai đoạn 1
    "frames_per_worker": 3,               # mỗi nhóm bao nhiêu ảnh
    "review_effort": "medium",            # medium rẻ hơn high, chỉ dùng cho engine "api"
    "skip_review_if_top": 0,              # 0 = review mọi trận; đặt 2 để bỏ qua trận Top 1-2
    "meta_max_age_hours": 72,

    # Tự dựng thống kê từ Riot API
    "research_platforms": ["vn2", "kr", "na1", "euw1", "br1", "jp1"],
    "research_tiers": ["challenger", "grandmaster"],
    "research_target_matches": 600,
    "research_matches_per_player": 2,
    "riot_per_sec": 18,       # key development: 20/giây, 100/2 phút
    "riot_per_2min": 95,
    "profile_games": 20,

    # Cửa sổ web
    "ui_port": 8787,
    "open_ui": True,
    "data_dir": "data",
}


def write_json(path, data) -> None:
    """Ghi JSON qua file tạm rồi đổi tên.

    Ghi thẳng thì tắt máy hoặc thoát app giữa chừng sẽ để lại file cắt cụt, và lần sau
    đọc lên là mất sạch dữ liệu đã thu thập.
    """
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def save(updates: dict) -> dict:
    """Ghi thêm vài khoá vào config.json, giữ nguyên phần còn lại."""
    path = ROOT / "config.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.update(updates)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load() -> dict:
    cfg = dict(DEFAULTS)
    path = ROOT / "config.json"
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            # launch.vbs chạy ẩn console nên không báo lỗi này thì app im lặng không mở
            raise SystemExit(
                f"config.json sai cú pháp JSON ở dòng {e.lineno}, cột {e.colno}: {e.msg}. "
                f"Mở {path} sửa lại rồi chạy lại. "
                "Thường là thiếu dấu phẩy, hoặc thừa dấu phẩy ở mục cuối.")
    cfg["data_path"] = (ROOT / cfg["data_dir"]).resolve()
    cfg["data_path"].mkdir(parents=True, exist_ok=True)
    return cfg
