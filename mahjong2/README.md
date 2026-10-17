# SFC 麻雀大会II 解析

KOEI，SFC（LoROM 1 MB）。四人麻雀，對手是 26 位歷史人物與故事角色（雀荘 23 人，另 3 人只在大会決勝出現），每人 9 張頭像（說話動畫、6 種表情）與 344 行台詞。資料用 KOEI LZ 壓縮，位址內嵌在程式碼裡。名字只有圖、沒有文字；台詞字型只有假名。前作 `mahjong/`（スーパー麻雀大会）的字碼、台詞與情境機制、參數展開、役名格式都沿用下來；本作另外解出規則設定 44 項、7 個雀荘的固定規則與固定キャラ、系統訊息（含人物紹介）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python mahjong2/export.py [--rom ROM] [--out DIR]          # → mahjong2/output/（CSV、XLSX、PNG）
.venv/bin/python mahjong2/export_kaodata.py --out <kaodata>/data-local/mahjong2-sfc
.venv/bin/python mahjong2/verify_kaodata_export.py --dataset <kaodata>/data-local/mahjong2-sfc
.venv/bin/python mahjong2/verify_faces.py                       # 約 2.5 分鐘
.venv/bin/python mahjong2/verify_dialogue.py                    # 約 1 分鐘
.venv/bin/python mahjong2/verify_yaku.py                        # 約 1 分鐘
.venv/bin/python mahjong2/verify_persons.py                     # 約 1 分鐘（雀荘、卡片、參數；分兩個 process 跑）
.venv/bin/python mahjong2/verify_rules.py                       # 約 30 秒
.venv/bin/python mahjong2/verify_messages.py                    # 約 30 秒
.venv/bin/python mahjong2/tools/charset_sheet.py                # 字型對照圖 → output/charset_sheet.png、glyph16_sheet.png
```

- ROM 預設直接讀 `roms/Mahjong Taikai II (Japan).zip`，`--rom` 也接受 .sfc。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。字型對照圖用 macOS 的ヒラギノ角ゴシック。
- 驗證腳本需要 Mesen 2（`tools/mesen.py` 用 ctypes 呼叫 MesenCore）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：解壓縮、字型與文字、對手、參數、雀荘、頭像、名字圖、台詞與情境、役名、規則、系統訊息 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `mahjong2-sfc` |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；人物的臉與樣貌（label）；checksums |
| `verify_faces.py` | 牌桌上換說話的人與表情碼，比對 WRAM 頭像串流、VRAM 表情圖與說話臉、CGRAM 調色盤、OAM |
| `verify_dialogue.py` | 26 人的台詞串流與 WRAM 比對；212 個字碼寫進台詞窗，比對 tilemap 與字型 tile |
| `verify_yaku.py` | 和牌畫面換成 65 個名稱，比對 tilemap 與 108 個 16 × 16 字 |
| `verify_persons.py` | 7 個雀荘的對手名單、卡片的頭像與名字圖、26 人＋玩家的參數展開 |
| `verify_rules.py` | 7 個雀荘開局時 `$0E02` 的 44 項規則（標準規則組、全部取最後一個值的規則組） |
| `verify_messages.py` | 改寫訊息號的 immediate，比對 71 則訊息的位址與標頭長度 |
| `tools/sequences.py` | 驗證共用的按鍵序列、WRAM／VRAM 位址與 Lua hook |
| `tools/charset_sheet.py` | ROM 字形與 `charset.txt`、`glyph16.txt` 並排的檢查圖 |
| `data/persons.tsv` | 對手 26 人：名前（照名字圖抄）、読み、`[EXT]出典` |
| `data/charset.txt` | 台詞字碼 → 字（00–D3；和前作相同，只有 `0D` 改成 G） |
| `data/glyph16.txt` | 役名 16 × 16 字號 → 字（108 字） |
| `data/rules.tsv` | 規則 44 項的名稱與選項（照ルール畫面抄；選項數和 ROM 核對過） |

## 輸出（`mahjong2/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 26 人：名前、読み、[EXT]出典、所屬雀荘、頭像調色盤、頭像與台詞串流位址、參數原始值（22 nibble、8 旗標，意義未解）、人物紹介 |
| `dialogue.csv` | 26 × 344 行：情境、表情碼與表情、3 行文字、字碼 |
| `situations.csv` | 103 個情境：起始行、行數、機率 n、旗標，附リンカーン與卑弥呼的第一行 |
| `yaku.csv` | 65 個名稱：役 54、満貫〜役満 5、荒牌、途中流局 5 |
| `rules.csv` | 規則 44 項：選項、標準值、7 個雀荘實際使用的值、前提項目 |
| `parlors.csv` | 7 個雀荘：固定キャラ、對手名單、固定規則、說明文 |
| `messages.csv` | 系統訊息 71 則：標頭、內容（49–71 是人物紹介） |
| `mahjong2.xlsx` | 以上七張表（需 openpyxl） |
| `faces/` | 每人 9 張（`02_3_リンカーン_笑.png`：平常、說話 1、說話 2、笑、困、哭、不滿、怒、驚） |
| `faces.png`、`names.png` | 全部頭像一覽；26 張名字圖 |
| `charset_sheet.png`、`glyph16_sheet.png` | 字型對照圖（`tools/charset_sheet.py`） |

