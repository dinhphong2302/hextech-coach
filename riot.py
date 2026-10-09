"""Riot API: lấy trận TFT, rank và thống kê của người chơi."""
import json
import re
import time
from collections import Counter, defaultdict
from urllib.parse import quote

import requests

import config

import names


class RiotError(Exception):
    pass


def clean(name: str) -> str:
    """Bỏ tiền tố mã nội bộ của Riot, đổi theo từng set.

    TFT13_Augment_CyberUplink -> CyberUplink · DA_18_Sivir -> Sivir
    DA_Lux18_Base -> Lux · DA_18_Maokai_UniqueTrait -> Maokai
    """
    viet = names.vi(name)
    if viet:
        return viet
    n = re.sub(r"^(TFT\d*|DA)_", "", name or "")
    n = re.sub(r"^(Item|Augment)_", "", n)
    n = re.sub(r"^\d+_", "", n)
    n = re.sub(r"_?(Unique)?Trait$", "", n)
    n = re.sub(r"_?Base$", "", n)
    n = re.sub(r"\d+$", "", n)
    n = n.replace("_", " ").strip()
    # tên nội bộ hay viết dính: ElderDragon -> Elder Dragon
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", n)


TIERS_VI = {"IRON": "Sắt", "BRONZE": "Đồng", "SILVER": "Bạc", "GOLD": "Vàng",
            "PLATINUM": "Bạch Kim", "EMERALD": "Lục Bảo", "DIAMOND": "Kim Cương",
            "MASTER": "Cao Thủ", "GRANDMASTER": "Đại Cao Thủ", "CHALLENGER": "Thách Đấu"}


def round_to_stage(r: int) -> str:
    if r <= 4:
        return f"1-{r}"
    return f"{2 + (r - 5) // 7}-{(r - 5) % 7 + 1}"


class Riot:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.enabled = bool(cfg["riot_api_key"] and cfg["riot_game_name"] and cfg["riot_tag_line"])
        self.s = requests.Session()
        self.s.headers["X-Riot-Token"] = cfg["riot_api_key"]
        self.cache = cfg["data_path"] / "matches"
        self.cache.mkdir(exist_ok=True)
        self._puuid = None

    def _get(self, url, params=None):
        loi_mang = None
        for _ in range(4):
            try:
                r = self.s.get(url, params=params, timeout=20)
            except requests.RequestException as e:
                # quy về RiotError để nơi gọi chỉ cần bắt một loại
                loi_mang = e
                time.sleep(2)
                continue
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "5")))
                continue
            if 500 <= r.status_code < 600:
                time.sleep(2)          # máy chủ Riot chập chờn, thử lại thay vì bỏ cuộc
                continue
            if r.status_code in (401, 403):
                raise RiotError("Riot API key sai hoặc đã hết hạn (key dev hết hạn sau 24 giờ).")
            if r.status_code == 404:
                raise RiotError(f"Không tìm thấy dữ liệu: {url}")
            r.raise_for_status()
            return r.json()
        if loi_mang is not None:
            raise RiotError(f"Không kết nối được Riot API (kiểm tra mạng): {loi_mang}")
        raise RiotError("Riot API giới hạn tốc độ hoặc lỗi máy chủ quá lâu, thử lại sau.")

    def puuid(self) -> str:
        if self._puuid:
            return self._puuid
        c = self.cfg
        url = (f"https://{c['account_region']}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
               f"{quote(c['riot_game_name'])}/{quote(c['riot_tag_line'])}")
        self._puuid = self._get(url)["puuid"]
        return self._puuid

    def match_ids(self, count=20):
        url = f"https://{self.cfg['match_region']}.api.riotgames.com/tft/match/v1/matches/by-puuid/{self.puuid()}/ids"
        return self._get(url, {"count": count})

    def match(self, mid: str) -> dict:
        path = self.cache / f"{mid}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        data = self._get(f"https://{self.cfg['match_region']}.api.riotgames.com/tft/match/v1/matches/{mid}")
        config.write_json(path, data)
        return data

    def rank_raw(self):
        """Rank dạng số để vẽ biểu đồ LP. None nếu chưa có rank hoặc API lỗi."""
        import time as _time
        url = f"https://{self.cfg['platform']}.api.riotgames.com/tft/league/v1/by-puuid/{self.puuid()}"
        try:
            for e in self._get(url):
                if e.get("queueType") != "RANKED_TFT":
                    continue
                tier = TIERS_VI.get(e["tier"], e["tier"])
                div = "" if e["tier"] in ("MASTER", "GRANDMASTER", "CHALLENGER") else f" {e['rank']}"
                return {"tier": e["tier"], "division": e.get("rank"), "lp": e.get("leaguePoints"),
                        "wins": e.get("wins"), "losses": e.get("losses"),
                        "tier_vi": f"{tier}{div}", "ts": _time.time()}
        except RiotError:
            pass
        return None

    def rank(self):
        url = f"https://{self.cfg['platform']}.api.riotgames.com/tft/league/v1/by-puuid/{self.puuid()}"
        try:
            for e in self._get(url):
                if e.get("queueType") == "RANKED_TFT":
                    tier = TIERS_VI.get(e["tier"], e["tier"])
                    div = "" if e["tier"] in ("MASTER", "GRANDMASTER", "CHALLENGER") else f" {e['rank']}"
                    return (f"{tier}{div} · {e['leaguePoints']} LP · "
                            f"{e['wins']} thắng / {e['losses']} thua")
        except RiotError:
            pass
        return None

    def find_match_near(self, end_ts: float, start_ts: float = 0, tries=6, wait=30, window=20 * 60):
        """Tìm đúng trận vừa chơi (Riot trễ 1-3 phút mới có dữ liệu).

        Lấy trận có thời điểm gần lúc kết thúc nhất, trong khoảng cho phép, và phải
        kết thúc sau khi bắt đầu ghi. Trước đây lấy trận đầu tiên lọt ±45 phút nên
        dễ nhận nhầm trận trước đó.
        """
        for i in range(tries):
            best, best_gap = None, window
            for mid in self.match_ids(5):
                m = self.match(mid)
                t = m["info"]["game_datetime"] / 1000
                if start_ts and t < start_ts - 60:
                    continue
                gap = abs(t - end_ts)
                if gap < best_gap:
                    best, best_gap = m, gap
            if best:
                return best
            if i < tries - 1:
                time.sleep(wait)
        return None


