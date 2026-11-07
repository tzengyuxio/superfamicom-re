# SFC 三国志正史 天舞スピリッツ 解析

SFC（LoROM SlowROM 1.5 MB，一版）。標題畫面「© WOLF TEAM © TELENET JAPAN」，標頭 maker `A0`；ROM 裡沒有年份字串。不是光榮的作品，不出 kaodata。整個遊戲用游標（滑鼠式）操作。劇本 4（190 後漢戦国、200 龍虎激突、215 天下三分、227 武侯出師），人物 600 格 × 4 劇本（格子每劇本重新分配）、勢力 15 格、郡国 126、州 13、官職 48、頭像 250。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python tenbu/export.py [--rom ROM] [--out DIR]      # → tenbu/output/（CSV、XLSX、PNG），約 1 秒
.venv/bin/python tenbu/verify_scenarios.py                    # 約 15 秒
.venv/bin/python tenbu/verify_persons.py                      # 約 8.5 分鐘（四個劇本平行）
.venv/bin/python tenbu/verify_faces.py                        # 約 3.5 分鐘
.venv/bin/python tenbu/verify_text.py                         # 約 5.5 分鐘
.venv/bin/python tenbu/verify_places.py                       # 約 1.5 分鐘（四個劇本平行）
.venv/bin/python tenbu/verify_provinces.py                    # 約 3 分鐘（四個劇本平行）
.venv/bin/python tenbu/verify_maps.py                         # 約 2 分鐘
.venv/bin/python tenbu/verify_lz.py                           # 約 15 秒（四個劇本平行）
```

- ROM 預設直接讀 `_original/sfc/Sangokushi Seishi - Tenbu Spirits (Japan).zip`；`--rom` 也接受 .sfc。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用共用的 `tools/replay.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninitialized` 濾掉。一個 process 只能開一次 Mesen，四個劇本分開的腳本會自己開四個子程序平行跑（`--scenario 0-3` 只跑一個；`verify_persons.py` 另有 `--persons`）。
- 這個遊戲在選單畫面把 NMI 關掉，改輪詢 `$4212` 等 vblank：選單畫面的 savestate 掛 `$00:ADA2`（`tools/sequences.py` 的 `FRAME_HOOK`），主地圖上 NMI 又打開，用 `tools/replay.py` 預設的 NMI handler（`MAP_HOOK`）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：LZSS、劇本串流（人物／勢力／郡国 → WRAM 區塊）、人物／勢力／郡国欄位、郡国名／讀音／位置、官職、州、異民族、王号、劇本名、字表與字型（16×16 glyph、半形）、文字 → tile code、頭像、地域拡大図、格子表、中国全土図 |
| `export.py` | 匯出 CSV（UTF-8-BOM）、XLSX、PNG |
| `sheet_manifest.py` | portrait-sheet/1 manifest，一人一格（姓名＋頭像）照遊戲順序：用專屬頭像的 150 人（`tenbu`）與用大眾臉的 787 人（`tenbu-shared`）；沒人用的臉 71、135 無名、標 unseen 放在 `tenbu` 最後，交給 simagame 做頭像 sheet |
| `data/charset.txt` | 字表中 92 個自訂 SJIS 碼 `EB9F–EC58` → 字元（其餘用 cp932） |
| `tools/sequences.py` | 驗證共用：開機到劇本清單／君主清單／君主卡／主地圖的按鍵序列、游標寫入排程（`replay.py` 不能在指定幀寫 WRAM，改在 Lua 的 endFrame 裡寫 `$0200`／`$0201`，每輪的編號經 WRAM 信箱 `$7F:7E00` 傳）、`$00:A0CA` 字碼攔截 Lua |
| `verify_scenarios.py` | 劇本載入結果與 `Rom.scenario_wram` 比對 |
| `verify_persons.py` | 君主卡：人物 35 bytes 的姓名、讀音、官職、六能力、年齢 |
| `verify_faces.py` | 君主卡的頭像 sprite 與 `Rom.face_rgb` 逐像素比對 |
| `verify_text.py` | 字表 1113 字與半形字的 tile code、字型位址 |
| `verify_places.py` | 武将情報検索的郡国武將名單：所在（+29）與在場規則 |
| `verify_provinces.py` | 郡国視窗：勢 人 兵 士 太 金 糧 規 |
| `verify_maps.py` | 地域拡大図（地圖讀取、BG tile、調色盤）與中国全土図 |
| `verify_lz.py` | LZSS 解壓與遊戲的解壓輸出 |

## 輸出（`tenbu/output/`，不進版控）

| 檔案 | 內容 |
|------|------|
| `scenario_persons.csv` | 4 劇本 × 600：姓名、讀音、全部欄位、勢力名／所在名／血縁名／官職名、原始 35 bytes |
| `factions.csv` | 4 劇本的勢力（36 筆）：君主、各欄位、郡国數、關係 15 值、原始 |
| `provinces.csv` | 郡国 126：名、讀音、位置 |
| `scenario_provinces.csv` | 4 劇本 × 126：勢力、人口、兵、金、糧、士、士上限、規模、太（人物）與未解欄位（欄名用偏移）、勢力名、原始 32 bytes |
| `offices.csv` | 官職 48：名稱、現代名、後續 2 byte |
| `names.csv` | 州 13、異民族 15、王号 41 |
| `tenbu.xlsx` | 以上各表 |
| `faces/`、`faces.png` | 頭像 250 張（32 × 40，以頭像編號命名；人物 +31 指向它）與總覽 |
| `map.png` | 地域拡大図 2160 × 1840（chip 圖，不含城標記） |
| `region.png` | 中国全土図 248 × 224（君主選擇畫面背景，未依勢力上色） |
| `charset.png` | 字型：glyph 0x00–0x6A（按鈕字與半形區）與字表 1113 字 |

## 進度

- ✓ LZSS（`$00:A527`）；劇本 3 串流 × 4（人物 600 × 35、勢力 15 × 30、郡国 126 × 32 → WRAM）
- ✓ 文字：SJIS ＋ 字表 1113 字（92 個自訂碼）、glyph → tile、字型位址（4bpp／1bpp）、半形片假名
- ✓ 人物：姓名、讀音、政 外 策 采 武 徳、年齢、官職、頭像編號、所在；在場規則（+14 = 1 且 +30 = 0）
- ✓ 郡国：勢力、人口、兵、金、糧、士（含上限 80／100 的規則）、規模、太；郡国名／讀音／位置
- ✓ 頭像 250 張（4bpp、共用調色盤）
- ✓ 地域拡大図 270 × 230 chip 與調色盤；中国全土図 tile 與調色盤
- △ 只有資料或人工核對：人物 勢力 +24、血縁 +22（武將詳細視窗人工核對）；勢力 君主、關係矩陣；格子表的城格
- △ 推測：人物 +21 忠誠、+25 身分、+27 壽命、+30 登場前年數；勢力 +8 皇帝、+12 都城；自訂字 3 個（`EBF2` 衮、`EBF0` 䵋 依字形，`EBA5` 未認出）
- ✗ 未解：人物 +14 = 2 的意義、+28；勢力 +10、+13、+14；郡国 +1、+14–21、+23–26、+27 高 4 bit、「尉」（WRAM `$7E:F920`）與「徴発」標籤的條件；中国全土図的勢力上色規則（ROM 裡沒有郡国範圍遮罩）；格子表的地形類別；城標記 sprite（`$00:D880`）；相鄰（沒有找到表）；戰鬥（選單「戦闘」，沒有找到戰術地圖，推測在地域拡大図上進行）；bank `$0B` 的 LZSS 串流與 `$00:E336` 疑似腳本直譯器；其他 100 多個 LZSS 串流

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 劇本清單存 savestate；4 輪各選劇本 k、按開場文字的「了」，載入程式返回 `$00:CA8D` 時 dump WRAM `$7E:8018–$E3A1`，與 `Rom.scenario_wram(k)` 逐 byte 比 | 4/4 劇本：人物 21000/21000、勢力 450/450、郡国 4032/4032 bytes 相同，OK（15 秒） |
| `verify_persons.py` | 君主清單存 savestate；每輪在 `$00:CA8D` 把人物 p 的 35 bytes 蓋到勢力 0 君主的紀錄，點君主卡：`$00:A0CA` 字碼（姓名、讀音、官職前 4 字）與 OAM 數字 sprite（政 外 策 采 武 徳、年） | 4 劇本 × 600/600，OK（506 秒，四個劇本平行） |
| `verify_faces.py` | 同上（劇本 190），君主紀錄 +31 = 0–249，讀 OAM、VRAM 0x4000–0x7FFF、CGRAM，畫出 sprite 56–61（(72,24) 的 32 × 48，上方 8 列空白） | 250/250 張逐像素相同，OK（216 秒） |
| `verify_text.py` | 同上，把字表的字每 3 個寫進姓名（371 輪）、半形字每 7 個寫進讀音（9 輪），攔 `$00:A0CA` 的 tile code 與 `$00:A47B`（1bpp）／`$00:A086`（4bpp）算出的字型位址 | tile code 10640/10640、字型位址 18240/18240（含卡片先畫的數字 0–9），OK（329 秒） |
| `verify_places.py` | 各劇本到主地圖（勢力 0、普），開 武将情報検索 存 savestate；每輪把 6 人的 +29 設成遼東、其餘設成三韓，點遼東，攔 `$00:CB6E`（X = 人物紀錄） | 4 劇本 × 100/100 組（2400 人）名單相同，OK（74 秒）。名單 = ROM 的 +14 為 1 且 +30 為 0 的人，依編號 |
| `verify_provinces.py` | 劇本 190 劉虞開局，地圖往左捲一格，savestate；每輪把一筆郡国紀錄（4 劇本 × 126）的欄位蓋到 代 的紀錄，點 代，解析 `$00:A0CA` 畫出的視窗文字；另有規模 0–4、士 0／37／255、+27 高 4 bit 5／A／E／F 的合成測試 | 138/138（劇本 190 含 12 筆合成）、126/126 × 3，OK（166 秒） |
| `verify_maps.py` | (1) 君主清單畫面：VRAM 0x8020 起 868 tile 與 `$24:94CD` 解壓結果、CGRAM 調色盤 7。(2) 主地圖存 savestate，21 輪按住捲軸箭頭捲到不同位置：`$00:BCEE` 每次讀出的 byte、調色盤 7 的 BG tile 與所在格的 chip、CGRAM 調色盤 7 | (1) 719/868 tile 相同、149 個只差顏色 1 → 8–15（勢力上色），調色盤 OK。(2) 71984 次讀取（3528 格）全部相同；BG tile 11555 個相同（2993 格）、430 個在視窗左框下（第 2 欄像素起相同）；調色盤 21/21，OK（107 秒） |
| `verify_lz.py` | 4 劇本各從開機玩到主地圖，攔解壓程式 `$00:A527` 的來源（A = bank、Y = 位址）與之後寫進 WMDATA `$2180` 的 bytes | 每劇本 28/28 次呼叫（22 個串流、約 30 萬 bytes，含中国全土図與劇本串流）相同，OK（15 秒） |
