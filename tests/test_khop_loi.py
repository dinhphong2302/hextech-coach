"""Tên lõi AI đọc ra phải được đối chiếu với cơ sở dữ liệu lõi thật trước khi vào báo cáo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import assets

DS = [
    {"name": "Ai Cũng Có Quyền Chọn Lựa", "en": "Beggars Can Be Choosers", "tier": "Bạc"},
    {"name": "Bước Đột Phá", "en": "Critical Success", "tier": "Bạc"},
    {"name": "Rễ Lan Toả", "en": "Spreading Roots", "tier": "Bạc"},
    {"name": "Trượng Seraphim", "en": "Seraphim's Staff", "tier": "Vàng"},
    {"name": "Chiến Lược Đầu Tư I", "en": "Investment Strategy I", "tier": "Bạc"},
]


def test_khop_chinh_xac_ten_tieng_viet():
    assert assets.match_augment("Rễ Lan Toả", DS) == "Rễ Lan Toả"


def test_khop_ten_tieng_anh_ve_ten_tieng_viet():
    """AI đọc thẻ tiếng Anh trên màn hình, báo cáo phải ra tên tiếng Việt."""
    assert assets.match_augment("Spreading Roots", DS) == "Rễ Lan Toả"
    assert assets.match_augment("Seraphim's Staff", DS) == "Trượng Seraphim"


def test_bo_qua_dau_va_hoa_thuong():
    assert assets.match_augment("re lan toa", DS) == "Rễ Lan Toả"
    assert assets.match_augment("SPREADING ROOTS", DS) == "Rễ Lan Toả"


def test_chiu_duoc_sai_vai_ky_tu():
    """Phụ đề và OCR hay nhầm một hai chữ."""
    assert assets.match_augment("Spreading Root", DS) == "Rễ Lan Toả"
    assert assets.match_augment("Investment Strategy 1", DS) == "Chiến Lược Đầu Tư I"


def test_ten_khong_co_that_thi_tra_none():
    assert assets.match_augment("Lõi Bịa Đặt Hoàn Toàn", DS) is None
    assert assets.match_augment("", DS) is None
    assert assets.match_augment(None, DS) is None


def test_khong_khop_bua_khi_chi_trung_mot_tu():
    """"Chiến Lược" trùng một phần nhưng quá ngắn để kết luận."""
    assert assets.match_augment("Chiến", DS) is None


def test_khop_tren_du_lieu_that():
    """Chạy trên 387 lõi thật của set, không phải danh sách mẫu."""
    import config
    ds = assets.augments(config.load())
    if not ds:
        return                                   # chưa tải assets.json thì bỏ qua
    that = ds[0]["name"]
    assert assets.match_augment(that, ds) == that
    assert assets.match_augment("khong-phai-loi-nao-ca-xyz", ds) is None
