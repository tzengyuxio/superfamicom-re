# SFC エアーマネージメント 大空に賭ける（航空霸業）解析

KOEI，SFC（LoROM 1 MB，SRAM 8 KB，無壓縮）。航空公司經營模擬：22 都市、2 個劇本（1963、1983 年）、20 種機種、5 家製造商、33 張頭像。本作沒有戰鬥，所以沒有戰術地圖。文字是 Shift-JIS（cp932），全形字型只收 690 字（漢字 437 字）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

支援原版 `Air Management - Oozora ni Kakeru (Japan)` 與 `(Rev 1)`；程式預設讀原版，`Rom.rev` 自動判斷版本。兩版匯出的資料表內容完全相同（只有檔案表的位置不同）。

## 指令

```bash
.venv/bin/python airmanage/export.py [--rom ROM] [--out DIR]       # → airmanage/output/（CSV、XLSX、PNG）
.venv/bin/python airmanage/export_kaodata.py --out <kaodata>/data-local/air-sfc
.venv/bin/python airmanage/verify_kaodata_export.py --dataset <kaodata>/data-local/air-sfc
.venv/bin/python airmanage/verify_scenarios.py [--rom ROM]        # 約 90 秒（兩個劇本各一個子程序）
.venv/bin/python airmanage/verify_tables.py [--rom ROM]           # 約 2 分鐘
.venv/bin/python airmanage/verify_faces.py [--rom ROM] [--quick]  # 約 35 秒
.venv/bin/python airmanage/verify_maps.py [--rom ROM]             # 約 25 秒
.venv/bin/python airmanage/verify_text.py [--rom ROM]             # 約 45 秒
```

