"""T-2: thoát app phải dừng recorder tử tế, nếu không game.mp4 mất phần đuôi và không phát được."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ui


class RecorderGia:
    def __init__(self):
        self.da_dung = False

    def stop(self):
        self.da_dung = True


def test_don_dep_goi_stop_cua_recorder_dang_ghi():
    rec = RecorderGia()
    ui.CLEANUP.clear()
    ui._CLEANED.clear()
    ui.register_cleanup(rec.stop)
    ui.run_cleanup()
    assert rec.da_dung, "phải gọi stop() trước khi thoát tiến trình"


def test_mot_ham_don_dep_loi_khong_chan_cac_ham_con_lai():
    thu_tu = []

    def hong():
        thu_tu.append("hong")
        raise RuntimeError("giả lập lỗi")

    def tot():
        thu_tu.append("tot")

    ui.CLEANUP.clear()
    ui._CLEANED.clear()
    ui.register_cleanup(hong)
    ui.register_cleanup(tot)
    ui.run_cleanup()
    assert thu_tu == ["hong", "tot"]


def test_don_dep_chi_chay_mot_lan():
    dem = []
    ui.CLEANUP.clear()
    ui._CLEANED.clear()
    ui.register_cleanup(lambda: dem.append(1))
    ui.run_cleanup()
    ui.run_cleanup()
    assert dem == [1]


def test_quit_app_co_goi_don_dep_truoc_khi_thoat():
    """Đọc mã nguồn: run_cleanup phải đứng trước os._exit."""
    import inspect
    # bỏ dòng chú thích, vì chú thích cũng nhắc tới os._exit và làm lệch phép tìm
    src = "\n".join(l for l in inspect.getsource(ui._start_tray).splitlines()
                    if not l.strip().startswith("#"))
    i_don = src.find("run_cleanup()")
    i_exit = src.find("os._exit(0)")
    assert i_don != -1, "quit_app phải gọi run_cleanup()"
    assert i_exit != -1 and i_don < i_exit, "run_cleanup() phải chạy TRƯỚC os._exit"
