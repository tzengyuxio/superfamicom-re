# SFC ウイニングポスト2 解析

KOEI，1995，SFC（HiROM 3 MB）。賽馬經營模擬：玩家當馬主，買馬、託調教師、選騎手、跑日程上的比賽，也經營牧場。程式是 C 編譯的原生 65816 程式，圖形用 KOEI LZ。沒有戰術地圖。也支援 1996 年的資料更新版 ウイニングポスト2 プログラム'96（原版與 Rev 1，`--rom`）。ROM 結構見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)；前作見 `winning/`。

## 指令

```bash
.venv/bin/python winning2/export.py [--rom ROM] [--out DIR]     # → winning2/output/（CSV、XLSX、PNG）
.venv/bin/python winning2/export_kaodata.py --out <kaodata>/data-local/winning2-sfc
.venv/bin/python winning2/verify_kaodata_export.py --dataset <kaodata>/data-local/winning2-sfc
.venv/bin/python winning2/verify_init.py        # 約 40 秒
.venv/bin/python winning2/verify_horses.py      # 約 310 秒
.venv/bin/python winning2/verify_people.py      # 約 210 秒
.venv/bin/python winning2/verify_races.py       # 約 1070 秒
.venv/bin/python winning2/verify_schedule.py    # 約 1130 秒
.venv/bin/python winning2/verify_faces.py       # 約 260 秒
```

- ROM 預設直接讀 `_original/sfc/Winning Post 2 (Japan).zip`；`--rom` 也接受 `_original/sfc/Winning Post 2 - Program '96 (Japan).zip`、`… (Rev 1).zip` 或 .sfc。全部腳本（匯出與驗證）都能跑 '96；'96 的表位址在 `rom.PROGRAM96`，Rev 1 位址相同。'96 匯出到 `output/program96/`（Rev 1：`output/program96_rev1/`）。
- '96 的 kaodata 是另一個資料集 `winning2-96-sfc`：和原版比，174 張頭像同碼相同、8 張換碼、26 張拿掉、33 張新增，21 個人物不同，無法併進 `winning2-sfc`。'96 原版與 Rev 1 匯出的資料集相同。
- 解壓縮用共用的 `tools/koei_lz.py`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。頭像總覽的標註用 macOS 的ヒラギノ角ゴシック。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用共用的 `tools/replay.py`，printf 追蹤用 `tools/printf_trace.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：版本判別與兩版位址、字型與文字、人名／馬名零件、現役馬／種牡馬／繁殖牝馬／幼駒、騎手／調教師／馬主／秘書、牧場、比賽與日程、名稱表、頭像（選臉規則）、開新局的初始資料區塊 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 資料集 `winning2-sfc`（208 張肖像、115 人；沒有組合臉）；`--rom` 給 '96 時匯出 `winning2-96-sfc`（235 張肖像、115 人），輸出目錄要用這個 id |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對（肖像、每個人物）；checksums |
| `verify_init.py` | 開新局時 9 個 WRAM 區塊與 ROM 逐 byte 比對；馬、人的名字零件與父母對 WRAM |
| `verify_horses.py` | 馬卡片：現役馬的年齡、性別、毛色、牧場、父、母、母父；種牡馬／牝馬／現役馬名 |
| `verify_people.py` | 馬卡片的父欄改接騎手／調教師／馬主的姓名函式：全部人名 |
| `verify_races.py` | 馬卡片的各欄改接比賽函式：每筆比賽的長名、短名、距離、芝／ダート、年齡條件、等級 |
| `verify_schedule.py` | 馬卡片的年齡欄改接 WRAM 裡的 shim，呼叫日程函式：96 天全部格子 |
| `verify_faces.py` | 對話框頭像函式強制每個種類／id／年／年齡：解壓出的 960 bytes 與調色盤 |
| `tools/w2.py` | 驗證共用：開新局與馬卡片的按鍵序列、收集 Lua、printf 追蹤（兩版位址） |
| `data/charset.txt` | 字形 → 字（3276 字，碼 = 0x8140 + 字形號） |
| `data/charset_96.txt` | プログラム'96 的字表（3277 字） |

## 輸出（`winning2/output/`）

| 檔案 | 內容 |
|------|------|
| `racehorses.csv` | 現役馬 120：馬名、零件、年齡、性別、毛色、父／母／母父、牧場、馬主、調教師、推定的賞金與戰績欄、原始 bytes |
| `stallions.csv`／`mares.csv`／`foals.csv` | 種牡馬 147（'96：150）、繁殖牝馬 140（含父）、幼駒 80（父母） |
| `jockeys.csv` | 騎手 110：姓名、零件、年齡、推定勝利數與能力、開局頭像碼 |
| `trainers.csv` | 調教師 20：姓名、年齡、所屬、專屬騎手、頭像碼 |
| `owners.csv` | 馬主・生產者 29：姓名、牧場、推定資金、頭像碼 |
| `farms.csv` | 牧場 24：名稱、場主、地區 |
| `secretaries.csv` | 秘書 6：姓名、性別、年齡、薪水、暱稱、頭像碼（15 年目前後） |
| `races.csv` | 比賽 1147（'96：1162）：長名、短名、等級、距離、芝／ダート、年齡條件、負重規則、未解欄位、在日程上的時間 |
| `schedule.csv` | 日程 2576 場（'96：2586）：月、週、土日、開催格、競馬場、開催回、場次、比賽 |
| `name_tables.csv` | 毛色、競馬場、等級、距離適性、成長型、氣性、地區等名稱表 |
| `winning2.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`faces.png` | 頭像 208 張（'96：235）與總覽 |
| `font.png` | 字型總覽 |

