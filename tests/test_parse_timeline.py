"""L-coach-1, L-coach-2, L-coach-3: bước đọc ảnh lệch kiểu nào cũng không được mất dữ liệu im lặng."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import coach


# ---------- L-coach-1: is_in_game không phải boolean ----------
def test_loai_moc_ngoai_game_du_o_dang_chuoi():
    for gia_tri in ('"false"', '"False"', '"no"', "0"):
        rows, tk = coach.parse_timeline('{"t":"01:00","is_in_game":%s,"gold":5}' % gia_tri)
        assert rows == [], f"is_in_game={gia_tri} phải bị loại"
        assert tk["ngoai_game"] == 1


def test_giu_moc_trong_game():
    for gia_tri in ("true", '"true"', "1"):
        rows, tk = coach.parse_timeline('{"t":"01:00","is_in_game":%s,"gold":5}' % gia_tri)
        assert len(rows) == 1, f"is_in_game={gia_tri} phải được giữ"


def test_thieu_is_in_game_thi_coi_la_trong_game():
    rows, _ = coach.parse_timeline('{"t":"01:00","gold":5}')
    assert len(rows) == 1


# ---------- L-coach-2: không được mất mốc im lặng ----------
def test_chu_dan_truoc_json_van_doc_duoc():
    rows, tk = coach.parse_timeline('Ảnh 1: {"t":"01:00","gold":10}')
    assert len(rows) == 1 and rows[0]["gold"] == 10


def test_json_xuong_dong_van_doc_duoc():
    raw = '{\n "t":"01:00",\n "gold":10\n}'
    rows, tk = coach.parse_timeline(raw)
    assert len(rows) == 1 and rows[0]["gold"] == 10


def test_dong_that_su_hong_duoc_dem():
    rows, tk = coach.parse_timeline('{"t":"01:00" hong het')
    assert rows == [] and tk["dong_hong"] == 1


def test_thong_ke_khop_voi_so_dau_vao():
    """moc + ngoai_game + dong_hong phải bằng số mục đầu vào, nếu không là mất dữ liệu ngầm."""
    raw = "\n".join([
        '{"t":"01:00","gold":1}',
        'Ảnh 2: {"t":"02:00","gold":2}',
        '{"t":"03:00","is_in_game":false}',
        '{"t":"04:00" hong',
    ])
    rows, tk = coach.parse_timeline(raw)
    assert tk["moc"] + tk["ngoai_game"] + tk["dong_hong"] == 4


# ---------- L-coach-3: nhãn thời gian một chữ số ----------
def test_nhan_thoi_gian_mot_chu_so_van_sap_dung_thu_tu():
    raw = "\n".join(['{"t":"2:00","gold":2}', '{"t":"1:5","gold":1}', '{"t":"10:00","gold":3}'])
    rows, _ = coach.parse_timeline(raw)
    assert [r["gold"] for r in rows] == [1, 2, 3]


# ---------- các ca đã đúng sẵn, giữ để khỏi vỡ về sau ----------
def test_khu_moc_trung():
    raw = '{"t":"01:00","gold":1}\n{"t":"01:00","gold":9}'
    rows, _ = coach.parse_timeline(raw)
    assert len(rows) == 1


def test_dau_vao_rong():
    assert coach.parse_timeline("") == ([], {"moc": 0, "ngoai_game": 0, "dong_hong": 0,
                                             "doc_duoc_vang": 0})


def test_boc_trong_nhay_ba():
    rows, _ = coach.parse_timeline('```json\n{"t":"01:00","gold":10}\n```')
    assert len(rows) == 1
