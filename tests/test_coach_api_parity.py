"""N-1: hai backend phải có cùng bộ phương thức public, nếu không một lệnh sẽ chết."""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import coach

ROOT = Path(__file__).resolve().parent.parent


def _phuong_thuc(ten_class):
    tree = ast.parse((ROOT / "coach.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == ten_class)
    return {m.name for m in cls.body
            if isinstance(m, ast.FunctionDef) and not m.name.startswith("_")}


def test_hai_backend_cung_bo_phuong_thuc():
    cli, api = _phuong_thuc("CliCoach"), _phuong_thuc("ApiCoach")
    assert cli == api, f"CliCoach thiếu {api - cli}, ApiCoach thiếu {cli - api}"


def test_moi_phuong_thuc_main_goi_deu_co_o_ca_hai():
    """Mọi lời gọi coach.<x>() trong main.py phải tồn tại ở cả hai backend."""
    goi = set()
    for node in ast.walk(ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "coach"):
            goi.add(node.func.attr)
    cli, api = _phuong_thuc("CliCoach"), _phuong_thuc("ApiCoach")
    thieu = {g for g in goi if g not in cli or g not in api}
    assert not thieu, f"main.py gọi {thieu} nhưng backend thiếu"
