# SFC スーパー信長の野望・全国版 解析

KOEI，SFC（HiROM 512 KB，單一版本）。4 個劇本（1560／1560／1571／1582 年），17 國版 1 個、50 國版 3 個；大名用的人物 68 人、頭像 73 張。文字是 KOEI 自訂的雙位元組碼（`0x8140 + 字號`，636 字）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。FC 版的對應解析在 `~/works/famicom-re/zenkoku`：國資料、相鄰、地方、戰場地形表和 FC 版逐 byte 相同，大名的年齡、能力與頭像編號不同。

## 指令

```bash
.venv/bin/python zenkoku/export.py [--rom ROM] [--out DIR]          # → zenkoku/output/（CSV、XLSX、PNG）
.venv/bin/python zenkoku/export_kaodata.py --out <kaodata>/data-local/nobu2-sfc
.venv/bin/python zenkoku/verify_kaodata_export.py --dataset <kaodata>/data-local/nobu2-sfc
.venv/bin/python zenkoku/verify_scenarios.py                      # 約 20 秒
.venv/bin/python zenkoku/verify_persons.py                        # 約 2.5 分鐘
.venv/bin/python zenkoku/verify_maps.py                           # 約 9.5 分鐘
```

- ROM 預設直接讀 `roms/Super Nobunaga no Yabou - Zenkoku Ban (Japan).zip`，`--rom` 也接受 .sfc。
- 解壓縮用共用的 `tools/koei_lz.py`（表在 `0x9ECE`）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。
- 驗證腳本需要 Mesen 2（`tools/mesen.py`），savestate 重播用 `tools/replay.py`。Mesen 會印大量 `Uninitialized memory read`，用 `2>&1 | grep -v Uninit` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：字型與文字、劇本映像（大名、國、擁有者、相鄰、地方）、人物、頭像、大地圖（含開局上色）、戰場地圖 |
| `scenes.py` | 驗證共用的按鍵序列、BG3 文字讀取（以 ROM 字型逐 tile 比對） |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `nobu2-sfc` |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；名字；checksums |
| `verify_scenarios.py` | 劇本選單文字；4 劇本載入後 WRAM `$2000–$3D2A` 與 ROM 組出的映像逐 byte 比對 |
| `verify_persons.py` | 情報畫面：所有大名、國的記錄寫進尾張／織田後讀畫面（國名、大名名、12 項數值、年齢＋5 能力、頭像）；636 字逐一顯示；女性頭像 |
| `verify_maps.py` | 大地圖 4 劇本的上色結果；電腦對戰時把 17 國戰場對照表改成 0–49，比對 50 張戰場地圖的 BG2；劇本 2 織田打美濃 |
| `data/charset.txt` | 字型 636 字的字號 → 字對照 |

## 輸出（`zenkoku/output/`）

| 檔案 | 內容 |
|------|------|
| `scenarios.csv` | 4 劇本：標題、開始年、國數、大名數 |
| `persons.csv` | 68 人（人物 id 0–67）：姓名、姓、名、登場劇本、頭像 LZ 段 |
| `daimyo_scenarios.csv` | 4 劇本的大名（17／53／41／29 筆，含劇本 2–4 的明智・羽柴・柴田 slot 50–52）：人物 id、年齢、健康、野心、運、魅力、知力、大地圖花紋、領國、byte 7 |
| `provinces.csv` | 50 國＋17 國：地方 1–7、相鄰、戰場地圖號（17 國經對照表）、大地圖上色起點 |
| `province_scenarios.csv` | 4 劇本 × 國（17／50／50／50）：大名、金、借金、町、兵糧、石高、治水、民忠、民財、兵力、兵忠、訓練、武装、Unk24、未解的 `$312E` |
| `battle_maps.csv`、`battle_cells.csv` | 50 張戰場（17 國版哪些國用到、各地形格數）；每格地形（11 × 5） |
| `zenkoku.xlsx` | 以上各表（需 openpyxl） |
| `faces/`、`portraits/` | 每人頭像（`031_織田信長.png`）、全部 73 張（068–072 是姫） |
| `map_50.png`、`map_17.png` | 未上色的大地圖（240 × 160，放大 2 倍） |
| `map_scenario1-4.png` | 各劇本開局時的大地圖（依擁有者填花紋，和遊戲相同） |
| `map_50_labelled.png` | 50 國版，放大 4 倍並標出各國上色起點與國名 |
| `battle/` | 50 張戰場地圖（176 × 176；格子外塗黑） |
| `font.png` | 636 字的字型總覽 |

## 進度

- ✓ 壓縮（共用 `tools/koei_lz.py`）、全形字型 636 字與字碼（含 `00` 跳脫、「長宗我部」合字）
- ✓ 4 劇本：標題、載入程式的來源表（WRAM 完全一致）、開始年、大名數
- ✓ 大名：姓名、年齢、健康 野心 運 魅力 知力、人物 id（頭像）、大地圖花紋；人物 68 人
- ✓ 國：50／17 國的名稱、12 項數值、擁有者、地方、相鄰；17 國 → 50 國戰場對照表
- ✓ 頭像 73 張（人物 68＋姫 5）；kaodata 資料集 `nobu2-sfc`
- ✓ 大地圖：50／17 國 bitmap、開局上色（flood fill＋花紋）
- ✓ 戰場地圖 50 張：地形表、BG tilemap、tile、調色盤
- … 未解：半形字的碼表（數字以外推測）、`$312E` 等未知區、國的 Unk24、LZ 段 44–119 的圖、姫的名字、事件、戰鬥規則、水面動畫（ROM_FORMAT.md §9）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 劇本選單 BG3 文字與 ROM 文字逐字形比對；選劇本 1–4 後 600 幀讀 WRAM `$7E:2000–$3D2A` 與 `scenario_image` 比對 | 標題 4/4；4 劇本皆 7467 bytes 相同 |
| `verify_persons.py` | 情報畫面（尾張），把每筆大名／國記錄寫進 slot 24 後讀畫面文字（ROM 字型精確比對）與 VRAM 頭像 | 大名 140/140、國 167/167、兩輪自訂值 2/2、字型 71/71 輪（636 字）、姫頭像 5/5、調色盤 245/245 |
| `verify_maps.py` | 大地圖：`$7F:0000`、VRAM `0x4600`、BG2 tilemap、調色盤 2；電腦對戰（劇本 1）讀戰場表的位址與畫面；劇本 2 打美濃 | 大地圖 4/4；17 國對照表（美濃 → 22）OK；戰場 50/50；美濃 OK |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `Rom.face_rgb` 逐 pixel 比對、名字、checksums | 68/68、73/73、OK |

