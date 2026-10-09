"""Mọi tên lõi trong dòng thời gian phải được ghim về tên thật trước khi vào báo cáo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import coach

DS = [
    {"name": "Rễ Lan Toả", "en": "Spreading Roots", "tier": "Bạc"},
    {"name": "Trượng Seraphim", "en": "Seraphim's Staff", "tier": "Vàng"},
    {"name": "Chiến Lược Đầu Tư I", "en": "Investment Strategy I", "tier": "Bạc"},
]


def test_doi_ten_tieng_anh_sang_ten_that():
    rows = [{"t": "04:00", "augments": ["Spreading Roots", None, None]}]
    coach.ghim_ten_loi(rows, DS)
    assert rows[0]["augments"] == ["Rễ Lan Toả", None, None]


def test_ba_lua_chon_o_vong_chon_loi_cung_duoc_ghim():
    rows = [{"t": "04:00", "is_augment_round": True,
             "augment_choices": ["Spreading Roots", "Seraphim's Staff", "Investment Strategy 1"]}]
    coach.ghim_ten_loi(rows, DS)
    assert rows[0]["augment_choices"] == ["Rễ Lan Toả", "Trượng Seraphim", "Chiến Lược Đầu Tư I"]


def test_ten_bia_thi_thanh_none_chu_khong_giu_lai():
    rows = [{"t": "04:00", "augments": ["Lõi Tôi Tự Nghĩ Ra", None, None]}]
    coach.ghim_ten_loi(rows, DS)
    assert rows[0]["augments"] == [None, None, None]


def test_khong_co_danh_sach_thi_giu_nguyen():
    rows = [{"t": "04:00", "augments": ["Spreading Roots"]}]
    coach.ghim_ten_loi(rows, None)
    assert rows[0]["augments"] == ["Spreading Roots"]


def test_du_lieu_la_khong_lam_no_chuong_trinh():
    rows = [{"t": "04:00", "augments": "khong-phai-list"},
            {"t": "05:00", "augments": [123, {"a": 1}]},
            {"t": "06:00"}]
    coach.ghim_ten_loi(rows, DS)          # không được ném lỗi
    assert rows[2].get("augments") is None


def test_dem_duoc_bao_nhieu_ten_bi_ghim():
    rows = [{"t": "04:00", "augments": ["Spreading Roots", "Lõi Bịa", None]}]
    kq = coach.ghim_ten_loi(rows, DS)
    assert kq == {"khop": 1, "bo": 1}
