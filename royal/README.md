# SFC スーパーロイヤルブラッド 解析

KOEI，SFC（LoROM 1 MB，SRAM 8 KB）；北美版 *Gemfire*。FC 版（`~/works/famicom-re/royal`）的移植：名稱、4 劇本、部隊、戰場地形的資料表和 FC 版相同，
頭像、地圖、戰場的圖像是重畫的。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python royal/export.py [--rom ROM] [--us-rom ROM] [--out DIR] [--scale N]   # → royal/output/
.venv/bin/python royal/export_kaodata.py --out <kaodata>/data-local/royal-sfc
.venv/bin/python royal/verify_kaodata_export.py --dataset <kaodata>/data-local/royal-sfc
.venv/bin/python royal/verify_scenarios.py      # 約 15 秒
.venv/bin/python royal/verify_faces.py          # 約 45 秒
.venv/bin/python royal/verify_map.py            # 約 10 秒
.venv/bin/python royal/verify_battle_maps.py    # 約 2 分鐘
```

- ROM 預設讀 `roms/Super Royal Blood (Japan).zip`（`--rom` 也接受 .sfc）；英語名讀 `roms/Gemfire (USA).zip`，沒有就留空。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。驗證腳本需要 Mesen 2（`tools/mesen.py`）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：名稱表、相談役、劇本（家、人物、領地）、可選当主表、部隊、頭像、戰略地圖、戰場地圖；Gemfire 英語名 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `royal-sfc` |
| `verify_kaodata_export.py` | 資料集用參考渲染器重畫，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 4 劇本載入後 WRAM `$7E:C004` 與 ROM 區塊比對，串列指標另以串列檢查 |
| `verify_faces.py` | 改 WRAM 的可選当主表讓選家畫面畫出頭像 0–67，加上相談役畫面；從畫面 tilemap／VRAM／CGRAM 重畫比對 |
| `verify_map.py` | 劇本選單的戰略地圖：tilemap、tile、調色盤、像素、4 劇本的家標記 |
| `verify_battle_maps.py` | デモ的第一場戰鬥換入 30 張戰場地形，比對 WRAM 地形、BG2 tilemap、tile、調色盤、像素 |

## 輸出（`royal/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 64 人：姓名、英語名、年齢基數、頭像、登場劇本 |
| `characters.csv` | 4 劇本登場人物 37／44／44／39 筆：年齢、知力、武力、魅力、所在領地、家、身分、一族（推定）、未知欄 |
| `houses.csv` | 4 劇本的家 7／7／6／6 家：当主、玩家可選、領地、旗標位元（未解） |
| `provinces.csv` | 4 × 30 領地：英語名、支配家、金、食料、兵、開発、作物、民忠（推定名稱）、部隊槽、人物、相鄰、家標記格 |
| `units.csv` | 23 種第 5 部隊：英語名、數值、類別位元 |
| `battle_maps.csv`、`battle_maps/` | 30 張戰場（10×8 地形、160×128 PNG） |
| `royal.xlsx` | 以上各表 |
| `faces/`、`advisors/` | 頭像：64 人（`F04_エラン.png`）、4 相談役（`F64_シドー.png`） |
| `map.png` | 戰略地圖 120×160（含領地編號，不含家標記） |

kaodata 資料集 `royal-sfc`：64 人、68 張頭像（P64–67 group「相談役」，name 是相談役選單的名字），沒有頭像碼；reading 是片假名轉平假名；
調色盤只有一組（BG 調色盤 1）。

## 進度

- ✓ 名稱表（人物 64、領地 30 含相鄰與標記格、部隊 23、家名 41）、相談役名 4、Gemfire 英語名
- ✓ 4 劇本：ROM 區塊位置（`0xB45A + 0x76C s` → `$7E:C004`）、家、人物、領地；可選当主表
- ✓ 頭像 68 張（單一調色盤，bank 邊界每 34 張）；kaodata `royal-sfc`
- ✓ 戰略地圖（15×20 tilemap、LZ tile）與家標記
- ✓ 戰場 30 張（metatile、tile、川的動畫 tile、調色盤）
- 未解：劇本標頭、多個未知欄位、部隊頭像、漢字文字、寶石（docs §7）

## 驗證結果

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 4 劇本到選家畫面時 WRAM `$C004–$C76F` 與 ROM 區塊逐 byte（188 個執行期指標 byte 除外）；指標串成的「領地 → 人物」串列與人物 +5 一致 | 4 劇本各 1712/1712 bytes、串列 30/30 |
| `verify_faces.py` | 選家畫面把 `$65CD` 改成 0–67，遊戲畫的頭像從 BG1 tilemap＋VRAM＋CGRAM 重畫，與 `Rom.face_rgb` 逐 pixel；未改時是 エラン（4）；相談役畫面不改值 | 68/68、未改 = 4、相談役 64–67 一致 |
| `verify_map.py` | 劇本選單 4 劇本：BG2 tilemap、tile、BG 調色盤 0–7、重畫像素；BG1 家標記的位置與家 | 每劇本 300/300 格、292/292 tile、19200/19200 pixel、標記 27／30／28／25 個全對 |
| `verify_battle_maps.py` | デモ戰鬥換入 30 張地形，開戰約 1000 幀後比對 | WRAM 地形 30/30、BG2 30/30（各 320 格）、tile 30/30、調色盤 30/30、像素 30/30 |
| `verify_kaodata_export.py` | 參考渲染器與 `Rom.face_rgb`、checksums | 64/64、68/68、OK；kaodata `pnpm verify`：132 checked、0 mismatched |

另外對照畫面：選家畫面 エラン 82／87／76、19 才，第 1 回合 ペトアリア 金 216、食料 189、兵 156（ROM 值）。
