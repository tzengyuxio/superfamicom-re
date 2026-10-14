# SFC 提督の決断 解析

KOEI，1992，SFC（LoROM 1.25 MB）。太平洋戰爭的海軍戰略遊戲：9 個劇本（1941-11 日米交渉決裂 ～ 1945-04 大和特攻）、艦船 270 艘、基地 50、艦隊 32、提督 40 人、他國 13。文字是光榮自訂的二字節碼（1036 字）加半形假名。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

原版（`roms/Teitoku no Ketsudan (Japan).zip`）與 Rev 1（`… (Rev 1).zip`）都支援：兩版只差程式碼，資料區與用到的程式位址完全相同；LZ 指標表位置不同（`0x4F3EF` → `0x4F3FB`），夾在程式碼間的 printf 格式字串也有幾處移位（驗證腳本用 `rom.REVISIONS` 換算）。`rom.py` 依標頭 `0x7FDB` 的版本 byte 切換。美版 *P.T.O.* 只當參考，沒有解析。

## 指令

```bash
.venv/bin/python teitoku/export.py [--rom ROM] [--out DIR]       # → teitoku/output/（CSV、XLSX、PNG），約 1 秒
.venv/bin/python teitoku/export_kaodata.py --out <kaodata>/data-local/tk-sfc
.venv/bin/python teitoku/verify_kaodata_export.py --dataset <kaodata>/data-local/tk-sfc
.venv/bin/python teitoku/verify_scenarios.py [--scenarios 1,2,...]   # 約 7 分鐘
.venv/bin/python teitoku/verify_text.py                         # 約 3.5 分鐘
.venv/bin/python teitoku/verify_faces.py                        # 約 1 分鐘
.venv/bin/python teitoku/verify_maps.py [--part world|sea]      # 約 3 分鐘
.venv/bin/python teitoku/verify_tables.py                       # 約 2 分鐘
```

- ROM 預設直接讀 `roms/Teitoku no Ketsudan (Japan).zip`，`--rom` 也接受 Rev 1 或 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0x18C8`）；savestate 重播用共用的 `tools/replay.py`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。基地標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`）。Mesen 會印大量 `[CPU] Uninitialized memory read`，可用 `2>&1 | rg -v Uninitialized` 濾掉。`verify_maps.py` 會用子程序分兩段跑（一個 process 只能開一次 Mesen）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字與字型、初始化資料與劇本修補、艦船／基地／艦隊／陣營／提督／他國、頭像、艦船圖、場景圖、世界地圖、大地圖（海圖） |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `tk-sfc`（40 位提督＋54 張頭像） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；group／keys／checksums |
| `verify_scenarios.py` | 9 劇本 × 2 陣營開局後的 WRAM 與 `Rom.scenario_image` 逐 byte 比對；主畫面艦隊面板（艦名、速度、飛機、兵員、在港時的場景圖） |
| `verify_text.py` | 把赤城的名字換成各個字碼，記錄遊戲字型複製程式讀的字形：1036 字＋跳脫碼＋空白碼 |
| `verify_faces.py` | 54 張頭像：以頭像函式 `$0A:B2A9` 載入，比對 VRAM tile 與 CGRAM |
| `verify_maps.py` | 世界地圖（tile、tilemap、調色盤）與大地圖區塊（把艦隊移到各區塊，比對載入的區塊圖） |
| `verify_tables.py` | 資料畫面：建造中艦船、予備艦船、基地一覽、他國一覽、基地詳細 7 個 |
| `tools/sequences.py` | 按鍵序列（標題→劇本選單、開新遊戲到主畫面、資料／命令選單） |
| `data/charset.txt` | 字形編號 → 字（1036 字） |

## 輸出（`teitoku/output/`）

| 檔案 | 內容 |
|------|------|
| `scenarios.csv` | 9 劇本：標題、日期（西曆、昭和）、開始時已經過的月數 |
| `ship_types.csv` | 艦種名稱 14 種 |
| `ships.csv` | 艦船 270 艘：艦名、讀音、陣營、艦種、艦級、艦船圖編號、対艦／対空／装甲（推測）、速度、搭載数（推測）、完成月 |
| `ship_scenarios.csv` | 9 劇本 × 270 艘：所屬艦隊、建造中、沈没、戦闘機／攻撃機／偵察機、兵員、未解欄位 |
| `bases.csv` | 基地 50：代號、名稱、座標、大地圖格 |
| `base_scenarios.csv` | 9 劇本 × 50 基地：所屬、司令部、友好、耐久、武装（含上限）、資源（鉄鉱 原油 人口 工業）、飛機 6 種、燃料、資材、兵員、輸送船、原始資料 |
| `fleets.csv` | 9 劇本的使用中艦隊：座標、目的地、基地、司令官、旗艦、艦船清單、燃料、士気、疲労、輸送船 |
| `admirals.csv`、`admiral_scenarios.csv` | 提督 40 人（陣營、頭像）；9 劇本的指揮艦隊、不登場旗標（能力值是開局亂數，不在 ROM） |
| `countries.csv` | 9 劇本 × 13 國：同盟、對日／對連合態度、未解數值、技術旗標（推測） |
| `sides.csv` | 9 劇本 × 2 陣營：司令部、原始資料 |
| `teitoku.xlsx` | 以上各表（需 openpyxl） |
| `faces/` | 54 張頭像（提督以姓名命名，其他以編號） |
| `ships/` | 101 個艦級的艦船圖（128 × 32，以該級第一艘命名） |
| `scenes/` | 場景圖 167–185（128 × 48，對應與調色盤部分推測） |
| `world_map.png` | 世界地圖 256 × 120 |
| `sea_map.png`、`sea_map_bases.png` | 大地圖 1024 × 512；標上 50 基地 |
| `font.png` | 1036 字的字型總覽 |

