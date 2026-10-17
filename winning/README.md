# SFC ウイニングポスト 解析

KOEI，1993，SFC（HiROM 2 MB；原版與 Rev 1）。賽馬經營模擬：1997 年開始，玩家當馬主，買馬、託調教師、選騎手、跑日程上的比賽。程式是 C 編譯的原生 65816 程式，圖形用 KOEI LZ。沒有戰術地圖。ROM 結構見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)；DOS 版的對照在 `~/works/winning-post-zh`（kaodata `winning-dos`）。

## 指令

```bash
.venv/bin/python winning/export.py [--rom ROM] [--out DIR]     # → winning/output/（CSV、XLSX、PNG）
.venv/bin/python winning/export_kaodata.py --out <kaodata>/data-local/winning-sfc
.venv/bin/python winning/verify_kaodata_export.py --dataset <kaodata>/data-local/winning-sfc
.venv/bin/python winning/verify_init.py         # 約 20 秒
.venv/bin/python winning/verify_horses.py       # 約 55 秒
.venv/bin/python winning/verify_people.py       # 約 800 秒
.venv/bin/python winning/verify_races.py        # 約 580 秒
.venv/bin/python winning/verify_faces.py        # 約 190 秒
.venv/bin/python winning/verify_text.py         # 約 195 秒
```

