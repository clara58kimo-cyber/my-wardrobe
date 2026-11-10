import sqlite3
import os
from datetime import datetime
import streamlit as st

# 設定網頁版面配置與標題
st.set_page_config(page_title="Clara 的質感衣櫃", page_icon="👗", layout="wide")

# 1. 初始化資料庫（加入 style 與 season 欄位）
def init_db():
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS clothing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            style TEXT,
            season TEXT,
            image_path TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()
os.makedirs("uploads", exist_ok=True)

st.title("👗 Clara 的質感服裝搭配資料庫")
st.markdown("打造專屬你的美學衣櫃，輕鬆管理與搭配每一套穿搭！")

# 建立分頁介面
tab1, tab2, tab3 = st.tabs(["✨ 新增衣物", "📂 質感衣櫃總覽", "🎨 穿搭組合推薦"])

# --- 標籤頁一：新增衣物 ---
with tab1:
    st.subheader("上傳或拍攝新衣物")
    
    col_a, col_b = st.columns(2)
    with col_a:
        category = st.selectbox("服裝分類", ["上身 (Tops)", "下身 (Bottoms)"])
        style = st.selectbox("風格標籤", ["休閒 (Casual)", "正式 (Formal)", "法式簡約 (Minimalist)", "甜美復古 (Vintage)"])
    with col_b:
        season = st.selectbox("適用季節", ["春季 (Spring)", "夏季 (Summer)", "秋季 (Autumn)", "冬季 (Winter)", "四季通穿 (All-Season)"])
    
    upload_option = st.radio("圖片來源", ["上傳本地照片", "現場拍照"])
    image_file = st.file_uploader("選擇圖片檔案", type=["jpg", "jpeg", "png"]) if upload_option == "上傳本地照片" else st.camera_input("使用相機拍攝")

    if image_file is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = getattr(image_file, 'name', 'cam.jpg')
        image_path = os.path.join("uploads", f"{timestamp}_{file_name}")
        
        with open(image_path, "wb") as f:
            f.write(image_file.getbuffer())
        
        if st.button("確認儲存至衣櫃", type="primary"):
            conn = sqlite3.connect('wardrobe.db')
            c = conn.cursor()
            c.execute("INSERT INTO clothing (category, style, season, image_path, created_at) VALUES (?, ?, ?, ?, ?)",
                      (category, style, season, image_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
            st.success("✨ 成功將衣物加入你的質感資料庫！")

# --- 標籤頁二：衣櫃總覽 ---
with tab2:
    st.subheader("我的衣櫃收藏")
    
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    c.execute("SELECT id, category, style, season, image_path FROM clothing")
    items = c.fetchall()
    conn.close()

    if items:
        # 篩選器
        filter_style = st.selectbox("依風格篩選檢視", ["全部風格", "休閒 (Casual)", "正式 (Formal)", "法式簡約 (Minimalist)", "甜美復古 (Vintage)"])
        
        filtered_items = items if filter_style == "全部風格" else [item for item in items if item[2] == filter_style]

        cols = st.columns(3)
        for index, (item_id, cat, sty, sea, img_path) in enumerate(filtered_items):
            with cols[index % 3]:
                if os.path.exists(img_path):
                    st.image(img_path, use_container_width=True)
                    st.markdown(f"**分類：** {cat}")
                    st.markdown(f"**風格：** {sty} | **季節：** {sea}")
                    st.divider()
    else:
        st.info("目前衣櫃還空空如也，快到第一頁新增衣服吧！")

# --- 標籤頁三：穿搭組合推薦 ---
with tab3:
    st.subheader("✨ 今日穿搭靈感與組合")
    
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    c.execute("SELECT id, style, season, image_path FROM clothing WHERE category = '上身 (Tops)'")
    tops = c.fetchall()
    c.execute("SELECT id, style, season, image_path FROM clothing WHERE category = '下身 (Bottoms)'")
    bottoms = c.fetchall()
    conn.close()

    if tops and bottoms:
        st.markdown("以下為你隨機配對的上身與下身質感組合：")
        import random
        selected_top = random.choice(tops)
        selected_bottom = random.choice(bottoms)

        col_top, col_bottom = st.columns(2)
        with col_top:
            st.markdown("### 上身 (Top)")
            if os.path.exists(selected_top[3]):
                st.image(selected_top[3], use_container_width=True)
                st.markdown(f"風格: {selected_top[1]} | 季節: {selected_top[2]}")
        with col_bottom:
            st.markdown("### 下身 (Bottom)")
            if os.path.exists(selected_bottom[3]):
                st.image(selected_bottom[3], use_container_width=True)
                st.markdown(f"風格: {selected_bottom[1]} | 季節: {selected_bottom[2]}")
        
        if st.button("🔄 換一套搭配組合"):
            st.rerun()
    else:
        st.warning("請確保衣櫃內**同時擁有至少一件上身與一件下身**，才能解鎖穿搭組合推薦喔！")