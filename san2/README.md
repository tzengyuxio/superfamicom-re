# SFC スーパー三國志II 解析

KOEI，1991，SFC（LoROM 1 MB）。FC 版三國志II 的移植，資料表大多和 FC 版相同（對照見 ROM_FORMAT.md §9）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python san2/export.py [--rom ROM] [--out DIR]             # → san2/output/（CSV、XLSX、PNG）
.venv/bin/python san2/export_kaodata.py --out <kaodata>/data-local/san2-sfc
.venv/bin/python san2/verify_kaodata_export.py --dataset <kaodata>/data-local/san2-sfc   # 約 2 分鐘
.venv/bin/python san2/verify_scenarios.py                          # 約 10 秒
.venv/bin/python san2/verify_maps.py                               # 約 45 秒
.venv/bin/python san2/tools/kanji_sheet.py                         # 字碼對照圖 → output/kanji_sheet.png

# 重建漢字碼對照 data/kanji_ext.json（需要 kaodata-re 的 PC 版人物表）
.venv/bin/python san2/tools/build_kanji_map.py --pc <kaodata-re>/PERSONS_TABLE/san2_persons.csv
```

- ROM 預設直接讀 `roms/Super Sangokushi II (Japan).zip`。`--rom` 也接受 .sfc 或 Rev 1 的 zip，資料表相同。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。
- 驗證腳本需要 Mesen 2（`tools/mesen.py` 用 ctypes 呼叫 MesenCore）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：檔案表、人物、配置、州、相鄰、字型、頭像、大地圖、戰場 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `san2-sfc` |
| `verify_kaodata_export.py` | 資料集與 ROM、checksums、模擬器畫面三方比對 |
| `verify_scenarios.py` | 6 劇本開局 WRAM 與 ROM 解碼比對 |
| `verify_maps.py` | 大地圖與 41 張戰場，和模擬器 VRAM 比對 |
| `tools/face_capture.py` | 在模擬器裡換王朗的頭像碼，讀畫面像素 |
| `tools/battle_capture.py` | 在模擬器裡開戰（袁術攻打州 20），換掉戰場資料，讀 tilemap |
| `tools/build_kanji_map.py` | 從 PC 版姓名推出漢字碼對照 |
| `tools/kanji_sheet.py` | ROM 字形與對照字並排的檢查圖 |
| `data/kanji_ext.json` | 漢字碼 → 漢字（外部資料推得，已用 ROM 字形核對） |

## 輸出（`san2/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 352 人：[EXT] 姓名、漢字碼、讀音、才智、戰力、號召、義理、人德、野望、相性、親族、生年、登場年、頭像碼 |
| `person_scenarios.csv` | 6 劇本 × 在場人物：身分（君主／武將／在野／未登場）、州、[EXT] 君主、忠誠、兵士、年齡 |
| `provinces.csv` | 6 劇本 × 41 州：勢力、[EXT] 君主、人口、金、兵糧、民忠、土地、治水、馬、信 |
| `adjacency.csv` | 41 州的六角座標、6 方向的鄰州、戰場地形格數 |
| `san2.xlsx` | 以上四張表（需 openpyxl） |
| `faces/`、`portraits/` | 每人頭像（`000_曹操.png`）、專屬頭像 P001–P208 |
| `mob_parts.png`、`mob_parts/` | 組合臉零件總覽與各零件 |
| `map.png` | 大地圖（未上勢力色的原圖） |
| `battle_maps/` | 41 張戰場（01–41） |
| `province_hex.png` | 州的六角格相鄰圖 |
| `china_battle_map(_labeled).png` | 41 張戰場依相鄰關係拼成的全中國戰場 |

## 進度

- ✓ 人物 352 人：讀音、7 項能力、親族、生年、頭像碼；每劇本的所在州、身分、忠誠、初期兵士、登場年
- ✓ 姓名漢字 387 個碼：由外部資料推出，再用 ROM 字型（`0x80000`）逐字核對，修正 6 字
- ✓ 6 劇本 × 41 州：金、兵糧、人口、勢力、土地、民忠、治水、馬、信
- ✓ 州相鄰表（六角格）
- ✓ 頭像：專屬 208 張、組合臉（8 頭型 × 5 區域 × 4 記錄，4 組調色盤）；kaodata 資料集 `san2-sfc`
- ✓ 大地圖（ROM 渲染）
- ✓ 41 張戰場（13 × 12 六角格，7 種地形）與全中國拼接
- … 未解：劇本標頭後 18 bytes、勢力上色的州範圍、佈陣圖、選單文字編碼、道具／事件（ROM_FORMAT.md §10）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_kaodata_export.py` | 參考渲染器與 ROM 組圖逐 pixel 比對、checksums；模擬器裡把王朗的頭像碼換成每個人用到的碼，比對畫面 | 560/560、OK、352/352 |
| `verify_scenarios.py` | 6 劇本選完後的 WRAM（州記錄、人物記錄）和 ROM 解碼比對 | 州 41/41 × 6；人物 150/203/210/214/196/183 全部相符 |
| `verify_maps.py` | 大地圖畫面的 VRAM tile／調色盤和 ROM 比對；41 張戰場逐張換進州 20 開戰，比對 tilemap、地形 tile 與調色盤 | 504/504、28/28、41/41 |
| `tools/kanji_sheet.py` | ROM 字形和對照字並排，目視核對 | 387/387 |

另外在模擬器追蹤了開戰時的 ROM 讀取：遊戲只讀 `0x322D4 + 78 × 19` 這一張戰場。
