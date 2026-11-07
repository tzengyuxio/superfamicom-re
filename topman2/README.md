# SFC トップマネジメントII 解析

KOEI，SFC（LoROM 1.5 MB）。電腦公司經營模擬：3 家公司（ＮＥ／ＦＴ／ＳＳパソコン）、47 都道府縣、3 種產品（DESKTOP／LAPTOP／NOTE）、6 個 PRESENT 劇本＋FREE MODE 3 種長度、5 個難度。程式是 C 編譯的原生 65816，資源放在 249 個具名檔。沒有具名人物，頭像是会長、社長、秘書、8 個部門的部長；沒有戰鬥（無戰術地圖）。ROM 結構見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python topman2/export.py [--rom ROM] [--out DIR]     # → topman2/output/（CSV、XLSX、PNG）
.venv/bin/python topman2/export_kaodata.py --out <kaodata>/data-local/topman2-sfc
.venv/bin/python topman2/verify_kaodata_export.py --dataset <kaodata>/data-local/topman2-sfc
.venv/bin/python topman2/verify_scenarios.py                 # 約 230 秒
.venv/bin/python topman2/verify_companies.py                 # 約 45 秒
.venv/bin/python topman2/verify_faces.py                     # 約 46 秒
.venv/bin/python topman2/verify_maps.py                      # 約 35 秒
```

- ROM 預設直接讀 `_original/sfc/Top Management II (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。圖上的標註用 macOS 的ヒラギノ角ゴシック。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用共用的 `tools/replay.py`；一個 process 只開一次 Mesen，多段的腳本用子程序（`--part`）。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：檔案表、bank `$01` 的表（縣名、人口、本社候補、座標、JAPANS 填色段、產品、劇本名、難度、產業、新聞）、劇本年份與說明（bank `$06` 立即值）、預設公司名、頭像、JAPANL／JAPANS |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 資料集 `topman2-sfc`（96 張 portrait，沒有 character） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；調色盤；group／name；沒有 label 與 code；checksums |
| `verify_scenarios.py` | PRESENT 6 劇本與 FREE 7 種設定：畫面上的名稱與說明、WRAM 劇本號／年份／人口表 |
| `verify_companies.py` | 本社候補 15 × 2 全部組合、據點遮罩、預設公司名；47 縣名 |
| `verify_faces.py` | 11 個頭像檔 96 frame 的 VRAM tile、tilemap、FACEPAL |
| `verify_maps.py` | JAPANL 的 tile、調色盤、tilemap |
| `tools/tm2.py` | 驗證共用：按鍵序列、收集文字繪製／頭像繪製呼叫的 Lua（搭配 `tools/replay.py`） |

## 輸出（`topman2/output/`）

| 檔案 | 內容 |
|------|------|
| `prefectures.csv` | 47 縣：名稱、5 個時期的人口（萬人）、JAPANL 畫面位置（`$CBAD`）、`$CC69`（未解）、JAPANS 填色段數與方向 |
| `hq_pairs.csv` | PRESENT MODE 本社候補 15 對（r1、r2 → 本社與據點） |
| `scenarios.csv` | 9 個劇本：模式、名稱、開始／結束年、說明 |
| `companies.csv` | 3 家公司的預設名稱 |
| `products.csv` | 3 種產品的略稱、英文名、日文名 |
| `levels.csv`、`industries.csv`、`news.csv` | 5 難度、股票的 4 產業、26 則新聞標題 |
| `faces.csv` | 96 個頭像 frame：檔、frame、group、角色、人、表情 |
| `files.csv` | 249 個檔：位置、大小、LZ 解壓後大小 |
| `topman2.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`faces.png` | 96 張頭像（32 × 48）與總覽 |
| `japan_large.png`、`japan_large_prefectures.png` | JAPANL 地形圖 224 × 192；放在畫面位置並標上 `$CBAD` 的 47 縣位置 |
| `japan_small.png`、`prefecture_map.png` | JAPANS 示意圖 144 × 176；用 `$CD25` 填色段替 47 縣上色並標番號 |

## 進度

- ✓ 檔案表 249 檔、KOEI LZ（共用）
- ✓ 都道府縣 47：名稱、5 時期人口（開局依開始年選一筆）、JAPANS 填色段、JAPANL 畫面位置
- ✓ 劇本：PRESENT 6（年份、說明）、FREE 3 種長度（開始年規則）
- ✓ 公司 3：預設名、本社候補 15 對與開局抽選規則、據點遮罩
- ✓ 產品 3、難度 5、股票產業 4、新聞 26（只有名稱）
- ✓ 頭像：11 檔 96 frame、FACEPAL；kaodata 資料集 `topman2-sfc`
- ✓ 大地圖 JAPANL；JAPANS 只從檔案解出（遊戲中的畫面沒找到，未驗證）
- － 戰術地圖：本作沒有戰鬥，不適用
- … 未解：開機複製的 .data 表、`$CBA1`、`$CC69` 的用途、產品能力值與市場模擬、景氣曲線數列、事件、SHABU／BAIBU 的部門、多數檔的用途（ROM_FORMAT.md §9）

## 驗證

所有驗證都在 Mesen 2 跑遊戲本身的程式（從開機按鍵進到對應畫面，savestate 後每輪改 WRAM 或攔截函式引數），比對遊戲畫的文字、WRAM、VRAM、CGRAM。

| 腳本 | 內容 | 結果（時間） |
|------|------|------|
| `verify_scenarios.py` | PRESENT：每輪選一個劇本走完設定頁；文字繪製 `$01:9392` 畫出的名稱與說明、確認頁的 BEGINNER，WRAM `$280C`／`$2810`／`$2812`（開局後是開始年 − 1）、`$4417` 人口 = `rom.population(開始年)`。FREE：短／中／長＋短劇本開始年 +1..+4（跨過 1980 的人口分界） | PRESENT 6/6、FREE 7/7（228 秒） |
| `verify_companies.py` | A：攔 `$06:8B61` 把亂數 r1、r2 換成 15 × 2 全部組合，檢查本社 `$2822` = `$C661[r1][r2]`、據點遮罩 = 兩縣、預設名；B：在公司頁畫出前改本社與據點為每一縣，檢查畫出「本社~縣名」「支社~縣名」與 3 個公司名 | 本社 30/30、據點 30/30、名稱 30/30；縣名 47/47、公司名 47/47（45 秒） |
| `verify_faces.py` | NEW GAME 後攔 `$01:B0D8`，把檔名、frame、slot 換成每個 frame，比對 VRAM 24 tile、BG tilemap 4 × 6、CGRAM 第 2 列 = FACEPAL；遊戲自己的第一個呼叫 = HISHO frame 1 | 96/96（KAICHO 12、SHACHO 3、HISHO 9、8 部長檔各 9），自身呼叫 OK、調色盤 OK（46 秒） |
| `verify_maps.py` | FREE MODE 改本社的畫面：VRAM tile 0xA0 起 188 個、CGRAM 第 3 列、BG tilemap cell (2, 3) 起未被視窗蓋住的列 | tile OK、調色盤 OK、tilemap 15/24 列（其餘被視窗蓋住）（35 秒） |
| `verify_kaodata_export.py` | 資料集逐 pixel 和 ROM 解碼比對 | 96/96、group／name 96/96、checksums OK |

沒有在遊戲中驗證的：JAPANS 圖與 `$CD25` 填色段（只確認填色段剛好填滿 JAPANS 的縣界，見 `prefecture_map.png`）、`$CBAD`／`$CC69` 座標、部長檔 JINBU／KEIBU／SHABU／BAIBU 的部門名稱。
