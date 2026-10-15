# SFC 太閤立志伝 解析

KOEI，1993，SFC（HiROM 1.5 MB）。主角木下藤吉郎，1560 年（桶狭間）開始；人物紀錄 713 筆（開始時 241 人＋之後登場 472 人）、名表 716 項、城 125、勢力 20。文字是 KOEI 自訂的兩 byte 字碼（2048 字）＋對話用的單 byte 假名。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python taikou/export.py [--rom ROM] [--out DIR]          # → taikou/output/（CSV、XLSX、PNG）
.venv/bin/python taikou/export_kaodata.py --out <kaodata>/data-local/taikoh-sfc
.venv/bin/python taikou/verify_kaodata_export.py --dataset <kaodata>/data-local/taikoh-sfc
.venv/bin/python taikou/verify_scenarios.py                    # 約 10 秒
.venv/bin/python taikou/verify_persons.py [--quick]            # 約 6 分鐘
.venv/bin/python taikou/verify_faces.py [--quick]              # 約 6 分鐘
.venv/bin/python taikou/verify_text.py [--quick]               # 約 6 分鐘（--quick 約 1.5 分鐘）
.venv/bin/python taikou/verify_maps.py [--quick]               # 約 6 分鐘（--quick 約 1.5 分鐘）
.venv/bin/python taikou/verify_battle_maps.py                  # 約 2 分鐘
```

- ROM 預設直接讀 `roms/Taikou Risshiden (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0x9C7D`），savestate 重播用共用的 `tools/replay.py`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`）。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：字型與文字、名表、開始時區塊（人物、勢力、城狀態）、之後登場的人物、城、字串表、頭像（專屬＋組合）、大地圖、戰場地圖 |
| `data/charset.txt` | 字表：字型 2048 字 → 字元（32 字一行，`#` 開頭是註解） |
| `tools/sequences.py` | 按鍵序列（到選型畫面、日本地圖、桶狭間情報畫面）、在中途切開序列（`*n` 展開與 `end_frame` 用共用的 `tools/replay.py`） |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `taikoh-sfc`（專屬頭像 258 張＋12 型組合臉） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；portrait code；checksums |
| `verify_scenarios.py` | 開新遊戲後 WRAM `$7E:2000–$7E:5F2C` 與 ROM 開始時區塊逐 byte 比對 |
| `verify_persons.py` | 713 筆人物紀錄逐一換進藤吉郎的情報畫面，攔遊戲畫字／畫能力條／算技能的引數 |
| `verify_faces.py` | 258 張專屬頭像＋名表用到的 518 種組合臉碼換進情報畫面，比對 VRAM tile 與 CGRAM |
| `verify_text.py` | 文字碼 → 字型 glyph 的規則（兩 byte 碼全部 2048 個、單 byte 假名、濁點）：追蹤遊戲讀字型 ROM 的位址 |
| `verify_maps.py` | 日本地圖：區塊、BG 字元、調色盤；把視窗中心移到各處讓遊戲自己畫，比對 BG1／BG2 tilemap |
| `verify_battle_maps.py` | 19 張戰場：在桶狭間載入戰場前改 `$7E:7F82`，讓遊戲畫出每一張，比對 tilemap、字元、調色盤 |

## 輸出（`taikou/output/`）

| 檔案 | 內容 |
|------|------|
| `names.csv` | 名表 716 項：姓、名、頭像碼 |
| `persons.csv` | 人物紀錄 713 筆：Id、姓名、開始時登場與否、所属（大名）、身分、居城（推測）、政略Lv、戦術Lv、外交 内政 魅力 統率 武力 野心、技能 8 項（D–A）、頭像碼、未解欄位原始值 |
| `factions.csv` | 勢力 20：大名、本城（推測）、開始時城數、未解欄位 |
| `castles.csv` | 城 125：相鄰、大地圖位置（格）、開始時的勢力、城主（推測）、城圖示、未解的狀態欄位 |
| `strings.csv` | 身分、技能、能力名、陣形、配置、天氣、兵種的字串表 |
| `battle_fields.csv` | 戰場 19 張：LZ entry、用途（推測）、尾 byte |
| `taikou.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`portraits/` | 每筆人物紀錄的頭像（`001_織田信長.png`，組合臉已組好）、全部專屬頭像 000–257 |
| `map.png`、`map_castles.png` | 日本地圖 5248 × 2944；縮半並標上 125 城與相鄰連線 |
| `battle/` | 19 張戰場（496 × 224，白天的調色盤） |
| `font.png` | 2048 字的字型總覽 |

## 進度

- ✓ 壓縮（共用 `tools/koei_lz.py`）、字型 2048 字與字表、兩 byte 字碼（含跳脫碼）、對話用單 byte 假名與濁點
- ✓ 名表 716 項（姓、名、頭像碼）
- ✓ 開始時區塊（`0x183F0` → `$7E:2000`）：人物 241、勢力 20、城狀態 123
- ✓ 人物紀錄 713 筆（241 筆在開始時區塊、472 筆在 `0xB63E0`）：所属、身分、政略Lv、戦術Lv、6 項能力、8 項技能
- ✓ 勢力：大名；城：名稱、相鄰、大地圖位置、開始時的勢力與城圖示
- ✓ 頭像：專屬 258 張＋組合臉 12 型；kaodata 資料集 `taikoh-sfc`
- ✓ 大地圖（日本地圖）：區塊表、區塊、格 byte → BG tilemap、BG 字元、調色盤
- ✓ 戰場地圖 19 張：tilemap、字元、調色盤；載入程式與選圖變數 `$7E:7F82`
- … 未解：人物的位置欄與多個欄位、勢力關係、城狀態多數欄位、居城／本城／城主（推測）、女性與茶人／町人表、大地圖的 17 個區域、戰場選圖規則（只從反組譯讀出）與戰場名稱（ROM_FORMAT.md §11）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 選型畫面時 WRAM `$7E:2000–$7E:5F2C` 與 ROM `0x183F0` 逐 byte 比對 | `$203A–$5F2C` 16115/16115 bytes 相同（標頭 58 bytes 已被遊戲改寫，只報告 24/58）；勢力 20/20、人物 241/241、城狀態 123/123、OK（10 秒） |
| `verify_persons.py` | 桶狭間的情報畫面：把 `$7E:24A7` 的紀錄 0 換成紀錄 k（713 筆），攔 vprintf `$C6:2E8B`（姓名、身分、所属大名、政略Lv、戦術Lv）、能力條 `$C8:21D4`、技能 `$CD:005D`，並比對頭像 VRAM | 713 筆：姓名、身分、所属（93 筆勢力無大名不檢）、政略Lv、戦術Lv、6 能力、技能 8 項、頭像 tile、調色盤全部 713/713，OK（354 秒） |
| `verify_faces.py` | 同一畫面，把名表 0 的頭像碼換成 0–257 與 518 種組合碼，比對 VRAM `0x2400` 640 bytes 與 CGRAM `0x120` | 未改動 = 頭像 0；專屬 258/258、組合 518/518，OK（377 秒） |
| `verify_text.py` | 把名表 0 的名換成各種字碼，追蹤 printf "%s%s" 期間遊戲讀字型（`$D7:xxxx`／`$57:xxxx`）的 glyph 順序 | 未改動 木下藤吉郎 = [1664, 335, 1359, 498, 1800]；兩 byte 683/683 組（2048 碼）、單 byte 19/19（55 碼）、單 byte＋濁點 9/9（25 碼），OK（360 秒） |
| `verify_maps.py` | 日本地圖：`$7F:0000` 區塊、VRAM `0x8240–0xAEA0` 字元、CGRAM 調色盤 2–7；156 輪把視窗中心移到各區塊，比對遊戲畫出的 BG1／BG2（每輪 1152 項） | 區塊相同、字元相同、調色盤 6/6、視窗 155/155（84 個不同中心；1 輪停在地圖外不計）、OK（344 秒） |
| `verify_battle_maps.py` | 桶狭間：未改動時 `$7F82` = 6；19 輪把 `$7F82` 改成 f，比對 VRAM `0xF000` 31 × 14、`0x8400–0xD000` 字元、CGRAM 調色盤 2、7 | 19/19、字元 20/20、調色盤 20/20、OK（130 秒） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_pixels` 逐 pixel 比對、portrait code、checksums | 716/716、258/258、OK |

另外對照遊戲畫面：藤吉郎情報畫面（姓名、身分、所属、能力條、技能、頭像）、開場對話「さて、どうするかな」（`0xE363F`）、日本地圖（尾張附近的城圖示位置）、桶狭間戰場截圖。
