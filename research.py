"""Tự dựng thống kê từ Riot API: bảng theo carry cho nhiều server, và hồ sơ cá nhân.

Không phụ thuộc trang thống kê bên ngoài. Mọi con số đều tính từ dữ liệu trận Riot trả về.
"""
import hashlib
import json
import re
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime

import requests

import config

import assets
from riot import LocSet, clean, la_tran_rank, round_to_stage, so_do_that, trait_chinh

# platform (xếp hạng) -> region (lịch sử trận)
PLATFORMS = {
    "vn2": "sea", "sg2": "sea", "tw2": "sea", "oc1": "sea", "ph2": "sea", "th2": "sea",
    "kr": "asia", "jp1": "asia",
    "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas",
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe",
}
QUEUE_RANKED_TFT = 1100


class Limiter:
    """Giới hạn tốc độ gọi Riot API: X request mỗi giây và Y request mỗi 2 phút."""

    def __init__(self, per_sec=18, per_2min=95):
        self.per_sec, self.per_2min = per_sec, per_2min
        self.calls = []
        self.lock = threading.Lock()

    def wait(self):
        while True:
            with self.lock:
                now = time.time()
                self.calls = [t for t in self.calls if now - t < 120]
                sec = sum(1 for t in self.calls if now - t < 1)
                if sec < self.per_sec and len(self.calls) < self.per_2min:
                    self.calls.append(now)
                    return
                if len(self.calls) >= self.per_2min:
                    sleep = 120 - (now - self.calls[0]) + 0.2
                else:
                    sleep = 1.05 - (now - max(t for t in self.calls if now - t < 1))
            time.sleep(max(0.05, sleep))