## 進度

- ✓ 壓縮（共用 `tools/koei_lz.py`）、LZ 編號 0–390 分類；391–432 未解
- ✓ 文字：二字節碼 1036 字（含 `0x9140+k` 跳脫）、半形假名（平／片假名切換）、日期字；`data/charset.txt`
- ✓ 初始化資料（4 段 MVN）與劇本 2–9 修補；9 劇本 WRAM 完全一致
- ✓ 艦船 270：名稱、讀音、艦種、艦級、速度、飛機、兵員、完成月、所屬艦隊、建造中／沈没；対艦／対空／装甲／搭載数為推測
- ✓ 基地 50：名稱、代號、座標、耐久、武装、資源、飛機、燃料、資材、兵員、輸送船、友好、所屬、司令部
- ✓ 艦隊 32：座標、目的地、基地、司令官、旗艦、燃料、士気、疲労、輸送船
- ✓ 陣營：名稱、司令部；提督 40：姓名、指揮艦隊、不登場；他國 13：同盟、對日／對連合
- ✓ 頭像 54 張（提督 40 ＋ 其他 14）；kaodata 資料集 `tk-sfc`
- ✓ 艦船圖 101 艦級；場景圖 19 張（在港顯示規則部分驗證）
- ✓ 世界地圖、大地圖（32 × 16 區塊、196 個陸地區塊）
- … 未解：戰鬥畫面（沒有戰術地圖）、場景圖的對應、陣營大部分欄位、他國數值、艦船／基地／艦隊的部分欄位（ROM_FORMAT.md §15）

## 驗證

原版與 Rev 1 都跑過，結果相同（時間是兩版同時跑的實測）。

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 9 劇本 × 日本軍／連合国軍開新遊戲；劇本載入 `$0B:9A5A` 返回時的 WRAM `$7E:205A–$5B0A` 與 `Rom.scenario_image` 逐 byte 比對（排除遊戲執行時寫的 9 bytes：劇本號、玩家數、`$2B9A–$2BA0`）；到主畫面後艦隊面板的 vprintf 引數（陣營、艦隊號、旗艦艦種與艦名、位置或基地名、燃料、士気、疲労、最高速度、飛機三種、兵員、輸送船）與面板載入的圖（出海 → 旗艦的艦船圖，在港 → 場景圖） | 18/18 runs OK：WRAM 15016/15016（9 劇本 × 2 陣營），面板 17 個全對（劇本 1 在港：日本クレ → 167、連合ハワイ → 169）；劇本 2 連合国軍開局即是珍珠港戰鬥，沒有面板（not reached，只比 WRAM）；原版 401 秒、Rev 1 402 秒 |
| `verify_text.py` | 劇本 3 予備艦船清單，把赤城的名稱字串換成 5 個字碼一組，攔 `$06:BD03` 確認是該列、攔 `$01:F06B` 記錄字形 | 未改動 赤城 OK；1036/1036 字形；空白碼 5/5 畫字形 0；ALL OK，原版 212 秒、Rev 1 213 秒 |
| `verify_faces.py` | 劇本 3 資料→人材（提督清單顯示游標所在提督的頭像，`$0A:B2A9(side, index)`），每輪把該函式開頭 `$0A:B2B0` 改成固定的 (side, index)，移動游標讓遊戲重畫，比對 VRAM `$7A00` 的 960 bytes 與 CGRAM 第 5 列 | 54/54 OK，原版 47 秒、Rev 1 48 秒 |
| `verify_maps.py` | 世界地圖：劇本 3 說明畫面的 VRAM `$9800` 317 tile、tilemap（VRAM `$E200`）32 × 15、CGRAM 第 7 列；大地圖：每輪把第一艦隊座標改到別處，開作戦→移動，記錄遊戲解壓的 LZ 編號（`$00:9896`），必須是周圍 3 × 3 區塊的 186 + `Rom.sea_block`；CGRAM 第 7 列 | 世界地圖 317 tile、tilemap 32 × 15、調色盤 OK；大地圖 56/56 個位置載入的區塊正確（共涵蓋 195 個陸地區塊）；ALL OK，原版 91 秒、Rev 1 91 秒 |
| `verify_tables.py` | 劇本 3 日本軍的資料畫面：建造中艦船、予備艦船（每列艦種與艦名，清單成員 = 解碼結果）、基地一覽（代號、名稱、所屬、鉄鉱 原油 人口 工業）、他國一覽（名稱、同盟、対日、対連）、命令→基地的基地詳細 7 個 × 20 欄（耐久、武装、飛機、燃料、資材、兵員等） | 建造中 26/26、予備 75/75、基地 50/50、他國 13/13、基地詳細 7/7；ALL OK，原版 108 秒、Rev 1 105 秒 |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對；group、keys、checksums | 54/54、40/40、group 14/14、無 label／code、ALL OK（0.1 秒） |

所有表的欄位意義另外對照過遊戲畫面（艦隊面板、資料畫面、基地詳細、他國一覽、工廠設計畫面的欄位名）；標「推測」的欄位沒有獨立驗證。
