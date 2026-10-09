"""S-8: chỉ được ghi hình khi cửa sổ game đang ở trước."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import recorder


class FakeWin32Gui:
    """Giả lập win32gui: cửa sổ game tồn tại, nhưng một cửa sổ khác đang ở trước."""

    def __init__(self, foreground_hwnd):
        self.foreground = foreground_hwnd

    def GetForegroundWindow(self):
        return self.foreground

    def IsWindowVisible(self, hwnd):
        return True

    def IsIconic(self, hwnd):
        return False

    def GetWindowRect(self, hwnd):
        return (0, 0, 1920, 1080)

    def EnumWindows(self, cb, extra):
        cb(1001, extra)          # 1001 = cửa sổ game

    def FindWindow(self, cls, title):
        return 0


class FakeWin32Process:
    """hwnd 1001 là cửa sổ game (pid 4242); mọi hwnd khác thuộc tiến trình khác."""

    def GetWindowThreadProcessId(self, hwnd):
        return (0, 4242 if hwnd == 1001 else 7777)


def _patch(monkeypatch, foreground_hwnd):
    monkeypatch.setattr(recorder, "win32gui", FakeWin32Gui(foreground_hwnd))
    monkeypatch.setattr(recorder, "win32process", FakeWin32Process())


def test_ghi_hinh_khi_cua_so_game_o_truoc(monkeypatch):
    _patch(monkeypatch, foreground_hwnd=1001)
    assert recorder.game_window_region(pid=4242) == {
        "left": 0, "top": 0, "width": 1920, "height": 1080}


def test_bo_qua_khi_cua_so_khac_dang_de_len(monkeypatch):
    """Trình duyệt đè lên game: mss sẽ chụp trình duyệt, nên phải bỏ khung hình."""
    _patch(monkeypatch, foreground_hwnd=9999)     # 9999 = trình duyệt
    assert recorder.game_window_region(pid=4242) is None
