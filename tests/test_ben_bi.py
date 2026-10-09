"""T-1, M-2, T-4: một file JSON ghi dở không được làm app ngừng hoạt động im lặng."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import charts
import config
import report


def _cfg(tmp_path):
    c = dict(config.DEFAULTS)
    c["data_path"] = tmp_path
    return c


# ---------- T-1: ghi nguyên tử ----------
def test_ghi_json_nguyen_tu_khong_de_lai_file_do_dang(tmp_path):
    f = tmp_path / "x.json"
    config.write_json(f, {"a": 1})
    assert json.loads(f.read_text(encoding="utf-8")) == {"a": 1}
    assert list(tmp_path.glob("*.tmp")) == [], "không được để lại file tạm"


def test_ghi_json_that_bai_thi_giu_nguyen_ban_cu(tmp_path):
    f = tmp_path / "x.json"
    config.write_json(f, {"cu": True})

    class KhongSerialize:
        pass

    try:
        config.write_json(f, {"moi": KhongSerialize()})
    except TypeError:
        pass
    assert json.loads(f.read_text(encoding="utf-8")) == {"cu": True}


# ---------- M-2: meta.json hỏng không được làm chết review ----------
def test_load_meta_chiu_duoc_file_hong(tmp_path):
    cfg = _cfg(tmp_path)
    (tmp_path / "meta.json").write_text('{"comps": [  ', encoding="utf-8")
    meta, age = report.load_meta(cfg)
    assert meta is None, "meta hỏng phải coi như chưa có, không được ném lỗi"


def test_meta_md_chiu_duoc_file_hong(tmp_path):
    import main
    cfg = _cfg(tmp_path)
    (tmp_path / "meta.json").write_text("khong phai json", encoding="utf-8")
    assert main.meta_md(cfg) == ""


# ---------- T-4: vòng lặp không được chết vì một ngoại lệ ----------
def test_watch_loop_co_bat_ngoai_le_toan_than():
    import ast
    import inspect
    import main
    src = inspect.getsource(main.watch_loop)
    tree = ast.parse(src.lstrip())
    fn = tree.body[0]
    than_while = [n for n in fn.body if isinstance(n, ast.While)]
    assert than_while, "watch_loop phải có vòng lặp chính"
    co_try = any(isinstance(n, ast.Try) and any(
        h.type is not None for h in n.handlers) for n in than_while[0].body)
    assert co_try, ("thân vòng lặp chính phải nằm trong try/except, "
                    "nếu không một ngoại lệ sẽ giết luồng ghi hình mà giao diện vẫn báo bình thường")
