"""S-3: chỉ giao diện của chính app mới được gọi các endpoint POST."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ui

CONG = 8787


def _ok(origin=None, referer=None, port=CONG):
    headers = {}
    if origin is not None:
        headers["Origin"] = origin
    if referer is not None:
        headers["Referer"] = referer
    return ui.same_origin(headers, port)


def test_khong_co_header_thi_cho_qua():
    """curl và các script cục bộ không gửi Origin; đó không phải tấn công từ trình duyệt."""
    assert _ok() is True


def test_origin_cua_chinh_app_duoc_qua():
    assert _ok(origin=f"http://127.0.0.1:{CONG}") is True
    assert _ok(origin=f"http://localhost:{CONG}") is True


def test_origin_trang_la_bi_chan():
    assert _ok(origin="https://evil.example.com") is False
    assert _ok(origin="http://evil.example.com") is False


def test_origin_cung_may_nhung_khac_cong_bi_chan():
    """Đúng kịch bản đã dựng được trong audit: trang ở 127.0.0.1:8899."""
    assert _ok(origin="http://127.0.0.1:8899") is False


def test_referer_duoc_dung_khi_thieu_origin():
    assert _ok(referer=f"http://127.0.0.1:{CONG}/") is True
    assert _ok(referer="https://evil.example.com/x") is False


def test_origin_null_bi_chan():
    """Trang mở từ file:// hoặc iframe sandbox gửi Origin: null."""
    assert _ok(origin="null") is False
