# 提督の決断II（SFC，KOEI，1993，HiROM）

太平洋戰爭的海軍戰略遊戲（3 MB HiROM）：10 個劇本（キャンペーン 3＋ショート 7）、艦型 152、艦船 255、艦隊 39、
潜水艦 32、航空機 60、戦車 10、基地 70、拠点 100、提督 60、將軍 30、國家 9。文字是光榮自訂的二字節碼（1216 字）
加半形假名。格式細節見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

ROM：`roms/Teitoku no Ketsudan II (Japan).zip`（原版，預設）與 `roms/Teitoku no Ketsudan II (Japan) (Rev 1).zip`。
兩版都支援：`rom.py` 依 header 版本 byte（0xFFDB）選位址表 `REVISIONS`，劇本資料區塊則直接解析劇本載入程式取得；
畫面格式字串以內容搜尋（`rom.FORMATS`）。兩版資料內容相同（只有字型最後 2 字 1214、1215 不同，兩字是非文字的 〓），Rev 1 是程式與資料搬家（位址對照見 ROM_FORMAT.md「版本」）。
美版 *P.T.O. II* 沒有解析。

## 指令

```sh
.venv/bin/python teitoku2/export.py [--rom ROM] [--out DIR]              # → teitoku2/output/（CSV、XLSX、PNG），約 10 秒
.venv/bin/python teitoku2/export_kaodata.py --out <kaodata>/data-local/tk2-sfc
.venv/bin/python teitoku2/verify_kaodata_export.py --dataset <kaodata>/data-local/tk2-sfc
.venv/bin/python teitoku2/verify_scenarios.py [--scenarios 0,1,...]       # 約 5 分鐘
.venv/bin/python teitoku2/verify_tables.py [--dump DIR | --load DIR]      # 約 4 分鐘
.venv/bin/python teitoku2/verify_text.py                                  # 約 3.5 分鐘
.venv/bin/python teitoku2/verify_faces.py                                 # 約 1.5 分鐘
.venv/bin/python teitoku2/verify_maps.py                                  # 約 0.5 分鐘
```

- 每支都接受 `--rom`（原版或 Rev 1 的 zip／.sfc），預設原版。
- 解壓縮用共用的 `tools/koei_lz.py`；savestate 重播用共用的 `tools/replay.py`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），會印大量 `[CPU] Uninitialized memory read`，可用 `2>&1 | rg -v Uninitialized` 濾掉。
- `verify_tables.py --dump DIR` 把 printf 紀錄與 WRAM 存起來，`--load DIR` 不跑模擬器、只重做比對（改解碼器時用）。

## 檔案

| 檔案 | 內容 |
|------|------|
| `rom.py` | ROM 讀取：文字解碼（字型 1216 字＋JIS X 0201 半形假名）、劇本載入程式解析（`Rom.loader`）、劇本 WRAM 映像（`Rom.wram_image`）、各資料表解碼器（`Decoders`，可套用在 ROM 映像或遊戲的 WRAM dump）、標題／日期、拠点、頭像、大地圖位圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `tk2-sfc`（90 人＋104 張頭像） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；code／characters／group／checksums |
| `verify_scenarios.py` | 10 劇本：載入程式的 19 個 WRAM 區段與 `Rom.wram_image` 逐 byte 比對、確認畫面標題、主畫面日期 |
| `verify_tables.py` | 劇本 0 的 22 個資料畫面：vsprintf 印出的值與同時 dump 的 WRAM 解碼結果比對 |
| `verify_text.py` | 把提督名換成各個字碼，記錄字型函式讀的 glyph：1216 字＋空白碼 |
| `verify_faces.py` | 人事畫面：104 張頭像的 VRAM tile 與 CGRAM；提督／將軍 → 頭像號 |
| `verify_maps.py` | 大地圖位圖與遊戲 WRAM 比對；拠点、潜水艦、艦隊座標與海陸 |
| `tools/sequences.py` | 按鍵序列（標題→劇本選單、開新遊戲到主畫面、情報／一覧／人事選單），以及 `tools/replay.py` 沒有的 `*n` 重複語法 |
| `tools/printf_trace.py` | 給 `tools/replay.py` 用的 vsprintf 追蹤 Lua：記錄每次呼叫的格式位址、依格式字串讀出的參數（%d/%ld/%s/%c）、實際輸出字串 |
| `data/charset.txt` | 字型 glyph → 字元對照（1216 字，每行 32 字） |

