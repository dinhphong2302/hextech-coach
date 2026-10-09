"""K-8: thống kê phải hiểu đúng dữ liệu TFT — lọc set, lọc trận rank, carry, tộc chính."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import research
import riot


def test_bo_tran_thuong_va_che_do_khac():
    assert riot.la_tran_rank({"tft_game_type": "standard", "queue_id": 1100})
    assert not riot.la_tran_rank({"tft_game_type": "standard", "queue_id": 1090})   # trận thường
    assert not riot.la_tran_rank({"tft_game_type": "pairs", "queue_id": 1160})      # Đôi Tuyển


def test_chi_giu_set_cua_tran_moi_nhat():
    loc = riot.LocSet()
    assert [loc.nhan({"tft_set_number": s}) for s in (18, 18, 17, 18)] == [True, True, False, True]


def test_tank_cam_hai_an_khong_phai_carry():
    p = {"units": [
        {"character_id": "DA_Tank", "rarity": 4, "tier": 2,
         "itemNames": ["TFT_Item_BruiserEmblemItem", "TFT_Item_JuggernautEmblemItem", "TFT_Item_Warmog"]},
        {"character_id": "DA_Carry", "rarity": 4, "tier": 2,
         "itemNames": ["TFT_Item_InfinityEdge", "TFT_Item_LastWhisper"]},
    ]}
    assert research.carry_raw(p) == "DA_Carry"


def test_toc_chinh_la_toc_nhieu_tuong_nhat():
    p = {"traits": [
        {"name": "Duo", "num_units": 2, "style": 3, "tier_current": 1},
        {"name": "Bruiser", "num_units": 6, "style": 2, "tier_current": 3},
        {"name": "LuxUniqueTrait", "num_units": 1, "style": 4, "tier_current": 1},
    ]}
    assert research.main_trait_raw(p) == "Bruiser"


def test_cap_cuoi_chi_xet_tran_top4():
    # 10 trận: Top 4 đều lên 9, trận thua sớm ở cấp 6 không được kéo chỉ số xuống
    ps = [{"place": 1 + i % 8, "level": 9 if (1 + i % 8) <= 4 else 6} for i in range(16)]
    kq = research.strengths_weaknesses({"placements": ps}, min_games=10)
    assert any(m["y"] == "Lên cấp đủ cao" for m in kq["manh"])
