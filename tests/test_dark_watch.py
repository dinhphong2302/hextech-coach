"""M-1: chế độ chụp dày phải phủ hết vòng chọn lõi, không tắt sau vài giây."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import recorder

FPS = 8.0
SANG, TOI = 100.0, 40.0          # độ sáng vùng giữa: lúc đánh thường và lúc chọn lõi


def _chay(watch, gia_tri, giay, t0=0.0):
    """Chạy watch qua `giây` giây ở nhịp 8 khung/giây. Trả về số khung được coi là tối."""
    n_toi, t = 0, t0
    for _ in range(int(giay * FPS)):
        if watch.update(gia_tri, t):
            n_toi += 1
        t += 1 / FPS
    return n_toi, t


def test_man_chon_loi_dai_30_giay_duoc_nhan_den_cuoi():
    w = recorder.DarkWatch()
    _, t = _chay(w, SANG, 60)                 # một phút đánh thường để có mức nền
    n_toi, _ = _chay(w, TOI, 30, t)           # vòng chọn lõi dài 30 giây
    tong = int(30 * FPS)
    assert n_toi == tong, f"chỉ nhận ra tối ở {n_toi}/{tong} khung hình"


def test_khong_bao_toi_khi_dang_danh_binh_thuong():
    w = recorder.DarkWatch()
    _, t = _chay(w, SANG, 60)
    n_toi, _ = _chay(w, SANG, 30, t)
    assert n_toi == 0


def test_chua_du_mau_thi_khong_ket_luan():
    w = recorder.DarkWatch()
    n_toi, _ = _chay(w, TOI, 2)               # mới 2 giây đầu trận
    assert n_toi == 0


def test_bam_them_vai_giay_sau_khi_sang_tro_lai():
    """Người chơi vừa bấm chọn lõi thì lõi mới hiện ở cột trái — khung hình duy nhất
    xác nhận họ chọn cái nào. Phải chụp tiếp một lát thay vì tắt ngay."""
    w = recorder.DarkWatch(bam_them_sec=8.0)
    _, t = _chay(w, SANG, 60)
    _, t = _chay(w, TOI, 30, t)
    n_toi, _ = _chay(w, SANG, 20, t)
    mong_doi = int(8.0 * FPS)
    assert abs(n_toi - mong_doi) <= 2, f"bám {n_toi} khung, mong đợi khoảng {mong_doi}"


def test_sau_khi_bam_them_thi_thoi_han():
    w = recorder.DarkWatch(bam_them_sec=8.0)
    _, t = _chay(w, SANG, 60)
    _, t = _chay(w, TOI, 30, t)
    _, t = _chay(w, SANG, 20, t)          # đã qua hết thời gian bám thêm
    n_toi, _ = _chay(w, SANG, 10, t)
    assert n_toi == 0
