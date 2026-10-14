# SFC エアーマネージメントII 航空王をめざせ 解析

KOEI，SFC（LoROM 1 MB）。航空公司經營：4 劇本（1955／1970／1985／2000 年開始）、7 地區、89 都市、57 國、32 家預設航空公司、53 機種、12 製造商。程式是 C 編譯的原生 65816 程式（不是前作的 KOEI p-code），資源放在 196 個具名檔裡。沒有具名人物，頭像只有秘書、職員、國家代表、製造商代表。ROM 結構見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python airmanage2/export.py [--rom ROM] [--out DIR]     # → airmanage2/output/（CSV、XLSX、PNG）
.venv/bin/python airmanage2/export_kaodata.py --out <kaodata>/data-local/air2-sfc
.venv/bin/python airmanage2/verify_kaodata_export.py --dataset <kaodata>/data-local/air2-sfc
.venv/bin/python airmanage2/verify_scenarios.py                 # 約 35 秒
.venv/bin/python airmanage2/verify_cities.py                    # 約 200 秒
.venv/bin/python airmanage2/verify_aircraft.py                  # 約 80 秒
.venv/bin/python airmanage2/verify_faces.py                     # 約 220 秒
.venv/bin/python airmanage2/verify_maps.py                      # 約 35 秒
.venv/bin/python airmanage2/verify_text.py                      # 約 80 秒
```

- ROM 預設直接讀 `roms/Air Management II - Koukuu Ou o Mezase (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖與頭像總覽的標註用 macOS 的ヒラギノ角ゴシック。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用共用的 `tools/replay.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：檔案表、bank `$05` 的表（都市、航空公司、國家、地區、機種、製造商、關聯事業）、劇本開局狀態、世界事件、頭像、字型、世界地圖與地區地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 資料集 `air2-sfc`（35 張 portrait，沒有 character） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；group／name／沒有 label 與 code；checksums |
| `verify_scenarios.py` | 4 劇本的名稱與年份頁、開局 WRAM（劇本號、都市記錄、4 個複製表）與 ROM 逐 byte 比對 |
| `verify_cities.py` | 89 都市在地區地圖上的位置與名稱、地區分組；32 家預設航空公司與本社都市 |
| `verify_aircraft.py` | 53 機種在規格畫面上的名稱與數值；製造商選單的名稱 |
| `verify_faces.py` | 4 種頭像檔每張的 VRAM、30 組調色盤、秘書／職員／國家代表／製造商的描述規則 |
| `verify_maps.py` | 7 張地區地圖與世界地圖的 tilemap、tile、調色盤、都市 sprite |
| `verify_text.py` | 字型 713 字＋表外碼，替換遊戲字形查詢的輸入，比對查到的字形 |
| `tools/am2.py` | 驗證共用：按鍵序列、WRAM 位址、收集遊戲 printf／頭像繪製的 Lua（搭配 `tools/replay.py`） |
| `data/charset.tsv` | Shift-JIS 碼 → 字形（713 字，含與 Shift-JIS 不同的字形） |
| `data/kanji.txt` | 字型的 461 個漢字（字形順序） |

## 輸出（`airmanage2/output/`）

| 檔案 | 內容 |
|------|------|
| `cities.csv` | 89 都市：名稱、地區、國家（劇本 1）、可否當本社、預設航空公司、地區地圖與世界地圖位置 |
| `scenario_cities.csv` | 4 劇本 × 89 都市：國家、都市記錄的 3 個未解值與第二記錄 |
| `countries.csv` | 57 國：名稱、`$2E21` 各劇本的值（未解）、`$05:E815`（未解） |
| `areas.csv` | 7 地區：本社都市、其他都市、遮罩、頭像調色盤組 |
| `events.csv` | 55 筆世界事件：年、種類、對象、內容 |
| `aircraft.csv` | 53 機種：製造商、座席、航續距離、基準價格、燃費、整備性、生產開始、生產終了（推測）、旗標（未解） |
| `makers.csv` | 12 製造商：頭像、調色盤、機種清單 |
| `businesses.csv` | 15 個關聯事業名稱 |
| `init_tables.csv` | 開局從 ROM 複製的 4 個 WRAM 表（原始 bytes，未解） |
| `files.csv` | 196 個檔：位置、大小、LZ 解壓後大小 |
| `airmanage2.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`faces.png` | 35 張頭像（SECRET 7、STAFF 11、MAYOR 5、製造商 12 個描述）與總覽 |
| `world_map.png`、`world_map_cities.png` | 世界地圖 256 × 176；放大並標上 89 都市（位置用 `$05:E233`，未獨立驗證） |
| `area_maps/` | 7 張地區地圖 256 × 184 與標上都市的版本 |
| `font.png` | 字型 713 字總覽 |

## 進度

- ✓ 檔案表 196 檔、KOEI LZ（共用）
- ✓ 字型與文字編碼：記號 21、數字 10、英文 52、平假名 83、片假名 86、漢字 461（`data/charset.tsv`）
- ✓ 都市 89：名稱、地區、國家、地區地圖位置；預設航空公司 32
- ✓ 國家 57、地區 7、月、難易度、劇本名稱與年份
- ✓ 劇本 4：開局都市記錄（A／B 表與插值）、4 個複製表、世界事件 55 筆（國家變更）——WRAM 完全一致
- ✓ 機種 53：名稱、座席、航續距離、基準價格、燃費、整備性、生產開始年；製造商 12
- ✓ 頭像：4 檔 29 張圖、30 組調色盤、秘書／職員／國家代表／製造商的描述規則；kaodata 資料集 `air2-sfc`
- ✓ 世界地圖、7 張地區地圖
- － 戰術地圖：本作沒有戰鬥，不適用
- … 未解：都市記錄 byte 1–3、國家表 `$2E21` 等多個表的意義、事件的季與訊息欄、機種旗標與生產終了年、價格係數規則、關聯事業、世界座標的驗證、多數檔的用途（ROM_FORMAT.md §10）

## 驗證

所有驗證都在 Mesen 2 跑遊戲本身的程式（從開機按鍵進到對應畫面，savestate 後每輪改 WRAM 或攔截函式引數），比對遊戲印出的文字、WRAM、VRAM、CGRAM、OAM。

| 腳本 | 內容 | 結果（時間） |
|------|------|------|
| `verify_scenarios.py` | NEW GAME 後選各劇本：劇本頁印出的名稱與年份；開局後 WRAM `$24E9`、`$2CBD`（89 × 4）、`$3E37`（89 × 2）、`$2E21`、`$2955`、`$2AD5`、`$3DF7` 與 `rom.scenario_cities`／`init_tables` 逐 byte 比對 | 4 劇本名稱頁 OK；4 劇本 × 7 區塊全部一致（33 秒） |
| `verify_cities.py` | 每地區開新局到選本社畫面，把地圖游標放到 ROM 的都市位置，遊戲判定後印出的都市名 = ROM 名；本社都市 0–31 繼續開局，設定畫面印出的 (公司, ｍａｎ／ｃｏｍ, 本社都市) 配對 = 該都市的預設航空公司 | 都市 89/89；航空公司 32/32 輪 OK、印出 32 組不同的公司／本社配對（202 秒） |
| `verify_aircraft.py` | 規格畫面的 savestate，把每個機種記錄與編號寫進 `$3DC0`／`$3D42`，比對遊戲印出的名稱、航續、座席、燃費、整備性、生產開始年、價格；製造商選單印出的名稱 | 53/53（價格係數 FFFF 28、110% 12、80% 6、90% 7）；選單 8 次印出、製造商 [0, 2, 6, 8, 9] = ROM 名（81 秒） |
| `verify_faces.py` | 秘書第一則訊息前的 savestate：換掉頭像描述，比對 VRAM 960 bytes 與 CGRAM 第 4 列；開局 4 名玩家的秘書／職員描述；把秘書頭像呼叫改道到國家代表視窗 `$8C:8634`（89 都市、57 國）；規格畫面的製造商頭像 `$86:C77A` 換成 12 家 | 圖 30/30、調色盤 30/30、秘書／職員描述 25/25、國家代表每都市 89/89、每國 57/57、製造商 12/12（216 秒） |
| `verify_maps.py` | 地區選單 savestate：7 地區的 BG tilemap `$F000`、CHR `$4000`、CGRAM 第 1 列、都市 sprite（OAM）；玩到世界地圖比對 BG1／BG2 tilemap、CHR、CGRAM | 7 地區全對（都市 sprite 24/7/8/17/9/16/8 個全對），世界地圖 6 項全對（34 秒） |
| `verify_text.py` | 攔截字形查詢 `$00:B8DE` 換成待測碼：16×16 字比對複製到 `$0CE9` 的字形 bytes，8×16 字比對 `$00:BC5E` 寫出的 tilemap tile 號 | 記號 21/21、數字 10/10、英文 52/52、平假名 83/83、片假名 86/86、漢字 461/461、表外 4/4（79 秒） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對；group／name；沒有 label、code；checksums | 35/35、35/35、35/35、checksums OK（1 秒內） |
