# SFC 項劉記 解析

KOEI，SFC（HiROM 1.5 MB）。楚漢相爭，4 個劇本（前 206–203 年），92 人、39 個地點。文字不是 Shift-JIS，用遊戲自己的 16 × 16 字型。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python kouryuuki/export.py [--rom ROM] [--out DIR]          # → kouryuuki/output/（CSV、XLSX、PNG）
.venv/bin/python kouryuuki/export_kaodata.py --out <kaodata>/data-local/kouryuuki-sfc
.venv/bin/python kouryuuki/verify_kaodata_export.py --dataset <kaodata>/data-local/kouryuuki-sfc
.venv/bin/python kouryuuki/verify_faces.py                        # 約 1.5 分鐘
.venv/bin/python kouryuuki/verify_scenarios.py                    # 約 2 分鐘
.venv/bin/python kouryuuki/tools/charset_sheet.py                 # 字型對照圖 → output/charset_sheet.png
```

- ROM 預設直接讀 `roms/Kouryuuki (Japan).zip`，`--rom` 也接受 .sfc。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py` 用 ctypes 呼叫 MesenCore）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：解壓縮、字型與文字、人物、地點、劇本狀態（人物、地點、軍隊）、頭像 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `kouryuuki-sfc` |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_faces.py` | 97 張頭像逐一換進君主簡介畫面，比對遊戲載入的 VRAM tile 與調色盤 |
| `verify_scenarios.py` | 4 劇本開局 WRAM `$2000–$472C` 與 ROM 組出的劇本狀態比對 |
| `tools/charset_sheet.py` | ROM 字形與 `charset.txt` 的字並排的檢查圖 |
| `data/charset.txt` | 字號 → 字（1288 字，字型與系統字型比對後人工修正） |

## 輸出（`kouryuuki/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 92 人：姓名、讀音、生年（紀元前）、頭像、未解欄位 |
| `person_scenarios.csv` | 4 劇本 × 92 人：勢力、君主、旗標、年齢、体力、上限、戦闘、統率、用兵、経験、外交、所屬軍與其将 |
| `places.csv` | 4 劇本 × 39 地點：讀音、地圖格座標、勢力、金、食料、人口、支持、疲弊、防御、農地 |
| `armies.csv` | 4 劇本的軍：勢力、将、所在、資金、兵糧、兵士、士気、武装、隨行武将 |
| `kouryuuki.xlsx` | 以上四張表（需 openpyxl） |
| `faces/`、`portraits/` | 每人頭像（`00_項羽.png`）、全部頭像 F00–F96 |
| `map_places.png` | 55 × 44 地圖格：道路、有地物的格、39 個地點 |
| `charset_sheet.png` | 字型對照圖（`tools/charset_sheet.py`） |

## 進度

- ✓ 壓縮（和天翔記同一套演算法）、字型（1288 字）與文字編碼、字號對照表
- ✓ 人物 92 人：姓名、讀音、生年；項羽、劉邦的簡介
- ✓ 4 劇本：標題、劇本狀態的 ROM 來源（WRAM 完全一致）
- ✓ 劇本人物：勢力、君主、体力、戦闘、統率、用兵、経験、外交、所屬軍
- ✓ 39 地點：名稱、讀音、地圖格；每劇本的金、食料、人口、勢力、各勢力支持、疲弊、防御、農地
- ✓ 軍隊：将、勢力、所在、資金、兵糧、兵士、士気、武装
- ✓ 頭像 97 張（單一調色盤）；kaodata 資料集 `kouryuuki-sfc`
- … 未解：大地圖渲染（每格 4 × 4 tile）、戰術地圖、勢力友好度、多個欄位、頭像 F92–F96 的主人（ROM_FORMAT.md §9）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_faces.py` | 開啟項羽的君主簡介，在 `$C9:4341` 把頭像號換成 0–96，比對 VRAM `0x400` 的 960 bytes 與 CGRAM 調色盤 8；未改動時的頭像號 = 項羽的人物編號 0 | 97/97、OK |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對、checksums | 92/92、97/97、OK |
| `verify_scenarios.py` | 4 劇本選完君主後的 WRAM `$2000–$472C` 與 `Rom.scenario_image` 逐 byte 比對 | 4 劇本皆 0 byte 不同（人物 92/92、地點 39/39、軍 99/99） |
| `tools/charset_sheet.py` | ROM 字形和對照字並排，目視核對 | 6 字不確定 |

欄位意義另外對照遊戲畫面：田仮的武将畫面、外交 7 人、薊・代・晋陽・平原・臨淄的地點畫面、第 1 軍（1500／1800／1700／100／80）。地點的地圖格用 `map_places.png` 目視核對。
