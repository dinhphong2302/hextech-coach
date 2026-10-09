"""L-crops-1: ảnh gửi cho AI phải nằm dưới ngưỡng bị thu nhỏ, nếu không việc phóng to là vô ích."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import crops

MAX_CANH = 1568          # ảnh dài hơn mức này bị thu nhỏ trước khi mô hình đọc
W, H = 1936, 1119        # kích thước khung hình thật của app


def _anh_gia(tmp_path, w=W, h=H):
    f = tmp_path / f"00021.jpg"
    cv2.imwrite(str(f), np.random.randint(0, 255, (h, w, 3), np.uint8))
    return f


def _he_so(f):
    im = cv2.imread(str(f))
    return min(1.0, MAX_CANH / max(im.shape[:2]))


def test_khong_tam_nao_bi_thu_nho(tmp_path):
    src = _anh_gia(tmp_path)
    for chon_loi in (False, True):
        ra = crops.build_all(src, tmp_path / f"ra{chon_loi}", dang_chon_loi=chon_loi)
        assert ra, "phải sinh được ảnh"
        for f in ra:
            im = cv2.imread(str(f))
            assert max(im.shape[:2]) <= MAX_CANH, (
                f"{f.name} có cạnh dài {max(im.shape[:2])} px, sẽ bị thu nhỏ")


def test_dung_hai_tam_moi_khung_hinh(tmp_path):
    """Đổi 1 tấm cao thành 4 tấm sẽ tốn gấp 5; chỉ gửi 2 tấm hợp với từng loại khung hình."""
    src = _anh_gia(tmp_path)
    assert len(crops.build_all(src, tmp_path / "a", dang_chon_loi=False)) == 2
    assert len(crops.build_all(src, tmp_path / "b", dang_chon_loi=True)) == 2


def test_khung_hinh_thuong_gui_vung_doc_va_dai(tmp_path):
    ra = crops.build_all(_anh_gia(tmp_path), tmp_path / "ra", dang_chon_loi=False)
    ten = {f.stem.split("_", 2)[-1] for f in ra}
    assert ten == {"cot", "dai"}


def test_vong_chon_loi_gui_the_loi_va_toan_canh(tmp_path):
    ra = crops.build_all(_anh_gia(tmp_path), tmp_path / "ra", dang_chon_loi=True)
    ten = {f.stem.split("_", 2)[-1] for f in ra}
    assert ten == {"toancanh", "giua"}


def test_moi_vung_net_hon_viec_gui_thang_anh_goc(tmp_path):
    """Sau khi tính cả việc bị thu nhỏ, từng vùng phải nét hơn là gửi ảnh gốc."""
    src = _anh_gia(tmp_path)
    goc = min(1.0, MAX_CANH / max(W, H))
    nhom_cua = {v: ten for ten, _, vung in crops.GROUPS for v in vung}
    ra = (crops.build_all(src, tmp_path / "a", dang_chon_loi=False)
          + crops.build_all(src, tmp_path / "b", dang_chon_loi=True))
    theo_ten = {f.stem.split("_", 2)[-1]: f for f in ra}
    for name, box, zoom, _ in crops.REGIONS:
        tam = theo_ten[nhom_cua[name]]
        net = zoom * _he_so(tam)
        assert net > goc, (f"vùng {name}: {zoom}x * {_he_so(tam):.2f} = {net:.2f}, "
                           f"không hơn ảnh gốc {goc:.2f}")


def test_anh_hong_thi_tra_ve_rong(tmp_path):
    assert crops.build_all(tmp_path / "khong-co.jpg", tmp_path / "ra") == []