- ROM 預設直接讀 `roms/Air Management - Oozora ni Kakeru (Japan).zip`；Rev 1 用 `--rom "roms/Air Management - Oozora ni Kakeru (Japan) (Rev 1).zip"`，也接受 .sfc。
- 本作沒有 KOEI LZ，不用 `tools/koei_lz.py`。
- 依賴：Pillow；openpyxl（匯出 .xlsx）。圖上的文字用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用共用的 `tools/replay.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：檔案表、模組資料（以 p-code 位址讀取）、都市、距離、劇本、機種、製造商、頭像、字型、大地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `air-sfc`（33 張頭像，沒有人物；頭像分 部下／交涉對象／廠商 三組，廠商頭像附公司名） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 兩劇本開局後的 WRAM 都市／スロット／玩家記錄，以及讓遊戲對 22 都市各開一次都市畫面的 printf 引數 |
| `verify_tables.py` | 讓遊戲的交易畫面顯示 20 種機種、主畫面的距離框顯示 462 組距離，比對 printf 引數 |
| `verify_faces.py` | 遊戲自己的頭像描述（部下、交渉相手）與調色盤配對；33 張頭像逐一換進部下的描述，比對 VRAM 與 CGRAM |
| `verify_maps.py` | 主畫面的大地圖 tilemap、CHR、調色盤與 22 都市標記位置 |
| `verify_text.py` | 全形字型 690 字＋4 個字型外的碼，比對遊戲的字形查找 `$00:BCAA` 算出的位址 |
| `tools/vm.py` | 驗證共用：開機按鍵序列、兩版的 WRAM／p-code 位址、p-code 注入（讓遊戲跑自己的函式）、printf 紀錄 |
| `data/kanji.txt` | 字型的 437 個漢字（依字形順序，每行 40 字） |

`tools/vm.py` 是包在共用 `tools/replay.py` 外面的一層（只提供 `extra_lua` 與 `wram` 修補），沒有複製 replay 的功能。

## 輸出（`airmanage/output/`）

| 檔案 | 內容 |
|------|------|
| `cities.csv` | 22 都市：全形／半形名、機場、預設航空公司、類型（ミリオン／ビジネス／リゾ－ト／バランス）、地圖位置；未解：第二組航空公司名、另一組座標、3 組航線值（推測是初期航線） |
| `scenario_cities.csv` | 2 劇本 × 22 都市：人口（万人）、経済力、観光地（值與畫面的 d–s 等級）、スロット數、本社スロット；推測：本社初期資金；未解：本社參數 4 個 |
| `distances.csv` | 22 × 22 都市距離（km） |
| `matrix2.csv` | 另一張 22 × 22 對稱表（未解） |
| `aircraft.csv` | 20 機種：名稱、メーカー、座席数、航続距離、価格（万$）、燃料費與等級、発売年、生産終了年、側面圖／上視圖編號；未解：+14 |
| `makers.csv` | 5 家製造商：名稱、代表色、頭像與調色盤、販售機種 |
| `files.csv` | ROM 檔案表 214 個檔（名稱、bank、位址、檔案偏移、大小） |
| `airmanage.xlsx` | 以上各表 |
| `faces/`、`faces.png` | 33 張頭像（`MANAGER_00.png` …，套用遊戲配對的調色盤）與總覽 |
| `world_map.png`、`world_map_cities.png` | 大地圖 256 × 256（ALMAPE）；放大 3 倍並標上 22 都市 |
| `font.png` | 全形字型 690 字總覽 |

## 進度

- ✓ ROM 結構：檔案表 214 檔、p-code 模組的載入位址；Rev 1 的位移
- ✓ 文字與字型：Shift-JIS；全形字型 690 字（符號 22、數字 10、英文 52、平假名 83、片假名 86、漢字 437）的字形位址公式；半形字型
- ✓ 22 都市：名稱、機場、預設航空公司、類型、地圖位置；距離表
- ✓ 2 劇本 × 22 都市：人口、経済力、観光地、スロット、本社スロット；玩家本社的初期スロット與 4 個參數（數值驗證過，意義未解）
- ✓ 20 機種：名稱、座席、航続距離、価格、燃料費（等級）；メーカー對應；発売年、生産終了年（推測，見下）
- ✓ 5 家製造商：名稱、頭像、販售機種
- ✓ 頭像 33 張（部下 8、交渉相手 20、メーカー 5）、12 組調色盤與遊戲的配對；kaodata 資料集 `air-sfc`
- ✓ 大地圖（ALMAPE）與 22 都市位置
- — 戰術地圖：本作沒有戰鬥，不適用
- … 未解：見 [docs/ROM_FORMAT.md §12](docs/ROM_FORMAT.md#12-未解)（第二組航空公司名、matrix2、航線表的值、本社參數、機種 +14、片頭 mode 7 地圖、事件、乗換率等）

`発売年`／`生産終了年` 的值與真實機種年份相符（b707 1957–、dc8 1958–1972），但沒有用遊戲畫面驗證，CSV 欄名不標 `[推測]` 是因為 ROM 裡就是這兩個年份；遊戲怎麼用它們（何時開始／停止販售）未驗證。

## 驗證

全部用 Mesen 2 跑遊戲本身的程式。開機序列：新遊戲 → 選劇本 → PLAYER1 = MAN → 本社選倫敦 → 其餘預設 → 主畫面（約第 9300 幀存 savestate）。之後用 `tools/vm.py` 的 p-code 注入，讓遊戲在主畫面的按鍵等待迴圈執行我們指定引數的遊戲函式（例如「顯示第 c 個都市」），再比對它的 printf 引數或 VRAM。

| 腳本 | 內容 | 原版 | Rev 1 |
|------|------|------|-------|
| `verify_scenarios.py` | 兩劇本：4 名玩家的本社、本社スロット、玩家記錄 +18..+25 與 OPENING 表；WRAM 城市記錄 `$5BF2`（12 B × 22）與スロット記錄 `$6DD6`（20 B × 22）；注入 COMMAND `$AA02(c)` 開 22 次都市畫面，比對 DIORMINF 的 printf（都市名、人口、経済力／観光地等級、スロット 已用／總數、類型） | 劇本 1、2 各：玩家 4/4、WRAM 22/22、都市畫面 22/22，OK（88 秒） | 同左 OK（88 秒） |
| `verify_tables.py` | 注入 `$1169("TRADE")` 進交易畫面，攔 TRADE `$DF43` 把機種號換成 0–19，比對名稱、座席、燃料費等級、航続距離、価格；注入 COMMAND `$A319(a, b)` 462 次，比對 `"%5u0km"` 的引數 | 機種 20/20、距離 462/462，OK（116 秒） | 同左 OK（116 秒） |
| `verify_faces.py` | 劇本 2 主畫面：遊戲寫的 16 個描述（4 玩家 × 部下＋交渉相手 3）調色盤和 `default_palette` 一致；33 張頭像逐一寫進部下描述 `$7146` 後按 A，比對 VRAM `$3700` 960 bytes 與 CGRAM 調色盤 7 | 描述 16/16、頭像 33/33，OK（35 秒） | 同左 OK（35 秒） |
| `verify_maps.py` | 主畫面 BG tilemap VRAM `$F000` 1024 格、CHR `$4000` 768 tile、CGRAM 調色盤 1（色 3、4 是閃爍游標色，除外）、22 個都市標記 sprite 位置 | 1024/1024、768/768、14/14、22/22，OK（24 秒） | 同左 OK（25 秒） |
| `verify_text.py` | 注入 printf `$1139` 印 100 個字，在 `$00:BCAA` 把字碼換成受測碼，於 `$00:BD79` 讀遊戲算出的字形位址；690 字＋`81A0` `837F` `889F` `9F40` | 694/694 OK（44 秒） | 694/694 OK（45 秒） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對、checksums | 33/33、checksums OK | 33/33（Rev 1 ROM 對原版資料集）OK |

COM 玩家的本社兩版不一定相同（劇本 1 玩家 3：原版モスクワ、Rev 1 東京；選法未解），驗證以遊戲實際選的本社比對。
