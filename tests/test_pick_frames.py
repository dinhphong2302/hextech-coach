"""L-main-1, L-main-2: chọn khung hình đúng hạn mức, và báo lỗi rõ khi thư mục không hợp lệ."""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
import main


def _thu_muc_anh(tmp_path, n=40, so_anh_toi=5):
    d = tmp_path / "keyframes"
    d.mkdir()
    for i in range(n):
        img = np.full((180, 320), 120, np.uint8)
        if i in range(2, 2 + so_anh_toi * 4, 4)[:so_anh_toi]:
            img[45:144, 64:256] = 20              # giả lập màn hình giao diện
        cv2.imwrite(str(d / f"{i * 12 + 90:05d}.jpg"), img)
    return d


@pytest.mark.parametrize("limit", [3, 4, 6, 8, 10, 14, 18, 25])
def test_khong_bao_gio_vuot_limit(tmp_path, limit):
    d = _thu_muc_anh(tmp_path)
    ra = main.pick_frames(d, limit)
    assert len(ra) <= limit, f"limit={limit} nhưng chọn {len(ra)} ảnh"


def test_van_dung_thu_tu_va_khong_trung(tmp_path):
    d = _thu_muc_anh(tmp_path)
    ra = main.pick_frames(d, 10)
    giay = [int(f.stem) for f in ra]
    assert giay == sorted(giay) and len(set(giay)) == len(giay)


def test_it_anh_hon_limit_thi_lay_het(tmp_path):
    d = _thu_muc_anh(tmp_path, n=5, so_anh_toi=0)
    assert len(main.pick_frames(d, 18)) == 5


def test_thu_muc_rong(tmp_path):
    d = tmp_path / "keyframes"
    d.mkdir()
    assert main.pick_frames(d, 18) == []


def test_review_thieu_session_json_bao_ro_khong_nem_loi(tmp_path, capsys):
    cfg = dict(config.DEFAULTS)
    cfg["data_path"] = tmp_path
    sess = tmp_path / "trong"
    (sess / "keyframes").mkdir(parents=True)
    main.review_session(cfg, sess, open_it=False)      # không được ném ngoại lệ
    assert "không phải thư mục trận" in capsys.readouterr().out
