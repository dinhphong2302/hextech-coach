"""Nhãn thời gian phải đọc được cả với tên ảnh ghép kiểu 00021_1_cot.jpg."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import coach


def test_giay_tu_ten_anh_ghep():
    assert coach.frame_seconds(Path("00021_1_cot.jpg")) == 21
    assert coach.frame_seconds(Path("01025_3_giua.jpg")) == 1025
    assert coach.frame_seconds(Path("00704.jpg")) == 704


def test_ten_la_thi_tra_ve_khong():
    assert coach.frame_seconds(Path("khong-co-so.jpg")) is None


def test_listing_khong_nem_loi_voi_anh_ghep(tmp_path):
    fs = [tmp_path / "00021_1_cot.jpg", tmp_path / "00704.jpg", tmp_path / "la.jpg"]
    for f in fs:
        f.write_bytes(b"")
    out = coach.CliCoach._listing(fs)
    assert "00:21" in out and "11:44" in out
    assert "la.jpg" in out          # ảnh không có nhãn vẫn được liệt kê