## 輸出（`teitoku2/output/`）

除 `ship_classes`、`sub_classes`、`admirals`、`generals` 外，每列都有「劇本」欄（10 劇本）。標「(推測)」的欄位未經畫面驗證；
`Unknown*`、`原始資料` 為原始值。

| 檔案 | 筆數 | 內容 |
|------|------|------|
| `scenarios.csv` | 10 | 標題、開始日期、日期表後未解 byte |
| `ship_classes.csv` | 152 | 艦型：國、艦種、対艦／対空／水雷／速度／搭載／物資、装甲 4 方向、艦船圖(推測)、新型兵器(110–149) |
| `sub_classes.csv` | 28 | 潜水艦型：國、装甲、速度、水雷、物資 |
| `ships.csv` | 2550 | 10 劇本 × 255 艘：艦名、讀音、艦型、艦種、國、対艦、対空、装甲、速度、練度、未解欄位 |
| `fleets.csv` | 153 | 有提督的艦隊：提督、在港／所在基地、座標、任務、目標、原始資料 |
| `submarines.csv` | 254 | 潜水艦單位：艦名、型、座標、目標、水雷、速度、物資、練度(推測) |
| `aircraft.csv` | 600 | 航空機：國、種別、戦闘、航続、旗標(未解) |
| `tanks.csv` | 100 | 戦車：口径、装甲 |
| `bases.csv` | 700 | 基地：代碼、名、擁有國、原屬國(推測)、座標(推測)、生産力、油、鉱、鄰接(推測) |
| `kyoten.csv` | 1000 | 拠点：名、擁有國、座標、地形、鄰接(推測) |
| `countries.csv` | 90 | 國家：領袖、稱號、對日友好度 |
| `sides.csv` | 20 | 日本／連合國國力：国民生産力、5 項技術力、基地維持費、軍事協定・同盟、援助協定 |
| `navy_reserve.csv`、`army_reserve.csv` | 20、20 | 海軍／陸軍予備兵力：費用、物資、陸戦隊／輸送船、師団／トラック、機種 A/B 與機數 |
| `marines.csv` | 400 | 陸戦隊：兵力、所在基地(推測)、任務(推測)、目標基地、指揮官 |
| `admirals.csv`、`generals.csv` | 60、30 | 提督、將軍：陣營、頭像、未解 bytes |
| `teitoku2.xlsx` | | 以上各表（需 openpyxl） |
| `faces/` | 104 | 頭像（人物以姓名命名，其他以 group 命名） |
| `world_map.png` | | 大地圖海陸位圖 640 × 360 |
| `world_map_marks.png` | | 2 倍大地圖，標上 100 拠点（黃）與 70 基地（紅圈＋代碼，座標推測） |
| `font.png` | | 字型 1216 字 |

## 進度

| 項目 | 狀態 |
|------|------|
| 文字編碼與字型 | 完成並驗證（1216 字；0x8140 不讀字型、0x8981–0x913F 畫 glyph 0） |
| 劇本載入程式、標題、開始日期 | 完成並驗證：20 個複製指令（19 個目的位址；艦船表劇本 0–4 與 5–9 來源不同），兩版自動解析 |
| 艦型、潜水艦型、航空機、戦車、艦船、艦隊、潜水艦、國家、國力、外交、海軍／陸軍予備、基地、拠点、陸戦隊、提督、將軍 | 畫面上顯示的欄位都驗證過（見下），其餘欄位列在「未解」 |
| 頭像 104 張 | 完成並驗證（LZ 753+f，40×48，兩組調色盤），kaodata `tk2-sfc` |
| 大地圖 | 海陸位圖（LZ entry 0）完成並驗證；遊戲畫面的圖塊渲染未解 |
| 戰術地圖 | 未解 |

### 驗證結果

