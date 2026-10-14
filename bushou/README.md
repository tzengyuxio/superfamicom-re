# SFC スーパー信長の野望・武将風雲録 解析

KOEI，1992，SFC（LoROM 1 MB，無壓縮）。2 個劇本（1555 戦国の動乱、1571 信長包囲網），48 國。資料表大多沿用 FC 版（`~/works/famicom-re/bushou/`），只有少數欄位位置不同。文字是遊戲自己的 2-byte 碼（`0x8140–0x84A3` = 字型第 0–867 字，JIS 順的子集），加半形片假名。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python bushou/export.py [--rom ROM] [--out DIR] [--scale N]   # → bushou/output/（CSV、XLSX、PNG）
.venv/bin/python bushou/export_kaodata.py --out <kaodata>/data-local/nobu4-sfc
.venv/bin/python bushou/verify_kaodata_export.py --dataset <kaodata>/data-local/nobu4-sfc
.venv/bin/python bushou/verify_scenarios.py              # 約 10 秒
.venv/bin/python bushou/verify_text.py [--quick]         # 約 3.5 分鐘
.venv/bin/python bushou/verify_faces.py [--quick]        # 約 5 分鐘
.venv/bin/python bushou/verify_maps.py [--quick]         # 約 50 秒
.venv/bin/python bushou/tools/province_probe.py OUT.png  # 國畫面欄位探測截圖
```

- ROM 預設直接讀 `roms/Super Nobunaga no Yabou - Bushou Fuuunroku (Japan).zip`，`--rom` 也接受 .sfc。
- 依賴：Pillow、openpyxl。字型總覽與城地圖示意圖的標字用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`）。存檔重播用共用的 `tools/replay.py`：先照按鍵序列玩到某一幀、在 NMI handler 的第二個指令（`$00:832C`）存檔，之後每一輪改 ROM／WRAM、重播、在指定幀讀記憶體。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：檔案表、文字與字型、劇本（國、茶器、大名、武將）、姓名表、登場武將、頭像（專屬＋組合）、大地圖、野戰地圖與戰場畫面、戰場名 |
| `data/charset.txt` | 字型 868 字對應的字元（`〓` = 外字，見 `rom.GAIJI`） |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `nobu4-sfc`（專屬頭像 180 張＋組合臉 8 頭） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 2 劇本在選大名畫面的 WRAM 與 ROM 劇本區塊逐 byte 比對 |
| `verify_text.py` | 868 個文字碼逐一換進信長的名字，追蹤遊戲讀的字型位址 |
| `verify_faces.py` | 180 張專屬頭像＋278 種組合臉碼逐一換進信長的姓名記錄，比對遊戲寫進 VRAM 的 tile 與調色盤 |
| `verify_maps.py` | 大地圖（BG1／BG2／調色盤）、48 張野戰地圖（遊戲自己畫的 BG2 tilemap、CHR、調色盤） |
| `tools/battle_capture.py` | 把任一張野戰地圖換進美濃的合戰，讓遊戲畫出來 |
| `tools/province_probe.py` | 在 WRAM 把尾張的每個欄位改成自己的偏移後截國畫面，用來對照欄位意義 |

## 輸出（`bushou/output/`）

| 檔案 | 內容 |
|------|------|
| `scenarios.csv` | 2 劇本：年月、開局武將 250／255、改名 2、登場武將 120／91、大名 41／32 |
| `generals.csv` | 720 筆（劇本 × 開局／改名／登場）：姓名、生年、年齢、登場年、政治 戦闘 教養 魅力 野望、忠誠、所在國、大名、頭像碼、未解欄位 |
| `provinces.csv` | 2 劇本 × 48 國：大名、金 米 石高 治水 町 文化 技術 民忠 城 兵 鉄砲 訓練 兵忠、武將、未解欄位 |
| `province_list.csv` | 48 國的名稱與相鄰國 |
| `daimyo.csv` | 2 劇本的大名：同盟、關係表（未解）、未解欄位 |
| `tea.csv` | 2 劇本 × 48 茶器：名稱、持有者、值（未解） |
| `battle_maps.csv` | 野戰 48 張＋城 49 張：戰場名（推定）、地形（hex），城地圖的第二層 |
| `files.csv` | ROM 內的檔案表（`0x7800`） |
| `bushou.xlsx` | 以上各表 |
| `faces/`、`portraits/` | 460 位不同的（姓名, 頭像碼）各一張（組合臉已組好）；專屬頭像 F000–F179 |
| `mob_parts/`、`mob_parts.png` | 組合臉 8 頭 × 5 區 × 4 頁的零件 |
| `map.png` | 大地圖視窗（240 × 168；BG2 外框與海＋BG1 陸地，未塗勢力色） |
| `battle_maps/field/` | 48 張野戰畫面（256 × 224，遊戲畫的 BG2，未含部隊與狀態列文字） |
| `battle_maps/castle/` | 49 張城地圖的地形值示意圖（不是遊戲畫面，城的畫面未解） |
| `font.png` | 868 字的字型，旁邊是 `data/charset.txt` 的字 |

