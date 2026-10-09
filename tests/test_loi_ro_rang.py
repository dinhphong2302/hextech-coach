"""D-1, D-2, D-5, G-1: lỗi phải ra câu người dùng hiểu được, và gợi ý phải đủ mẫu."""
import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
import research
import riot


# ---------- D-1: mất mạng phải quy về RiotError ----------
def test_mat_mang_quy_ve_riot_error(monkeypatch, tmp_path):
    cfg = dict(config.DEFAULTS)
    cfg["data_path"] = tmp_path
    cfg["riot_api_key"] = "x"
    cfg["riot_game_name"] = "a"
    cfg["riot_tag_line"] = "b"
    r = riot.Riot(cfg)

    def mat_mang(*a, **k):
        raise requests.ConnectionError("giả lập mất mạng")

    monkeypatch.setattr(r.s, "get", mat_mang)
    with pytest.raises(riot.RiotError) as e:
        r._get("https://example.invalid/x")
    assert "mạng" in str(e.value).lower() or "kết nối" in str(e.value).lower()


# ---------- D-5: 5xx phải thử lại ----------
def test_loi_may_chu_duoc_thu_lai(monkeypatch, tmp_path):
    cfg = dict(config.DEFAULTS)
    cfg["data_path"] = tmp_path
    cfg["riot_api_key"] = "x"
    r = riot.Riot(cfg)
    dem = {"n": 0}

    class Resp:
        headers = {}

        def __init__(self, code):
            self.status_code = code

        def json(self):
            return {"ok": True}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(str(self.status_code))

    def gia(*a, **k):
        dem["n"] += 1
        return Resp(200 if dem["n"] >= 3 else 503)

    monkeypatch.setattr(r.s, "get", gia)
    monkeypatch.setattr(riot.time, "sleep", lambda s: None)
    assert r._get("https://example.invalid/x") == {"ok": True}
    assert dem["n"] == 3, "phải thử lại khi máy chủ trả 5xx"


# ---------- D-2: config.json sai cú pháp phải báo rõ ----------
def test_config_hong_bao_ro_khong_nem_json_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "config.json").write_text("{ thieu dau ngoac", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        config.load()
    assert "config.json" in str(e.value)


def test_config_dung_thi_van_nap_binh_thuong(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "config.json").write_text('{"rank": "Kim Cương"}', encoding="utf-8")
    assert config.load()["rank"] == "Kim Cương"


# ---------- G-1: gợi ý phải đủ mẫu ----------
def test_khong_khuyen_bo_bai_khi_moi_choi_vai_tran():
    prof = {"by_carry": [{"name": "Malphite", "games": 3, "avg_place": 6.33}]}
    glob = {"carries": [{"name": "Malphite", "games": 500, "avg_place": 4.82}]}
    assert research.suggestions(prof, glob)["drop"] == [], "3 trận là quá ít để kết luận"


def test_van_khuyen_bo_khi_du_mau():
    prof = {"by_carry": [{"name": "Malphite", "games": 8, "avg_place": 6.33}]}
    glob = {"carries": [{"name": "Malphite", "games": 500, "avg_place": 4.82}]}
    drop = research.suggestions(prof, glob)["drop"]
    assert len(drop) == 1 and drop[0]["games"] == 8
