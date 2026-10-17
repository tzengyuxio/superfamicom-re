# SFC スーパー麻雀大会 解析

KOEI，SFC（LoROM 512 KB，Rev 0）。四人麻雀，對手是 21 位歷史人物與原創角色，各有 7 張頭像（說話動畫、表情、怒）與 133 行台詞。資料用 KOEI LZ 壓縮，位址內嵌在程式碼裡（沒有指標表）。名字只有圖、沒有文字；台詞字型只有假名。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python mahjong/export.py [--rom ROM] [--out DIR]          # → mahjong/output/（CSV、XLSX、PNG）
.venv/bin/python mahjong/export_kaodata.py --out <kaodata>/data-local/mahjong-sfc
.venv/bin/python mahjong/verify_kaodata_export.py --dataset <kaodata>/data-local/mahjong-sfc
.venv/bin/python mahjong/verify_faces.py                        # 約 1.5 分鐘
.venv/bin/python mahjong/verify_dialogue.py                     # 約 1 分鐘
.venv/bin/python mahjong/verify_janso.py                        # 約 10 秒
.venv/bin/python mahjong/verify_yaku.py                         # 約 30 秒
.venv/bin/python mahjong/tools/charset_sheet.py                 # 字型對照圖 → output/charset_sheet.png、glyph16_sheet.png
```

- ROM 預設直接讀 `roms/Super Mahjong Taikai (Japan).zip`，`--rom` 也接受 .sfc。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。字型對照圖用 macOS 的ヒラギノ角ゴシック。
- 驗證腳本需要 Mesen 2（`tools/mesen.py` 用 ctypes 呼叫 MesenCore）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：解壓縮、字型與文字、對手、參數、頭像、名字圖、台詞與情境、役名 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `mahjong-sfc` |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；人物的臉與樣貌；checksums |
| `verify_faces.py` | 牌桌上換說話的人與表情碼，比對 WRAM 頭像串流、VRAM 表情圖與說話臉、CGRAM 與 OAM 調色盤 |
| `verify_dialogue.py` | 21 人的台詞串流與 WRAM 比對；212 個字碼寫進台詞窗，比對 tilemap 與字型 tile |
| `verify_janso.py` | 雀荘畫面的 21 張卡片：頭像、名字圖、調色盤 |
| `verify_yaku.py` | 和牌畫面換成 52 個役，比對 tilemap 與 99 個 16 × 16 字 |
| `tools/sequences.py` | 驗證共用的按鍵序列、WRAM／VRAM 位址與 Lua hook |
| `tools/charset_sheet.py` | ROM 字形與 `charset.txt`、`glyph16.txt` 並排的檢查圖 |
| `data/persons.tsv` | 對手 21 人：名前（照名字圖抄）、読み、`[EXT]出典` |
| `data/charset.txt` | 台詞字碼 → 字（00–D3） |
| `data/glyph16.txt` | 役名 16 × 16 字號 → 字（99 字） |

## 輸出（`mahjong/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 21 人：名前、読み、[EXT]出典、頭像調色盤、頭像與台詞串流位址、參數原始值（22 nibble、8 旗標，意義未解） |
| `dialogue.csv` | 21 × 133 行：情境、表情碼與表情、上段、下段、字碼 |
| `situations.csv` | 66 個情境：起始行、行數、機率 n、旗標，附織田信長與朝香えり的第一行 |
| `yaku.csv` | 52 個役名 |
| `mahjong.xlsx` | 以上四張表（需 openpyxl） |
| `faces/` | 每人 7 張（`00_3_織田信長_笑.png`：普通、口 1、口 2、笑、泣、驚、怒） |
| `faces.png`、`names.png` | 全部頭像一覽；21 張名字圖 |
| `charset_sheet.png`、`glyph16_sheet.png` | 字型對照圖（`tools/charset_sheet.py`） |

## 進度

- ✓ 壓縮（KOEI LZ，位址內嵌在程式碼）
- ✓ 對手 21 人：名字圖與抄錄、調色盤選擇；打牌參數的位置與展開方式（意義未解）
- ✓ 頭像 21 × 7 張（說話 3 格、笑、泣、驚、56 × 56 的怒），台詞表情碼 → 頭像；kaodata 資料集 `mahjong-sfc`（147 張，表情放 `expressions`）
- ✓ 台詞 21 × 133 行、字型 212 碼；66 個情境的行範圍、機率與旗標（情境意義未解）
- ✓ 役名 52 個與 16 × 16 字型 99 字
- … 未解：參數與情境的意義、飜數表、規則設定的存放處、大会（進不去）、玩家組合臉、Rev 1–5（ROM_FORMAT.md §7）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_faces.py` | 打到豊臣秀吉說話前存 savestate；在 `$00:AB7C` 把說話的人換成 0–20、在 `$00:ABB4` 把表情碼換成 0–4。比對 WRAM `$7F:1000` 的頭像串流、VRAM `$E400` 的表情圖、`$EA20` 的說話臉（face 0–2 之一）、CGRAM 第 9–10 列、OAM 的調色盤號＝1＋`$01:8925`；未改動時是秀吉說自己的台詞 | 串流 21/21、表情 105/105、說話臉 105/105、調色盤 105/105、調色盤選擇 105/105、OK |
| `verify_dialogue.py` | 同一 savestate；21 人的 `$7F:F400` 台詞串流與 ROM 比對；00–D3 與 FF 每 16 碼一組寫進要顯示的行，比對台詞窗 BG1 tilemap（tile `0x6E + 2c`、調色盤 3）與字型 tile | 串流 21/21、字碼 213/213、字形 212/212、OK |
| `verify_janso.py` | 雀荘畫面捲動 0、3、6 次，找出每張卡片的 5 × 5 頭像與 6 × 2 名字圖，比對 VRAM tile、BG 調色盤、CGRAM 第 1–3 列；卡片依人物順序 | 21/21、OK |
| `verify_yaku.py` | 打到織田信長和牌（平和、ドラ）前存 savestate；在 `$00:C37A` 把役清單換成每輪 6 個，比對和牌畫面的 tilemap 與 99 個字的 tile | 未改動 OK、役名 52/52、字形 99/99、OK |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對；每人的 face＋6 個 expressions 與 label；checksums（含 `ch:<id>/<k>`，294 項） | 147/147、21/21、OK |
| `tools/charset_sheet.py` | ROM 字形和對照字並排，目視核對 | 台詞字型 212 碼、役名 99 字都對得上；碼 00 不是字 |

名字圖的抄錄用 `names.png` 目視核對；頭像的表情名稱用 `faces.png` 與台詞內容（表情碼 3 的行都是生氣的話）判斷。