- ROM 預設直接讀 `roms/Winning Post (Japan).zip`；`--rom` 也接受 Rev 1（`roms/Winning Post (Japan) (Rev 1).zip`）或 .sfc。Rev 1 的表位址在 `rom.REV1`；驗證腳本的 hook 位址是原版的，只對原版跑。
- 解壓縮用共用的 `tools/koei_lz.py`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。頭像總覽的標註用 macOS 的ヒラギノ角ゴシック。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用共用的 `tools/replay.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字與字型定址、人名表、馬主／調教師／騎手、現役馬／種牡馬／繁殖牝馬、馬名 word、名字範本／固定名／外國馬名、比賽名／日程／等級／開催／競馬場、名稱表、頭像（肖像與組合臉）、開新局的初始資料區塊 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 資料集 `winning-sfc`（208 張肖像、8 類型組合臉、140 人） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對（肖像、2048 種組合、每個人物）；checksums |
| `verify_init.py` | 開新局後 22 個 WRAM 區塊與 ROM 逐 byte 比對；馬、騎手的解碼欄位對 WRAM |
| `verify_horses.py` | 馬名函式 `$C5:5D4E`：遊戲自己的 1510 次呼叫，與強制換成 1809 個測試 word 的結果 |
| `verify_people.py` | 調教師資訊視窗：30 位調教師的姓名、頭像、所屬騎手、6 項性格；256 個人名 |
| `verify_races.py` | 月刊競馬ニュース的重賞頁：日程上每個有名字的格（名稱、回數、等級、開催、週、距離、年齡、性別）；232 個比賽名與回數 |
| `verify_faces.py` | 208 張肖像與 78 個組合臉碼：VRAM 960 bytes 與 CGRAM 調色盤 |
| `verify_text.py` | 字形查詢 `$C2:0E5D`：2368 個碼＋跳脫碼與空白碼，比對遊戲讀的字形位址與 32 bytes |
| `tools/wp.py` | 驗證共用：按鍵序列、收集遊戲 vprintf／puts／頭像繪製的 Lua（搭配 `tools/replay.py`） |
| `data/charset.txt` | 字形 → 字（2368 字，碼 = 0x8140 + 字形號） |

## 輸出（`winning/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 256 人名（姓、名） |
| `owners.csv` | 41 馬主：姓名、頭像碼、冠名、冠名位置、未解 bytes |
| `trainers.csv` | 30 調教師：姓名、頭像碼、所屬騎手、性格／方針／連闘／騎手起用／調教／相手比較、未解 bytes |
| `jockeys.csv` | 70 騎手：姓名、人名號、頭像碼、各欄原始值（意義未解） |
| `horses.csv`／`stallions.csv`／`mares.csv` | 現役馬 381、種牡馬 50、繁殖牝馬 170：馬名、馬名 word、父母 ID 與名字、未解 bytes |
| `name_templates.csv`／`fixed_names.csv`／`foreign_names.csv` | 馬名範本 828、固定名 605、外國馬名 100 |
| `races.csv` | 232 比賽：名稱、是否重賞、1997 年回數、等級、日程格與時期 |
| `calendar.csv` | 384 個日程格：月、週、東西、開催（回、競馬場）、比賽、等級、距離、年齡、性別、未解 b2／b3 |
| `tracks.csv` | 8 競馬場 |
| `name_tables.csv` | 毛色、白斑、腳白、距離適性、產地、等級、年齡、性別等名稱表 |
| `winning.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`faces.png` | 208 張肖像與 40 位馬主的組合臉、總覽 |
| `font.png` | 字型 2368 字總覽 |

## 進度

- ✓ 字型與文字編碼：2368 字（`data/charset.txt`）、0x91 跳脫、半形假名的平／片假名切換
- ✓ 人名 256、馬主 41（冠名）、調教師 30（性格 6 項、所屬騎手）、騎手 70（姓名與頭像）
- ✓ 現役馬 424 格（381 匹）、種牡馬 70 格（50 匹）、繁殖牝馬 170：馬名與父母
- ✓ 馬名 word 的全部種類、名字範本 828、固定名 605、外國馬名 100
- ✓ 比賽名 232、重賞回數 86、日程 384 格（開催、週、距離、年齡、性別、等級）、競馬場 8
- ✓ 頭像：肖像 208（調色盤依碼範圍）、組合臉 8 類型 × 4 零件；kaodata 資料集 `winning-sfc`
- ✓ 開新局 22 個 WRAM 區塊與 ROM 一致
- ✓ Rev 1：表位址（`rom.REV1`），解碼結果與原版相同，只有外國馬名表多一筆
- － 戰術地圖：本作沒有
- … 未解：馬記錄的能力／成績欄、血統表（ID > 640）、騎手資料欄、初始資料多數區塊、日程 b2／b3、8×16 半形字、馬的頭像與全身像、肖像 0xB6–0xCE 的用途（ROM_FORMAT.md §12）

## 驗證

所有驗證都在 Mesen 2 跑遊戲本身的程式（從開機按鍵進到對應畫面，savestate 後每輪改 WRAM／ROM 或攔截函式引數），比對遊戲印出的文字、WRAM、VRAM、CGRAM。

| 腳本 | 內容 | 結果（時間） |
|------|------|------|
| `verify_init.py` | 標題畫面開新局後（第 6600 幀）讀回 `rom.INIT_COPIES` 的 22 個 WRAM 區塊，與 ROM 逐 byte 比對；現役馬／牝馬／種牡馬的馬名 word 與父母、騎手的頭像碼與人名號對 WRAM | 區塊 22/22（27598 bytes）；現役馬 400/400＋24/24、牝馬 170/170、種牡馬 70/70、騎手 70/70（18 秒） |
| `verify_horses.py` | 取名後遊戲把名字和所有馬比對（`$C5:5D4E` 1510 次）：記錄每次的 word 與回傳的字串；再把每次呼叫的 word 換成測試值（範本 828 × 不同馬主、固定名 605、外國馬名 100、0x2C 256、其他種類 20） | 遊戲自己的 1510/1510（579 種 word），現役馬 0–399／牝馬／種牡馬的 word 577/577 都出現；強制 1809/1809（55 秒） |
| `verify_people.py` | 調教師清單 savestate，攔截資訊視窗 `$CB:77D7` 換調教師號：印出的姓名、所屬騎手姓名、6 項性格；ROM patch 把第一位的頭像碼換成該調教師的，比對清單載入到 VRAM `$A800` 的 960 bytes；把奥山的騎手 byte 改 0、騎手 20 的人名號改成 0–255，比對印出的姓名 | 調教師 30/30（姓名、頭像、所屬騎手、6 項性格）；人名 256/256（798 秒） |
| `verify_races.py` | 重賞頁 savestate，攔截 `$C8:5258` 換日程格、`$DA63` 設成該格的月：比對 puts 的比賽名、`第%y回`、等級、`%y回%s%y週`、`%2d00m %s %s`；再把格 6 的比賽號改成 0–231 | 日程格 192/192（有名字的格全部欄位）；比賽 232/232（名稱與回數）（580 秒） |
| `verify_faces.py` | 秘書頭像繪製前的 savestate，換掉 `$CA:2DAD` 的頭像碼：VRAM `$85C0` 960 bytes、CGRAM 第 2 列 32 bytes | 秘書 OK；肖像 208/208（tile 與調色盤）；組合臉 78/78（8 類型 × 4、未用 bit 設 1 的 8 個、馬主 38 個）（189 秒） |
| `verify_text.py` | 資訊視窗的 savestate，每次字形查詢把碼換成待測碼，比對 `$C2:091E` 讀的字形位址與 32 bytes | 2380/2380（字型 2368、0x91 跳脫 9、空白碼 3）（195 秒） |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對；每個人物的名字與頭像對記錄；checksums | 肖像 208/208、組合 2048/2048、人物 140/140、checksums OK（3 秒） |
