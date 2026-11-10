"""
智慧搭配引擎（非隨機）
每一組搭配都依「季節 → 風格 → 配色 → 新鮮度 → 偏好」計分排序，
並附上推薦理由；同樣的衣櫃與條件，永遠得到同樣的排序結果。
"""
from __future__ import annotations

from datetime import date
from itertools import product

# ---- 基本設定 ---------------------------------------------------------------
CATEGORIES = ["上身", "下身", "洋裝/連身", "外套", "鞋子", "配件"]
CATEGORY_ICON = {"上身": "👚", "下身": "👖", "洋裝/連身": "👗", "外套": "🧥", "鞋子": "👟", "配件": "👜"}
SEASONS = ["春", "夏", "秋", "冬"]
STYLES = ["休閒", "通勤正式", "法式簡約", "甜美復古", "優雅約會", "街頭", "運動"]

# 顏色：名稱 → (色碼, 色系)。neutral=中性色、warm=暖色、cool=冷色、pattern=花紋
COLORS = {
    "黑": ("#1f1f1f", "neutral"),
    "白": ("#f7f7f5", "neutral"),
    "灰": ("#9a9a9a", "neutral"),
    "米/杏": ("#e8dcc4", "neutral"),
    "卡其/駝": ("#b9965b", "neutral"),
    "咖啡": ("#6b4a32", "neutral"),
    "海軍藍": ("#24324f", "neutral"),
    "丹寧": ("#4a6a8f", "neutral"),
    "紅": ("#c8323c", "warm"),
    "酒紅": ("#7a1f2b", "warm"),
    "粉": ("#ecaec0", "warm"),
    "橘": ("#e2873b", "warm"),
    "黃": ("#e8c547", "warm"),
    "綠": ("#4f7f5a", "cool"),
    "藍": ("#3d7cc9", "cool"),
    "紫": ("#7d5aa6", "cool"),
    "花紋/印花": ("#cccccc", "pattern"),
    "條紋/格紋": ("#bbbbbb", "pattern"),
}
SOLID_COLORS = [c for c, (_, g) in COLORS.items() if g != "pattern"]

LEGACY_CATEGORY = {"上身 (Tops)": "上身", "下身 (Bottoms)": "下身"}
LEGACY_STYLE = {
    "休閒 (Casual)": "休閒", "正式 (Formal)": "通勤正式",
    "法式簡約 (Minimalist)": "法式簡約", "甜美復古 (Vintage)": "甜美復古",
}
LEGACY_SEASON = {
    "春季 (Spring)": ["春"], "夏季 (Summer)": ["夏"], "秋季 (Autumn)": ["秋"],
    "冬季 (Winter)": ["冬"], "四季通穿 (All-Season)": SEASONS,
}


def normalize(item: dict) -> dict:
    """把舊版欄位值轉成新版格式。"""
    it = dict(item)
    it["category"] = LEGACY_CATEGORY.get(it.get("category"), it.get("category") or "上身")
    it["styles"] = [LEGACY_STYLE.get(s, s) for s in it.get("styles", [])]
    seasons = []
    for s in it.get("seasons", []):
        seasons.extend(LEGACY_SEASON.get(s, [s]))
    it["seasons"] = list(dict.fromkeys(seasons)) or SEASONS
    return it


def current_season(today: date | None = None) -> str:
    m = (today or date.today()).month
    return {12: "冬", 1: "冬", 2: "冬", 3: "春", 4: "春", 5: "春",
            6: "夏", 7: "夏", 8: "夏"}.get(m, "秋")


# ---- 計分規則 ---------------------------------------------------------------
def color_pair_score(a: str | None, b: str | None) -> tuple[float, str | None]:
    """兩件單品的配色分數與理由。"""
    if not a or not b or a not in COLORS or b not in COLORS:
        return 0.0, None
    ga, gb = COLORS[a][1], COLORS[b][1]
    if ga == "pattern" and gb == "pattern":
        return -3.0, None
    if "pattern" in (ga, gb):
        other = gb if ga == "pattern" else ga
        return (2.0, "花紋配素色中性色，主次分明") if other == "neutral" else (-0.5, None)
    if ga == "neutral" and gb == "neutral":
        if a == b and a not in ("黑", "白"):
            return 1.5, f"同色系{a}，低調有層次"
        return 2.5, "中性色組合，安全耐看"
    if "neutral" in (ga, gb):
        return 3.0, "中性色襯托亮色，重點突出"
    if a == b:
        return 1.5, f"{a}色同色系穿搭"
    if ga == gb:
        return 1.0, "同色溫搭配，色調和諧"
    return -1.5, None


def freshness(item: dict, today: date) -> float:
    """越久沒穿分數越高（0~1.5），避免一直穿同幾件。"""
    lw = item.get("last_worn")
    if not lw:
        return 1.5
    try:
        days = (today - date.fromisoformat(lw)).days
    except ValueError:
        return 1.0
    return min(days, 21) / 14


def _fits_season(item, season):
    return not season or season in item.get("seasons", SEASONS)


