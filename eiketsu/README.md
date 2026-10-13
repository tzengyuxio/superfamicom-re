# SFC 三國志英傑伝 解析

KOEI 1995 年的 SFC 遊戲，HiROM，檔案 3 MB。遊戲內容是劉備一方的劇情戰略 RPG：58 場戰鬥、384 名人物、240 張頭像。文字用 Shift-JIS（cp932），人名和地名另外用到使用者外字區 `0xEB9F–0xEBE7` 的 37 個字。各表的 ROM 格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python eiketsu/export.py [--rom ROM] [--out DIR]       # → eiketsu/output/（CSV、XLSX、PNG）
.venv/bin/python eiketsu/export_kaodata.py --out <kaodata>/data-local/eiketsu-sfc
.venv/bin/python eiketsu/verify_kaodata_export.py --dataset <kaodata>/data-local/eiketsu-sfc
.venv/bin/python eiketsu/verify_persons.py                  # 約 5 秒
.venv/bin/python eiketsu/verify_tables.py                   # 約 1 分鐘
.venv/bin/python eiketsu/verify_font.py                     # 約 1 分鐘
.venv/bin/python eiketsu/verify_faces.py [--quick]          # 約 3 分鐘（--quick 約 80 秒）
.venv/bin/python eiketsu/verify_maps.py [--quick]           # 約 3–4 分鐘（--quick 約 2 分鐘）
```

- ROM 預設直接讀 `roms/Sangokushi Eiketsuden (Japan).zip`，`--rom` 也可以給 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0xF037`）。
- 依賴：Pillow；openpyxl 可選，用來匯出 .xlsx。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到就退回 PIL 的預設字型。
- 驗證腳本需要 Mesen 2，由 `tools/mesen.py` 透過 ctypes 呼叫 MesenCore。MesenCore 自己印出的 `Uninitialized memory read` 已經在 `tools/replay.py` 裡濾掉。一個 process 只能開一次 Mesen，所以 `verify_maps.py` 會把大地圖和戰場分成兩個子 process 跑。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：字型與外字、人物（名稱表、能力表）、勢力、兵種、地形、道具、地點列表與大地圖標記、NPC 類型、頭像、戰鬥名稱與戰場地圖、大地圖 |
| `export.py` | 匯出 CSV、XLSX、PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `eiketsu-sfc`（240 張頭像、384 名人物、單一調色盤） |
| `verify_kaodata_export.py` | 用參考渲染器畫出資料集，和 ROM 解碼逐 pixel 比對，並檢查 checksums |
| `verify_persons.py` | 新遊戲時遊戲在 WRAM 建出的 384 筆人物紀錄，和 ROM 兩張表逐欄比對 |
| `verify_tables.py` | 打開関羽的狀態畫面，追蹤 CPU 讀取：兵種名指標、名稱字串、三張兵種係數表、道具紀錄 |
| `verify_font.py` | 開場劇情中，每個字的二分搜尋結果與字形讀取位址 |
| `verify_faces.py` | 把 240 個頭像號逐一換進華雄說話時的頭像程式，比對 VRAM 和 CGRAM |
| `verify_maps.py` | 大地圖：VRAM、CGRAM、地點標記；58 場戰鬥：改寫腳本的戰鬥號，讓遊戲自己載入每一場，再比對標題、tile、調色盤、地形格、BG tilemap |
| `tools/replay.py` | 驗證腳本共用：開機照按鍵序列玩到指定幀、存 savestate，每輪換參數重播並讀記憶體；也定義各操作序列 |
| `data/ext_chars.txt` | 外字對照表：碼、字形號、字、用例 |

## 輸出（`eiketsu/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 384 人：姓名、讀音、頭像、勢力、武力、統率、知力、兵種、持ち物、未解欄位（Unknown8 推測是等級） |
| `items.csv` | 183 個道具：名稱、種類（附推測的種類名）、價格、未解欄位 |
| `classes.csv` | 19 個兵種與 3 個係數（第一個是 Lv1 的策略） |
| `forces.csv`、`terrains.csv` | 15 個勢力名、20 個地形名 |
| `places.csv` | 4 組地點列表（共 88 個地點）：用到該組的章、讀音、種類、大地圖標記格 |
| `npc_types.csv` | 256 種 NPC 類型名稱 |
| `battles.csv` | 58 場戰鬥：名稱、遊戲顯示的標題、大小、圖塊組 |
| `battle_cells.csv` | 58 張戰場的地形格（32 × 32 px 一格）與地形名（推測） |
| `eiketsu.xlsx` | 以上各表（需要 openpyxl） |
| `faces/` | 240 張頭像（48 × 48） |
| `map.png`、`map_places.png` | 大地圖 256 × 224；放大 4 倍、標出 4 組地點標記 |
| `battle/` | 58 張戰場地圖（`00_汜水関.png`…） |
| `font.png` | 1655 字的字型總覽 |
| `verify_tables_status.png` | `verify_tables.py` 截下的関羽狀態畫面 |

