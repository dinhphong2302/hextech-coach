"""Điểm mạnh / điểm yếu của người chơi phải tính từ số thật, không phải nhận xét chung chung."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import research


def _ho_so(places, **kw):
    n = len(places)
    prof = {
        "games": n,
        "avg_place": round(sum(places) / n, 2),
        "top4": round(100 * sum(p <= 4 for p in places) / n, 1),
        "win": round(100 * sum(p == 1 for p in places) / n, 1),
        "placements": [{"place": p, "carry": "Ahri", "trait": "X",
                        "level": 8, "eliminated": "5-1"} for p in places],
        "by_carry": [],
    }
    prof.update(kw)
    return prof


def test_moi_y_deu_kem_so():
    prof = _ho_so([2, 4, 5, 5, 5, 2, 2, 8, 2, 6, 2, 4, 6, 2, 3, 6, 2, 6, 4, 6])
    kq = research.strengths_weaknesses(prof)
    tat_ca = kq["manh"] + kq["yeu"]
    assert tat_ca, "phải ra được ít nhất một nhận định"
    for y in tat_ca:
        assert y.get("so"), f"nhận định thiếu số: {y}"
        assert any(c.isdigit() for c in y["so"]), f"cột bằng chứng không có số: {y}"


def test_bat_duoc_kieu_nhieu_hang_2_nhung_khong_hang_1():
    """Đúng hồ sơ thật của Jordi: 7 trận hạng 2, không trận nào hạng 1."""
    prof = _ho_so([2, 4, 5, 5, 5, 2, 2, 8, 2, 6, 2, 4, 6, 2, 3, 6, 2, 6, 4, 6])
    kq = research.strengths_weaknesses(prof)
    chu = " ".join(y["y"] + y["so"] for y in kq["yeu"])
    assert "hạng 1" in chu or "Top 1" in chu


def test_nguoi_choi_gioi_ra_diem_manh():
    prof = _ho_so([1, 1, 2, 1, 3, 2, 1, 4, 2, 1])
    kq = research.strengths_weaknesses(prof)
    assert kq["manh"], "hồ sơ toàn Top 4 mà không ra điểm mạnh nào là sai"


def test_qua_it_tran_thi_khong_ket_luan():
    prof = _ho_so([1, 8, 3])
    kq = research.strengths_weaknesses(prof)
    assert kq["manh"] == [] and kq["yeu"] == []
    assert "chưa đủ" in kq.get("ghi_chu", "")


def test_ho_so_rong_khong_nem_loi():
    assert research.strengths_weaknesses({}) == {"manh": [], "yeu": [],
                                                 "ghi_chu": "Chưa có hồ sơ."}
