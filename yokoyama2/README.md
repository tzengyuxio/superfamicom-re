# SFC 横山光輝 三国志2 解析

エンジェル，1993，SFC（LoROM FastROM 1.5 MB，一版）。前作 `yokoyama/`（横山光輝 三国志）的引擎重新組譯：16-bit 自訂字碼、LZSS、sprite 組合頭像、mode 7 大地圖的做法相同，但程式位址、字型、各表格式都換過，要重新解。劇本 3（189 年 桃園の誓い、200 年 群雄割拠、215 年 三国時代）、人物 229（名表另有 10 個通用稱呼）、國 35、勢力 16 格（189 年 14 個、200 年 9 個、215 年 4 個）。不出 kaodata。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)（§11 是和前作的比較）。

## 指令

```bash
.venv/bin/python yokoyama2/export.py [--rom ROM] [--out DIR]      # → yokoyama2/output/（CSV、XLSX、PNG）
.venv/bin/python yokoyama2/tools/charset_sheet.py                 # → yokoyama2/output/charset_sheet.png
.venv/bin/python yokoyama2/verify_scenarios.py                    # 約 55 秒
.venv/bin/python yokoyama2/verify_persons.py                      # 約 17 分鐘（三個劇本平行）
.venv/bin/python yokoyama2/verify_countries.py                    # 約 1 分鐘（三個劇本平行）
.venv/bin/python yokoyama2/verify_faces.py                        # 約 17 分鐘
.venv/bin/python yokoyama2/verify_text.py                         # 約 1 分鐘
.venv/bin/python yokoyama2/verify_maps.py                         # 約 1 分鐘
.venv/bin/python yokoyama2/verify_lz.py                           # 約 1 分鐘
```

- ROM 預設直接讀 `_original/sfc/Yokoyama Mitsuteru Sangokushi 2 (Japan).zip`；`--rom` 也接受 .sfc。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。字型核對圖用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用共用的 `tools/replay.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninitialized` 濾掉。一個 process 只能開一次 Mesen，三個劇本 savestate 不同的腳本（`verify_persons.py`、`verify_countries.py`）會自己開三個子程序平行跑（`--scenario 0|1|2` 只跑一個；`verify_persons.py` 另有 `--persons 0-228`）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：字型與文字、名表與讀音、劇本載入（人物／配置／國／勢力 → WRAM）、難易度金米表、國名／讀音／位置、頭像（部件、metasprite、調色盤）、LZSS、大地圖（mode 7 VRAM、砦、行軍部隊、調色盤、國的標記） |
| `data/charset.txt` | 字表：字碼 0x100–0x5FF → 字元（16 字一行，`#` 開頭是註解） |
| `tools/sequences.py` | 按鍵序列（劇本選擇、三劇本第一個月的地圖、人事→人材→武將詳細畫面）、攔 `$80:8C2E` 字碼與攔劇本載入的 Lua |
| `tools/charset_sheet.py` | 字型核對圖：每個字碼的 ROM 字形與字表的字元並排 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `parts_manifest.py` | portrait-sheet/1 manifest：頭像零件 405 個（共用 `yokoyama/parts_manifest.py` 的 build），交給 simagame |
| `sheet_manifest.py` | portrait-sheet/1 manifest（武將頭像 229 張，交給 simagame 做頭像 sheet） |
| `verify_scenarios.py` | 3 劇本 × 3 難易度：劇本載入後 WRAM 人物／國／勢力區塊與 `Rom.scenario_wram` 逐 byte 比對 |
| `verify_persons.py` | 人物 229 × 3 劇本：逐一移進玩家的國，開武將詳細畫面，攔 `$80:8C2E` 的字碼 |
| `verify_countries.py` | 國 35 × 3 劇本：游標寫到各國的標記，開國的資訊畫面，攔字碼 |
| `verify_faces.py` | 頭像 229：武將詳細畫面的 OAM／VRAM／CGRAM 畫出來，和 `Rom.face_rgb` 逐 pixel 比對 |
| `verify_text.py` | 字碼 0x100–0x5FF：換進國的讀音字串，比對 `$80:8C2E` 讀字型的位置 |
| `verify_maps.py` | 大地圖：VRAM 0x0000–0x7FFF（含砦、行軍部隊）、地圖調色盤、國的標記 sprite 與標記顏色 |
| `verify_lz.py` | 開機到三劇本第一個月地圖之間遊戲解壓的 37 個串流，和 `rom.lz` 比對大小與 checksum |

