# SFC リーディングカンパニー 解析

KOEI，SFC（LoROM 1 MB）。家用錄影機（VTR）產業的經營模擬：玩家當一家廠商的社長，在 4 個規格協議會（JVD／BE／NVX／VCD）之間競爭；2 劇本（1970-1990、1980-2000）、12 家廠商、產品分 8 個等級、9 種機能、12 種販促。程式是 C 編譯的原生 65816 程式（和エアーマネージメントII 同引擎），資源放在 254 個具名檔裡。沒有具名人物，頭像只有会長、社長、秘書、各部部長。沒有戰鬥，所以沒有戰術地圖。ROM 結構見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python leading/export.py [--rom ROM] [--out DIR]     # → leading/output/（CSV、XLSX、PNG）
.venv/bin/python leading/export_kaodata.py --out <kaodata>/data-local/leading-sfc
.venv/bin/python leading/verify_kaodata_export.py --dataset <kaodata>/data-local/leading-sfc
.venv/bin/python leading/verify_scenarios.py                 # 約 20 秒
.venv/bin/python leading/verify_products.py                  # 約 240 秒
.venv/bin/python leading/verify_faces.py                     # 約 45 秒
.venv/bin/python leading/verify_maps.py                      # 約 30 秒
```

- ROM 預設直接讀 `_original/sfc/Leading Company (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。頭像總覽的標註用 macOS 的ヒラギノ角ゴシック。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用共用的 `tools/replay.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：檔案表、bank `$0C` 名稱表（協議會、廠商、等級、機能、販促）、bank `$02` 劇本表（協議會、廠商、產品、機能、市場格）、頭像、街區地圖與建物 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 資料集 `leading-sfc`（44 張 portrait，沒有 character） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；group；沒有 name／label／code；checksums |
| `verify_scenarios.py` | 2 劇本開局 WRAM 與 ROM 表逐 byte 比對 |
| `verify_products.py` | 產品畫面：改產品記錄的等級、廠商、契約、認知度、新鮮度、稼働率，比對遊戲印出的字 |
| `verify_faces.py` | 44 張頭像經遊戲的繪製程式 `$01:A58F` 寫進 VRAM／CGRAM 的內容 |
| `verify_maps.py` | 主畫面街區的 BG2 tilemap／tile／調色盤、BG1 的 4 個建物格 |
| `tools/lc.py` | 驗證共用：按鍵序列、收集遊戲 printf 的 Lua（搭配 `tools/replay.py`） |

## 輸出（`leading/output/`）

| 檔案 | 內容 |
|------|------|
| `formats.csv` | 2 劇本 × 4 協議會：名稱、是否存在、開局前四季市場規模（百萬円） |
| `makers.csv` | 2 劇本 × 12 廠商：名稱、所屬協議會、是否 leader、對 4 協議會的信用度、產品、未解的 w14／w16 |
| `products.csv` | 2 劇本的開局產品（21 筆）：協議會、槽、名稱、狀態、等級、市場格、製造廠商、契約、比例、新鮮度、稼働率、認知度、未解欄位原始 bytes |
| `market_cells.csv` | 開局市場格（等級 × 欄）上的產品 |
| `features.csv` | 9 種機能：bit、名稱、未解值、2 劇本的狀態 bytes |
| `grades.csv` | 8 個等級與定價 |
| `promotions.csv` | 12 種販促 |
| `files.csv` | 254 個檔：位置、大小、LZ 解壓後大小 |
| `leading.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`faces.png` | 44 張頭像與總覽 |
| `town_map.png` | 主畫面街區（劇本 1 開局的 4 個建物） |
| `buildings.png` | 營業所／工場／研究所 5 級 × 5 變體 |

## 進度

- ✓ 檔案表 254 檔、KOEI LZ（共用）
- ✓ 名稱表：協議會 4、廠商 12、等級 8（含定價）、機能 9、販促 12、難度、劇本年份
- ✓ 劇本 2：協議會、廠商、產品、機能、`$5401`／`$5541`／`$6E05`、8 × 8 市場格——開局 WRAM 完全一致
- ✓ 產品記錄：狀態、名稱、等級、製造廠商、契約、新鮮度、稼働率、認知度
- ✓ 頭像：7 種 44 張、調色盤 `KAO`；kaodata 資料集 `leading-sfc`
- ✓ 主畫面街區地圖與 15 個建物檔
- － 人物資料：本作沒有具名人物（頭像只是職位），不適用
- － 戰術地圖：本作沒有戰鬥，不適用
- … 未解：`$5401`／`$5541`／`$6E05` 的意義、廠商 w14／w16、產品多數欄位與定價、機能的 4 個值、販促費用、建物選擇規則、頭像動畫條、事件與結局（ROM_FORMAT.md §9）

## 驗證

所有驗證都在 Mesen 2 跑遊戲本身的程式（從開機按鍵進到對應畫面，savestate 後每輪改 WRAM、ROM 或攔截函式引數），比對遊戲印出的文字、WRAM、VRAM、CGRAM。

| 腳本 | 內容 | 結果（時間） |
|------|------|------|
| `verify_scenarios.py` | 劇本選單 savestate，選劇本 1／2 + YES，建好開局後讀 WRAM `$4600–$76FF`，和 `rom.scenario_wram`（機能、產品、協議會、廠商含產品指標、`$5401`、`$5541`、`$6E05`、市場格）及劇本號 `$46DE` 比對 | 劇本 1 58/58 區塊（10381 bytes）、劇本 2 59/59（10395 bytes），`$46DE` = 0／1（19 秒） |
| `verify_products.py` | 主畫面 savestate，改 JVD 第 0 槽產品（`hit 1bas`）的欄位後開產品畫面，收集遊戲 printf | 開局值（廠商 hitashi、license、basic1、認知度 57）= ROM 記錄 OK；等級 +0x0E → 等級名 8/8、廠商 +0x10 → 廠商名 12/12、契約 +0x11 → `original`／`license`／`oem` 3/3、認知度 +0x27／新鮮度 +0x21／稼働率 +0x25 → 印出的數值 3/3（239 秒） |
| `verify_faces.py` | 会長講話前的 savestate，攔截 `$01:A58F` 換成每個（種類, 圖號）（引數經 ROM patch 傳入），比對 VRAM 0xBC00 960 bytes 與 CGRAM 0x1E0 | 圖 44/44、調色盤 44/44（42 秒） |
| `verify_maps.py` | 主畫面：BG2 tilemap（VRAM 0xF000）、tile（0x6000）、CGRAM 調色盤 2 = `OFFCBACK`，調色盤 3 = `EQUIP`；BG1 4 格的 tilemap 配置；每格 36 tiles = 某個建物變體 | 4 項 OK、建物格 4/4（29 秒） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對；group；沒有 name、label、code；checksums | 44/44、44/44、44/44、checksums OK（1 秒內）；kaodata repo 的 `scripts/verify.ts` 也通過（ok 44） |
