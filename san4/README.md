# SFC 三國志IV 解析

KOEI，1994，SFC（HiROM 3 MB）。6 個劇本（189–235 年），462 人、43 都市。文字是 Shift-JIS（cp932），外加使用者外字區 `0xEB9F–0xEBFC` 的人名用字。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python san4/export.py [--rom ROM] [--out DIR]          # → san4/output/（CSV、XLSX、PNG）
.venv/bin/python san4/export_kaodata.py --out <kaodata>/data-local/san4-sfc
.venv/bin/python san4/verify_kaodata_export.py --dataset <kaodata>/data-local/san4-sfc
.venv/bin/python san4/verify_scenarios.py                    # 約 30 秒
.venv/bin/python san4/verify_faces.py [--quick]              # 約 5 分鐘（--quick 約 50 秒）
.venv/bin/python san4/verify_maps.py                         # 約 1 分鐘
.venv/bin/python san4/verify_persons.py                      # 與外部能力值表比對
.venv/bin/python san4/tools/ext_chars_sheet.py               # 外字對照圖 → output/ext_chars.png
```

- ROM 預設直接讀 `_original/sfc/Sangokushi IV (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0xF037`，和天翔記同一套）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py` 用 ctypes 呼叫 MesenCore）。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：字型與外字、人物、都市、劇本（人物、都市、勢力）、特殊能力、頭像（專屬＋組合）、大地圖、戰場地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `san4-sfc`（專屬頭像＋16 包組合臉） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 6 劇本在選君主畫面的 WRAM（劇本人物、都市、勢力）與 ROM 解壓結果逐 byte 比對 |
| `verify_faces.py` | 339 張專屬頭像＋259 種組合臉碼逐一換進劉繇的確認框，比對遊戲寫進 VRAM 的 tile 與調色盤 |
| `verify_maps.py` | 大地圖（mode 7 平面、調色盤、都市位置）、一場野戰與一場攻城戰的戰場地圖 |
| `verify_persons.py` | 人物姓名與五項能力值和外部資料比對 |
| `tools/ext_chars_sheet.py` | 外字字形與 `rom.EXT_CHARS` 指定的字並排的檢查圖 |

## 輸出（`san4/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 462 人：姓名、讀音、生年、統率 武力 知力 政治 魅力、頭像碼、關係、相性（推測）、未解欄位 |
| `person_scenarios.csv` | 6 劇本的登場人物（182／222／222／235／208／181）：年齢、勢力、身分（君主／太守／武将／在野／異民族）、所在、忠誠、能力、特殊能力 |
| `cities.csv` | 43 都市：讀音、大地圖位置（格）、相鄰都市 |
| `city_scenarios.csv` | 6 劇本 × 43 都市：勢力、太守、人口、金、兵糧、兵士、開発、治水、商業、技術、民忠、士気、訓練、弩、強弩、連弩、軍馬、発石 |
| `forces.csv` | 6 劇本的勢力：君主、本拠（君主所在）、都市、對其他勢力的友好度 |
| `abilities.csv` | 24 種特殊能力的位元 |
| `battle_maps.csv` | 88 張戰場：野戦 45 張（哪些「攻方→守方」用到）、攻城 43 張（各都市） |
| `battle_cells.csv` | 88 張戰場的每一格（20 × 11 六角格）：地形 byte、配置 byte（意義未解） |
| `san4.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`portraits/` | 每人頭像（`074_劉繇.png`，組合臉已組好）、全部專屬頭像 000–338 |
| `map.png`、`map_cities.png` | 大地圖 1024 × 768；放大 2 倍並標上 43 都市與相鄰連線 |
| `battle/` | 88 張戰場地圖（320 × 176，12 月的調色盤） |
| `font.png`、`ext_chars.png` | 1997 字的字型總覽；外字對照圖 |

## 進度

| 項目 | 狀態 | 證據 | 說明 |
|------|------|------|------|
| 壓縮、字型 1997 字、外字 47 個 | ✅ | code | 共用 `tools/koei_lz.py`；Shift-JIS 碼表；外字 `rom.EXT_CHARS`，`EBF8` 未辨識；見 ROM_FORMAT §2、§3 |
| 人物 462 人 | ✅ | emu+capture+cross | 姓名、讀音、生年、五項能力、頭像碼；遊戲直接讀 ROM；`verify_persons.py` 和外部能力值表 445/445 一致；見 ROM_FORMAT §4 |
| 6 劇本 | ✅ | emu | 標題、劇本人物／都市／勢力的 ROM 來源（WRAM 完全一致，載入後才設定的位元另計）；見 ROM_FORMAT §5 |
| 劇本人物 | ✅ | emu+capture | 忠誠、所在、勢力、特殊能力（24 種位元）、所屬串列（武将／在野／異民族）；見 ROM_FORMAT §5.1、§6 |
| 43 都市 | ✅ | emu+capture+modified | 名稱、讀音、相鄰、大地圖位置；每劇本的勢力、太守、人口、金、兵糧、兵士、開発、治水、商業、技術、民忠、士気、訓練、弩、強弩、連弩、軍馬、発石；見 ROM_FORMAT §5.2、§7 |
| 勢力 | ✅ | emu | 君主、所轄都市串列、友好度；見 ROM_FORMAT §5.3 |
| 頭像：專屬 339 張＋組合臉 16 包 | ✅ | emu+modified | 專屬 2 組調色盤；見 ROM_FORMAT §9 |
| 頭像（kaodata `san4-sfc`） | ✅ | checksum | `verify_kaodata_export.py` |
| 大地圖 | ✅ | emu | mode 7 平面 128 × 96 格、256 tile、調色盤（含水面動畫 4 幀）；見 ROM_FORMAT §8 |
| 戰場地圖 88 張 | ✅ | emu+modified | BG tilemap、tile、調色盤；野戰地圖選擇表、攻城地圖編號；模擬器比對了一場野戰與一場強制攻城戰；見 ROM_FORMAT §10 |
| 戰場地形與配置 byte、多個未知欄位 | ❌ | | 見「未解」 |

## 未解

- 戰場的地形 byte（高低 4 位元似乎分開編碼）與配置 byte（0–7 推測是部隊初始位置）的意義（ROM_FORMAT §10）
- 戰場調色盤組 s 與月份的對應（12 月用 s = 3，推測對應四季）；BG1 地物層沒有驗證，只驗證了地面層 BG2（ROM_FORMAT §10）
- 人物 +24（相性？）、+26、+27–29；劇本人物 +2–5、+13–14（ROM_FORMAT §4、§5.1）
- 都市基本表 +0–2；劇本都市 +28、在野 A／B 與 +11／+13 兩個人物串列的差別；衝車的位置未找到（ROM_FORMAT §5.2、§7）
- 勢力 +8、+10–11（載入後改寫）（ROM_FORMAT §5.3）
- `0x2852E5` 等多張指標表的內容（ROM_FORMAT §11）
- 外字 `EBF8`（ROM_FORMAT §3）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 6 劇本選完劇本後（選君主地圖）WRAM `$7E:73B2`（人物）、`$7E:B872`（都市）、`$7E:C70F`（勢力）與 ROM 解壓結果逐 byte 比對 | 6 劇本皆 0 byte 不同（人物 182/222/222/235/208/181 筆、都市 43、勢力 25）；載入後才設定的位元：勢力 +10/+11、劇本 5–6 皇帝的旗標 |
| `verify_faces.py` | 劉繇的確認框呼叫 `$C3:59B7`，把引數換成每個頭像碼，比對 VRAM `0x440` 的 960 bytes 與 CGRAM 調色盤 3；未改動時的引數 = 劉繇（人物 74）的頭像碼 74 | 專屬 339/339、組合 259/259、OK |
| `verify_maps.py` | 大地圖：第一回合的 VRAM（mode 7）與 CGRAM；43 都市位置；寿春→徐州的野戰與強制成攻城戰的地圖編號、BG2 tilemap、tile、調色盤 | 12288/12288 格、256 tile、43/43、野戰 660/660、攻城 660/660、OK |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對、checksums | 462/462、339/339、OK |
| `verify_persons.py` | `[EXT]` 外部能力值表（kaodata-re 的 `MISC_TABLE/ROTK - Character Stats & Abilities.csv`，S04 欄）依姓名比對 | 445/462 找得到，445/445 五項全同 |

欄位意義另外對照遊戲畫面：劉繇（統率 19 武力 15 知力 40 政治 54 魅力 23、生年 151、特殊能力 駆虎 落石 罵声）、張飛的能力、陳横 陳武 張英的忠誠；寿春、建業的都市畫面；在 WRAM 改寫寿春的欄位後看都市畫面，確認強弩（+34）、連弩（+38）、発石（+40）、所屬勢力（+23）。人物基本表由遊戲直接讀 ROM（Mesen 讀取追蹤：顯示劉繇時讀 `$C9:B536` = `0x9AB18 + 35 × 74`）。