## 輸出（`yokoyama2/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 人物 229：姓名、讀音、頭像部件 12 個、三劇本的配置 |
| `scenario_persons.csv` | 3 劇本 × 229：配置（種類、國、關係人物、登場年、原始值）、開局所屬勢力、官位、レベル 経験値 体力 武力 兵法力 政治力 統率力 忠誠度 人望 士気 疲労度 兵士数 移動力、攻撃力（武力 + 士気）、武器力 騎 弓 歩、原始 17 bytes |
| `countries.csv` | 國 35：國名、讀音、地圖位置（16 px 單位） |
| `scenario_countries.csv` | 3 劇本 × 35：勢力、太守、金、米（中級）、民、収穫高、産業値、統治度、防災値、税率、城塞値、開発度、砦、上級與初級的金米、原始 18 bytes |
| `factions.csv` | 各劇本存在的勢力：君主、國數、武將數、國 |
| `yokoyama2.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`faces.png` | 229 人的頭像 48 × 64（`102_諸葛亮.png`，透明背景）與總覽 |
| `map.png` | 大地圖 1024 × 1024（1 月的調色盤，水的循環取第一格） |
| `map_189.png`、`map_200.png`、`map_215.png` | 三劇本開局：各國位置畫勢力顏色的方塊（顏色取自遊戲的標記調色盤，方塊形狀是示意） |
| `charset_sheet.png` | 字型核對圖（`tools/charset_sheet.py`） |

## 進度

- ✓ 字碼：16-bit、16 × 16 全形 1024 字與 8 × 16 半形 256 字、控制碼 F0–F9；字表人工判讀（7 字沒把握，ROM_FORMAT.md §3）
- ✓ 名表 239（229 人＋10 個通用稱呼；三字、讀音）
- ✓ 劇本 3：載入程式（`$99:E436`）的人物 229 × 17、配置 229 × 5（種類 0）、國 35 × 18、勢力 16 × 3，WRAM 紀錄格式；難易度 上級／初級 的金米表
- ✓ 人物 17 bytes 全部欄位（官位、レベル、経験値、体力、忠誠度、人望、士気、疲労度、武器力 騎 弓 歩、兵士数、移動力、武力、兵法力、政治力、統率力）
- ✓ 國 18 bytes 全部欄位；國名、讀音、地圖位置
- ✓ 勢力君主；玩家勢力 `$0184`
- ✓ 頭像：12 部件 → sprite 緩衝、metasprite（5 人有自己的一組）、每人 16 色調色盤
- ✓ LZSS（`$81:A8F0`）與 16-byte 交錯（`$81:A98C`）
- ✓ 大地圖：mode 7 串流 `$91:827D`、砦（國 +17 的 6 個 bit）、行軍部隊（六角格）、調色盤、國的標記 sprite
- △ 配置種類 1–5（在野、親族、勢力、推挙、登用）：照前作的解讀匯出，沒有模擬器驗證
- △ 頭像表情 metasprite 1–3：只從程式碼解出（詳細畫面一直是 0）
- ✗ 沒有找到戰術地圖與地形表：部隊在大地圖的六角格上行軍，沒有觸發過戰鬥（ROM_FORMAT.md §10）；沒有相鄰表
- … 未解：エディット、君主選擇表、WRAM 人物 +3–6／國 +18–19、同盟／政策／捕虜、訊息字串表與事件、事件場景圖（未在開局用到的 LZ 串流）、標記 tile 的圖形、其他月份的地圖調色盤

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 劇本選擇畫面存 savestate；9 輪（3 劇本 × 上級／中級／初級，君主都選第 0 項 劉備），載入程式返回 `$80:8089` 時 dump WRAM `$0700–$1F8B`，人物 229 × 24、國 35 × 20（最後一國 18）、勢力 16 × 4 與 `Rom.scenario_wram(劇本, 難易度)` 逐 byte 比對 | 9/9 輪：人物 5496/5496、國 698/698、勢力 64/64 bytes 相同，OK（54 秒） |
| `verify_persons.py` | 三劇本各到玩家第一個月存 savestate；每輪寫回開局狀態（電腦勢力已行動、第一個月已處理），把人物 p 移進玩家的國（并州／下邳／成都，原有武將移出），國的面板 → 政略 → 人事 → 人材 → 選択 → X，攔 `$80:8C2E` 的字碼：姓名、所屬君主、讀音、官位、レベル、太守、経験値、体力、武力 政治力 兵法力 統率力、疲労度 忠誠度 人望 兵士数、攻撃力 = 武力 + 士気、士気 移動力、兵器、武器力 騎 弓 歩 | 189 年 229/229、200 年 229/229、215 年 229/229，OK（1032 秒，三個劇本平行）。玩家的君主 劉備 顯示官位「君主」、レベル後面是「太守」，期望值照這個規則 |
| `verify_countries.py` | 同上的 savestate；每輪寫回開局狀態、游標 `$0160`／`$0162` 寫到國 c 的標記，X 開國的資訊畫面，攔字碼：國名、君主、讀音、太守、政策、金、産業値、米、収穫高、民、開発度、税率、統治、城塞、防災、砦、武将数、兵士（無勢力的國到砦為止） | 3 劇本各 35/35，OK（58 秒） |
| `verify_faces.py` | 用 `verify_persons.py` 的 189 年輪次讀 OAM、VRAM 0xC000–0xCFFF、CGRAM 0x100–0x11F，依 OAM 畫出 (104, 22) 的 48 × 64 範圍，和 metasprite 0–3 比對 | 229/229 人逐 pixel 相同（含夏侯惇 胡軫 張飛 文醜 陳宮 自己的 metasprite 組；拍到的都是表情 0），OK（1028 秒） |
| `verify_text.py` | 40 輪把 32 個待測字碼寫進空白 ROM `$8C:F960`、遼東的讀音指標指過去，X 開資訊畫面，攔 `$80:8C2E` 與讀字型的 `$80:8C8B`／`$80:8CBE` 的 X | 字碼 0x100–0x5FF 1280/1280 讀在 `$9A:8000 + 32 (code − 0x200)`／`$99:A000 + 16 (code − 0x100)`，OK（64 秒） |
| `verify_maps.py` | 劇本選擇存 savestate；3 輪各到玩家第一個月：VRAM 0x0000–0x7FFF 與 `Rom.map_vram()`、顏色 0x20–0x5F 與 `$A0:CC8F`（0x50–0x57 容許循環）、OBJ 1–35 的位置／tile／屬性與 `Rom.marker`、OBJ 調色盤 6–7；第 4 輪改 ROM 讓每國的砦 byte 不同、第 5 輪在地圖上寫進 8 支行軍部隊再 X、B 讓地圖重建 | 5/5 輪：VRAM 32768/32768 bytes 相同（砦 412 bytes、部隊 32 bytes 有變化）、調色盤 OK、標記 35/35，OK（69 秒） |
| `verify_lz.py` | 開機（第 20 幀存 savestate）到三劇本玩家第一個月，攔 `$81:A8F0` 的來源與返回時（`$81:A986`）`$7E:8000` 的大小、checksum | 37/37 個串流相同，OK（69 秒） |

另外對照遊戲畫面：189 年玩家第一個月的大地圖截圖，35 個國的標記中心顏色有 34 個和 `Rom.marker` 的顏色相同（玩家的國 并州 是白色，推測在閃爍）。
