# SFC スーパー三國志 解析

KOEI，SFC（HiROM 1 MB，只有一個版本）。FC 版 `三國志`（`~/works/famicom-re/sangokushi/`，kaodata `san1-fc`）的移植：劇本 5、人物 255、國 58（15 州）、勢力 14，數量都和 FC 一樣。文字是 KOEI 自訂的兩 byte 字碼（921 字）＋半形片假名。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python sangokushi/export.py [--rom ROM] [--out DIR]       # → sangokushi/output/（CSV、XLSX、PNG）
.venv/bin/python sangokushi/export_kaodata.py --out <kaodata>/data-local/san1-sfc
.venv/bin/python sangokushi/verify_kaodata_export.py --dataset <kaodata>/data-local/san1-sfc
.venv/bin/python sangokushi/verify_scenarios.py                 # 約 20 秒
.venv/bin/python sangokushi/verify_persons.py                   # 約 2 分鐘
.venv/bin/python sangokushi/verify_countries.py                 # 約 4 分鐘
.venv/bin/python sangokushi/verify_faces.py                     # 約 4 分鐘
.venv/bin/python sangokushi/verify_text.py                      # 約 1.5 分鐘
.venv/bin/python sangokushi/verify_maps.py                      # 約 2 分鐘
```

- ROM 預設直接讀 `roms/Super Sangokushi (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0xF037`），savestate 重播用共用的 `tools/replay.py`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖國號用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`）。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninitialized` 濾掉。一個 process 只能開一次 Mesen，需要兩個 savestate 的腳本（`verify_countries.py`、`verify_maps.py`）會自己開子程序。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：字型與文字、名表、劇本（國／勢力／人物的複製與修補）、靜態國表、州、頭像（肖像＋男女組合臉）、大地圖（含支配勢力上色層）、戰場（格子、tilemap、城位置） |
| `data/charset.txt` | 字表：字型 921 字 → 字元（32 字一行，`#` 開頭是註解） |
| `tools/sequences.py` | 按鍵序列（劇本一覽、189 年曹操的指令畫面、情報子選單、全圖、對 5 國開戰）與 `*n` 展開（`replay.py` 不支援） |
| `tools/printf.py` | 攔遊戲的 printf `$C2:16DC`，收集格式位址與引數（數字、`%s` 指標），給驗證腳本用 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `san1-sfc`（肖像 128＋男性組合 6 型＋女性組合 52 張） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；頭像碼；checksums |
| `verify_scenarios.py` | 5 個劇本到君主選擇畫面，WRAM 國／勢力／人物區塊與 ROM（複製＋修補）逐 byte 比對；可選君主 |
| `verify_persons.py` | 人物 1–255 分批換進曹操所在的國，攔武将一覽的 printf |
| `verify_countries.py` | 領地一覽（全部 58 國設成曹操的）與他国詳細（57 國），攔 printf |
| `verify_faces.py` | 頭像碼 0–0x132 全部換進曹操的詳細畫面，比對 VRAM、OAM、CGRAM |
| `verify_text.py` | 921 字全部換進人名，比對遊戲畫在 VRAM 的字 |
| `verify_maps.py` | 大地圖（BG1／BG2、上色層、調色盤，7 組支配勢力）與 58 張戰場（改被攻打的國，讓遊戲自己載入） |

## 輸出（`sangokushi/output/`）

| 檔案 | 內容 |
|------|------|
| `scenarios.csv` | 劇本 5：名稱、開始年、可選君主、勢力數 |
| `persons.csv` | 人物 255：姓名、讀音、生年、身体 知力 武力 カリスマ 運勢、頭像碼與種類 |
| `scenario_persons.csv` | 5 劇本 × 255：年齡、身分（君主／太守／武將／在野）、所屬、所在國、能力、忠誠、兵士、兵忠、訓練、武装、水軍、旗標與未解欄位原始值 |
| `countries.csv` | 國 58：州、相鄰國、城位置（欄,列）、靜態表未解欄位 |
| `scenario_countries.csv` | 5 劇本 × 58：支配勢力、太守、金、兵糧、土地、洪水、治水、民忠、人口、名馬、鉄、城、未解欄位原始值 |
| `states.csv` | 州 15：名稱、讀音、所含國 |
| `factions.csv` | 各劇本存在的勢力：君主、可選、國數、武將數、娘、未解欄位原始值 |
| `battle_fields.csv` | 戰場 58：LZ entry、開始時城數、城位置數、各地形格數（含城） |
| `faces.csv` | 頭像碼 307：種類、使用者、組合臉的型與部位 |
| `sangokushi.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`portraits/`、`composites/` | 人物 1–255 的頭像（`001_曹操.png`）、肖像 000–127、男性組合 `male_080`–`male_0FE`、女性組合 `female_0FF`–`female_132` |
| `map.png` | 大地圖 240 × 176（海的調色盤第 4 幀） |
| `map_owners_1.png`–`map_owners_5.png` | 各劇本開始時的支配勢力上色（遊戲的顏色）＋國號，放大 4 倍 |
| `battle/` | 58 張戰場（224 × 200，`05_冀州.png`，含劇本開始時的城） |
| `font.png` | 921 字的字型總覽 |

## 進度

- ✓ 壓縮（共用 `tools/koei_lz.py`；指標表 `0xED802` 817 項，另有兩段直接位址的串流）
- ✓ 字型 921 字與字表、兩 byte 字碼與跳脫碼 `0x9140 + k`、半形片假名、`1B` 換色碼
- ✓ 名表 256 項（讀音、姓名、頭像碼、生年）；和 FC 版的人名差異已列出（ROM_FORMAT.md §4）
- ✓ 劇本 5 個：國 58 × 30、勢力 14 × 77、人物 256 × 18 的 ROM 複製與劇本 2–5 修補表
- ✓ 人物：5 能力、忠誠、水軍、兵士、所在國、所屬勢力、兵忠、武装、訓練、年齡
- ✓ 國：金、兵糧、土地、治水（洪水）、人口、民忠、名馬、鉄、城、支配勢力、太守；靜態表的州與相鄰國；州 15
- ✓ 勢力：君主、可選、娘
- ✓ 頭像：肖像 128、男性組合 6 型 127 個、女性組合 2 型 52 個；調色盤；kaodata 資料集 `san1-sfc`
- ✓ 大地圖：BG1 字元／tilemap／海的調色盤循環；支配勢力上色層（58 個區域 ↔ 國、顏色 = 勢力 + 1）
- ✓ 戰場 58 張：格子（地形＋布陣區）、tilemap、字元、調色盤（含循環）、城位置表與開戰時放城的規則
- … 未解：國 +0–1、+13、+16、+17、+18 高位、+19、+20–29、靜態表旗標與 x／y、開局處理、在野的計算；人物 +7 bit 1、+15–17；勢力 +2、+7–20、+21–76；遊戲找上色區域的方式與國標籤位置；女性組合臉的用途；戰鬥部隊與流程（ROM_FORMAT.md §10）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 5 劇本各跑到君主選擇畫面：WRAM `$2052` 國 58 × 30、`$2722` 勢力 14 × 77、`$2B57` 人物 256 × 18 與 `Rom.scenario_wram` 逐 byte 比對；攔 printf `$C1:D337`／`$C1:D33E` 的可選君主 | 5 劇本：國 1740/1740、勢力 1078/1078、人物 4608/4608 bytes 相同；可選君主 5/5 劇本相同，OK（18 秒） |
| `verify_persons.py` | 劇本 1 曹操的指令畫面存 savestate；43 輪各把 6 人移到 7 國／勢力 1（原本的人移出），兵忠／武装／訓練寫測試值，開武将一覽兩組欄位，攔 printf：姓名指標、身分、年齡、5 能力、忠誠、兵士/100、兵忠、訓練、武装、水軍 | 255/255 人：姓名、身分、年齡、5 能力、忠誠、兵士、兵忠、訓練、武装、水軍全部相同，OK（118 秒）。參考：[EXT] kaodata-re 能力表 253/255 相同（郭図、龐徳 該表知力／武力對調） |
| `verify_countries.py` | 子程序先讀他国地圖的國標籤 sprite 位置；1 輪把 58 國支配勢力都設成 1，翻領地一覽 8 頁 × 2 組欄位；57 輪把指標移到各國標籤開他国詳細；期望值用同一輪的 WRAM 以 `rom.py` 解碼 | 開局處理改動 +22（58 國）、+13（25 國）、+2／+6／+7（少數國）；領地 58/58、他国 57/57（7 國是自己，不能選），OK（244 秒） |
| `verify_faces.py` | 曹操的詳細畫面，`$C1:143F` 進入時把頭像碼換成 0–0x132（307 輪），比對 VRAM `0xEC80` 960 bytes、OAM 30 個 sprite、CGRAM `0x120` | 肖像 128/128、男性組合 127/127、女性組合 52/52；sprite 307/307、調色盤 `0x4E711` 307/307，OK（241 秒） |
| `verify_text.py` | 44 輪把全部名表的 3 個漢字碼換成待測字（每輪 7 人 × 3 字），開武将一覽，在 VRAM 找連續 3 字 × 4 個 2bpp tile | 921/921 字（含跳脫碼的 192、448、704），OK（96 秒） |
| `verify_maps.py` | 大地圖：在新遊戲最後一次按鍵前存 savestate，7 輪設定支配勢力（劇本 1–5、c mod 15、c // 15），開全圖比對 VRAM `0x9800`、`0xA020`、`0x3800`、`0x4020`（上色層逐 pixel）、CGRAM 調色盤 2、3。戰場：對 5 國開戰前存 savestate，58 輪把 `$2720` 改成 c 國，比對 WRAM `$7F:8000`、`$9499`、VRAM `0x3800`、`0x4C00`、CGRAM 調色盤 5–7；另 1 輪不改（遊戲自己選 5 國） | 大地圖 7/7 輪：BG1 660/660、字元相同、BG2 660/660、上色層 42240/42240 px、調色盤 2 是循環幀之一、調色盤 3 相同（劇本 1 遊戲把 9 國的支配勢力 11 改成 0，以畫面當時的 WRAM 為準）；戰場：遊戲自己選的 5 國相同，58/58 張 tilemap、格子（含 233 個城）、BG2、字元、調色盤 5–7 相同，OK（131 秒） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_pixels` 逐 pixel 比對、頭像碼、調色盤、checksums | 255/255、肖像 180/180、頭像碼 255/255、checksums OK（不到 1 秒） |

另外對照遊戲畫面：曹操的武將詳細畫面截圖，頭像以 OBJ 調色盤 1 渲染後與截圖逐 pixel 相同（最初誤用 BG 調色盤 3，靠這張截圖改正）。
