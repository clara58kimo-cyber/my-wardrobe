import sqlite3
import os
from datetime import datetime
import streamlit as st
from PIL import Image
import random

# 設定網頁版面配置與標題
st.set_page_config(page_title="Clara 的質感衣櫃", page_icon="👗", layout="wide")

# 1. 初始化資料庫
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

# 圖片壓縮與儲存函式
def save_and_resize_image(img, suffix=""):
    try:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        img.thumbnail((1000, 1000))
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = os.path.join("uploads", f"{timestamp}_{suffix}.jpg")
        
        img.save(image_path, "JPEG", quality=85)
        return image_path
    except Exception as e:
        st.error(f"圖片處理失敗：{e}")
        return None

st.title("👗 Clara 的質感服裝搭配資料庫")
st.markdown("打造專屬你的美學衣櫃，以智慧風格邏輯為妳推薦質感穿搭！")

# 建立分頁介面（首頁為 AI 智慧穿搭推薦）
tab1, tab2, tab3 = st.tabs(["🎨 AI 智慧穿搭靈感", "✨ 新增衣物", "📂 質感衣櫃總覽"])

# --- 標籤頁一：AI 智慧穿搭靈感（主頁） ---
with tab1:
    st.subheader("✨ AI 質感風格智慧推薦")
    st.markdown("為妳嚴格把關風格一致性，提供具備美感的穿搭組合：")
    
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    c.execute("SELECT id, style, season, image_path FROM clothing WHERE category = '上身 (Tops)'")
    tops = c.fetchall()
    c.execute("SELECT id, style, season, image_path FROM clothing WHERE category = '下身 (Bottoms)'")
    bottoms = c.fetchall()
    conn.close()

    if tops and bottoms:
        available_styles = list(set([item[1] for item in tops] + [item[1] for item in bottoms]))
        selected_style = st.selectbox("🎯 選擇今日想要演繹的質感風格", available_styles)
        
        filtered_tops = [t for t in tops if t[1] == selected_style]
        filtered_bottoms = [b for b in bottoms if b[1] == selected_style]
        
        if filtered_tops and filtered_bottoms:
            ai_top = random.choice(filtered_tops)
            ai_bottom = random.choice(filtered_bottoms)

            col_top, col_bottom = st.columns(2)
            with col_top:
                st.markdown(f"### 上身 (Top)")
                if os.path.exists(ai_top[3]):
                    st.image(ai_top[3], use_container_width=True)
                    st.markdown(f"**風格:** {ai_top[1]} | **季節:** {ai_top[2]}")
            with col_bottom:
                st.markdown(f"### 下身 (Bottom)")
                if os.path.exists(ai_bottom[3]):
                    st.image(ai_bottom[3], use_container_width=True)
                    st.markdown(f"**風格:** {ai_bottom[1]} | **季節:** {ai_bottom[2]}")
            
            if st.button("🔄 重新尋找此風格的靈感組合", type="primary"):
                st.rerun()
        else:
            st.info(f"目前【{selected_style}】風格中，尚未同時擁有上身與下身單品，建議上傳更多單品來豐富此風格！")
    else:
        st.warning("請確保衣櫃內**同時擁有至少一件上身與一件下身**，才能啟動 AI 智慧風格推薦喔！快到第二頁新增衣物吧！")

# --- 標籤頁二：新增衣物（按鈕互動式） ---
with tab2:
    st.subheader("上傳或拍攝新衣物")
    
    if 'add_mode' not in st.session_state:
        st.session_state.add_mode = 'single'

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("👕 新增單件衣物", use_container_width=True):
            st.session_state.add_mode = 'single'
    with col_btn2:
        if st.button("📸 上傳整套穿搭（自動切分）", use_container_width=True):
            st.session_state.add_mode = 'set'

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        style = st.selectbox("風格標籤", ["休閒 (Casual)", "正式 (Formal)", "法式簡約 (Minimalist)", "甜美復古 (Vintage)"])
    with col_b:
        season = st.selectbox("適用季節", ["春季 (Spring)", "夏季 (Summer)", "秋季 (Autumn)", "冬季 (Winter)", "四季通穿 (All-Season)"])

    if st.session_state.add_mode == 'single':
        st.markdown("### 【單件衣物上傳模式】")
        category = st.selectbox("服裝分類", ["上身 (Tops)", "下身 (Bottoms)"])
        upload_option = st.radio("圖片來源", ["上傳本地照片", "現場拍照"])
        image_file = st.file_uploader("選擇圖片檔案", type=["jpg", "jpeg", "png"]) if upload_option == "上傳本地照片" else st.camera_input("使用相機拍攝")

        if image_file is not None:
            if st.button("確認儲存單件衣物", type="primary"):
                img = Image.open(image_file)
                image_path = save_and_resize_image(img, suffix="single")
                
                if image_path:
                    conn = sqlite3.connect('wardrobe.db')
                    c = conn.cursor()
                    c.execute("INSERT INTO clothing (category, style, season, image_path, created_at) VALUES (?, ?, ?, ?, ?)",
                              (category, style, season, image_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()
                    st.success("✨ 成功將單件衣物加入你的質感資料庫！")

    else:
        st.markdown("### 【整套穿搭照自動切分模式】")
        st.info("💡 請上傳一張整套照片（上半身在上方、下半身在下方），系統會自動幫您切分為上身與下身並同時存入衣櫃！")
        outfit_file = st.file_uploader("選擇整套穿搭照片", type=["jpg", "jpeg", "png"])
        
        if outfit_file is not None:
            img = Image.open(outfit_file)
            width, height = img.size
            
            st.markdown("### 截圖預覽")
            col_prev1, col_prev2 = st.columns(2)
            
            top_img = img.crop((0, 0, width, height // 2))
            bottom_img = img.crop((0, height // 2, width, height))
            
            with col_prev1:
                st.image(top_img, caption="自動切分之【上身】預覽", use_container_width=True)
            with col_prev2:
                st.image(bottom_img, caption="自動切分之【下身】預覽", use_container_width=True)
            
            if st.button("確認切分並同時存入衣櫃", type="primary"):
                top_path = save_and_resize_image(top_img, suffix="top")
                bottom_path = save_and_resize_image(bottom_img, suffix="bottom")
                
                if top_path and bottom_path:
                    conn = sqlite3.connect('wardrobe.db')
                    c = conn.cursor()
                    c.execute("INSERT INTO clothing (category, style, season, image_path, created_at) VALUES (?, ?, ?, ?, ?)",
                              ("上身 (Tops)", style, season, top_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    c.execute("INSERT INTO clothing (category, style, season, image_path, created_at) VALUES (?, ?, ?, ?, ?)",
                              ("下身 (Bottoms)", style, season, bottom_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()
                    st.success("✨ 成功將整套穿搭自動切分為上身與下身，並存入衣櫃！")

# --- 標籤頁三：衣櫃總覽 ---
with tab3:
    st.subheader("我的衣櫃收藏")
    
    conn = sqlite3.connect('wardrobe.db')
    c = conn.cursor()
    c.execute("SELECT id, category, style, season, image_path FROM clothing")
    items = c.fetchall()
    conn.close()

    if items:
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
        st.info("目前衣櫃還空空如也，快到第二頁新增衣服吧！")