def score_outfit(pieces: list[dict], style: str | None, today: date,
                 recent_combos: set[frozenset]) -> tuple[float, list[str]]:
    score, reasons = 0.0, []
    main = [p for p in pieces if p["category"] in ("上身", "下身", "洋裝/連身")]

    # 風格
    if style:
        hits = sum(style in p.get("styles", []) for p in main)
        score += hits * 3
        if hits == len(main):
            reasons.append(f"全身都是「{style}」風格")
        elif hits:
            reasons.append(f"帶有「{style}」元素")
    if len(main) >= 2:
        common = set(main[0].get("styles", [])).intersection(*[set(p.get("styles", [])) for p in main[1:]])
        if common:
            score += 2
            if not style or style not in common:
                reasons.append(f"風格一致：{'、'.join(sorted(common))}")
        elif main[0].get("styles") and main[1].get("styles"):
            score -= 1

    # 配色（主要單品兩兩比較）
    for i in range(len(main)):
        for j in range(i + 1, len(main)):
            s, r = color_pair_score(main[i].get("color"), main[j].get("color"))
            score += s
            if r:
                reasons.append(r)

    # 新鮮度與偏好
    score += sum(freshness(p, today) for p in main) / max(len(main), 1)
    fav = sum(p.get("favorite", False) for p in main)
    score += fav * 0.5
    if fav:
        reasons.append("包含你最愛的單品")

    if frozenset(p["id"] for p in main) in recent_combos:
        score -= 6
        reasons.append("⚠️ 最近兩週穿過這套")
    return round(score, 2), list(dict.fromkeys(reasons))


def _best_addon(candidates, base, season, style, today):
    """為主搭配挑最合適的外套/鞋子。"""
    best, best_s = None, -99
    for c in candidates:
        if not _fits_season(c, season):
            continue
        s = sum(color_pair_score(c.get("color"), b.get("color"))[0] for b in base) / len(base)
        if style and style in c.get("styles", []):
            s += 1.5
        s += freshness(c, today) * 0.3 + (0.3 if c.get("favorite") else 0)
        if s > best_s:
            best, best_s = c, s
    return best


def recommend(items: list[dict], season: str | None = None, style: str | None = None,
              anchor_id: int | None = None, wear_log: list[dict] | None = None,
              with_outer: bool = False, with_shoes: bool = True,
              today: date | None = None, limit: int = 30) -> list[dict]:
    today = today or date.today()
    items = [normalize(i) for i in items]
    by_cat = {c: [i for i in items if i["category"] == c] for c in CATEGORIES}

    recent = set()
    for w in wear_log or []:
        try:
            if (today - date.fromisoformat(str(w["worn_on"])[:10])).days <= 14:
                recent.add(frozenset(w["item_ids"]))
        except (KeyError, ValueError):
            pass
    main_ids = {i["id"] for c in ("上身", "下身", "洋裝/連身") for i in by_cat[c]}
    recent = {frozenset(x for x in r if x in main_ids) for r in recent}

    tops = [i for i in by_cat["上身"] if _fits_season(i, season)]
    bottoms = [i for i in by_cat["下身"] if _fits_season(i, season)]
    dresses = [i for i in by_cat["洋裝/連身"] if _fits_season(i, season)]

    anchor = next((i for i in items if i["id"] == anchor_id), None)
    if anchor:
        if anchor["category"] == "上身":
            tops = [anchor]
        elif anchor["category"] == "下身":
            bottoms = [anchor]
        elif anchor["category"] == "洋裝/連身":
            tops, bottoms, dresses = [], [], [anchor]

    combos = [[t, b] for t, b in product(tops, bottoms)] + [[d] for d in dresses]
    if anchor and anchor["category"] in ("外套", "鞋子", "配件"):
        pass  # 以外套/鞋子為主時，下方會固定帶入

    results = []
    for base in combos:
        s, reasons = score_outfit(base, style, today, recent)
        extras = []
        if with_outer or (anchor and anchor["category"] == "外套"):
            o = anchor if anchor and anchor["category"] == "外套" else _best_addon(by_cat["外套"], base, season, style, today)
            if o:
                extras.append(o)
        if with_shoes or (anchor and anchor["category"] == "鞋子"):
            sh = anchor if anchor and anchor["category"] == "鞋子" else _best_addon(by_cat["鞋子"], base, season, style, today)
            if sh:
                extras.append(sh)
        if anchor and anchor["category"] == "配件":
            extras.append(anchor)
        for e in extras:
            cs = sum(color_pair_score(e.get("color"), b.get("color"))[0] for b in base) / len(base)
            s += cs * 0.5
        results.append({"pieces": base + extras, "score": round(s, 2), "reasons": reasons or ["基本款組合"]})

    results.sort(key=lambda r: (-r["score"], [p["id"] for p in r["pieces"]]))
    return results[:limit]


def match_label(score: float) -> str:
    if score >= 9:
        return "絕配"
    if score >= 6:
        return "很推薦"
    if score >= 3:
        return "不錯"
    return "可以試試"
