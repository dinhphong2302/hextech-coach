"""C-1, C-2: giá trị lạ ở is_in_game không được làm chết review, và null không được xoá chữ "ngoài game"."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import coach


@pytest.mark.parametrize("val", [[], {}, [False], {"x": 1}])
def test_kieu_khong_bam_duoc_khong_nem_loi(val):
    assert coach._ngoai_game(val) is False


def test_parse_timeline_song_sot_khi_is_in_game_la_danh_sach():
    raw = '{"t":"01:00","is_in_game":[],"gold":5}\n{"t":"02:00","is_in_game":{},"gold":7}'
    rows, tk = coach.parse_timeline(raw)
    assert [r["gold"] for r in rows] == [5, 7]
    assert tk["moc"] + tk["ngoai_game"] + tk["dong_hong"] == 2


def test_tam_null_khong_xoa_ket_luan_ngoai_game():
    raw = '{"t":"03:00","is_in_game":false}\n{"t":"03:00","is_in_game":null,"gold":3}'
    rows, tk = coach.parse_timeline(raw)
    assert rows == [] and tk["ngoai_game"] == 1


def test_mot_tam_khang_dinh_trong_game_van_thang():
    raw = '{"t":"04:00","is_in_game":false}\n{"t":"04:00","is_in_game":true,"gold":9}'
    rows, _ = coach.parse_timeline(raw)
    assert len(rows) == 1 and rows[0]["gold"] == 9
