import base64
import io
import uuid
from datetime import date, timedelta, timezone, datetime

import streamlit as st
from PIL import Image, ImageOps

import matcher as M
from storage import SQLiteStore, SupabaseStore, export_backup, import_backup

st.set_page_config(page_title="Clara 的質感衣櫃", page_icon="👗", layout="wide")

TAIPEI = timezone(timedelta(hours=8))


def today() -> date:
    return datetime.now(TAIPEI).date()


# ---------------------------------------------------------------------------
# 樣式
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; max-width: 1200px;}
    [data-testid="stImage"] img {border-radius: 12px; aspect-ratio: 3/4; object-fit: cover;}
    .outfit {display:grid; gap:10px; margin:.4rem 0 .6rem;}
    .outfit .pc img, .outfit .pc .ph {width:100%; aspect-ratio:3/4; object-fit:cover; border-radius:10px;
          background:rgba(150,120,90,.08); display:flex; align-items:center; justify-content:center; font-size:2.4rem;}
    .outfit .nm {font-weight:600; font-size:.88rem; margin-top:4px; line-height:1.3;}
    @media (max-width: 640px) {
      h1 {font-size: 1.7rem !important;}
      .outfit {gap:6px;} .outfit .nm {font-size:.75rem;} .outfit .tag {font-size:.65rem; padding:1px 6px;}
      [data-testid="stImage"] img {max-height: 280px; object-fit: contain;}
    }
    .tag {display:inline-block; padding:2px 10px; margin:2px 4px 2px 0; border-radius:999px;
          font-size:0.78rem; background:rgba(150,120,90,.12); color:inherit;}
    .swatch {display:inline-block; width:12px; height:12px; border-radius:50%;
             border:1px solid rgba(0,0,0,.2); vertical-align:-1px; margin-right:4px;}
    .score {font-size:1.4rem; font-weight:700;}
    .muted {opacity:.65; font-size:.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# 設定與密碼保護
# ---------------------------------------------------------------------------
def secret(key, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def password_gate():
    pw = secret("APP_PASSWORD")
    if not pw or st.session_state.get("authed"):
        return
    st.title("👗 Clara 的質感衣櫃")
    entered = st.text_input("請輸入密碼", type="password")
    if entered:
        if entered == pw:
            st.session_state.authed = True
            st.rerun()
        st.error("密碼不正確")
    st.stop()


password_gate()


@st.cache_resource
def get_store():
    url, key = secret("SUPABASE_URL"), secret("SUPABASE_KEY")
    if url and key:
        try:
            s = SupabaseStore(url, key, secret("SUPABASE_BUCKET", "wardrobe"))
            s.list_items()  # 確認連線與資料表正常
            return s, None
        except Exception as e:  # 設定錯誤時退回本機模式，不讓整個系統掛掉
            return SQLiteStore("wardrobe.db"), str(e)
    return SQLiteStore("wardrobe.db"), None


store, store_error = get_store()


@st.cache_data(ttl=600, show_spinner=False)
def load_items(_mode):
    return [M.normalize(i) for i in store.list_items()]


@st.cache_data(ttl=600, show_spinner=False)
def load_outfits(_mode):
    return store.list_outfits()


@st.cache_data(ttl=600, show_spinner=False)
def load_wear_log(_mode):
    return store.list_wear_log()


@st.cache_data(max_entries=800, show_spinner=False)
def image_bytes(path):
    return store.get_image(path)


def refresh():
    load_items.clear()
    load_outfits.clear()
    load_wear_log.clear()


items = load_items(store.mode)
items_by_id = {i["id"]: i for i in items}
outfits = load_outfits(store.mode)
wear_log = load_wear_log(store.mode)


# ---------------------------------------------------------------------------
# 圖片處理
# ---------------------------------------------------------------------------
def process_image(file) -> tuple[bytes, bytes]:
    """修正手機照片方向、透明背景補白、壓縮，產生大圖與縮圖。"""
    img = Image.open(file)
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")

    def encode(im, size, q):
        im = im.copy()
        im.thumbnail((size, size))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True)
        return buf.getvalue()

    return encode(img, 1000, 85), encode(img, 420, 80)


def guess_color(file) -> str:
    """取照片中央區域的主要顏色，對應到最接近的色票作為預設值。"""
    try:
        img = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
        w, h = img.size
        img = img.crop((w * 0.3, h * 0.3, w * 0.7, h * 0.7)).resize((40, 40))
        q = img.quantize(colors=3)
        palette = q.getpalette()
        counts = sorted(q.getcolors(), reverse=True)
        idx = counts[0][1]
        rgb = palette[idx * 3: idx * 3 + 3]
    except Exception:
        return "黑"
    finally:
        try:
            file.seek(0)
        except Exception:
            pass

    def dist(hexcode):
        h_ = hexcode.lstrip("#")
        c = [int(h_[i:i + 2], 16) for i in (0, 2, 4)]
        return sum((a - b) ** 2 for a, b in zip(c, rgb))

    return min(M.SOLID_COLORS, key=lambda c: dist(M.COLORS[c][0]))


# ---------------------------------------------------------------------------
# 共用元件
# ---------------------------------------------------------------------------
def tags_html(it):
    color = it.get("color")
    sw = f'<span class="swatch" style="background:{M.COLORS[color][0]}"></span>{color}' if color in M.COLORS else ""
    tags = [sw] if sw else []
    tags += it.get("styles", [])
    seasons = it.get("seasons", [])
    tags.append("四季" if len(seasons) == 4 else "".join(s for s in M.SEASONS if s in seasons))
    return "".join(f'<span class="tag">{t}</span>' for t in tags if t)


def item_title(it):
    icon = M.CATEGORY_ICON.get(it["category"], "")
    name = it.get("name") or it["category"]
    return f"{icon} {name}{' ⭐' if it.get('favorite') else ''}"


def show_image(it, thumb=True):
    path = (it.get("thumb_path") if thumb else None) or it.get("image_path")
    data = image_bytes(path) if path else None
    if data:
        st.image(data, width="stretch")
    else:
        st.markdown(f"<div style='aspect-ratio:3/4;display:flex;align-items:center;justify-content:center;"
                    f"border-radius:12px;background:rgba(150,120,90,.08);font-size:3rem'>"
                    f"{M.CATEGORY_ICON.get(it['category'], '👕')}</div>", unsafe_allow_html=True)


def outfit_html(pieces, with_tags=True):
    """整套穿搭用 HTML 格線呈現，手機上也會維持並排，不會被拆成一件一列。"""
    cells = []
    for p in pieces:
        path = p.get("thumb_path") or p.get("image_path")
        data = image_bytes(path) if path else None
        pic = (f'<img src="data:image/jpeg;base64,{base64.b64encode(data).decode()}">' if data
               else f'<div class="ph">{M.CATEGORY_ICON.get(p["category"], "👕")}</div>')
        tags = f"<div>{tags_html(p)}</div>" if with_tags else ""
        cells.append(f'<div class="pc">{pic}<div class="nm">{item_title(p)}</div>{tags}</div>')
    n = max(len(pieces), 3)
    return f'<div class="outfit" style="grid-template-columns:repeat({n},minmax(0,1fr))">{"".join(cells)}</div>'


def item_form(prefix, it=None, suggested_color=None):
    it = it or {}
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("名稱（選填）", it.get("name") or "", key=f"{prefix}_name",
                             placeholder="例：白色亞麻襯衫")
        cat_idx = M.CATEGORIES.index(it["category"]) if it.get("category") in M.CATEGORIES else 0
        category = st.selectbox("分類", M.CATEGORIES, index=cat_idx, key=f"{prefix}_cat",
                                format_func=lambda c: f"{M.CATEGORY_ICON[c]} {c}")
        color_default = it.get("color") or suggested_color or "黑"
        color = st.selectbox("主色", list(M.COLORS), index=list(M.COLORS).index(color_default)
                             if color_default in M.COLORS else 0, key=f"{prefix}_color",
                             help="新增照片時會自動偵測顏色，可自行修改")
    with c2:
        styles = st.pills("風格（可複選）", M.STYLES, selection_mode="multi",
                          default=[s for s in it.get("styles", []) if s in M.STYLES], key=f"{prefix}_styles")
        seasons = st.pills("適用季節（可複選）", M.SEASONS, selection_mode="multi",
                           default=it.get("seasons") or M.SEASONS, key=f"{prefix}_seasons")
        notes = st.text_input("備註（選填）", it.get("notes") or "", key=f"{prefix}_notes",
                              placeholder="例：需手洗、適合搭高腰褲")
        favorite = st.toggle("⭐ 最愛單品", value=bool(it.get("favorite")), key=f"{prefix}_fav")
    return {"name": name.strip(), "category": category, "color": color, "styles": styles or [],
            "seasons": seasons or M.SEASONS, "notes": notes.strip(), "favorite": favorite}


@st.dialog("編輯衣物", width="large")
def edit_dialog(item_id):
    it = items_by_id[item_id]
    c_img, c_form = st.columns([1, 2])
    with c_img:
        show_image(it, thumb=False)
        st.caption(f"穿過 {it.get('wear_count', 0)} 次"
                   + (f"・上次 {it['last_worn']}" if it.get("last_worn") else ""))
    with c_form:
        data = item_form(f"edit{item_id}", it)
    b1, b2, b3 = st.columns([1, 1, 2])
    if b1.button("💾 儲存", type="primary", width="stretch"):
        store.update_item(item_id, data)
        refresh()
        st.rerun()
    if b2.button("👕 今天穿", width="stretch"):
        store.log_wear([item_id], today().isoformat())
        refresh()
        st.rerun()
    with b3.popover("🗑️ 刪除", width="stretch"):
        st.write("確定要刪除這件衣物嗎？無法復原。")
        if st.button("確定刪除", type="primary", key=f"del{item_id}"):
            store.delete_item(it)
            refresh()
            st.rerun()


# ---------------------------------------------------------------------------
# 頁首
# ---------------------------------------------------------------------------
st.title("👗 Clara 的質感衣櫃")
counts = {c: sum(i["category"] == c for i in items) for c in M.CATEGORIES}
st.caption(f"共 {len(items)} 件　|　" + "　".join(f"{M.CATEGORY_ICON[c]} {c} {n}" for c, n in counts.items() if n)
           + f"　|　儲存：{store.label}")

if store.mode == "local":
    with st.expander("⚠️ 目前資料存在 Streamlit Cloud 暫存空間，重新部署或休眠後**可能會消失**", expanded=not items):
        st.markdown(
            "- **馬上可做**：到「⚙️ 統計與備份」定期下載備份檔，資料不見時可一鍵還原。\n"
            "- **一勞永逸**：依 README 設定免費的 Supabase，資料就會永久保存在雲端。"
        )
if store_error:
    st.error(f"Supabase 連線失敗，已改用本機模式：{store_error}")

tab_match, tab_closet, tab_add, tab_saved, tab_stats = st.tabs(
    ["🎨 智慧搭配", "👚 我的衣櫃", "➕ 新增衣物", "⭐ 收藏穿搭", "⚙️ 統計與備份"]
)

# ---------------------------------------------------------------------------
# 🎨 智慧搭配
# ---------------------------------------------------------------------------
with tab_match:
    season_now = M.current_season(today())
    f1, f2, f3 = st.columns([1.2, 2, 1.6])
    with f1:
        season = st.segmented_control("季節", ["不限"] + M.SEASONS, default=season_now, key="m_season")
    with f2:
        style = st.pills("想要的風格", ["不限"] + M.STYLES, default="不限", key="m_style")
    with f3:
        anchor_opts = [None] + [i["id"] for i in items]
        anchor = st.selectbox("以某件單品為主（選填）", anchor_opts, key="m_anchor",
                              format_func=lambda x: "— 不指定 —" if x is None else
                              f"#{x} {item_title(items_by_id[x])}")
    o1, o2, _ = st.columns([1, 1, 3])
    with_outer = o1.toggle("加外套", value=season in ("秋", "冬"), key="m_outer")
    with_shoes = o2.toggle("加鞋子", value=True, key="m_shoes")

    recs = M.recommend(
        items,
        season=None if season in (None, "不限") else season,
        style=None if style in (None, "不限") else style,
        anchor_id=anchor, wear_log=wear_log,
        with_outer=with_outer, with_shoes=with_shoes, today=today(),
    )

    if not recs:
        need = []
        if not counts["上身"] and not counts["洋裝/連身"]:
            need.append("上身或洋裝")
        if not counts["下身"] and not counts["洋裝/連身"]:
            need.append("下身")
        if need:
            st.info(f"衣櫃裡還缺少 **{'、'.join(need)}**，到「➕ 新增衣物」加入後就能開始搭配。")
        else:
            st.info("目前條件下沒有符合的組合，試試把季節或風格改成「不限」。")
    else:
        st.caption(f"依季節、風格、配色、多久沒穿與你的最愛計分，共找到 {len(recs)} 組，由高到低排列。")
        page_size = 3
        pages = (len(recs) + page_size - 1) // page_size
        key_sig = f"{season}-{style}-{anchor}-{with_outer}-{with_shoes}"
        if st.session_state.get("m_sig") != key_sig:
            st.session_state.m_sig, st.session_state.m_page = key_sig, 0
        page = st.session_state.m_page % pages

        for rank, rec in enumerate(recs[page * page_size:(page + 1) * page_size], start=page * page_size + 1):
            with st.container(border=True):
                h1, h2 = st.columns([3, 1])
                h1.markdown(f"**第 {rank} 名・{M.match_label(rec['score'])}**　"
                            f"<span class='muted'>{'・'.join(rec['reasons'])}</span>", unsafe_allow_html=True)
                h2.markdown(f"<div style='text-align:right'><span class='score'>{rec['score']}</span>"
                            f"<span class='muted'> 分</span></div>", unsafe_allow_html=True)
                st.markdown(outfit_html(rec["pieces"]), unsafe_allow_html=True)
                ids = [p["id"] for p in rec["pieces"]]
                a1, a2, _ = st.columns([1, 1, 3])
                if a1.button("👕 今天就穿這套", key=f"wear_{rank}_{key_sig}", width="stretch"):
                    store.log_wear(ids, today().isoformat())
                    refresh()
                    st.toast("已記錄！這套兩週內會往後排，避免重複。")
                    st.rerun()
                with a2.popover("⭐ 收藏", width="stretch"):
                    oname = st.text_input("穿搭名稱", value=f"{style if style not in (None, '不限') else ''}"
                                          f"{season if season not in (None, '不限') else ''}穿搭 {today():%m/%d}",
                                          key=f"oname_{rank}_{key_sig}")
                    if st.button("儲存", key=f"save_{rank}_{key_sig}", type="primary"):
                        store.add_outfit(oname, ids)
                        refresh()
                        st.toast("已加入收藏穿搭")
                        st.rerun()

        n1, n2, n3 = st.columns([1, 2, 1])
        if n1.button("⬅️ 上一批", disabled=page == 0, width="stretch"):
            st.session_state.m_page = page - 1
            st.rerun()
        n2.markdown(f"<div style='text-align:center' class='muted'>第 {page + 1} / {pages} 批</div>",
                    unsafe_allow_html=True)
        if n3.button("下一批 ➡️", disabled=page >= pages - 1, width="stretch"):
            st.session_state.m_page = page + 1
            st.rerun()

# ---------------------------------------------------------------------------
# 👚 我的衣櫃
# ---------------------------------------------------------------------------
with tab_closet:
    if not items:
        st.info("衣櫃還空空的，到「➕ 新增衣物」加入第一件吧！")
    else:
        g1, g2, g3, g4 = st.columns([2, 1.3, 1.3, 1.3])
        q = g1.text_input("搜尋名稱或備註", key="c_q", placeholder="輸入關鍵字…")
        f_cat = g2.multiselect("分類", M.CATEGORIES, key="c_cat")
        f_style = g3.multiselect("風格", M.STYLES, key="c_style")
        f_season = g4.multiselect("季節", M.SEASONS, key="c_season")
        h1, h2, h3 = st.columns([1.3, 1.3, 2.4])
        f_color = h1.multiselect("顏色", list(M.COLORS), key="c_color")
        sort = h2.selectbox("排序", ["最新加入", "最少穿", "最常穿", "最久沒穿"], key="c_sort")
        only_fav = h3.toggle("只看最愛 ⭐", key="c_fav")

        shown = [
            i for i in items
            if (not q or q.lower() in f"{i.get('name') or ''} {i.get('notes') or ''}".lower())
            and (not f_cat or i["category"] in f_cat)
            and (not f_style or set(f_style) & set(i["styles"]))
            and (not f_season or set(f_season) & set(i["seasons"]))
            and (not f_color or i.get("color") in f_color)
            and (not only_fav or i.get("favorite"))
        ]
        if sort == "最少穿":
            shown.sort(key=lambda i: i["wear_count"])
        elif sort == "最常穿":
            shown.sort(key=lambda i: -i["wear_count"])
        elif sort == "最久沒穿":
            shown.sort(key=lambda i: i.get("last_worn") or "0000")

        st.caption(f"顯示 {len(shown)} / {len(items)} 件，點「編輯」可修改、標記穿著或刪除")
        per_row = 4
        for r in range(0, len(shown), per_row):
            cols = st.columns(per_row)
            for col, it in zip(cols, shown[r:r + per_row]):
                with col, st.container(border=True):
                    show_image(it)
                    st.markdown(f"**{item_title(it)}**<br>{tags_html(it)}", unsafe_allow_html=True)
                    worn = f"穿過 {it['wear_count']} 次" + (f"・{it['last_worn']}" if it.get("last_worn") else "")
                    st.caption(worn)
                    if st.button("編輯", key=f"edit_{it['id']}", width="stretch"):
                        edit_dialog(it["id"])

# ---------------------------------------------------------------------------
# ➕ 新增衣物
# ---------------------------------------------------------------------------
with tab_add:
    src = st.segmented_control("圖片來源", ["上傳照片", "現場拍照"], default="上傳照片", key="a_src")
    if src == "現場拍照":
        files = [f for f in [st.camera_input("拍攝衣物", key="a_cam")] if f]
    else:
        files = st.file_uploader("選擇圖片（可一次多張，同一批會套用相同設定）",
                                 type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True,
                                 key=f"a_up_{st.session_state.get('a_nonce', 0)}") or []

    if files:
        prev = st.columns(min(len(files), 6))
        for col, f in zip(prev, files[:6]):
            col.image(f, width="stretch")
        if len(files) > 6:
            st.caption(f"…另外還有 {len(files) - 6} 張")
        suggested = guess_color(files[0])
        st.caption(f"🎨 自動偵測主色：{suggested}（可在下方修改）")
        data = item_form(f"add_{st.session_state.get('a_nonce', 0)}", suggested_color=suggested)
        if st.button(f"✨ 儲存 {len(files)} 件到衣櫃", type="primary"):
            prog = st.progress(0.0)
            for n, f in enumerate(files, 1):
                try:
                    full, thumb = process_image(f)
                except Exception as e:
                    st.error(f"{getattr(f, 'name', '照片')} 處理失敗：{e}")
                    continue
                key = f"{today():%Y%m}/{uuid.uuid4().hex[:12]}"
                store.put_image(f"{key}.jpg", full)
                store.put_image(f"{key}_t.jpg", thumb)
                row = dict(data)
                if len(files) > 1 and n > 1 and data.get("color") == suggested:
                    row["color"] = guess_color(f)  # 多張時每張各自偵測顏色
                store.add_item({**row, "image_path": f"{key}.jpg", "thumb_path": f"{key}_t.jpg"})
                prog.progress(n / len(files))
            refresh()
            st.session_state.a_nonce = st.session_state.get("a_nonce", 0) + 1
            st.toast(f"已新增 {len(files)} 件衣物 ✨")
            st.rerun()
    else:
        st.info("💡 小技巧：平放或掛在素色背景前拍攝，顏色偵測與搭配效果最好。")

# ---------------------------------------------------------------------------
# ⭐ 收藏穿搭
# ---------------------------------------------------------------------------
with tab_saved:
    if not outfits:
        st.info("在「🎨 智慧搭配」按下「⭐ 收藏」，喜歡的穿搭就會出現在這裡。")
    for o in outfits:
        pieces = [items_by_id[i] for i in o["item_ids"] if i in items_by_id]
        with st.container(border=True):
            t1, t2, t3 = st.columns([3, 1, 1])
            t1.markdown(f"**{o['name']}**　<span class='muted'>{str(o.get('created_at') or '')[:10]}</span>",
                        unsafe_allow_html=True)
            if t2.button("👕 今天穿", key=f"ow_{o['id']}", width="stretch", disabled=not pieces):
                store.log_wear([p["id"] for p in pieces], today().isoformat())
                refresh()
                st.toast("已記錄穿著")
                st.rerun()
            if t3.button("🗑️ 移除", key=f"od_{o['id']}", width="stretch"):
                store.delete_outfit(o["id"])
                refresh()
                st.rerun()
            if not pieces:
                st.caption("這套穿搭的單品已被刪除")
            if pieces:
                st.markdown(outfit_html(pieces, with_tags=False), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# ⚙️ 統計與備份
# ---------------------------------------------------------------------------
with tab_stats:
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("衣物總數", len(items))
    s2.metric("收藏穿搭", len(outfits))
    s3.metric("穿著紀錄", len(wear_log))
    month = today().strftime("%Y-%m")
    s4.metric("本月穿搭次數", sum(str(w["worn_on"]).startswith(month) for w in wear_log))

    if items:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 各分類數量")
            st.bar_chart({c: n for c, n in counts.items() if n}, horizontal=True, height=220, color="#8B6F4E")
        with c2:
            st.markdown("##### 顏色分布")
            color_counts = {}
            for i in items:
                c = i.get("color") or "未設定"
                color_counts[c] = color_counts.get(c, 0) + 1
            st.bar_chart(color_counts, horizontal=True, height=220, color="#8B6F4E")
            if "未設定" in color_counts:
                st.caption(f"有 {color_counts['未設定']} 件舊衣物還沒設定主色，可到「我的衣櫃」點「編輯」補上。")

        idle = [i for i in items if not i.get("last_worn")
                or (today() - date.fromisoformat(i["last_worn"])).days > 60]
        st.markdown(f"##### 💤 被冷落的單品（60 天以上沒穿）：{len(idle)} 件")
        if idle:
            cols = st.columns(6)
            for col, it in zip(cols, idle[:12]):
                with col:
                    show_image(it)
                    st.caption(item_title(it))
            st.caption("在「智慧搭配」選擇「以某件單品為主」，幫它們找到新搭配吧！")

    st.divider()
    st.markdown("##### 💾 備份與還原")
    b1, b2 = st.columns(2)
    with b1:
        st.caption("把所有衣物、照片、收藏穿搭與穿著紀錄打包成一個 .zip 檔。")
        if st.button("準備備份檔"):
            st.session_state.backup = export_backup(store)
        if st.session_state.get("backup"):
            st.download_button("⬇️ 下載備份", st.session_state.backup,
                               file_name=f"wardrobe_backup_{today():%Y%m%d}.zip", mime="application/zip",
                               type="primary")
    with b2:
        st.caption("上傳先前下載的備份檔，資料會「合併加入」目前的衣櫃。")
        up = st.file_uploader("選擇備份 .zip", type=["zip"], key="restore")
        if up and st.button("還原備份", type="primary"):
            try:
                n_items, n_outfits = import_backup(store, up.getvalue())
                refresh()
                st.success(f"已還原 {n_items} 件衣物、{n_outfits} 組收藏穿搭")
            except Exception as e:
                st.error(f"還原失敗：{e}")
