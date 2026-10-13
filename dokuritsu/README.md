# SFC 独立戦争 Liberty or Death 解析

KOEI，1994，SFC（HiROM 1.25 MB）。美國獨立戰爭，劇本只有 1775 年一個，人物 250 人、地點 53 個（15 州、3 區）、陣營 アメリカ／イギリス。文字是半形假名＋遊戲自訂順序的漢字碼。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python dokuritsu/export.py [--rom ROM] [--out DIR]          # → dokuritsu/output/（CSV、XLSX、PNG）
.venv/bin/python dokuritsu/export_kaodata.py --out <kaodata>/data-local/dokuritsu-sfc
.venv/bin/python dokuritsu/verify_kaodata_export.py --dataset <kaodata>/data-local/dokuritsu-sfc
.venv/bin/python dokuritsu/verify_scenarios.py                    # 約 1 分鐘
.venv/bin/python dokuritsu/verify_persons.py [--quick]            # 約 3 分鐘（--quick 約 45 秒）
.venv/bin/python dokuritsu/verify_faces.py [--quick]              # 約 3.5 分鐘（--quick 約 50 秒）
.venv/bin/python dokuritsu/verify_maps.py                         # 約 4 分鐘
.venv/bin/python dokuritsu/verify_battle_maps.py [--quick]        # 約 7 分鐘（--quick 約 1.5 分鐘）
```

- ROM 預設直接讀 `roms/Dokuritsu Sensou - Liberty or Death (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0xA0D9`，和覇王伝同一套；指標表 `0x39649`，419 筆）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`）。stderr 的 `Uninitialized memory read` 可以用 `2>&1 | rg -v Uninit` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、人物、地點、州、1775 年劇本（人物狀態、地點狀態、陣營）、頭像（專屬＋組合）、大地圖 3 區、HEX 戰場 53 張 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `dokuritsu-sfc`（專屬頭像 174 張＋4 型組合臉） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；頭像碼；checksums |
| `verify_scenarios.py` | 開局 6 塊 WRAM 與 ROM 逐 byte 比對；掛 vprintf 比對選陣營畫面、指令畫面、人物列表的欄位 |
| `verify_persons.py` | 選陣營畫面把ワシントン換成每個人（改 10 處 `LDA #$00EE`），比對姓名指標、能力、名声、頭像 tile 與調色盤 |
| `verify_faces.py` | 同一畫面把ワシントン的頭像碼換成每個碼，比對 VRAM 的 960 bytes 與 CGRAM |
| `verify_maps.py` | 第一個指令畫面的大地圖：改 LZ 指標換成 3 區，比對 VRAM tile、tilemap、調色盤 |
| `verify_battle_maps.py` | 看電腦戰鬥：改地點編號換成 53 張，比對 WRAM 複本與遊戲建好的 BG2 tilemap |
| `tools/replay.py` | savestate 重播（照抄 `haouden/tools/replay.py`） |

## 輸出（`dokuritsu/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 250 人：名、姓、首字母、体力 統率力 戦術力 指導力、頭像碼、未解欄位 |
| `persons_1775.csv` | 1775 年人物狀態：所在（地點或待機陣營）、体力、名声、忠誠、所屬（推測）、階級（推測）、未解欄位 |
| `locations.csv` | 53 地點：番號、地區、州、港（推測）、相鄰、未解欄位 |
| `locations_1775.csv` | 1775 年地點狀態：支持、食糧、武器（推測）、弾薬（推測）、擁有者代碼（未解）、駐在人物 |
| `states.csv` | 15 州的略稱與全名 |
| `sides.csv` | 2 陣營：待機人物、資金（推測） |
| `battle_maps.csv` | 53 張戰場：各地形格數（地形名稱推測） |
| `battle_cells.csv` | 53 × 168 格：地形、未解位元、疊加碼 |
| `dokuritsu.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`portraits/` | 每人頭像（`238_ジョージ・ワシントン.png`，組合臉已組好）、全部專屬頭像 000–173 |
| `map_0_北部.png` … `map_2_南部.png` | 大地圖 3 區（224 × 192，擁有者上色前的白底） |
| `battle/` | 53 張 HEX 戰場（224 × 200，`10_ポーツマス.png`） |

## 進度

- ✓ 壓縮（共用 `tools/koei_lz.py`）、文字（半形假名＋ESC 模式；漢字只對出 10 字）
- ✓ 人物 250 人：姓名、首字母、体力、統率力、戦術力、指導力、頭像碼
- ✓ 1775 年劇本：6 塊初始 WRAM 的 ROM 來源；人物狀態（串列、所在、体力、名声、忠誠）、地點狀態（人物串列、支持、食糧、兩種物資）、陣營（待機串列）
- ✓ 地點 53 個：名稱、相鄰、地區、州；州名 15 個
- ✓ 頭像：專屬 174 張＋組合臉 4 型（未壓縮部件）；kaodata 資料集 `dokuritsu-sfc`
- ✓ 大地圖 3 區（tile、tilemap 配置、調色盤）
- ✓ HEX 戰場 53 張（地形、疊加、tile、調色盤）
- … 未解：漢字字型、擁有者上色遮罩、多個未知欄位、戰場部隊／兵種（ROM_FORMAT.md §12）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 第 10172 幀 6 塊 WRAM vs ROM；選陣營畫面ワシントン的 `%s %s` 與 4 個數值；指令畫面的地點名與 4 個數值 vs 當下 WRAM 地點狀態；人物列表的「首字母.姓」順序 vs 地點的 WRAM 串列，3 個數值 vs 人物狀態 | 6/6 塊 0 byte 不同（4520 bytes）；ワシントン 97 88 98 80 全同；地點 6 スプリングフィールド 支持 71、+10 600、食糧 1848、+8 2151 全同；人物列表 8 人姓名順序同、8/8 列數值同；ALL OK，62 秒 |
| `verify_persons.py` | 250 人逐一顯示在選陣營畫面 | 姓名指標、統率力 戦術力 指導力、名声、頭像 tile、調色盤 各 250/250；ALL OK，179 秒 |
| `verify_faces.py` | 專屬 0–173、人物用到的 125 種組合碼、補 13 種「全部數字相同」的組合碼 | 174/174、125/125、13/13，調色盤全同；ALL OK，213 秒 |
| `verify_maps.py` | 3 區大地圖（北部原樣、中部／南部改 LZ 指標） | tilemap 572/672 同＋100 個外海動畫格、0 其他；調色盤（不含水的 9–11）同；像素除擁有者上色（→3/8/12）外 0 差異；ALL OK，234 秒 |
| `verify_battle_maps.py` | 53 張戰場逐一載入 | 未改動那場是地點 10、168/168 格、VRAM tile `0x2B9` = entry 241、調色盤 5 = `0x39DD2`；53/53 張 WRAM 複本同 ROM、8904/8904 格 tilemap 同；ALL OK，420 秒 |
| `verify_kaodata_export.py` | 參考渲染器 vs `Rom.face_rgb`、頭像碼、checksums | 250/250、174/174、OK |

欄位的標籤另對照畫面：選陣營畫面（統率力 戦術力 指導力 名声）、人物列表（体力 忠誠 名声）、指令畫面的圖示（支持、食糧、武器／弾薬圖示）。
