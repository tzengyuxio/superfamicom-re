# SFC 三國志III 解析

KOEI，SFC（HiROM 1.5 MB，1992）。6 個劇本（189–235 年），532 人、46 州。文字不是 Shift-JIS，用遊戲自己的 16 × 16 字型。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python san3/export.py [--rom ROM] [--out DIR]          # → san3/output/（CSV、XLSX、PNG）
.venv/bin/python san3/export_kaodata.py --out <kaodata>/data-local/san3-sfc
.venv/bin/python san3/verify_kaodata_export.py --dataset <kaodata>/data-local/san3-sfc
.venv/bin/python san3/verify_faces.py                        # 約 3 分鐘
.venv/bin/python san3/verify_scenarios.py                    # 約 15 秒
.venv/bin/python san3/verify_map.py                          # 約 15 秒
.venv/bin/python san3/verify_tactical.py                     # 約 15 秒
.venv/bin/python san3/tools/charset_sheet.py                 # 字型對照圖 → output/charset_sheet.png
```

- ROM 預設直接讀 `roms/Sangokushi III (Japan).zip`，`--rom` 也接受 .sfc。只支援原版；Rev 1 的 bank `$C1` 資料與壓縮指標表位置不同（ROM_FORMAT.md §1）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py` 用 ctypes 呼叫 MesenCore）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：壓縮（`tools/koei_lz.py`）、字型與文字、人物、州、寶物、6 劇本（人物、州、勢力、寶物持有者）、頭像（一般＋合成）、大地圖、戰場資料 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `san3-sfc`（一般頭像＋合成頭像） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_faces.py` | 307 張一般頭像＋311 個合成頭像碼逐一換進劉備的武将畫面，比對遊戲寫進 VRAM 的 tile 與調色盤 |
| `verify_scenarios.py` | 6 劇本載入後的 WRAM 與 ROM 各表逐欄比對 |
| `verify_map.py` | 劇本 1 第一回合的大地圖：BG tilemap、tile、調色盤 |
| `verify_tactical.py` | 開局 AI 戰鬥（董卓攻鄴）時遊戲載入的戰場資料 |
| `tools/charset_sheet.py` | ROM 字形與 `charset.txt` 的字並排的檢查圖 |
| `data/charset.txt` | 字號 → 字（1855 字，字型與系統字型比對後人工修正） |

## 輸出（`san3/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 532 人：姓名、讀音、生年、頭像（`P###` 一般／`C####` 合成碼）、陸指、水指、武力、智力、政治、魅力、野心、運、冷静、勇猛、相性、義理、血縁、未解欄位 |
| `person_scenarios.csv` | 6 劇本 × 531 人：登場、年齢（虛歲）、身分、勢力、所在、忠誠、兵士、訓練、士気、寶物 |
| `provinces.csv` | 46 州：讀音、大地圖格座標、未解欄位 |
| `province_scenarios.csv` | 6 劇本 × 46 州：勢力、人口、金、米、開発、治水、商業、税率、民忠、訓練、士気、未解欄位 |
| `factions.csv` | 6 劇本的勢力：君主、首都、州、旗色、未解欄位 |
| `items.csv` | 13 件寶物：種類、能力加算（推測）、6 劇本的持有者 |
| `scenarios.csv` | 6 劇本：標題、年、勢力數、君主、劇本 header 原始 bytes |
| `san3.xlsx` | 以上七張表（需 openpyxl） |
| `faces/`、`portraits/` | 每人頭像（`481_劉備.png`）、一般頭像 P001–P307 |
| `composite_parts.png` | 合成頭像的 13 型 × 5 部位全部變體（灰 = 該部位不畫） |
| `map.png`、`map_scenario1-6.png`、`map_provinces.png` | 大地圖（240 × 224）：無標記、各劇本開局的勢力旗色、州名標註版 |
| `tactical/` | 46 州的戰場資料：三層格子的 CSV、B 層示意圖（未渲染成遊戲畫面） |
| `charset_sheet.png` | 字型對照圖（`tools/charset_sheet.py`） |

