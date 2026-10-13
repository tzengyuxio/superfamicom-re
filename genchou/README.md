# SFC スーパー蒼き狼と白き牝鹿・元朝秘史 解析

KOEI，1993，SFC（HiROM 1.5 MB）。4 個劇本（1184／1206／1271／1185 年，第 4 個只在劇本 1 統一モンゴル後出現），モンゴル編 14 地域、世界編 33 國。文字是自訂碼：半形假名＋2046 字的漢字字型。FC 版（`~/works/famicom-re/genchou/`）的人物、國、兵科、戰場地圖等表格內容大多相同。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python genchou/export.py [--rom ROM] [--out DIR]          # → genchou/output/（CSV、XLSX、PNG）
.venv/bin/python genchou/export_kaodata.py --out <kaodata>/data-local/genchou-sfc
.venv/bin/python genchou/verify_kaodata_export.py --dataset <kaodata>/data-local/genchou-sfc
.venv/bin/python genchou/verify_scenarios.py                   # 約 15 秒
.venv/bin/python genchou/verify_persons.py                     # 約 3 分鐘
.venv/bin/python genchou/verify_countries.py                   # 約 5 分鐘
.venv/bin/python genchou/verify_faces.py                       # 約 4 分鐘
.venv/bin/python genchou/verify_map.py                         # 約 30 秒
.venv/bin/python genchou/verify_battle_maps.py                 # 約 2.5 分鐘
```

- ROM 預設直接讀 `roms/Super Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0x9C57`）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用 `tools/replay.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninit` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字與字型、劇本（人物、國、王家、女性、家族）、主檔表（兵科、交易品、文化…）、頭像（專屬＋組合）、大地圖、戰場地圖 |
| `data/charset.txt` | 字型 2046 字 → 字元對照（JIS 順序子集） |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `genchou-sfc`（97 張專屬頭像＋56 個組合臉頭） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 4 劇本載入後的 WRAM 與 ROM 區塊逐 byte 比對 |
| `verify_persons.py` | 人物記錄逐一寫進政治顧問確認卡，讀畫面上的能力、體力、年齡 |
| `verify_countries.py` | 國記錄逐一寫進オノン河流域，讀主畫面國資訊的金、食糧、人口與三個數值 |
| `verify_faces.py` | 每個頭像碼寫進確認卡（男）與后妃畫面（女），比對 VRAM tile、tilemap 調色盤號、CGRAM |
| `verify_map.py` | 4 劇本主畫面的大地圖 tile、tilemap、調色盤 |
| `verify_battle_maps.py` | 47 張戰場：強制遠征目標，比對 tilemap、tile 組、調色盤 |

## 輸出（`genchou/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 4 劇本的人物（47／72／69／70）：王家、所在國、身分、體力／上限、戦闘 政治 魅力 指揮（E–A）、年齢、文化（推測）、頭像碼、未解 bits |
| `family.csv` | 家族區 8 人（カサル…チラウン、タイチャル） |
| `women.csv` | 4 劇本的女性（14／32／23／23）：所在國、頭像碼、未解欄位 |
| `countries.csv` | 4 劇本 × 國（14／33／33／33）：王家、相鄰、金、食糧、人口、住民配分、畫面值 +20..+22、部隊（推測）、未解欄位 |
| `houses.csv` | 4 劇本的王家（13／29／23／30）：國王、所轄國、+23（推測為文化） |
| `regions.csv` | モンゴル 14 地域＋世界 33 國：名稱、大地圖標籤位置、戰場圖與 tile 組 |
| `units.csv` | 16 兵科：分類、戦意、機動、近接、突撃、矢弾、防御、特殊、徵兵價格、電腦優先順 |
| `goods.csv` | 12 交易品 × 4 商人的表值（推測為價格） |
| `battle_maps.csv`、`battle_cells.csv` | 47 張戰場；每格（14 × 10）的地形與出入口（相鄰國） |
| `genchou.xlsx` | 以上各表（需 openpyxl） |
| `faces/` | 每劇本每人與每位女性的頭像（`s2_012_チンギス・ハーン.png`、`s1_w00_ボルテ.png`） |
| `portraits/` | 專屬頭像 00–96（57 起是女性） |
| `heads.png` | 56 個組合臉頭（每頭：5 部位全用版本 0、全用版本 1） |
| `map_mongol.png`、`map_world.png` | 大地圖 184 × 192（地域內部是遊戲執行時填色的顏色 15）；`_labels` 放大 4 倍並標地名 |
| `battle/` | 47 張戰場地圖（224 × 168） |
| `font.png` | 2046 字字型總覽 |