## 進度

- ✓ 壓縮（共用 `tools/koei_lz.py`）；字型 1655 字（Shift-JIS 碼表）；外字 37 個，其中 36 個已辨識（`data/ext_chars.txt`）
- ✓ 人物 384 人：姓名、讀音、頭像、勢力、武力、統率、知力、兵種、等級、持有道具
- ✓ 勢力 15、兵種 19（名稱與 3 張係數表）、地形 20、道具 183（名稱、種類、價格）、NPC 類型 256
- ✓ 地點：4 組地點列表，各組和大地圖標記的對應，以及章與組的對應
- ✓ 頭像 240 張（單一調色盤）；kaodata 資料集 `eiketsu-sfc`
- ✓ 大地圖：tile、32 × 28 tilemap、調色盤、地點標記
- ✓ 戰場地圖 58 張：方塊地圖、2 組圖塊（tile、方塊表、調色盤）、地形格、戰鬥標題
- … 未解：劇本腳本（opcode、敵方配置、勝利條件、劇情假名碼）、攻撃／防御／耐久公式、幾個未知欄位、城鎮與幕舎地圖（見 ROM_FORMAT.md §10）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_persons.py` | 新遊戲時，`$C8:0D39` 在 `$7E:200D` 建出 384 筆 × 43 bytes 的紀錄。逐欄和 ROM 名稱表、能力表比對：姓名、讀音、頭像、勢力 byte、武力統率知力、+6（+2）、兵種、等級、+9、持ち物、+18 | 11 欄都是 384/384；劉備的紀錄是 武力 75 統率 91 知力 64 耐久 250 等級 1，和狀態畫面一致 |
| `verify_tables.py` | 打開関羽的狀態畫面時追蹤讀取。兵種：讀了 `0x37BE6 + 4 × 6` 的指標和「軽騎兵」字串，以及三張係數表的第 6 個 byte（策略 15 和畫面一致）。道具：只讀了第 12 筆（青龍偃月刀）的 +19 | OK |
| `verify_font.py` | 開場劇情中畫出的 249 種字：二分搜尋的結果 = 碼在 `FONT_CODES` 的位置；渲染程式讀的 250 個字形位址都是 `FONT + 32 × 字號`（有 1 個字形是直接用字號畫的，沒有經過搜尋） | 249/249、OK |
| `verify_faces.py` | 華雄說話時呼叫 `$C7:04F7`，把引數換成 0–239，比對 VRAM `0x5F40` 的 1152 bytes 和 CGRAM 調色盤 3；沒改動時，引數是華雄（人物 5）的頭像 138 | 240/240、OK |
| `verify_maps.py` | 大地圖：VRAM tile、tilemap、CGRAM 4–6，以及章 0 的標記格。戰場：把腳本的戰鬥號（`0xB076B`）改成 0–57，讓遊戲自己建好每一場，再比對 `$7E:D97F` 的標題、VRAM tile 64 起的 tile、CGRAM 4–6、`$7F:C910` 的地形格、BG tilemap（有一個 32 × 28 畫面範圍，在地圖內的格子全部相符） | 大地圖：tile OK、896/896、調色盤 OK、標記 22/22 同格。戰場：標題、tile、調色盤、地形格都是 58/58；tilemap 58/58（最少 780 格，鏡頭停在地圖角落時是 30 × 26） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）和 `Rom.face_rgb` 逐 pixel 比對，並檢查 checksums | 384/384、240/240、OK |

另外和遊戲畫面對照過的地方：

- 劉備、関羽、張飛的狀態畫面與武将表（武力、統率、知力、等級、兵種）。
- 華雄的兵種（劇情對話）。
- 汜水関戰場的地形值和地圖圖案一致（崖、林、川、橋、城壁、草原、荒地、砦、兵糧庫）。
- 大地圖輸出和遊戲的全体図截圖一致。
- 把腳本 `0xB05E4` 的 byte 改掉以後，華雄的等級跟著變（3 + 加值）。這證明能力表 +8 是基礎等級。

沒有外部資料，所以沒有 `[EXT]` 欄位。kaodata-re 的能力值表只有 S01–S12，沒有英傑傳。