## 進度

| 項目 | 狀態 | 證據 | 說明 |
|------|------|------|------|
| 字型與文字編碼 3276 字 | ✅ | code | 用到的全部認出（第二水準 16 字從名字逐一認，最後 1 字沒用到）、0x91 跳脫；字形 → 字靠人工與 DP 比對，沒有獨立的 Mesen 驗證；見 ROM_FORMAT §2 |
| 人名零件 1003、馬名零件 6000 | ✅ | emu+modified | 馬名的組法；見 ROM_FORMAT §3 |
| 現役馬 120、種牡馬 147、繁殖牝馬 140、幼駒 80 | ✅ | emu+modified | 現役馬的年齡、性別、毛色、父母、牧場、馬主、調教師；幼駒只比開局區塊；見 ROM_FORMAT §5 |
| 騎手 110、調教師 20、馬主 29、牧場 24 | ✅ | emu+modified | 騎手 60 在 WRAM、50 直接讀 ROM；見 ROM_FORMAT §6、§7 |
| 秘書 6 | ✅ | code | 姓名、性別、年齡、薪水、暱稱；見 ROM_FORMAT §6.4 |
| 比賽 1147、日程 96 天 × 3 格 × 10 場 | ✅ | emu+modified | 名稱 919、等級、距離、芝／ダート、年齡條件、開催地與開催回；見 ROM_FORMAT §8 |
| 比賽的負重規則 | 🟡 | code | +4 bits 6–7，沒有 Mesen 驗證；見 ROM_FORMAT §8.1 |
| 推定欄位 | 【推】 | | 現役馬的賞金與戰績、騎手的勝利數與能力、馬主的資金、調教師的所屬；見 ROM_FORMAT §5、§6 |
| 頭像 208 與選臉規則 | ✅ | emu+modified | 秘書依年、騎手依年齡、女騎手與調教師後繼依年；沒有組合臉；見 ROM_FORMAT §10 |
| 頭像（kaodata `winning2-sfc`） | ✅ | checksum | 肖像 208、人物 115 |
| 開新局 9 個 WRAM 區塊 | ✅ | emu | 與 ROM 逐 byte 一致；見 ROM_FORMAT §4 |
| プログラム'96（原版與 Rev 1） | ✅ | emu+modified | 同一套格式：全部表位址、字表、新頭像 27 張與改過的選臉規則、比賽 1162；所有驗證都在三個 ROM 上跑過；見 ROM_FORMAT §11 |
| 馬的能力欄、多數人物欄位 | ❌ | | 見「未解」 |

戰術地圖：本作沒有。

## 未解

- 馬記錄的大部分欄位 — 能力、距離適性、成長型、氣性、戰績與賞金的確切意義；種牡馬與牝馬除名字與父以外、幼駒除父母以外的欄位（ROM_FORMAT §5、§12）
- 人的多數欄位 — 騎手 +4 bit 7、+7、+13 以外；調教師 +4 bit 6；馬主除牧場與資金以外；牧場 +8 bits 0–5；秘書薪水單位（ROM_FORMAT §6、§7）
- 初始資料區塊 `$687C`（0x123E bytes）、`$A68B`（全 0）（ROM_FORMAT §4）
- 比賽記錄 +2 bits 10–13、+4 bits 0–5、+5；負重規則沒有 Mesen 驗證；日程每天 +60..62 只比對了值、意義未解（ROM_FORMAT §8）
- 玩家名字的存法 — 玩家輸入的馬名（零件 ≥ 6000）只解到位址；'96 的人名零件沒有ユーザ／プレイ（ROM_FORMAT §3、§12）
- 馬的圖、比賽畫面、地圖類圖形沒有追（ROM_FORMAT §12）
- Rev 1 ROM 0x2ACC79 的 2520 bytes（ROM_FORMAT §11.3）

