"""Đọc tài khoản đang đăng nhập trong Riot Client trên máy này.

Riot Client mở một API cục bộ, khoá nằm trong file lockfile. Đây là cách các công cụ
cộng đồng vẫn dùng để biết người chơi là ai mà không cần mật khẩu.
"""
import os
import urllib3
from pathlib import Path

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOCKFILES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Riot Games" / "Riot Client" / "Config" / "lockfile",
    Path("C:/Riot Games/League of Legends/lockfile"),
    Path(os.environ.get("ProgramFiles", "")) / "Riot Games" / "League of Legends" / "lockfile",
    Path(os.environ.get("ProgramFiles(x86)", "")) / "Riot Games" / "League of Legends" / "lockfile",
]

ENDPOINTS = [
    "/chat/v1/session",                      # Riot Client: game_name + game_tag
    "/player-account/aliases/v1/active",     # Riot Client: alias
    "/lol-chat/v1/me",                       # LCU: gameName + gameTag
    "/lol-summoner/v1/current-summoner",     # LCU: gameName + tagLine
]


class NotLoggedIn(Exception):
    pass


def _lockfiles():
    for p in LOCKFILES:
        try:
            if p and p.is_file():
                yield p
        except OSError:
            continue


def _pick(data):
    """Lấy gameName/tagLine từ nhiều dạng trả về khác nhau."""
    if isinstance(data, list):
        for item in data:
            got = _pick(item)
            if got:
                return got
        return None
    if not isinstance(data, dict):
        return None
    if "alias" in data and isinstance(data["alias"], dict):
        return _pick(data["alias"])
    name = data.get("game_name") or data.get("gameName")
    tag = data.get("game_tag") or data.get("gameTag") or data.get("tagLine") or data.get("tag_line")
    if name and tag:
        return {"game_name": name, "tag_line": tag}
    return None


def current_account() -> dict:
    """Trả về {'game_name', 'tag_line'} của tài khoản đang đăng nhập.

    Ném NotLoggedIn nếu chưa mở Riot Client hoặc không đọc được.
    """
    tried = []
    for lock in _lockfiles():
        try:
            parts = lock.read_text(encoding="utf-8").strip().split(":")
            if len(parts) < 5:
                continue
            _, _, port, password, protocol = parts[:5]
        except OSError:
            continue
        base = f"{protocol}://127.0.0.1:{port}"
        for ep in ENDPOINTS:
            try:
                r = requests.get(base + ep, auth=("riot", password), verify=False, timeout=4)
            except requests.RequestException:
                continue
            tried.append(f"{ep}:{r.status_code}")
            if r.status_code != 200:
                continue
            try:
                got = _pick(r.json())
            except ValueError:
                continue
            if got:
                got["source"] = lock.name + ep
                return got
    if not tried:
        raise NotLoggedIn("Chưa mở Riot Client. Hãy mở game (hoặc chỉ cần mở client) rồi thử lại.")
    raise NotLoggedIn("Riot Client đang chạy nhưng không đọc được tài khoản (" + ", ".join(tried[:4]) + ").")
