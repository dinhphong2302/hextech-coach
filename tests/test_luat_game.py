"""K-1..K-6: luật game chỉ có một nguồn (tft_rules), và mọi prompt/tài liệu phải khớp với nó."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import coach
import tft_rules as R


def test_thuong_chuoi_set18():
    # op.gg Season 18: 2, 3, 4 trận +1 · 5 trận +2 · 6+ trận +3
    assert [R.streak_bonus(n) for n in range(0, 9)] == [0, 0, 1, 1, 1, 2, 3, 3, 3]


def test_lai_va_thu_nhap():
    assert [R.interest(g) for g in (0, 9, 10, 49, 50, 120)] == [0, 0, 1, 4, 5, 5]
    assert R.income(gold=50, streak=6, won=True) == 5 + 5 + 3 + 1


def test_odds_moi_cap_cong_du_100():
    for lv, row in R.SHOP_ODDS.items():
        assert sum(row) == 100, lv


def test_vong_chon_loi_la_2_1():
    assert R.AUGMENT_ROUNDS == ("2-1", "3-2", "4-2")


def test_prompt_dung_luat_chung():
    for ten, txt in (("REVIEW_FORMAT", coach.REVIEW_FORMAT), ("EXTRACT_FORMAT", coach.EXTRACT_FORMAT)):
        assert "2-1, 3-2, 4-2" in txt, ten
        assert "2-2, 3-2" not in txt and "2-2 và 3-2" not in txt, ten
    assert "LUẬT GAME SET" in coach.SYSTEM
    assert "bên trái, đúng dòng có tên" not in coach.EXTRACT_FORMAT


def test_buoc_dung_cam_nang_khong_mang_cam_nang_cu():
    assert "Cẩm nang tổng hợp từ tài liệu của Dishsoap" not in coach.SYSTEM_BASE


def test_guide_khong_con_bang_chuoi_cu():
    g = (ROOT / "guide_vi.md").read_text(encoding="utf-8")
    assert "2 trận: +1" not in g
    assert "khoảng 80 giây" not in g


def test_html_streak_khop_luat():
    html = (ROOT.parent / "tft-coach.html").read_text(encoding="utf-8")
    m = re.search(r"function streakBonus\(n\)\{ return (.*?); \}", html)
    assert m, "không tìm thấy streakBonus"
    js = m.group(1)
    # dịch biểu thức ba ngôi của JS sang Python để chạy thử
    py = re.sub(r"n>=(\d+)\?(\d+) :", r"\2 if n>=\1 else", js)
    for n in range(0, 9):
        assert eval(py, {"n": n}) == R.streak_bonus(n), n
