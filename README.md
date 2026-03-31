# Akashic

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-6.11-green?logo=qt&logoColor=white)
![xAI](https://img.shields.io/badge/AI-Grok%20%28xAI%29-black?logo=x&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

以 AI 驅動的互動文字冒險引擎，能即時生成動態奇幻世界。描述你想要的世界，AI 便會為你建構——包含 NPC、任務、道具，以及一個隨你的選擇不斷演化的故事。

---

## 功能特色

- **AI 生成世界** — 描述一個設定，AI 即自動建立完整世界：世界觀、地圖、NPC、任務與道具
- **動態敘事** — 每次行動皆產生 3–5 段故事內容，以及 4 個新的行動選項
- **活躍的世界狀態** — NPC、任務、道具與地圖隨遊玩過程持續更新
- **自動儲存** — 每回合後自動將世界狀態寫入磁碟，隨時可繼續遊玩
- **故事封存** — 遊戲過程同步寫入可閱讀的 `novel.md` 故事文稿
- **自動壓縮** — 故事摘要過長時於背景執行壓縮，維持上下文精簡
- **流暢介面** — 深色／淺色主題、可調字體大小，以及道具、任務、裝備等獨立頁面

---

## 系統需求

- Python 3.10+
- [xAI API 金鑰](https://console.x.ai/)（Grok 模型）

---

## 安裝方式

```bash
# 複製專案
git clone <repo-url>
cd akashic

# 建立虛擬環境
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 安裝相依套件
pip install -r requirements.txt
```

---

## 啟動方式

```bash
python main.py
```

首次啟動後，前往**設定**頁面輸入你的 xAI API 金鑰，再切換至**聊天**頁面開始建立世界。

---

## 設定

設定儲存於 `config/settings.json`，可於應用程式內調整，或直接編輯檔案：

```json
{
  "ui": {
    "theme_mode": "Auto",
    "font_size": 16,
    "window_opacity": 100
  },
  "ai": {
    "base_url": "api.x.ai",
    "model": "grok-4-1-fast-non-reasoning",
    "reasoning_model": "grok-4-1-fast-reasoning"
  }
}
```

如需調整 AI 行為，可編輯 `core/` 資料夾中的提示詞檔案：

| 檔案 | 用途 |
|---|---|
| `core/system.md` | 敘事規則、狀態變更協定 |
| `core/init.md` | 世界生成指示 |
| `core/compression.md` | 摘要壓縮策略 |
| `core/template/greetings.md` | 開場提示詞 |

---

## 專案結構

```
akashic/
├── main.py               # 程式進入點
├── app_config.py         # 設定單例
├── app_logger.py         # 日誌（Loguru）
├── responses.py          # xAI API 客戶端
├── game/
│   ├── controller.py     # 遊戲主控制器
│   ├── context.py        # 執行期上下文建構
│   ├── world_io.py       # 世界檔案讀寫
│   ├── parsing.py        # API 回應解析
│   ├── changes.py        # 世界狀態變更
│   └── validation.py     # 資料驗證
├── ui/
│   ├── main_window.py    # 主視窗與導覽
│   ├── chat_page.py      # 聊天介面
│   ├── item_page.py      # 道具欄
│   ├── equipment_page.py # 裝備頁面
│   ├── quest_page.py     # 任務頁面
│   ├── library_page.py   # 封存世界瀏覽
│   └── settings_page.py  # 設定頁面
└── core/                 # 系統提示詞
```

---

## 技術架構

| | |
|---|---|
| 圖形介面 | PySide6 + PySide6-Fluent-Widgets |
| AI | xAI SDK（Grok） |
| 日誌 | Loguru |
| 資料儲存 | JSON 檔案（無資料庫） |
