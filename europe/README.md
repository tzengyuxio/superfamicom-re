# ヨーロッパ戦線 Europe Sensen（SFC，中文名歐陸戰線）

KOEI，1992，HiROM 1.5 MB（標頭 `EUROPE SENSEN`，SRAM 32 KB），只做日版。ROM：`roms/Europe Sensen (Japan).zip`。
格式細節見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```sh
.venv/bin/python europe/export.py                  # CSV（UTF-8-BOM）＋ europe.xlsx ＋ PNG → europe/output/
.venv/bin/python europe/export_kaodata.py --out <kaodata>/data-local/europe-sfc   # 要在 commit 之後跑
.venv/bin/python europe/verify_kaodata_export.py --dataset <kaodata>/data-local/europe-sfc
.venv/bin/python europe/verify_persons.py          # 以下都要 Mesen 2，時間見驗證結果
.venv/bin/python europe/verify_scenarios.py
.venv/bin/python europe/verify_maps.py
.venv/bin/python europe/verify_europe_map.py
.venv/bin/python europe/verify_weapons.py
.venv/bin/python europe/verify_cities.py
```

## 檔案

| 檔案 | 內容 |
|------|------|
| `rom.py` | ROM 解析（LZ 用 `tools/koei_lz.py`）：劇本、將領、領袖、經歷、都市、兵器、頭像、歐洲地圖、戰場地圖、字碼 |
| `scenes.py` | 按鍵序列（標題→劇本→0 人／1 人枢軸／1 人連合→能力審查→指令畫面）與 Lua 事件擷取（`EVENTS_LUA`，透過 `tools/replay.py` 的 `EXTRA_SHOT` 以 hex 回傳） |
| `export.py` | 匯出 CSV、xlsx、PNG |
| `export_kaodata.py` | kaodata `europe-sfc`：characters 100（id 0–99）、portraits 120（無組合臉，沒有頭像碼 → 不寫 `code`） |
| `verify_kaodata_export.py` | 資料集與 ROM 重新解碼比對、checksums |
| `verify_persons.py` | 將領、經歷行指標、頭像（VRAM＋CGRAM）、字碼→字形位址 |
| `verify_scenarios.py` | 6 劇本的區塊複製（MVN）與選單文字 |
| `verify_maps.py` | 6 張戰場：tilemap、tile、地形、閃爍調色盤 |
| `verify_europe_map.py` | 選單背景的歐洲地圖：tilemap、chr、兩組調色盤 |
| `verify_weapons.py` | 158 種兵器的名稱與 AP AT 防 速 射 |
| `verify_cities.py` | 94 個都市的名稱、耐久、三項物資、駐軍、陣營旗標 |
| `data/charset.txt` | 字型 652 字 → 字元（碼 0x8140 + g） |
| `docs/ROM_FORMAT.md` | 格式、操作序列、未解 |

## 輸出（`europe/output/`，不進版控）

`scenarios.csv`（6 劇本）、`persons.csv`（人物 id 0–99，含經歷）、`scenario_generals.csv`（137 筆）、`leaders.csv`（6 人）、
`biographies.csv`（94 人 × 7 行）、`cities.csv`（94 筆，含駐軍、陣營）、`weapons.csv`（158 種）、`map_cells.csv`（6 × 1600 格的地形與格碼）、
`europe.xlsx`（以上各一頁）、`portraits/`（120 張頭像）、`europe_map.png`（選單背景的歐洲圖）、`maps/`（6 張 640×640 戰場地圖，另一版標都市名）、
`font.png`、`kaodata/`（`dataset.json`、`portraits.bin`、`checksums.json` 等）。

## 進度

| 項目 | 解碼 | 驗證 |
|------|------|------|
| 劇本 6 個（名稱、日期、地圖號、區塊） | ✓（header 大半未解） | ✓ `verify_scenarios.py` |
| 將領 94 人（名、國籍、指揮、魅力、歩兵、砲兵、戦車、経験） | ✓（+12 +13 +14 +19 +21 未解） | ✓ `verify_persons.py` |
| 經歷 94 × 7 行 | ✓ | ✓ 行指標（`verify_persons.py`） |
| 頭像 120 張＋調色盤 | ✓ | ✓ VRAM＋CGRAM（`verify_persons.py`）、kaodata（`verify_kaodata_export.py`） |
| 文字編碼／字型 652 字、半形 年月日 Ⅰ Ⅱ | ✓（字形→字元靠字型比對＋人工） | ✓ 碼→字形位址（`verify_persons.py`）；`$`=Ⅰ、`'`=Ⅱ 截圖確認 |
| 領袖 6 人 | ✓（+19、+21 意義推測） | 只驗頭像 |
| 兵器 158 種（名稱、AP AT 防 速 射、國籍） | ✓（種別名稱、登場時期推測；+10 +11 +13 未解） | ✓ `verify_weapons.py`；國旗截圖 |
| 都市 94 個（名、座標、弾薬／燃料／食料、耐久、駐軍、陣營） | ✓（第二組三值、+57 其他位元未解） | ✓ `verify_cities.py`（駐軍只驗畫面顯示的前 3 槽）；座標全在「都市」格 |
| 歐洲地圖（選單背景） | ✓ | ✓ `verify_europe_map.py` |
| 戰場地圖 6 張（格碼、地形、tile、調色盤） | ✓（地形 high nibble 未解） | ✓ `verify_maps.py` |
| kaodata `europe-sfc` | ✓ | ✓ `verify_kaodata_export.py` |
| 部隊（師団／連隊）結構、勝利條件 | 未解 | — |

