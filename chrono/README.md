# SFC クロノ・トリガー 音樂輸出

スクウェア，1995，SFC（HiROM 4 MB，日版）。不是光榮的作品，不出 kaodata。目前只做音樂：曲目 01–50 共 80 首轉成 SPC、OGG、MP3。格式與做法見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python chrono/tools/music.py [--songs 01,18] [--loops 2] [--fade 10]   # → chrono/output/music/（約 2 分鐘）
```

- ROM 預設直接讀 `_original/sfc/Chrono Trigger (Japan).zip`（`--rom` 可換）。
- 依賴：Mesen 2（`tools/mesen.py`，savestate 重播用 `tools/replay.py`）、Homebrew 的 `game-music-emu`（libgme）與 ffmpeg；SPC、渲染、轉檔用共用的 `tools/spc.py`。Mesen 會在 stderr 印大量 `Uninitialized memory read`，可以用 `2>&1 | rg -v Uninitialized` 濾掉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `tools/music.py` | 在標題畫面把第一個播放指令的曲號換成目標曲號，在第一次 key-on 時傾印 SPC700 狀態（PC 倒回 key-on 那條指令）；從 Akao 樂譜算前奏與循環，再用 libgme 波形量實際循環長度；轉 OGG（Opus）與 MP3，寫 `music.csv` |
| `data/music_zophar.tsv` | Zophar's Domain 的 SPC 合集 → 曲號（`[EXT]` 檔名、曲名、比對方式；出處見 `docs/ROM_FORMAT.md`），`tools/music.py` 併進 `music.csv`，也拿曲名當用途 |

## 輸出 `output/music/`

80 首，檔名 `NN_<種類>_<用途>`（NN 曲號；種類 `bgm` 循環、`jingle` 播完就停；用途是 Zophar 曲名轉成 kebab-case，沒有曲名的寫 `unknown`，格式照 `~/.claude/re-common.md` §10）：`.spc`（ID666 填長度與淡出）、`.ogg`（Opus 96k，48 kHz）、`.mp3`（LAME VBR `-q:a 2`，32 kHz）。長度是前奏＋循環 2 次＋淡出 10 秒，不循環的播完為止。`music.csv` 欄位是編號、種類、檔名、用途、前奏秒、循環秒、依據、`[EXT]` Zophar 檔名、曲名、比對方式。音源是 libgme 的 SPC 模擬，沒有和實機錄音比對過。

## 進度

- ✓ 曲目指標表 `$C7:0D18`（01–50）、播放指令（`$1E00` = 10、`$1E01` = 曲號，`$C7:0004`）；SPC ✅ emu+modified（曲號在 Lua 裡換掉；傾印出的 SPC `$2000` 和 ROM 的樂譜逐 byte 相同）
- ✓ 樂譜格式（FF6 那一代的 Akao）：音符、音長表、指令參數長度、迴圈與跳躍、tempo 換算；循環點 ✅ code（F6 跳躍）
- △ 循環長度：驅動來不及處理時會漏掉計時器步數，實際比樂譜慢；31 首用 libgme 波形量到（慢 0–1%，✅ emu），35 首比對不出，用樂譜的長度（🟡）；不循環的 14 首長度多留 3%
- △ 曲名：71 首和 Zophar 的美版 SPC 對上（🟡 reference）；12、19、1A、20、21、34、37、41、43 沒有對到
- … 未做：各曲在遊戲中的場景、音效、人物、地圖等其他資料