## 進度

- ✓ 壓縮（共用 `tools/koei_lz.py`）、文字（半形假名＋2046 字字型，字表 `data/charset.txt`）
- ✓ 4 劇本：標題、年、載入程式與 5 個 WRAM 區域（劇本 4 的續行載入方式）
- ✓ 人物：姓名、王家、所在、體力（現在／上限）、戦闘 政治 魅力 指揮、年齢、頭像碼；身分 3 = 国王
- ✓ 國：相鄰（與戰場出入口一致）、金、食糧、人口、畫面上的三個數值、王家的國串列
- ✓ 王家：名稱、國王、所轄國；女性：姓名、所在、頭像碼；家族區
- ✓ 主檔表：兵科、徵兵價格、電腦優先順、交易品與商人名稱、官職、文化、氣候分類名稱
- ✓ 頭像：專屬 97 張＋組合臉 56 頭（5 部位 × 2 版本）；kaodata 資料集 `genchou-sfc`
- ✓ 大地圖：モンゴル／世界兩張（tile、tilemap、調色盤）
- ✓ 戰場地圖：47 張（記錄＝FC 版；SFC 的 tile 組 5 種與調色盤）
- … 未解：國的多個欄位與氣候分類來源、大地圖王家填色、女性 +16/+17、區塊 B 後段、子女格式、事件、戰場 sprite 與城內圖（ROM_FORMAT.md §9）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 劇本選單存檔；每個劇本先清空 5 個 WRAM 區域再選，讀回 `$7E:37F7`（區塊 A）、`$7E:4F38`（區塊 B）、`$7E:4C94`（家族）、`$7E:2000`（地名）、`$7E:545C`（標籤位置）；劇本 4 改 `$C4:2B4F` 強制載入 | 4 劇本全部 5277/5277、1316/1316、676/676、528/528、66/66 bytes；WRAM 解出的人物、國、王家、女性 = ROM 解出的 |
| `verify_persons.py` | 人事 → 政治顧問 → カサル 的確認卡；把 258 名劇本人物＋8 名家族的 +18..+21 寫進カサル的記錄，讀 BG3 上的 政治 指揮 戦力 魅力、體力「現在/上限」、年齢 | 266/266 |
| `verify_countries.py` | 劇本 1 開場前把 113 筆國記錄的 +9..+14、+20..+22 寫進オノン河流域，讀主畫面國資訊 | 113/113 |
| `verify_faces.py` | 確認卡（男，`$C4:5EDB`）與后妃畫面（女，`$C4:5F63`）；改寫記錄的頭像碼，比對 VRAM 960 bytes、BG tilemap 的調色盤號、CGRAM 調色盤 | 男專屬 57/57、男組合 201/201、女專屬 40/40、女組合 33/33 |
| `verify_map.py` | 4 劇本主畫面的 BG2：552 tile（顏色 15 以外逐 pixel）、tilemap、CGRAM 調色盤 6 | 4/4 全部一致 |
| `verify_battle_maps.py` | 遠征ゴルゴナク河原，把 `$C7:92F4`／`$C7:9395`／`$C7:9527` 讀國編號的指令改成常數、`$7E:5425` 設世界旗標，比對戰場 BG2 tilemap、tile 組、調色盤 | 47/47（tile 組 0–4：20／6／5／6／10 張） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對、checksums | 321/321 人（女 73）、97/97 張、OK |

另外：戰場記錄 47 筆和 FC 版逐 byte 相同；國的相鄰欄位和戰場出入口格 47/47 一致；人名、王家名、地名的 152 個漢字逐一和字形對照過。