## 進度

- ✓ 檔案表、文字碼（含低位 byte 為 00 的跳脫碼 `85F0–85F2`）、字型 868 字與字元對照、外字 4 組
- ✓ 劇本 2 個：國 48 × 32 bytes、茶器、大名、武將 15 bytes 記錄、姓名表 20 bytes、改名、登場武將
- ✓ 國欄位：金 米 石高 治水 町 文化 技術 民忠 城 兵 鉄砲 訓練 兵忠（畫面＋WRAM 探測；FC 版文件的民忠／兵忠寫反了）
- ✓ 頭像：專屬 180 張、組合臉 8 頭（區域表 `0x1793C`），單一調色盤；kaodata 資料集 `nobu4-sfc`
- ✓ 大地圖：BG2 tilemap、BG1 陸地點陣、調色盤
- ✓ 野戰地圖 48 張：地形 → 2×2 metatile 規則、底圖、CHR、調色盤（遊戲畫面逐 tile 一致）
- … 推定：戰場名表（與 FC 版相同的 98 個名字，遊戲中沒看到顯示處）、登場武將表（結構與 FC 相同，未在遊戲中等到登場）
- … 未解：城地圖的畫面（沒能進入籠城戰；地形值 0–D 的意義、第二層）、大名關係表與 +29/+30、武將旗標與 byte 8、姓名表 byte 16、登場武將 byte 2／7、茶器的值、國 +19／+21／+30／+31、季節調色盤（見 ROM_FORMAT.md §9）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 劇本 1、2 選完後（選大名地圖）WRAM `$7E:DC04–$7E:F78B` 與 ROM 劇本區塊 +4…+0x1B8C 逐 byte 比對 | 7048 bytes 中只有載入時改寫的位置不同：國 +19（48）、+21（36，= ROM 值 << 6）、+31（10），劇本 2 的大名 +31（41，重新編號），最後一格後 1 byte；其餘全同，OK |
| `verify_text.py` | 選大名畫面按 A 出「織田信長でよろしいですか」，把信長的名（`0x10ED3`）換成 3 個字碼，追蹤遊戲從 `FONT + 32 × (碼 − 0x8000)` 讀的字 | 未改時讀 織田信長 4 字 OK；868/868 字碼、跳脫碼 85F0–85F2 OK（203 秒） |
| `verify_faces.py` | 開局後尾張國畫面的信長頭像；把姓名記錄的頭像碼（`0x10EDE`）換成每個碼，比對 VRAM `0xC800` 的 960 bytes 與 CGRAM 調色盤 5 | 未改時 = 頭像 25 OK；專屬 180/180、組合 278/278，OK（312 秒） |
| `verify_maps.py` | 大地圖（選大名畫面）的 BG2 tilemap 與 tile、BG1 陸地 tile、調色盤 0–7；野戰：48 張地圖逐一換進美濃的合戰，比對 BG2 tilemap 32 × 28、WRAM 地形、BG2 CHR、BG 調色盤 0–5 | BG2 630/630、BG1 476/476（只有色 7 被塗成勢力色）、CGRAM OK；野戰 48/48（188 格有部隊略過）、CHR 562/562、調色盤 OK（47 秒） |
| `verify_kaodata_export.py` | 參考渲染器與 `Rom.face_rgb` 逐 pixel 比對、checksums | 460/460、180/180、OK |

欄位意義另外對照遊戲畫面：信長的情報（政治 95 戦闘 87 教養 80 魅力 97 野望 100 年齢 21）、出陣選將清單（柴田勝家等 6 人的能力）；`tools/province_probe.py` 把尾張的欄位改成各自的偏移後截圖，金 1004、米 1006、石高 1008、治水 10、町 1011、文化 13、技術 1014、民忠 16、城 1017、兵 1024、鉄砲 1026、訓練 28、兵忠 29 都出現在對應的圖示旁。大名 +2–4 對照「浅井家」等同盟顯示。