## 進度

- ✓ 壓縮（KOEI LZ，位址內嵌在程式碼）
- ✓ 對手 26 人：名字圖與抄錄、所屬雀荘、調色盤選擇；打牌參數的位置與展開方式（意義未解）
- ✓ 頭像 26 × 9 張（說話 3 格、笑、困、哭、不滿、56 × 56 的怒、驚），台詞表情碼 → 頭像；kaodata 資料集 `mahjong2-sfc`（234 張，表情放 `expressions`）
- ✓ 台詞 26 × 344 行、字型 212 碼；103 個情境的行範圍、機率與旗標（情境意義未解）
- ✓ 役名等 65 個與 16 × 16 字型 108 字
- ✓ 規則 44 項：選項數、標準規則、7 個雀荘的固定規則、13 組前提關係、持ち点
- ✓ 7 個雀荘的對手名單與固定キャラ；系統訊息 71 則（雀荘說明、大会說明、人物紹介 23 則）
- … 未解：參數與情境的意義、飜數表、大会的結構、ランク／成績／記録與存檔、玩家頭像、規則選項字的字型（ROM_FORMAT.md §10）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_faces.py` | 打到リンカーン說話前存 savestate；在 `$00:C318` 把說話的人換成 1–26、在 `$00:C366` 把表情碼換成 0–6、台詞換成一個字（讓表情圖在打字結束後出現）。比對 WRAM `$7F:1000` 的頭像串流、VRAM `$DC60` 的表情圖、`$D940` 的說話臉、CGRAM 第 15 列（`$01:CCB1`／怒用 `$01:CCCB`）、OAM tile 與調色盤；未改動時是リンカーン說自己的台詞 | 串流 26/26、表情 182/182、說話臉 182/182、調色盤 182/182、sprite 182/182、未改動 OK |
| `verify_dialogue.py` | 同一 savestate；26 人的 `$7F:6000` 台詞串流與 ROM 比對；01–D4 每 24 碼一組寫進要顯示的行，比對台詞窗 tilemap（tile `0x56 + 2c`、調色盤 3；D4 是空白，畫成 tile `0x06E`）與字型 tile | 串流 26/26、字碼 212/212、字形 212/212、OK |
| `verify_yaku.py` | 打到ノストラダムス和牌（三暗刻、立直、門前清摸和、ドラ）前存 savestate；在 `$00:E0DB` 把 `$41`／`$175F` 的清單換成 65 個名稱，比對和牌畫面的 tilemap 與 108 個字的 tile | 未改動 [19, 5, 0, 32] OK、名稱 65/65、字形 108/108、OK |
| `verify_persons.py` | 雀荘選擇畫面的 savestate，依序進 7 個雀荘並捲動卡片，`$00:AF13` 建在 `$0423` 的對手名單要等於 `$01:D41C` 算出的名單；每張卡片的 5 × 5 頭像、8 × 2 名字圖 tile 與 CGRAM 調色盤；開局前的 savestate 在 `$01:C999` 把 3 個座位換成 1–26，比對展開到 `$13D9` 以下的 30 個值 | 雀荘 7/7、卡片 23/23、參數 26/26＋玩家、OK |
| `verify_rules.py` | 開局前存 savestate；在 `$01:8F8E` 換雀荘 0–6，分別用標準規則組與「每項取最後一個值」的規則組（WRAM `$192F`），比對 `$0E02` 的 44 bytes；值都在選項數內 | 未改動＋7＋7 局全部 OK、範圍 OK |
| `verify_messages.py` | 雀荘選擇畫面的 savestate；把 `$00:AF9B` 的 `LDA #$17`（file `0x2F9C`）改成 1–71，比對 `$00:918A` 存進 DP `$58` 的訊息位址與 `$0D9E` 的標頭長度 | 71/71、OK |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對；每人的 face＋8 個 expressions 與 label、名字；checksums（含 `ch:<id>/<k>`，468 項）。kaodata 的 `scripts/verify.ts` 也跑過（468 項、0 不符） | 234/234、26/26、OK |
| `tools/charset_sheet.py` | ROM 字形和對照字並排，目視核對 | 台詞字型 212 碼、役名 108 字都對得上 |

名字圖的抄錄用 `names.png` 目視核對；表情名稱用 `faces.png` 與台詞內容判斷；規則名稱與選項是把每項設成 0–7 截 ルール畫面抄下來的。