## 驗證

所有驗證都在 Mesen 2 跑遊戲本身的程式：從開機按鍵進到開新局或第一張待售馬卡片，savestate 後每輪改 WRAM／ROM 或攔截函式引數，比對遊戲印出的字（vsprintf 的格式與引數）、WRAM、解壓出的頭像。表中時間是原版；'96 與 Rev 1 的結果在下一節。

| 腳本 | 內容 | 結果（時間） |
|------|------|------|
| `verify_init.py` | 開新局後在最後一次複製後（`$C3:0FEE`）讀回 `rom.INIT_COPIES` 的 9 個 WRAM 區塊，與 ROM 逐 byte 比對；現役馬／種牡馬／牝馬的名字零件與父母、騎手 0–59、調教師、馬主的名字零件對 WRAM | 區塊 9/9（20585 bytes）；現役馬 120/120、種牡馬 147/147、牝馬 140/140、騎手 60/60、調教師 20/20、馬主 29/29（36 秒） |
| `verify_horses.py` | 馬卡片 `$C3:360A`：每輪先把初始區塊寫回 WRAM，hook 換馬號；比對 `%u歳`、`%s馬`、毛色、牧場、父、母、母父。再把馬 0 的父母改成每匹種牡馬／牝馬，第三次組名時換成現役馬的零件 | 現役馬 120/120（7 欄）；種牡馬 147/147、牝馬 140、現役馬名 120（302 秒） |
| `verify_people.py` | 馬卡片的父名函式 `$C4:64A7` patch 成 JML 到騎手 `$C4:A698`／調教師 `$C4:AE9E`／馬主 `$C4:B4A7` 的姓名函式，父欄設成人的 id | 騎手 110/110（8 位只有一個名字的外國騎手比前綴）、調教師 20/20、馬主 28/28（212 秒） |
| `verify_races.py` | 馬卡片的 11 個 JSL 改接比賽函式（距離 `$C4:C7C8`、芝 `$C4:C803`、年齡條件 `$C4:C85A`、等級 `$C4:C48C`、長名 `$C4:C60C`、短名 `$C4:C66D`），hook 把馬號換成比賽號 | 比賽 1147/1147（名稱、短名、距離、芝／ダート、年齡條件、等級）（1065 秒） |
| `verify_schedule.py` | WRAM `$7F:FF40` 寫入 shim（推 5 個引數、JSL 日程函式 `$C4:C225`），馬卡片的年齡呼叫改 JSL shim；每次畫卡片換下一組引數，左右鍵重畫，一輪 24 組 | 2976/2976（96 天 × 3 格 × 10 場＋每天 +60 的 word，FFFF 也比）（1134 秒） |
| `verify_faces.py` | 秘書第一次對話前的 savestate，hook 對話框頭像 `$CC:0C67` 換種類與 id，改年份 `$8583` 與騎手年齡；載入調色盤時讀調色盤指標與 `$7F:8000` 的 960 bytes | 208/208 runs（208 個碼全部，pixel 與調色盤）（256 秒） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對；每個人物的名字與頭像對記錄；checksums | 肖像 208/208、人物 115/115、checksums OK（3 秒） |

### プログラム'96 與 Rev 1

驗證腳本裡各有 '96 的位址（`ADDR["program96"]`，Rev 1 共用）。

| 腳本 | '96 | '96 Rev 1 |
|------|------|------|
| `verify_init.py` | 區塊 9/9；現役馬 120/120、種牡馬 150/150、牝馬 140/140、騎手 60/60、調教師 20/20、馬主 29/29 | 同左 |
| `verify_horses.py` | 現役馬 120/120；種牡馬 150/150、牝馬 140、現役馬名 120 | 同左 |
| `verify_people.py` | 騎手 110/110、調教師 20/20、馬主 28/28 | 同左 |
| `verify_races.py` | 1161/1161（比賽 0 是空記錄，不比） | 1161/1161 |
| `verify_schedule.py` | 2976/2976 | 2976/2976 |
| `verify_faces.py` | 234/234 runs（235 個碼中的 233 個；104／105 遊戲不會用） | 234/234 |
| `verify_kaodata_export.py` | 肖像 235/235、人物 115/115（`winning2-96-sfc`） | — |