### 驗證方式

- `verify_persons.py`：1 人枢軸的能力審查畫面，每一頁把 WRAM 將領槽換成 id n 的記錄，擷取 vprintf 參數、經歷行的 `$C1:195E` 指標、VRAM 0xEC00 頭像與 CGRAM 調色盤 11；
  另外掛 `$C1:19C0` 記錄遊戲為每個 2-byte 碼抄字形的來源位址，與 `rom.glyph_address` 比對。
- `verify_scenarios.py`：6 劇本各一輪，在 MVN 剛結束（`$00:006F`）讀 WRAM `$7E:2000` 0x1FEB bytes 與 `Rom.block(k)` 比對，並擷取選單印出的 6 行字串指標。
- `verify_maps.py`：6 劇本 0 人模式進戰場，比對 VRAM tilemap／chr、WRAM `$7E:40C2` 地形低 4 位元與 LZ 原樣、WRAM `$7E:0D77`/`$7E:0D97` 兩組調色盤。
- `verify_europe_map.py`：開機 900 幀後讀 VRAM tilemap／chr 與 CGRAM，重組成圖和 `Rom.europe_rgb()` 比；記錄所有送到 CGRAM 調色盤 2 的 DMA。
- `verify_weapons.py`：1 人枢軸到指令畫面 → 情報 → 兵器 → 自軍，在 `$CA:24D0` 把清單位元組換成要測的 id（ids 經 WRAM `$7F:FF00` 傳入），擷取名字指標與 `$CA:6433` 的參數。
- `verify_cities.py`：1 人連合到指令畫面 → 情報 → 都市 → 自軍 → 第一個都市；每個都市一輪，把 WRAM 都市表換成該 ROM 記錄（+57 bit 4 設成連合），擷取名字指標、耐久、三項物資與駐軍；
  再兩輪測陣營位元（清掉後不在連合清單）與兩組三值（畫面印第一組）。

### 驗證結果（實際輸出）

| 腳本 | 時間 | 結果 |
|------|------|------|
| `verify_persons.py` | 198 s | ALL OK |
| `verify_scenarios.py` | 103 s | ALL OK |
| `verify_maps.py` | 78 s | ALL OK |
| `verify_europe_map.py` | 18 s | ALL OK |
| `verify_weapons.py` | 108 s | ALL OK |
| `verify_cities.py` | 369 s | ALL OK |
| `verify_kaodata_export.py` | < 1 s | ALL OK |

`verify_persons.py`：

```
[review] ids 0-93: name, 指揮 魅力 経験, 歩兵 砲兵 戦車, 7 biography line pointers; portraits 0-119 (VRAM 0xEC00, 960 bytes) and CGRAM palette 11
[glyphs] 383/383 text codes copied from rom.glyph_address(code) (2 codes >= 0x89F0)
ALL OK (198 s)
```

`verify_scenarios.py`：

```
[scenario 1] フランス侵攻戦 1940/5/10 map 0: MVN MC1513C:1FEB, WRAM after the copy 8171/8171 bytes = Rom.block, 6 menu lines printed: True (20 generals, 11 cities)
[scenario 2] 北アフリカ戦 1942/5/26 map 1: MVN MC17127:1FEB, WRAM after the copy 8171/8171 bytes = Rom.block, 6 menu lines printed: True (24 generals, 15 cities)
[scenario 3] クルスク機甲戦 1943/7/5 map 2: MVN MC19112:1FEB, WRAM after the copy 8171/8171 bytes = Rom.block, 6 menu lines printed: True (24 generals, 13 cities)
[scenario 4] ノルマンディーの戦い 1944/6/6 map 3: MVN MC1B0FD:1FEB, WRAM after the copy 8171/8171 bytes = Rom.block, 6 menu lines printed: True (24 generals, 20 cities)
[scenario 5] バルジの戦い 1944/12/16 map 4: MVN MC292EB:1FEB, WRAM after the copy 8171/8171 bytes = Rom.block, 6 menu lines printed: True (24 generals, 21 cities)
[scenario 6] ベルリン攻防戦 1945/4/16 map 5: MVN MC2B2D6:1FEB, WRAM after the copy 8171/8171 bytes = Rom.block, 6 menu lines printed: True (21 generals, 14 cities)
ALL OK (103 s)
```

