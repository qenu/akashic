# 阿卡西 Akashic 

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-6.11-green?logo=qt&logoColor=white)
![xAI](https://img.shields.io/badge/AI-Grok%20%28xAI%29-black?logo=x&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

以 AI 驅動的互動文字冒險引擎，能即時生成動態奇幻世界。描述你想要的世界，AI 便會為你建構——包含 NPC、任務、道具，以及一個隨你的選擇不斷演化的故事。

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
