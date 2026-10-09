"""R-1: mỗi khung hình cho ra 2 tấm ảnh, nên AI trả 2 dòng cùng một mốc — phải GỘP, không được vứt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import coach


def test_danh_sach_rong_khong_tinh_la_doc_duoc():
    """[] nghĩa là KHÔNG đọc được (theo đúng luật trong EXTRACT_FORMAT), không phải bàn trống."""
    rows, _ = coach.parse_timeline('{"t":"09:00","gold":5,"bench":[]}')
    assert rows[0].get("bench") == []      # giữ nguyên khi chỉ có một tấm


def test_gop_hai_dong_cung_moc_thay_vi_vut_mot_dong():
    raw = "\n".join([
        '{"t":"01:40","gold":11,"level":4,"shop_slots":["Kayle",null,null,null,null]}',
        '{"t":"01:40","hp":100,"augments":["A",null,null],"bench":[{"champion":"Ashe","star":1}]}',
    ])
    rows, tk = coach.parse_timeline(raw)
    assert len(rows) == 1
    r = rows[0]
    for truong in ("gold", "level", "shop_slots", "hp", "augments", "bench"):
        assert truong in r, f"mất trường {truong} khi gộp"
    assert r["gold"] == 11 and r["hp"] == 100


def test_gia_tri_doc_duoc_thang_gia_tri_null():
    """Tấm này đọc được vàng, tấm kia trả null cho vàng — phải giữ cái đọc được."""
    raw = "\n".join([
        '{"t":"02:00","gold":null,"hp":90}',
        '{"t":"02:00","gold":25,"hp":null}',
    ])
    rows, _ = coach.parse_timeline(raw)
    assert rows[0]["gold"] == 25 and rows[0]["hp"] == 90


def test_danh_sach_rong_khong_de_len_danh_sach_co_du_lieu():
    raw = "\n".join([
        '{"t":"03:00","bench":[{"champion":"Ashe","star":1}]}',
        '{"t":"03:00","bench":[]}',
    ])
    rows, _ = coach.parse_timeline(raw)
    assert rows[0]["bench"] == [{"champion": "Ashe", "star": 1}]


def test_gop_ba_tam_tro_len():
    raw = "\n".join([
        '{"t":"04:00","gold":1}',
        '{"t":"04:00","hp":2}',
        '{"t":"04:00","level":3}',
    ])
    rows, tk = coach.parse_timeline(raw)
    assert len(rows) == 1 and rows[0]["gold"] == 1 and rows[0]["hp"] == 2 and rows[0]["level"] == 3


def test_moc_khac_nhau_van_tach_rieng():
    raw = '{"t":"01:00","gold":1}\n{"t":"02:00","gold":2}'
    rows, _ = coach.parse_timeline(raw)
    assert [r["gold"] for r in rows] == [1, 2]


def test_mot_tam_ngoai_game_khong_lam_hong_ca_moc():
    """Tấm toàn cảnh có thể bị chấm là ngoài game; tấm kia vẫn trong game thì giữ mốc."""
    raw = "\n".join([
        '{"t":"05:00","is_in_game":false}',
        '{"t":"05:00","is_in_game":true,"gold":30}',
    ])
    rows, tk = coach.parse_timeline(raw)
    assert len(rows) == 1 and rows[0]["gold"] == 30
