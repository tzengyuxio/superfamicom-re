# SFC スーパー大航海時代 解析

KOEI，SFC（LoROM 1 MB）。主角レオン、航海士 20 人、4 國 × 5 名提督、女性 20 人、港口 70 個（交易港 50、補給港 20）。
資料與文字編碼沿用 FC 版（`~/works/famicom-re/daikoukai`）：FC 的初始狀態（bank 57）、名稱資料（bank 58）、
世界地圖檔都原封不動搬進 SFC ROM，圖像則全部重做。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python daikoukai/export.py [--rom ROM] [--out DIR] [--no-map]   # → daikoukai/output/（CSV、XLSX、PNG）
.venv/bin/python daikoukai/export_kaodata.py --out <kaodata>/data-local/daikoukai-sfc
.venv/bin/python daikoukai/verify_kaodata_export.py --dataset <kaodata>/data-local/daikoukai-sfc
.venv/bin/python daikoukai/verify_persons.py     # 約 30 秒
.venv/bin/python daikoukai/verify_faces.py       # 約 2 分鐘
.venv/bin/python daikoukai/verify_maps.py        # 約 1.5 分鐘
.venv/bin/python daikoukai/verify_towns.py       # 約 2 分鐘
```

- ROM 預設直接讀 `roms/Super Daikoukai Jidai (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0x1696`）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`）。stderr 的 `Uninitialized memory read` 可用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、初始狀態（人物、能力、艦隊、建物旗標）、女性、港口、名稱表、頭像（專屬＋組合）、世界地圖、港町圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `daikoukai-sfc`（專屬 53 張＋4 頭型組合臉） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_persons.py` | 新遊戲時 WRAM 初始區塊、リスボン時的人物表／能力表／艦隊／建物旗標、檔案 handle |
| `verify_faces.py` | 序幕顯示レオン頭像時換成每個頭像碼，比對 VRAM 與 CGRAM |
| `verify_maps.py` | 改艦隊位置後出港，比對海面畫面的 tilemap、緯度組、CHR、調色盤 |
| `verify_towns.py` | 改目前港口（與建物旗標）後進港，比對港口記錄讀取位置、港町 BG2 tilemap、CHR、調色盤 |
| `tools/boot.py` | 共用的按鍵序列（新遊戲 → リスボン → 港務所 → 出港）與各 savestate frame |

## 輸出（`daikoukai/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 41 人（開局狀態）：姓名、身分、國（推定）、戰鬥／航海等級、年齡（推定）統率 判断 知力 勇気 強さ（主角＋航海士）、頭像、頭像碼、旗標、姓名指標；能力表 byte 6–9 以 hex 輸出（未解） |
| `girls.csv` | 女性 20 人：姓名、頭像（推定 k + 13） |
| `ports.csv` | 70 港：名稱、種類、地圖座標（chunk／metatile／像素）、緯度組、經濟圈、特產品、道具（推定）、未解 byte、建物旗標 |
| `nations.csv` | 4 國（推定國名）與各國提督、旗標同國的航海士 |
| `fleets.csv` | 開局 21 筆艦隊記錄：位置、座標相同的港口；其餘 bytes 以 hex 輸出（未解） |
| `names.csv` | 交易品 26、大砲 3、船首像 6、船種 6、木材 4、桅 3、帆 2 |
| `daikoukai.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`portraits/` | 每人頭像（`21_ジョアン.png`，組合臉已組好；女性 41–60）、全部專屬頭像 F00–F52 |
| `mob_parts/`、`mob_parts.png` | 組合臉 4 頭型 × 5 部位 × 4 頁的零件 |
| `map.png`、`map_small.png` | 世界地圖 16128 × 8064（各緯度組用調色盤第 0 格、海用 `SEA_CHR` 那一格）；1/4 縮圖標上港口（紅＝交易港、黃＝補給港） |
| `towns/` | 70 港的港町圖（開局建物旗標）；`town_flags_XX.png` 為旗標 bit 2／bit 4 四種組合 |

## 進度

- ✓ 文字（JIS X0201 半形假名，與 FC 相同；不需字碼表，所以沒有 `data/`）
- ✓ 初始狀態：人物 41、能力 21、艦隊 21（位置）、建物旗標 70；與 WRAM 完全一致
- ✓ 女性 20 人姓名（頭像對應推定）
- ✓ 港口 70：名稱、座標、屬性（經濟圈、特產品、道具推定）
- ✓ 名稱表：交易品、大砲、船首像、船種、木材、桅、帆
- ✓ 頭像：專屬 53 張、組合臉 4 頭型（代碼 ≥ 0x1000）；kaodata 資料集 `daikoukai-sfc`
- ✓ 世界地圖：72 × 36 chunk、18 種 metatile、4 個緯度組的 CHR 與調色盤
- ✓ 港町圖（戰術地圖的替代）：所有港共用一套圖，零件依建物旗標 bit 2／bit 4 增減
- … 未解：海戰畫面（戰術地圖）、港町 BG1 的船與文字窗、海面與調色盤動畫順序、出港後艦隊記錄的座標意義、市場行情、船隻資料、多個未知欄位（ROM_FORMAT.md §10）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_persons.py` | 新遊戲複製完初始區塊（frame 2126）時 WRAM `$7E:DF02` 與 ROM `0xF4FE` 0x1286 bytes 比對；リスボン（frame 11766）時人物表、航海士能力列、主角姓名、艦隊 0 位置、建物旗標；handle `$1E1C`、`$1E0E` 指向的 ROM 位移 | 4742/4742 bytes；8 項全 OK（31 秒） |
| `verify_faces.py` | 序幕 VM pc `$7E:4FA7` 時把頭像碼寫進 `$F295`，比對 VRAM 0x2B20 的 960 bytes 與 CGRAM 調色盤 5；未改動 = レオン（頭像 0） | 專屬 53/53、組合 80/80（提督 20 種＋每頭型每部位每頁各一的 60 種）、OK（134 次，110 秒） |
| `verify_maps.py` | 港務所改艦隊位置 `$E564`（9 個港口＋南北極各一處）後出港，比對 28 × 28 畫面的 BG1／BG2 tilemap、`$F164` 緯度組、陸地 CHR 72 張、BG 調色盤 2 | 12/12 處：tile 784/784（リスボン 780＋港口記號 4）、緯度組 0–3 都出現、CHR 72/72、調色盤皆為該組 4 格之一（84 秒） |
| `verify_towns.py` | 進港前改 `$EF69`（70 港）與 `$EE78 + p` 建物旗標（9 種），比對遊戲對 DATA 檔的 seek 位置、BG2 tilemap 32 × 28、CHR、8 組調色盤 | seek 79/79、tilemap 79/79（70 港開局旗標＋9 次改旗標）、CHR 2/2（港 0、55，水面動畫 32 張另計，24 張在某次與初始格相同）、調色盤 79/79、OK（109 秒） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對、checksums | 61/61、53/53、OK |

名稱與座標的字串、表格格式和 FC 版逐 byte 相同（FC 版已驗證）；SFC 版另外確認遊戲進港時讀的正是 `DATA + 0x12D4 + 19 × 港號`（verify_towns.py）。
女性頭像（k + 13）與國籍（旗標高 4 bit）未在 SFC 遊戲中驗證，標為推定。