| 腳本 | 原版 | Rev 1 |
|------|------|-------|
| `verify_scenarios.py` | 10/10 劇本 ALL OK（19 區塊 29755/29755 bytes、標題、日期；301 s） | 10/10 劇本 ALL OK（300 s） |
| `verify_tables.py` | 22 個畫面 ALL OK（242 s）：就航艦船 29/29、予備艦船 66/66、艦型 52+52+48 列（110 類）、航空機 36+33+37 列（31 機）、潜水艦型 20+20、戦車 11/11、国力 7/7、海軍兵力 15/15、陸軍兵力 9/9、外交 8/8、艦隊 5/5、陸戦隊 21/21、潜水艦 14/14、基地 75 列（70/70）、拠点 120 列（100/100）、提督 30/30、將軍 15/15 | 同左，ALL OK（242 s） |
| `verify_text.py` | ALL OK（202 s）：未修改名字 OK、1216/1216 glyph、空白碼 6 個 | ALL OK（202 s） |
| `verify_faces.py` | ALL OK（93 s）：提督 0/1、將軍 0/1 → 頭像 0/1/60/61；104/104 頭像（第二組調色盤 53 張） | ALL OK（92 s） |
| `verify_maps.py` | ALL OK（34 s）：位圖 32400/32400 bytes、拠点 100/100、潜水艦 254/254、未在港艦隊 86/86；基地 57/70 距陸地 5 px 內（只報告） | ALL OK（33 s），數字同左 |
| `verify_kaodata_export.py` | ALL OK（<1 s）：render 104/104、code 104/104、characters 90/90、group 104/104、checksums OK | ALL OK（1 s） |

- `verify_scenarios.py`：每個劇本比對載入程式最後一次複製後的 19 個 WRAM 區段（29755 bytes）與 `Rom.wram_image` 逐 byte 相同；
  確認畫面 vsprintf 的標題指標；主畫面日期 printf 與 $7E:21A7 的日期。
- `verify_tables.py`：劇本 0 以日本開始，進各畫面翻頁，用 `tools/printf_trace.py` 記錄 vsprintf，同一時點 dump WRAM，
  用 `rom.Decoders` 解 dump 後比對（開局後部分值會變，所以比對同時的 WRAM，不是 ROM 映像）。項目：就航艦船、予備艦船
  （水雷遊戲印 0，不比）、艦型性能（日 48／米 40／その他 22 類）、航空機性能、戦車性能、潜水艦性能（日米各 10 類）、
  国力情報、海軍兵力、陸軍兵力、外交情報、艦隊一覧、陸戦隊一覧、潜水艦一覧、基地一覧（生産力、油鉱）、拠点一覧（100）、
  人事（提督 30／將軍 15 名稱與指揮）。
- `verify_text.py`：劇本 0 把提督 0–5 的名字 patch 成各字碼，掛字型函式（原版 $D3:0E6B）讀出的 glyph 號。
- `verify_faces.py`：人事畫面，在頭像函式入口把頭像號換成測試值（經 ROM 0xFF 填充 byte 傳入），比對 VRAM 0x800 的 30 個
  tile 與 CGRAM 第 15 列；另外確認提督 0/1 → 頭像 0/1、將軍 0/1 → 頭像 60/61。
- `verify_maps.py`：主畫面 WRAM $7F:8000 = LZ entry 0；10 劇本的拠点在陸地（或 1 px 內）、潜水艦與未在港艦隊在海上；
  基地座標只報告（遠離陸地的 13 個多為位圖上沒有的小島：AT GB GM II MC MD MS NH PL PR SN TR WK）。

kaodata 資料集的 `source.revision` 記的是匯出當下的 HEAD；本資料夾尚未 commit，正式匯出要在 commit 之後重跑。

## 未解

- 海軍航空隊（$7E:92C5，765×5 bytes）：每筆 [?, 機種, 機數, 練度?, 0–2]，與基地的對應未解（一覧畫面沒驗證）
- 陸軍師団（$7E:842A，88×8）未解；陸戦隊 +2 所在基地、+3 任務、+5 未驗證
- $7E:6710（70×7，載入後 +6 設 0xFF）未解
- 基地座標（+11/+13，推測）、+31..+46 的 8 組 (index, 種類)（推測為駐留部隊：種類 5＝艦隊）、+47；基地一覧的「陸軍／海軍」欄與部隊數來源
- 艦船 +15/+16/+18/+20–27/+34/+35、就航艦船畫面的機数（計算值），提督／將軍的能力值（畫面上沒有能力值顯示）
- 航空機 +17 旗標；國家 +30 旗標；國力外交費
- 劇本日期表後 10 bytes；キャンペーン／ショート劇本旗標位置
- 主畫面大地圖的圖塊渲染（LZ 2、4、92、1041），戰術（海戰／陸戰）地圖
- 頭像 90–95（推測為各國領袖，目前 group「其他」）、96–103 的身分；事件頭像 488–531（未匯出）
