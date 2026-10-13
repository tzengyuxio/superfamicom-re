# SFC 信長の野望・天翔記 解析

KOEI，1996，SFC（HiROM 3 MB）。PC 版天翔記的移植，劇本只有 2 個（信長初陣 1547、信長包囲網 1571）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python tenshouki/export.py [--rom ROM] [--out DIR] [--scale N]   # → tenshouki/output/（CSV、XLSX、PNG）
.venv/bin/python tenshouki/export_kaodata.py --out <kaodata>/data-local/nobu6-sfc
.venv/bin/python tenshouki/verify_kaodata_export.py --dataset <kaodata>/data-local/nobu6-sfc
.venv/bin/python tenshouki/verify_faces.py                     # 約 5 分鐘
.venv/bin/python tenshouki/verify_scenarios.py
.venv/bin/python tenshouki/verify_maps.py
.venv/bin/python tenshouki/verify_field_maps.py               # 約 3.5 分鐘
```

- ROM 預設直接讀 `roms/Nobunaga no Yabou - Tenshouki (Japan).zip`，`--rom` 也接受 .sfc。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py` 用 ctypes 呼叫 MesenCore）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：解壓縮、人物、姓名、劇本人物、城、軍団、頭像、大地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `nobu6-sfc` |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 組圖逐 pixel 比對；checksums |
| `verify_faces.py` | 每個頭像碼換進模擬器，比對遊戲自己組出來的頭像 tile 與調色盤 |
| `verify_scenarios.py` | 2 劇本開局 WRAM（人物、城、軍団）與 ROM 解碼比對 |
| `verify_maps.py` | 第一回合畫面的大地圖 VRAM tilemap／tile／調色盤與 ROM 比對 |
| `verify_field_maps.py` | 330 張野戰地圖逐一換進一場野戰，比對 VRAM 的兩層 tilemap、戰場 tile 與調色盤 |
| `tools/face_capture.py` | 在模擬器裡換蠣崎季広的頭像碼，讀 VRAM 與 CGRAM |

## 輸出（`tenshouki/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 700 人：姓名（2 劇本寫法不同時另列）、生年、政治／戦闘／智謀上限、魅力、野望、父、頭像碼、未解欄位 |
| `person_scenarios.csv` | 2 劇本 × 在場人物（333／406）：狀態、身分、大名、軍団、城、年齢、政治／戦闘／智謀、忠誠、勲功、兵士、訓練、士気、部隊、4 種適性 |
| `castles.csv` | 2 劇本 × 128 城：国、地圖座標、軍団、大名、城郭、石高、商業、人口、民忠、徴兵 |
| `corps.csv` | 2 劇本的軍団：大名、軍団長、居城、金、米 |
| `tenshouki.xlsx` | 以上四張表（需 openpyxl） |
| `faces/`、`portraits/` | 每人頭像（`000_<姓名>.png`）、專屬頭像 P000–P311 |
| `face_packs.png` | 組合臉 19 包 × 4 張原圖 |
| `mob_parts.png`、`mob_parts/` | 組合臉零件總覽與各零件 |
| `map.png`、`map_terrain.png` | 大地圖（地形＋道路／只有地形），`--scale` 倍 |
| `map_castles.png` | 大地圖標上 128 城的編號與名稱 |
| `field_map.png` | 330 張野戰地圖拼成的全日本戰場圖（30 × 11 張，3840 × 1056 px） |
| `field_map_grid.png` | 同上，加上每張地圖的邊界與編號 |

## 進度

- ✓ 人物 700 人：姓名（每劇本一份）、生年、能力上限、魅力、野望、父子關係、頭像碼
- ✓ 2 劇本人物：能力（上限的百分比）、忠誠、勲功、所屬大名／軍団／城、兵士、訓練、士気、部隊、適性、狀態與身分
- ✓ 128 城：名稱（含館／本願寺等字尾規則）、国、地圖座標、石高、商業、人口、民忠、城郭、徴兵
- ✓ 軍団：居城、軍団長、大名、金、米
- ✓ 頭像：專屬 312 張、組合臉 19 包（上半／下半／眼／口 4 個零件槽 × 4 張），3 組調色盤；kaodata 資料集 `nobu6-sfc`
- ✓ 大地圖（150 × 65 tile，地形與道路兩層）
- ✓ 野戰地圖 330 張：全日本切成 30 × 11 張，一場野戰用城周圍的 3 × 4 張；拼成全日本戰場圖
- … 未解：攻城戰地圖、野戰地形格的值、人物 +10/+11 與旗標、城資料 +1–+6、姓名表後 3 bytes、姫與未登場人物的執行期位置、事件改名的城、B 鍵縮小地圖（ROM_FORMAT.md §10）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_faces.py` | 700 人用到的頭像碼與 P000–P311，逐一換成蠣崎季広的頭像碼後打開武将畫面，比對 VRAM 的 960 bytes tile 與 CGRAM 調色盤 9 | 716/716 |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對、checksums | 700/700、312/312、OK |
| `verify_scenarios.py` | 選完劇本後的 WRAM：人物 `$7E:3F70`、城 `$7E:882C`、軍団 `$7E:93AC`（串列連結由載入程式重建，另計） | 人物 333/333、406/406；城 128/128 × 2；軍団 128/128 × 2 |
| `verify_field_maps.py` | 蠣崎季広攻打三戸城的野戰：每輪把 2 張地圖換進戰場可見的位置，比對 BG1／BG2 tilemap；戰場 tile 與調色盤 3–6 | 330/330（119488 格，視窗遮住 8000 格另計）、512/512、OK |
| `verify_maps.py` | 第一回合畫面：地形 BG 與道路 BG 的可見範圍、地圖 tile 301 個、調色盤 3–5（動畫色除外） | 896/896、198/198（視窗遮住的格另計）、301/301、OK |

城座標用 `map_castles.png` 目視核對：每個標記都落在城圖示的右上角 tile。