`verify_maps.py`：

```
[map 0] scenario 1: tilemap 1590/1600 cells = Rom.map_words (10 differ on 都市/橋/川, 0 elsewhere), tiles 280/280 = Rom.map_chr, terrain copy = LZ 5: True, CGRAM palette 2 = base (0x1476C), blink buffers = ROM base / +32: True, palettes DMA'd from the area: ['0x1468c', '0x1476c']
[map 1] scenario 2: tilemap 1600/1600 cells = Rom.map_words (0 differ on 都市/橋/川, 0 elsewhere), tiles 240/240 = Rom.map_chr, terrain copy = LZ 6: True, CGRAM palette 2 = +32 (0x1476C), blink buffers = ROM base / +32: True, palettes DMA'd from the area: ['0x1468c', '0x1476c']
[map 2] scenario 3: tilemap 1596/1600 cells = Rom.map_words (4 differ on 都市/橋/川, 0 elsewhere), tiles 120/120 = Rom.map_chr, terrain copy = LZ 7: True, CGRAM palette 2 = +32 (0x1476C), blink buffers = ROM base / +32: True, palettes DMA'd from the area: ['0x1468c', '0x1476c']
[map 3] scenario 4: tilemap 1590/1600 cells = Rom.map_words (10 differ on 都市/橋/川, 0 elsewhere), tiles 244/244 = Rom.map_chr, terrain copy = LZ 8: True, CGRAM palette 2 = base (0x1476C), blink buffers = ROM base / +32: True, palettes DMA'd from the area: ['0x1468c', '0x1476c']
[map 4] scenario 5: tilemap 1589/1600 cells = Rom.map_words (11 differ on 都市/橋/川, 0 elsewhere), tiles 280/280 = Rom.map_chr, terrain copy = LZ 9: True, CGRAM palette 2 = base (0x148AC), blink buffers = ROM base / +32: True, palettes DMA'd from the area: ['0x1468c', '0x148ac']
[map 5] scenario 6: tilemap 1593/1600 cells = Rom.map_words (7 differ on 都市/橋/川, 0 elsewhere), tiles 280/280 = Rom.map_chr, terrain copy = LZ 10: True, CGRAM palette 2 = base (0x1476C), blink buffers = ROM base / +32: True, palettes DMA'd from the area: ['0x1468c', '0x1476c']
ALL OK (78 s)
```

（不同的格是執行中佔領都市、架橋／爆破造成，腳本只容許它們落在都市／橋／川格。CGRAM 調色盤 2 截到哪一組（base 或 +32）看時間點，兩組都是遊戲每 20 幀輪流 DMA 的閃爍調色盤；另外遊戲也直接從 ROM `0x1468C`（調色盤表 `0x146AC` 之前 32 bytes）DMA 一組調色盤到 CGRAM，用途未解。）

`verify_europe_map.py`：

```
[after 900 frames] tilemap 1024/1024 words ... at (1, 2); LZ entry 623 (15392 bytes) at VRAM 0x8400: True; CGRAM palette 2 = 0x69B62; picture 240x184 from the dump = Rom.europe_rgb(): True
[palette DMAs] 2 distinct 32-byte palettes DMA'd to CGRAM; both EUROPE_PALETTES among them: True
ALL OK (18 s)
```

`verify_weapons.py`：

```
[weapons] 158/158 weapons: name pointer (record +0) and AP AT 防 速 射 (+7 +6 +8 +9 +12) as the screen prints them
ALL OK (108 s)
```

`verify_cities.py`：

```
[cities] 94/94 cities: name (record pointer), 耐久 cur/max, 弾薬 燃料 食料 and every garrison slot the detail screen shows (weapon name pointer, count; first 3) as the city screen prints them; 2 cities have more slots (2 not shown, not checked)
[side] scenario 1 city 0 with +57 bit 4 cleared is left out of the Allies' list: True
[supplies] with the two triples made different the screen prints the first (+13 +15 +17)
ALL OK (369 s)
```

（シディ・ムフタハ、トブルク有第 4 個駐軍槽，詳細畫面只列 3 行，所以第 4 槽沒有驗到。）

`verify_kaodata_export.py`：

```
[render] characters 100/100, portraits 120/120 match the ROM
[codes] portraits without code / label: OK
[checksums] OK
ALL OK
```

## 未解

見 `docs/ROM_FORMAT.md` 最後一節：部隊（師団／連隊）結構、勝利條件、劇本 header、將領 +12 +13 +14 +19 +21、兵器 +4 +5（推測）+10 +11 +13、
都市第二組三值與 +57 其他位元、駐軍槽後 2 bytes、半形字型排列、地形 high nibble、LZ entry 207–365。