def me_in(match: dict, puuid: str) -> dict:
    return next(p for p in match["info"]["participants"] if p["puuid"] == puuid)


def summarize_player(p: dict) -> dict:
    traits = sorted((t for t in p.get("traits", []) if t.get("tier_current", 0) > 0),
                    key=lambda t: (-t.get("style", 0), -t["num_units"]))
    return {
        "placement": p["placement"],
        "level": p["level"],
        "gold_left": p.get("gold_left"),
        "eliminated_at": round_to_stage(p.get("last_round", 0)),
        "damage_to_players": p.get("total_damage_to_players"),
        "augments": [clean(a) for a in p.get("augments", [])],
        "traits": [f"{clean(t['name'])} {t['num_units']}" for t in traits],
        "units": [f"{clean(u['character_id'])} {u['tier']}★" +
                  (f" [{', '.join(clean(i) for i in u.get('itemNames', []))}]" if u.get("itemNames") else "")
                  for u in p.get("units", [])],
    }


def lobby_summary(match: dict) -> list:
    out = []
    for p in sorted(match["info"]["participants"], key=lambda x: x["placement"]):
        s = summarize_player(p)
        carries = [u for u in s["units"] if u.count(",") >= 2]
        out.append(f"#{s['placement']}: {', '.join(s['traits'][:4])} | carry: {'; '.join(carries) or '-'}")
    return out


QUEUE_RANKED_TFT = 1100


def la_tran_rank(info: dict) -> bool:
    """Chỉ tính trận xếp hạng: bỏ Đôi Tuyển, Siêu Tốc và trận thường (queue khác 1100)."""
    if info.get("tft_game_type") not in (None, "standard"):
        return False
    q = info.get("queue_id")
    return q is None or q == QUEUE_RANKED_TFT


class LocSet:
    """Giữ đúng một set: set của trận mới nhất. Riot trả trận mới trước, nên trận đầu tiên
    hợp lệ quyết định set. Không lọc thì qua set mới, hồ sơ trộn carry của set cũ."""

    def __init__(self):
        self.set = None

    def nhan(self, info: dict) -> bool:
        s = info.get("tft_set_number")
        if s is None:
            return True
        if self.set is None:
            self.set = s
        return s == self.set


def trait_chinh(p: dict) -> dict | None:
    """Tộc chính = tộc nhiều tướng nhất, hoà thì xét mốc cao hơn. Bỏ tộc riêng của từng tướng.

    Xét mốc (style) trước thì tộc 2 tướng ở mốc vàng thắng 6 Đấu Sĩ mốc bạc — sai ý "chơi bài gì".
    """
    active = [t for t in p.get("traits", [])
              if t.get("tier_current", 0) > 0 and "Unique" not in t.get("name", "")]
    return max(active, key=lambda t: (t.get("num_units", 0), t.get("style", 0)), default=None)


def so_do_that(u: dict) -> int:
    """Số món đồ tính để đoán carry. Ấn tộc hệ không phải đồ carry: tank cầm hai ấn không phải carry."""
    return sum(1 for i in (u.get("itemNames") or u.get("items") or [])
               if not (isinstance(i, str) and "Emblem" in i))


def stats(riot: Riot, n=20) -> dict:
    puuid = riot.puuid()
    places, by_trait, augs = [], defaultdict(list), Counter()
    loc = LocSet()
    for mid in riot.match_ids(n):
        m = riot.match(mid)
        if not la_tran_rank(m["info"]) or not loc.nhan(m["info"]):
            continue
        p = me_in(m, puuid)
        places.append(p["placement"])
        top = trait_chinh(p)
        if top:
            by_trait[clean(top["name"])].append(p["placement"])
        augs.update(clean(a) for a in p.get("augments", []))
    if not places:
        return {"games": 0}
    return {
        "games": len(places),
        "avg_place": round(sum(places) / len(places), 2),
        "top4_rate": round(100 * sum(x <= 4 for x in places) / len(places), 1),
        "win_rate": round(100 * sum(x == 1 for x in places) / len(places), 1),
        "recent": places,
        "by_main_trait": sorted(
            ({"trait": k, "games": len(v), "avg": round(sum(v) / len(v), 2)} for k, v in by_trait.items()),
            key=lambda d: -d["games"]),
        "top_augments": augs.most_common(8),
    }
