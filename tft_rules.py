"""Luật game TFT — nguồn sự thật DUY NHẤT cho prompt, báo cáo và các phép tính kinh tế.

Trước đây luật nằm rải rác trong prompt, guide_vi.md và web, mỗi nơi một số (thưởng chuỗi có
ba bảng khác nhau, vòng chọn lõi ghi 2-2 trong khi game là 2-1). Đổi set thì chỉ sửa file này.

Đối chiếu ngày 26/09/2026 cho Set 18 (patch 18.x):
- Vòng chọn lõi, odds, bể tướng: tftflow.com/tables/set18
- Thu nhập, lãi: wiki.leagueoflegends.com/en-us/TFT:Gold
- Thưởng chuỗi: op.gg/tft/game-guide/gold-xp (Season 18: 2/3/4 trận +1, 5 trận +2, 6+ trận +3).
  Wiki LoL còn ghi bảng cũ 3-4/5/6+ — ĐỪNG dùng.
- XP: tftflow.com và noxutft.com (hai nguồn lệch ở mốc 7→8: 56 và 60)
"""

SET = 18

AUGMENT_ROUNDS = ("2-1", "3-2", "4-2")

BASE_INCOME = 5                 # từ 2-2 trở đi; 1-2/1-3/1-4/2-1 lần lượt là 2/2/3/4
INTEREST_PER = 10
INTEREST_CAP = 5
PVP_WIN_GOLD = 1

# (số trận liên tiếp tối thiểu, vàng thưởng) — thắng hay thua như nhau
STREAK_TABLE = ((6, 3), (5, 2), (2, 1))

XP_BUY_COST = 4                 # 4 vàng mua 4 XP
XP_PER_ROUND = 2
# XP cần để lên cấp kế tiếp, tính từ đầu cấp hiện tại
XP_TO_NEXT = {3: 6, 4: 10, 5: 20, 6: 36, 7: 60, 8: 68, 9: 68}
XP_UNCERTAIN = {7: "nguồn lệch 56/60"}

# % mỗi ô cửa hàng ra tướng giá 1..5 theo cấp
SHOP_ODDS = {
    3: (75, 25, 0, 0, 0),
    4: (55, 30, 15, 0, 0),
    5: (45, 33, 20, 2, 0),
    6: (30, 40, 25, 5, 0),
    7: (16, 30, 43, 10, 1),
    8: (15, 20, 32, 30, 3),
    9: (10, 17, 25, 33, 15),
    10: (5, 10, 20, 40, 25),
}

# số bản sao mỗi tướng trong bể chung theo giá
POOL_COPIES = {1: 30, 2: 25, 3: 18, 4: 10, 5: 9}


def streak_bonus(n: int) -> int:
    for toi_thieu, vang in STREAK_TABLE:
        if n >= toi_thieu:
            return vang
    return 0


def interest(gold: int) -> int:
    return min(INTEREST_CAP, max(0, gold) // INTEREST_PER)


def income(gold: int, streak: int, won: bool) -> int:
    """Thu nhập đầu round kế tiếp ở giai đoạn ổn định (từ 2-2)."""
    return BASE_INCOME + interest(gold) + streak_bonus(streak) + (PVP_WIN_GOLD if won else 0)


def rules_md() -> str:
    """Khối luật đưa vào prompt. Đặt TRƯỚC mọi kiến thức khác và thắng khi có mâu thuẫn."""
    odds = "\n".join(f"| {lv} | " + " | ".join(f"{p}%" for p in row) + " |"
                     for lv, row in SHOP_ODDS.items())
    xp = " · ".join(f"{lv}→{lv + 1}: {x}" + (f" ({XP_UNCERTAIN[lv]})" if lv in XP_UNCERTAIN else "")
                    for lv, x in XP_TO_NEXT.items())
    return f"""## LUẬT GAME SET {SET} (nguồn sự thật — mâu thuẫn với bất kỳ đoạn nào bên dưới thì luật này thắng)

- Vòng chọn lõi: **{", ".join(AUGMENT_ROUNDS)}**. Không có vòng nào khác.
- Thu nhập mỗi round (từ 2-2): {BASE_INCOME} vàng + lãi (1 vàng mỗi {INTEREST_PER} vàng đang giữ, tối đa {INTEREST_CAP}) + thưởng chuỗi + {PVP_WIN_GOLD} nếu thắng PvP.
- Thưởng chuỗi (thắng hay thua như nhau): 2–4 trận: +1 · 5 trận: +2 · từ 6 trận: +3.
- XP: {XP_BUY_COST} vàng mua 4 XP; +{XP_PER_ROUND} XP miễn phí mỗi round. XP cần mỗi cấp: {xp}.
- Bảng máu 8 nhà nằm ở **bên phải** màn hình. Lõi đã chọn và tộc hệ nằm ở cột **bên trái**.

Tỉ lệ ra tướng theo cấp (giá 1 / 2 / 3 / 4 / 5):

| Cấp | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
{odds}

Bể tướng: mỗi tướng giá 1/2/3/4/5 có {"/".join(str(POOL_COPIES[c]) for c in range(1, 6))} bản sao dùng chung cả sảnh."""