class Collector:
    def __init__(self, cfg, log=print, stop_flag=None):
        self.cfg, self.log = cfg, log
        self.stop = stop_flag or threading.Event()
        self.s = requests.Session()
        self.s.headers["X-Riot-Token"] = cfg["riot_api_key"]
        self.lim = Limiter(cfg.get("riot_per_sec", 18), cfg.get("riot_per_2min", 95))
        self.cache = cfg["data_path"] / "matches"
        self.cache.mkdir(exist_ok=True)
        self.errors = 0

    def get(self, url, params=None):
        for attempt in range(4):
            if self.stop.is_set():
                raise KeyboardInterrupt
            self.lim.wait()
            try:
                r = self.s.get(url, params=params, timeout=20)
            except requests.RequestException:
                self.errors += 1
                time.sleep(2)
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "10")))
                continue
            if r.status_code in (401, 403):
                raise PermissionError("Riot API key sai hoặc đã hết hạn.")
            if r.status_code == 404:
                return None
            self.errors += 1
            time.sleep(1.5)
        return None

    # ---------- thu thập ----------
    def league_puuids(self, platform: str, tiers: list[str]) -> list[str]:
        out = []
        for tier in tiers:
            data = self.get(f"https://{platform}.api.riotgames.com/tft/league/v1/{tier}")
            for e in (data or {}).get("entries", []):
                if e.get("puuid"):
                    out.append(e["puuid"])
        return out

    def match_ids(self, region: str, puuid: str, count: int) -> list[str]:
        return self.get(f"https://{region}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids",
                        {"count": count}) or []

    def match(self, region: str, mid: str):
        path = self.cache / f"{mid}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                path.unlink(missing_ok=True)
        data = self.get(f"https://{region}.api.riotgames.com/tft/match/v1/matches/{mid}")
        if data:
            config.write_json(path, data)
        return data

    def run(self, on_progress=None) -> dict:
        cfg = self.cfg
        platforms = [p for p in cfg["research_platforms"] if p in PLATFORMS]
        tiers = cfg["research_tiers"]
        target = cfg["research_target_matches"]
        per_player = cfg["research_matches_per_player"]
        per_region = max(1, target // max(1, len(platforms)))

        rows, seen, done = [], set(), 0
        meta = {"platforms": [], "tiers": tiers, "started": datetime.now().isoformat(timespec="seconds")}
        for platform in platforms:
            if self.stop.is_set():
                break
            region = PLATFORMS[platform]
            self.log(f"[{platform}] đang lấy danh sách người chơi {', '.join(tiers)}...")
            puuids = self.league_puuids(platform, tiers)
            if not puuids:
                self.log(f"[{platform}] không lấy được danh sách, bỏ qua server này.")
                continue
            self.log(f"[{platform}] có {len(puuids)} người chơi, bắt đầu tải trận.")
            got = 0
            for puuid in puuids:
                if got >= per_region or self.stop.is_set():
                    break
                for mid in self.match_ids(region, puuid, per_player):
                    if mid in seen or got >= per_region:
                        continue
                    seen.add(mid)
                    m = self.match(region, mid)
                    if not m:
                        continue
                    info = m.get("info", {})
                    if info.get("queue_id") not in (None, QUEUE_RANKED_TFT):
                        continue
                    if info.get("tft_game_type") not in (None, "standard"):
                        continue
                    for p in info.get("participants", []):
                        rows.append(participant_row(p, platform, info))
                    got += 1
                    done += 1
                    if on_progress and done % 10 == 0:
                        on_progress(done, target)
            meta["platforms"].append({"platform": platform, "matches": got, "players": len(puuids)})
            self.log(f"[{platform}] xong {got} trận.")
        meta["finished"] = datetime.now().isoformat(timespec="seconds")
        meta["matches"] = done
        meta["participants"] = len(rows)
        meta["key_fingerprint"] = key_fingerprint(cfg["riot_api_key"])
        meta["errors"] = self.errors
        return {"meta": meta, "carries": aggregate_carries(rows), "traits": aggregate_traits(rows),
                "items": aggregate_items(rows), "augments": aggregate_augments(rows)}


def aggregate_from_cache(cfg, log=print) -> dict:
    """Tính lại bảng thống kê từ các trận đã tải về, không gọi Riot API."""
    rows, matches = [], 0
    for f in sorted((cfg["data_path"] / "matches").glob("*.json")):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        info = m.get("info", {})
        if info.get("tft_game_type") not in (None, "standard"):
            continue
        platform = (m.get("metadata", {}).get("match_id", "?").split("_")[0] or "?").lower()
        for p in info.get("participants", []):
            rows.append(participant_row(p, platform, info))
        matches += 1
    log(f"Tính lại từ {matches} trận đã tải ({len(rows)} lượt chơi).")
    by_platform = Counter(r["platform"] for r in rows)
    meta = {"matches": matches, "participants": len(rows), "tiers": cfg["research_tiers"],
            "platforms": [{"platform": k, "matches": v // 8} for k, v in by_platform.items()],
            "finished": datetime.now().isoformat(timespec="seconds"),
            "key_fingerprint": key_fingerprint(cfg["riot_api_key"]),
            "augments_available": any(r["augments"] for r in rows)}
    return {"meta": meta, "carries": aggregate_carries(rows), "traits": aggregate_traits(rows),
            "items": aggregate_items(rows), "augments": aggregate_augments(rows)}


def key_fingerprint(key: str) -> str:
    """Vân tay của key để biết đã đổi key mới hay chưa. Không lưu key."""
    return hashlib.sha256((key or "").encode()).hexdigest()[:12]


# ---------- rút gọn một người chơi trong trận ----------
def _carry_unit(p: dict):
    """Tướng carry: nhiều đồ nhất (không tính ấn), rồi tới giá cao nhất và số sao."""
    return max(p.get("units", []),
               key=lambda u: (so_do_that(u), u.get("rarity", 0), u.get("tier", 1)), default=None)


def carry_raw(p: dict) -> str:
    """ID gốc của tướng carry, dùng để lấy ảnh."""
    return (_carry_unit(p) or {}).get("character_id", "")


def main_trait_raw(p: dict) -> str:
    top = trait_chinh(p)
    return top["name"] if top else ""


def carry_of(p: dict) -> tuple[str, int]:
    best = _carry_unit(p)
    if not best:
        return "?", 0
    return clean(best.get("character_id", "?")), best.get("tier", 1)


def main_trait(p: dict) -> str:
    top = trait_chinh(p)
    if not top:
        return "?"
    return f"{clean(top['name'])} {top['num_units']}"


def items_of(p: dict) -> list[str]:
    """Các món đồ hoàn chỉnh trên sân (mỗi món tính một lần cho mỗi lượt chơi)."""
    out = set()
    for u in p.get("units", []):
        for i in (u.get("itemNames") or []):
            if "Component" not in i and "Emblem" not in i:
                out.add(i)
    return sorted(out)


def participant_row(p: dict, platform: str, info: dict) -> dict:
    carry, star = carry_of(p)
    return {
        "platform": platform, "placement": p["placement"], "level": p.get("level"),
        "carry": carry, "carry_star": star, "trait": main_trait(p),
        "carry_id": carry_raw(p), "trait_id": main_trait_raw(p),
        "items": items_of(p),
        "augments": [clean(a) for a in p.get("augments", [])],
        "eliminated": round_to_stage(p.get("last_round", 0)),
    }


# ---------- tổng hợp ----------
def _summary(places: list[int], total_rows: int) -> dict:
    n = len(places)
    return {
        "games": n,
        "avg_place": round(sum(places) / n, 2),
        "top4": round(100 * sum(x <= 4 for x in places) / n, 1),
        "win": round(100 * sum(x == 1 for x in places) / n, 1),
        "pick_rate": round(100 * n / total_rows, 2) if total_rows else None,
    }


def _aggregate(rows, key_fn, min_games, extra=None, id_key=None) -> list:
    buckets = defaultdict(list)
    for r in rows:
        for key in key_fn(r):
            buckets[key].append(r)
    out = []
    for key, group in buckets.items():
        if len(group) < min_games:
            continue
        raw = group[0].get(id_key, "") if id_key else ""
        item = {"name": key, "img": assets.img(raw, key),
                **_summary([g["placement"] for g in group], len(rows))}
        if extra:
            item.update(extra(group))
        out.append(item)
    return sorted(out, key=lambda d: d["avg_place"])


def aggregate_carries(rows, min_games=25) -> list:
    def extra(group):
        stars = Counter(g["carry_star"] for g in group)
        traits = Counter(g["trait"] for g in group)
        three = stars.get(3, 0)
        return {"star3_rate": round(100 * three / len(group), 1),
                "top_traits": [t for t, _ in traits.most_common(3)]}
    return _aggregate(rows, lambda r: [r["carry"]] if r["carry"] != "?" else [], min_games, extra,
                      id_key="carry_id")


def aggregate_traits(rows, min_games=25) -> list:
    return _aggregate(rows, lambda r: [r["trait"]] if r["trait"] != "?" else [], min_games,
                      id_key="trait_id")


def aggregate_items(rows, min_games=25) -> list:
    """Hạng trung bình của từng món đồ, tính từ chính các trận đã tải."""
    buckets = defaultdict(list)
    for r in rows:
        for raw in r.get("items", []):
            buckets[raw].append(r)
    out = []
    for raw, group in buckets.items():
        if len(group) < min_games:
            continue
        name = clean(raw)
        out.append({"name": name, "img": assets.img(raw, name), "recipe": assets.recipe(name),
                    **_summary([g["placement"] for g in group], len(rows))})
    return sorted(out, key=lambda d: d["avg_place"])


def aggregate_augments(rows, min_games=25) -> list:
    return _aggregate(rows, lambda r: r["augments"], min_games)


# ---------- hồ sơ cá nhân ----------
def personal_profile(riot, n=20) -> dict:
    """Hồ sơ kiểu tactics.tools cho chính tài khoản đang cấu hình."""
    puuid = riot.puuid()
    rows, placements, matches_used = [], [], 0
    loc = LocSet()
    for mid in riot.match_ids(n):
        m = riot.match(mid)
        info = m.get("info", {})
        if not la_tran_rank(info) or not loc.nhan(info):
            continue
        p = next((x for x in info["participants"] if x["puuid"] == puuid), None)
        if not p:
            continue
        row = participant_row(p, riot.cfg["platform"], info)
        row["date"] = datetime.fromtimestamp(info["game_datetime"] / 1000).strftime("%d/%m %H:%M")
        row["level"] = p.get("level")
        rows.append(row)
        placements.append(p["placement"])
        matches_used += 1
    if not rows:
        return {"games": 0}

    by_carry = _aggregate(rows, lambda r: [r["carry"]], 1, id_key="carry_id")
    by_trait = _aggregate(rows, lambda r: [r["trait"]], 1, id_key="trait_id")
    by_aug = _aggregate(rows, lambda r: r["augments"], 1)
    has_aug = any(r["augments"] for r in rows)
    return {
        "augments_available": has_aug,
        "rank_img": assets.rank_crest(riot.rank() or ""),
        "riot_id": f"{riot.cfg['riot_game_name']}#{riot.cfg['riot_tag_line']}",
        "rank": riot.rank(),
        "games": matches_used,
        **_summary(placements, matches_used),
        "placements": [{"place": r["placement"], "carry": r["carry"], "trait": r["trait"],
                        "date": r["date"], "level": r["level"], "eliminated": r["eliminated"],
                        "carry_img": assets.img(r["carry_id"], r["carry"]),
                        "trait_img": assets.img(r["trait_id"], r["trait"])}
                       for r in rows],
        "by_carry": sorted(by_carry, key=lambda d: (-d["games"], d["avg_place"])),
        "by_trait": sorted(by_trait, key=lambda d: (-d["games"], d["avg_place"])),
        "by_augment": sorted(by_aug, key=lambda d: (-d["games"], d["avg_place"]))[:12],
        "updated": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


# Mặt bằng của một sảnh 8 người: trung bình hạng 4,5; một nửa vào Top 4; 1/8 về nhất.
CHUAN_TOP4, CHUAN_TOP1, CHUAN_HANG = 50.0, 12.5, 4.5


def _round_cua_stage(nhan: str):
    """Đổi nhãn stage "6-1" thành số round để so sớm hay muộn. None nếu không đọc được."""
    m = re.match(r"^(\d+)-(\d+)$", str(nhan or "").strip())
    if not m:
        return None
    st, r = int(m.group(1)), int(m.group(2))
    return r if st <= 1 else 4 + (st - 2) * 7 + r


def strengths_weaknesses(profile: dict, glob: dict | None = None, min_games=10) -> dict:
    """Điểm mạnh và điểm yếu của người chơi, tính từ số thật.

    Mỗi nhận định bắt buộc kèm con số dẫn ra nó, vì nhận xét không có số thì không sửa được.
    Trả về {"manh": [...], "yeu": [...]} với mỗi mục là {"y", "so", "chi_tiet"}.
    """
    places = [p.get("place") for p in (profile.get("placements") or [])
              if isinstance(p.get("place"), int)]
    n = len(places)
    if not n:
        return {"manh": [], "yeu": [], "ghi_chu": "Chưa có hồ sơ."}
    if n < min_games:
        return {"manh": [], "yeu": [],
                "ghi_chu": f"Mới {n} trận, chưa đủ để kết luận (cần {min_games})."}

    manh, yeu = [], []

    def them(tot, y, so, chi_tiet=""):
        (manh if tot else yeu).append({"y": y, "so": so, "chi_tiet": chi_tiet})

    top4 = 100 * sum(p <= 4 for p in places) / n
    top1 = 100 * sum(p == 1 for p in places) / n
    hai = sum(p == 2 for p in places)
    tham = sum(p >= 7 for p in places)
    tb = sum(places) / n

    # 1. Vào Top 4
    lech = top4 - CHUAN_TOP4
    them(lech >= 5, "Tỉ lệ vào Top 4" if lech >= 5 else "Chưa giữ được Top 4 ổn định",
         f"{top4:.0f}% ({sum(p <= 4 for p in places)}/{n} trận), mặt bằng {CHUAN_TOP4:.0f}%",
         f"Chênh {lech:+.0f} điểm phần trăm so với mặt bằng một sảnh 8 người.")

    # 2. Chốt hạng 1 — chỗ hay lộ nhất
    if top1 < CHUAN_TOP1 and hai >= max(2, n * 0.15):
        them(False, "Vào được top cao nhưng không chốt được hạng 1",
             f"{hai}/{n} trận hạng 2 nhưng {sum(p == 1 for p in places)}/{n} trận hạng 1",
             "Thường là do ở thế thủ cuối trận: đủ mạnh để trụ nhưng thiếu một nâng cấp "
             "hoặc một món đồ để lật.")
    elif top1 >= CHUAN_TOP1:
        them(True, "Chốt được hạng 1", f"{top1:.0f}% ({sum(p == 1 for p in places)}/{n} trận), "
             f"mặt bằng {CHUAN_TOP1:.0f}%")

    # 3. Trận hỏng nặng
    if tham:
        them(False, "Có trận hỏng nặng", f"{tham}/{n} trận về hạng 7–8",
             "Trận hạng 7–8 mất nhiều điểm hơn phần một trận Top 4 kiếm được.")
    else:
        them(True, "Không có trận hỏng nặng", f"0/{n} trận về hạng 7–8")

    # 4. Ổn định
    do_lech = (sum((p - tb) ** 2 for p in places) / n) ** 0.5
    them(do_lech <= 1.8, "Kết quả ổn định" if do_lech <= 1.8 else "Kết quả dao động mạnh",
         f"độ lệch chuẩn {do_lech:.2f} hạng quanh mức trung bình {tb:.2f}",
         "Dưới 1,8 là ổn định; trên 2,2 nghĩa là ăn may nhiều hơn là kiểm soát.")

    # 5. Bị loại sớm hay muộn
    rounds = [r for r in (_round_cua_stage(p.get("eliminated"))
                          for p in profile.get("placements") or []) if r]
    if len(rounds) >= min_games:
        tb_round = sum(rounds) / len(rounds)
        som = sum(1 for r in rounds if r < 26)          # trước stage 5-1
        them(som <= n * 0.25, "Trụ được tới cuối trận" if som <= n * 0.25 else "Hay bị loại sớm",
             f"{som}/{len(rounds)} trận bị loại trước stage 5-1, "
             f"trung bình trụ tới round {tb_round:.0f}")

    # 6. Độ đa dạng bài
    carries = [p.get("carry") for p in profile.get("placements") or [] if p.get("carry")]
    khac = len(set(carries))
    if carries:
        them(khac >= 6, "Đánh được nhiều bài" if khac >= 6 else "Bài đánh còn hẹp",
             f"{khac} carry khác nhau trong {len(carries)} trận",
             "Đánh hẹp thì dễ bị tranh bài và dễ bí khi đồ ra không hợp.")

    # 7. Bài tốt nhất và kém nhất so với mặt bằng chung
    vs = [r for r in (profile.get("vs_global") or []) if r.get("games", 0) >= 3]
    if vs:
        tot = min(vs, key=lambda r: r["diff"])
        kem = max(vs, key=lambda r: r["diff"])
        if tot["diff"] <= -0.5:
            them(True, f"Đánh {tot['carry']} tốt hơn mặt bằng",
                 f"hạng TB {tot['mine']} so với {tot['global']} chung ({tot['diff']:+.2f}), "
                 f"{tot['games']} trận")
        if kem["diff"] >= 0.7:
            them(False, f"Đánh {kem['carry']} kém mặt bằng",
                 f"hạng TB {kem['mine']} so với {kem['global']} chung ({kem['diff']:+.2f}), "
                 f"{kem['games']} trận")

    # 8. Level cuối trận
    # Chỉ xét trận Top 4: trận hạng 7-8 bị loại sớm nên cấp cuối thấp là HỆ QUẢ của hạng,
    # không phải nguyên nhân. Tính cả trận thua thì chỉ số này chỉ lặp lại hạng trung bình.
    top4_lv = [p.get("level") for p in profile.get("placements") or []
               if isinstance(p.get("level"), int) and isinstance(p.get("place"), int) and p["place"] <= 4]
    if len(top4_lv) >= min_games // 2:
        tb_lv = sum(top4_lv) / len(top4_lv)
        them(tb_lv >= 8.0, "Lên cấp đủ cao" if tb_lv >= 8.0 else "Vào Top 4 ở cấp thấp",
             f"cấp trung bình lúc kết thúc ở {len(top4_lv)} trận Top 4: {tb_lv:.1f}",
             "Chỉ tính trận Top 4. Thấp có thể do chơi bài reroll — đối chiếu bài hay chơi trước khi kết luận.")

    return {"manh": manh, "yeu": yeu, "games": n,
            "ghi_chu": f"Tính từ {n} trận gần nhất, mọi con số lấy từ dữ liệu Riot API."}


def suggestions(profile: dict, glob: dict, min_games=40, min_cua_ban=5) -> dict:
    """Gợi ý: bài nên bỏ, bài nên giữ, bài nên thử. Tính cục bộ, không cần AI."""
    if not glob or not profile.get("by_carry"):
        return {}
    ref = {c["name"]: c for c in glob.get("carries", []) if c["games"] >= min_games}
    mine = {c["name"]: c for c in profile["by_carry"]}
    drop, keep = [], []
    for name, m in mine.items():
        g = ref.get(name)
        # Hạng trung bình của 2-3 trận dao động khoảng ±1,3 hạng, lớn hơn cả ngưỡng
        # 0,7 dùng để kết luận. Dưới min_cua_ban trận thì chưa nói được gì.
        if not g or m["games"] < min_cua_ban:
            continue
        diff = round(m["avg_place"] - g["avg_place"], 2)
        row = {"carry": name, "img": m.get("img") or g.get("img"), "games": m["games"],
               "mine": m["avg_place"], "global": g["avg_place"], "diff": diff}
        (drop if diff >= 0.7 else keep).append(row)
    played = set(mine)
    try_these = [{"carry": c["name"], "img": c.get("img"), "global": c["avg_place"],
                  "top4": c["top4"], "pick_rate": c["pick_rate"], "games": c["games"]}
                 for c in glob.get("carries", [])
                 if c["games"] >= min_games and c["name"] not in played][:5]
    return {"drop": sorted(drop, key=lambda r: -r["diff"])[:5],
            "keep": sorted(keep, key=lambda r: r["diff"])[:5],
            "try": try_these,
            "min_games": min_games, "min_cua_ban": min_cua_ban}


def compare_with_global(profile: dict, glob: dict) -> list:
    """So sánh hạng trung bình của bạn với mặt bằng chung ở cùng carry."""
    if not glob or not profile.get("by_carry"):
        return []
    ref = {c["name"]: c for c in glob.get("carries", [])}
    out = []
    for mine in profile["by_carry"]:
        g = ref.get(mine["name"])
        if not g:
            continue
        out.append({"carry": mine["name"], "games": mine["games"], "mine": mine["avg_place"],
                    "global": g["avg_place"], "diff": round(mine["avg_place"] - g["avg_place"], 2)})
    return sorted(out, key=lambda d: -d["diff"])