## 進度

- ✓ 壓縮（`tools/koei_lz.py`，491 個 entry）、字型（1855 字）與文字編碼（含 `0x91xx` 跳脫碼）、字號對照表
- ✓ 人物 532 人：姓名、讀音、生年、頭像、能力（陸指・水指・武力・智力・政治・魅力）、野心・運・冷静・勇猛、相性、義理、血縁
- ✓ 6 劇本：標題、年、劇本 header；劇本人物（身分、忠誠、所在、兵士、寶物、訓練・士気）、州（人口、金、米、開発、治水、商業、税率、民忠）、勢力（君主、首都與州鏈、旗色）、寶物持有者，全部和遊戲載入的 WRAM 一致
- ✓ 頭像：一般 307 張＋合成頭像（13 型 × 5 部位），單一調色盤；kaodata 資料集 `san3-sfc`（532 人：221 一般、311 合成）
- ✓ 大地圖：30 × 28 tile 的 tilemap、圖、調色盤（含水面色循環）、46 州的旗標格與勢力旗色
- △ 戰術地圖：46 州的戰場資料（entry 47–92，三層 22 格寬）已定位並驗證載入；畫成遊戲畫面（等角 tile 組合）未解
- … 未解：見 ROM_FORMAT.md §10（人物 +3／+4、州的多個欄位、勢力 +3 與 21 bytes、身分 6／7 的意義、寶物欄位、劇本 header 尾段、entry 93–114、戰場渲染）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_faces.py` | 劇本 1 劉備的武将畫面，在 `$C1:65D7` 把頭像碼換成 1–307 與 311 個合成碼，比對 VRAM `0x7C0` 的 960 bytes 與 CGRAM 調色盤 4；未改動時的頭像碼 = 劉備的 `0x00A1` | 一般 307/307、合成 311/311、OK（185 秒） |
| `verify_scenarios.py` | 6 劇本在載入器 `$C7:4FBD`（所有表複製完）時的 WRAM，逐欄比對 header、寶物持有者、州、勢力、人物 | 6 劇本皆：header 1/1、寶物 13/13、extra 22/22、州 46/46、勢力 21/21、人物 531/531（11 秒） |
| `verify_map.py` | 劇本 1 第一回合指令畫面：BG2 tilemap、VRAM tile、CGRAM 調色盤 2／3 | tilemap 840/840（旗標 46/46）、地圖 tile 751/751、旗標 tile 26/26、調色盤 OK（15 秒） |
| `verify_tactical.py` | 開局 AI 戰鬥（董卓攻 7.鄴）：戰場程式 `$C3:56BE` 第一次讀格子時 WRAM `$7E:C104` 的 1342 bytes | = entry 53（鄴，州 index 6），且只和這一個 entry 相同（16 秒） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對、checksums | 人物 532/532（311 合成）、頭像 307/307、OK（1 秒） |
| `tools/charset_sheet.py` | ROM 字形和對照字並排，目視核對 | 5 處不確定（字號 9、17–18、1697、1699、1741） |

欄位意義另外對照遊戲畫面：公孫瓚與關羽的武将畫面（能力、青竜偃月刀 武力 +5 顯示為 103）、劉備（年齢 29 = 虛歲）、北平的都市畫面（人 70000、金 1500、米 25000、開 20、治 10、商 250、民 60、税 40）、身分（劉備 君主、関羽 軍師、張飛 将軍、厳綱／公孫越 武官）。

外部資料：字型對照的字號 1807–1854（追加的人名用字）參考了 PC 版三國志III 的人名（`~/works/kaodata-re/PERSONS_TABLE/san3_persons_s*.csv`），以 8 項能力配對 530 人；SFC 字形與 PC 人名不一致的地方以 SFC 字形為準。
