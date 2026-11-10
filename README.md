# 👗 Clara 的質感衣櫃 v2

Streamlit 服裝搭配系統：管理衣物、依「季節 → 風格 → 配色 → 新鮮度 → 最愛」**計分排序**推薦穿搭（非隨機，同樣條件永遠得到同樣的排序），並附上推薦理由。

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `app.py` | 主程式（介面） |
| `matcher.py` | 智慧搭配引擎（計分規則、色票、分類設定都在這裡，可自行調整） |
| `storage.py` | 資料儲存層（Supabase 雲端 / SQLite 本機，自動切換）＋備份還原 |
| `supabase_schema.sql` | 啟用 Supabase 時要執行的建表語法 |
| `.streamlit/config.toml` | 主題配色、上傳大小上限 |
| `requirements.txt` | 套件清單 |
| `.gitignore` | 避免把資料庫、密鑰推上 GitHub |
| `舊版備份_v1/` | 優化前的 app.py、requirements.txt、wardrobe.db（不需上傳） |

## 更新到 GitHub / Streamlit Cloud

1. 把以上檔案（含 `.streamlit` 資料夾）上傳到原本的 GitHub repo，覆蓋舊的 `app.py`、`requirements.txt`。
2. **不要上傳 `wardrobe.db`、`uploads/`、`舊版備份_v1/`**；若 repo 裡已經有 `wardrobe.db`，建議刪除。
3. Streamlit Cloud 偵測到 commit 後會自動重新部署（約 1–2 分鐘）。
4. 舊版資料庫欄位會自動升級，舊資料不會遺失。

## ⚠️ 為什麼建議接 Supabase

Streamlit Cloud 的硬碟是**暫存的**：App 休眠、重開或每次重新部署時，`wardrobe.db` 與上傳的照片都會被清空。

- **沒接 Supabase 時**：系統照常運作，但請定期到「⚙️ 統計與備份」下載 .zip 備份，資料不見時再上傳還原。
- **接上 Supabase（免費）**：資料與照片永久保存，手機電腦同步。

### Supabase 設定步驟（約 10 分鐘）

1. 到 <https://supabase.com> 註冊並建立新專案（Region 選 Northeast Asia (Tokyo) 或 Singapore 較快）。
2. 左側 **SQL Editor** → 貼上 `supabase_schema.sql` 全部內容 → Run。
3. 左側 **Project Settings → API**（或 API Keys）複製：
   - Project URL
   - **service_role / secret key**（只會放在 Streamlit 伺服器端的 Secrets，不會暴露給瀏覽器）
4. Streamlit Cloud → 你的 App → **⋮ → Settings → Secrets**，貼上：

```toml
SUPABASE_URL = "https://xxxxxxxx.supabase.co"
SUPABASE_KEY = "你的 service_role 或 secret key"

# 選填：替網站加上密碼（網址是公開的，強烈建議設定）
APP_PASSWORD = "自訂密碼"
```

5. 儲存後 App 會自動重啟，頁首顯示「儲存：Supabase 雲端（永久保存）」即成功。
6. 若之前在本機模式已有資料：切換前先下載備份 → 接上 Supabase 後到「⚙️ 統計與備份」上傳還原。

## 本機執行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 搭配計分規則（matcher.py）

| 項目 | 規則 |
|---|---|
| 季節 | 不符合所選季節的單品直接排除（預設依台北日期自動判斷當季） |
| 風格 | 每件符合所選風格 +3；上下身有共同風格 +2；風格完全不同 −1 |
| 配色 | 中性色＋亮色 +3、中性色互搭 +2.5、同色系 +1.5、同色溫 +1、冷暖亮色硬撞 −1.5、花紋配花紋 −3 |
| 新鮮度 | 越久沒穿加分越多（最多 +1.5） |
| 最愛 | 每件最愛單品 +0.5 |
| 重複 | 兩週內穿過的同一套 −6 |
| 外套/鞋子 | 依配色與風格自動挑最合適的一件 |
