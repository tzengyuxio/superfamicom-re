---
status: adopted
created: 2026-11-07
---

# 遊戲研究的封存與素材庫

2026-11-07 定案，規範正本已移到 `~/.claude/re-common.md` §11 與 `~/.claude/repos.md`「研究成果的素材庫」；這份留作討論與試做的紀錄。適用於所有 `*-re` repo（superfamicom-re、famicom-re、megadrive-re、dosgame-re、kaodata-re）。

## 研究的目的

依優先順序：

1. **simagame 發文的素材基礎**：頭像表、統一度規則、冒險地圖等，包含圖像、影音、機制規則。
2. **了解遊戲機制**：給其他遊戲的開發當參考。
3. **個人喜好與好奇心**。

所以研究成果的主要用途是「被叫出來用」。保留的標準是：**之後會被取用的才留，只有重新研究才會用到的不留。**

## 狀態：進行中 → 封存 → 重啟

研究沒有明確的終點：一段時間後想知道的都知道了，就封存；幾個月或幾年後可能又想重啟。所以只用可逆的狀態，不用「結案」。

| 狀態 | repo 裡有什麼 | 其他地方有什麼 |
|------|---------------|----------------|
| **進行中** | 程式、docs、`roms/`、`output/`、`captures/`、`scratch/` | 素材庫可以已有部分成品 |
| **封存** | 程式、docs、`data/`（都在 git 裡） | 素材庫：成品、具名素材、素材型錄、captures；原始檔封存區：ROM 等原始檔 |
| **重啟** | 從原始檔封存區取回 ROM，跑 `scripts/rebuild.py <遊戲>`，`output/` 就回來了 | |

封存時，在該遊戲的主文件（README 進度表）記下：

- 狀態與日期
- 素材庫位置與原始檔位置
- 重啟時從哪裡開始：沿用 §9 交接段落的「下一輪候選」「remaining-unknowns」「負面結論」

`scripts/rebuild.py` 以單款遊戲為單位。研究進行中用它重跑、清掉過期檔；重啟時用它把 `output/` 做回來；封存前用它產出最新的成品與素材型錄。

## 保留什麼：四類

| 類別 | 例子 | 處理 |
|------|------|------|
| **成品** | 總覽圖、拼好的地圖、MP3／OGG、CSV／XLSX | 放進素材庫，直接打開就能看或用 |
| **具名素材** | 每位人物的頭像、每首曲子、每個地點圖、美少女夢工場的 NPC 頭像 | 放進素材庫；同一類打包成一個 zip（例如 `faces.zip`），附一份對照 CSV（編號 → 名字） |
| **無名碎片** | sprite 單格、地圖圖塊、中間 dump | 不保留，改留素材型錄；要用時再從原始檔重新解出 |
| **captures** | 標題畫面、遊戲畫面截圖、錄音 | 保留，放進素材庫（網站素材、發文素材） |

**具名和無名的分界是「有沒有身分」**：能用名字叫出來的（呂布的頭像、標題曲），就算還沒做總覽也保留；沒有人會用名字找的（圖塊 #0473），就不保留。分不清時歸為具名，因為多留的成本比較低。

### 素材型錄

素材型錄的用途：封存後還能先看一眼「遊戲檔案裡有什麼」，再決定要不要取回原始檔重新解出來。

- 把一類素材的所有項目排成縮圖，每格標上編號與來源位置（ROM 位移、檔名＋索引），讓重新解出時對得回去。
- 素材很多時，不做成一張超大圖，拆成多頁（`catalog/<類別>-p01.png`…），每頁固定格數，像型錄一樣翻；另附一份索引 CSV（頁、格、編號、來源位置）。
- 由 `rebuild.py` 產生，屬於 generated。
- 可以沿用 portrait-sheet 的分頁做法，但目的是查閱，不是發文，所以不需要排版裝飾。

## 放在哪裡

### 素材庫 `game-library/`

- **正本放在 `~/game-library/`**，不放在 iCloud 底下的 `~/Documents/`。理由見下方「雲端佔位符的風險」。
- **備份是單向的**：正本 → dongzhi 的 Personal（rsync），以及正本 → iCloud（複製一份到 iCloud Drive，不含 `_original/`）。備份端不回寫正本。
- **結構**：光榮的遊戲全部集中在 `koei/`，其他公司的照平台分；再往下是遊戲 id（照共通語言 §5）：

```
~/game-library/
├── koei/<slug>-<platform>/   光榮的所有平台，不分出自哪個 repo（san2-fc、san2-sfc、san2-pc98 並排）
├── fc/<slug>/                 其他公司的 FC 遊戲（famicom-re）
├── sfc/<slug>/                其他公司的 SFC 遊戲（superfamicom-re，例如 yokoyama、tenbu）
├── md/<slug>/                 其他公司的 MD 遊戲（megadrive-re）
├── dos/<slug>/                其他公司的 DOS 遊戲（dosgame-re）
├── _original/<platform>/      原始檔封存區，照平台分，光榮的也一樣（見下）
├── README.md                  素材庫的總說明
├── koei.md                    光榮遊戲的研究狀態，依系列分節
└── fc.md、sfc.md、md.md、dos.md   其他公司遊戲的研究狀態
```

- **研究狀態寫在素材庫，和平台資料夾同一層的 `<名稱>.md`**，一個平台一張表，不用逐層開資料夾就看得到全部。欄位：遊戲 id、名稱、repo 與資料夾、狀態、日期、素材庫位置、原始檔位置、備註。光榮的狀態可能和系列有關，所以 `koei.md` 依系列分節。repo 的 README 寫給外部讀者看，不寫封存狀態與本機路徑。

- 每款遊戲的資料夾：`README.md`（這份素材從哪個 repo、哪個 commit、怎麼產生）、成品、`<類別>.cbz`、`catalog/`、`captures/`。
- simagame、kaodata 之後可以改從素材庫取用，不必引用各 repo 裡的 `output/` 路徑，也就不受 repo 資料夾結構調整的影響。

### 雲端佔位符的風險

這台 Mac 的「桌面與文件」有同步到 iCloud，而且「最佳化 Mac 儲存空間」是開著的（2026-11-07 查 `com.apple.bird optimize-storage = 1`），所以 `~/Documents/` 裡的檔案可能被換成雲端佔位。

- macOS 14 以後，佔位檔保留原檔名與原大小，讀取時才下載。rsync 比對大小和時間時不讀內容，所以沒變動的檔案不受影響；有變動的檔案會觸發下載，離線時讀取失敗、報錯，rsync 不會用空內容覆蓋目的端。【推】依 macOS 的行為推論，還沒實測。
- 舊版 macOS 的佔位檔是 `.檔名.icloud`，原檔名會消失；這時用 rsync `--delete`，會把備份端的真檔刪掉。
- 正本不放 iCloud 底下，就完全避開這個問題。如果還是想放 `~/Documents/`，要先實測：用 `brctl evict` 把測試檔換成佔位，rsync 到暫存資料夾，比對內容。

### 原始檔封存區 `_original/`

repo 裡不留原始檔，但要確保「拿得回來，而且是同一份」。每份原始檔記下：檔名、hash（sha1）、來源（No-Intro 名、商店與 appid、網址）、取得日期。

| 種類 | 例子 | 怎麼封存 |
|------|------|----------|
| 主機 ROM | SFC／FC／MD 的 No-Intro zip | 原樣複製到 `_original/<平台>/`；No-Intro 名＋hash 就能確認是同一份 |
| DOS 發行包 | zip、fdi、hdi、d88、iso | 原樣複製到 `_original/dos/<slug>/`；分享者加進包裡的檔案也一起留（共通語言 §1） |
| Steam 等商店版 | 安裝後的遊戲資料夾 | 打包成壓縮檔，記下 appid、depot／build id；目的是省下重新下載的時間，不是唯一來源（帳號還在就能重新下載） |
| 從遠端映像只抓部分檔案 | archive.org iso 的 HTTP Range | 記下來源 URL 與取了哪些路徑就夠了（共通語言 §1），檔案本身可以不留 |

原始檔只做個人備份，絕不進版控，也不分享。`_original/` 只備份到 dongzhi，不進 iCloud。

## 刪什麼

封存時，只刪 repo 裡的工作檔：

- `roms/`（或對應的原始檔資料夾）：確認 `_original/` 有那份檔案、hash 一致之後才刪。
- `output/`：確認成品、具名素材、型錄都已經進素材庫之後才刪。
- `scratch/`：結論寫進 docs 之後才刪（共通語言 §4）。
- `captures/`：**不刪**，搬到素材庫（或在素材庫留一份，repo 裡的再刪）。

## 和現行規範的差異

- 共通語言 §1 把 extracted、generated 定為「隨時可以重跑」。這個前提是 ROM 一直都在；封存之後，素材庫就是唯一的成品，要和 capture 一樣保護。
- 現在的 export 角色只指「交給下游 repo」；素材庫是新的「交付給自己」的落點，要加進共通語言，也要加進 `repos.md`。
- 「`roms/` 不進版控、程式預設直接讀 zip」不變；改變的只是封存後 `roms/` 可以是空的。

## 待決定

已決定（2026-11-07）：

1. 素材庫正本放 `~/game-library/`。
2. 光榮的遊戲全部放 `koei/<slug>-<platform>/`，不分出自哪個 repo（`koei/san2-fc`、`koei/san2-sfc`、`koei/san2-pc98` 並排，方便跨平台對照）；其他公司的放平台資料夾。`_original/` 照平台分。
3. 具名素材打包成 cbz（不壓縮的 zip，看圖軟體可以直接翻）。
4. `_original/` 只備份到 dongzhi，不進 iCloud。
5. 第一款試做 superfamicom-re 的 san2。

還沒決定：

- dongzhi 的同步方式（rsync 指令、頻率、要不要排程）：先記著，之後再做；目前和 dongzhi 不在同一個網段，速度慢。

已有方向：

- 跨 repo 讀 ROM：megadrive-re 的 `san2/tools/build_kanji_map.py`、`bushou/verify_maps.py` 現在讀 superfamicom-re 的 `roms/`。規範定案後交給 megadrive-re，改讀 `~/game-library/_original/sfc/`；`_original/` 封存時不會被刪，比讀別的 repo 的 `roms/` 穩。

## 試做：san2（2026-11-07）

- `scripts/rebuild.py san2` 重跑後，建立 `~/game-library/koei/san2-sfc/`（3.7 MB）：
  - 成品：大地圖、全中國戰場圖、州 hex 圖、零件總覽、字碼圖、4 張 CSV、xlsx
  - 具名素材：`faces.cbz` 352、`portraits.cbz` 208、`battle_maps.cbz` 41。逐檔比對內容和 `output/` 相同；檔名用 UTF-8 旗標，日文檔名不會亂碼
  - 素材庫的 `README.md`：寫明產生的 commit、原始檔位置、每個檔案的內容與編號怎麼對
- 無名碎片 `mob_parts/` 640 個零件沒有保留，既有的 `mob_parts.png` 就是型錄，所以這款不用另做型錄工具。
- captures：san2 沒有截圖。
- 原始檔：原版與 Rev 1 的 zip 複製到 `~/game-library/_original/sfc/`，`SHA1SUMS.txt` 記下 zip 與裡面 .sfc 的 sha1。
- **沒做的**：
  - repo 裡的 `roms/`、`output/` 都還沒刪（見上面「跨 repo 讀 ROM 的依賴」）。
  - 還沒同步到 dongzhi。
  - 封存狀態寫在 `~/game-library/koei.md`（三國志一節），不寫進 `san2/README.md`。素材庫另有 `README.md` 說明結構。
- 試做時是手動操作。流程穩定後，再寫成 `scripts/archive.py <遊戲>`：依「成品／具名素材」清單複製並打包、寫素材庫 README、複製 ROM 並算 hash。

## 試做：yokoyama（2026-11-07）

- `scripts/rebuild.py yokoyama` 重跑後，建立 `~/game-library/sfc/yokoyama-1/`（59 MB，138 個檔）。素材庫的 id 照共通語言 §5 加代數：repo 的資料夾是 `yokoyama/`，素材庫是 `yokoyama-1`，之後的二代是 `yokoyama-2`。對應寫在素材庫的 README 和 `sfc.md`。
  - 成品：7 張 CSV、xlsx、頭像總覽、大地圖 3 張、地形圖、字型核對圖。
  - `faces.cbz`：224 張，逐檔比對內容相同。
  - `sheets/`：portrait-sheet 畫好的發文頁，頭像 5 頁、零件 11 頁。
  - `music/`：33 首 × SPC／OGG／MP3，加上 `music.csv`，整個資料夾照原樣保留。音樂本身就能直接播，cbz 只用在圖片。
  - `captures/screenshots/`：8 張截圖。素材庫 README 有一張來源表，記下擷取者、工具、Mesen 版本（2.1.1）、ROM 版本、日期與畫面，補上共通語言 §1 要求的 capture 來源。
- 原始檔：原版與 Rev 1 複製到 `_original/sfc/`，hash 加進 `SHA1SUMS.txt`。
- 狀態：新增 `~/game-library/sfc.md`，記一行 yokoyama-1。
- **型錄還是不用另做**：零件單張已經有零件 sheet（`sheets/yokoyama-parts-*`）當型錄，地圖圖塊和 sprite 原本就沒有拆成單張。兩款試下來，型錄只在「拆出了大量單張，卻沒有總覽」的遊戲才需要，所以型錄工具等遇到那種遊戲再寫。
- **`scripts/archive.py` 的規則可以照檔名來定**（試做兩款後的歸納，還沒寫）：
  - `output/` 第一層的檔案（CSV、XLSX、PNG）→ 原樣複製。
  - `output/<資料夾>/` 的單張圖片 → 打包成 `<資料夾>.cbz`。例外是有總覽圖、本身又沒有身分的碎片（`mob_parts/`、portrait-sheet 的 `parts/`），這類不保留。
  - `output/music/` → 原樣複製。
  - `output/portrait-sheet/*/out/` → `sheets/`；manifest 與中間檔不保留。
  - `captures/` → 原樣複製，素材庫 README 附來源表。
  - ROM → `_original/<平台>/`，hash 加進 `SHA1SUMS.txt`。
  - 哪些資料夾算碎片，每款遊戲在一個小清單裡標出來就好。

## `scripts/archive.py`（2026-11-07）

照上面的規則寫成 `scripts/archive.py <遊戲> [--library DIR]`。每款遊戲在 `GAMES` 裡設定素材庫 id、ROM 清單、碎片資料夾；其他都照檔名決定。

- 驗證：san2、yokoyama 輸出到暫存素材庫，和手動試做的逐檔比對 sha1，157 個檔案相同（`SHA1SUMS.txt` 原本行序不同，改成依路徑排序後一致）。之後用它重寫了正式素材庫的檔案。
- 不處理的：素材庫各款的 `README.md` 和狀態表（`koei.md`、`sfc.md`）要手寫，缺少時腳本會提示；素材庫裡已有的檔案會覆寫，但不刪。
- `output/` 裡不是單張圖片的子資料夾（winning2 的 `program96/` 整份版本輸出、bushou 的 `battle_maps/{castle,field}/`、san3 的 `tactical/`）用同一套規則往下一層處理。

## 光榮 27 款（2026-11-07）

san2 以外的 26 款光榮遊戲加上伊忍道，用 `rebuild.py` 重建後跑 `archive.py`，全部進了素材庫（`koei/<dataset id>/`，伊忍道沒有 kaodata，用 `inindou-sfc`）。

- ROM：每款的日版（含 Rev 1、香港版）和 `roms/` 裡的美版一起進 `_original/sfc/`，共 59 個 zip；`SHA1SUMS.txt` 和 `shasum` 逐一比對過。
- 碎片：只有 bushou、daikoukai、tenshouki（和 san2）的 `mob_parts/`，都有 `mob_parts.png` 總覽，所以不必另做型錄。
- 素材庫 README：由各款 repo README 的「輸出」表轉成（`faces/` 寫成 `faces.cbz` 等），再比對素材庫的檔案；europe 拿掉已移走的 `kaodata/`，winning2 補 `program96/`。轉換腳本是 scratch 級，沒有留在 repo。
- captures：這 27 款都沒有，來源表不必寫。
- 狀態表 `koei.md` 依系列分節，狀態寫「封存（repo 未清）」：使用者決定 repo 的 `roms/`、`output/` 等素材庫備份到 dongzhi 之後再刪。

## 原始檔只留一份（2026-11-07，共通語言 v1.3）

使用者決定 `roms/` 和 `_original/` 不要各放一份（太佔空間；megadrive-re 的 Mega-CD、kaodata-re 的 Steam 版尤其大）。

- 程式改成直接讀 `~/game-library/_original/sfc/`：路徑在 `tools/paths.py`（`GAME_LIBRARY` 可換素材庫位置），讀不到時提示從備份取回。`roms/` 裡另外 45 個還沒封存的 ROM 也放進去了，共 103 個，sha1 都核對過。
- 新 ROM 用 `scripts/add_rom.py` 放進去；`archive.py` 不再複製 ROM，只檢查 `GAMES` 列的 ROM 在 `_original/sfc/`、`SHA1SUMS.txt` 有記。
- 驗證：把 `roms/` 移開後跑 `rebuild.py --all`。
- 重啟只要跑 `rebuild.py`；本機為空間刪掉的原始檔，先從 dongzhi 取回。
- Steam 等商店版不進 `_original/`，只留一份紀錄（appid、depot、manifest id、build id、工具會讀的檔案的 sha1），安裝的資料夾當 runtime。

## 下一步

1. 使用者確認試做結果與草案方向。
2. 改寫共通語言（新增「素材庫」「封存狀態」兩節）與 `repos.md`（下游改從素材庫取用、megadrive-re 改讀 `_original/`），通知其他 `*-re` repo。
3. 之後要封存的遊戲：先 `rebuild.py`，再 `archive.py`，手寫素材庫 README 與狀態表一行；確認後才刪 repo 裡的 `roms/`、`output/`。
4. 素材庫備份到 dongzhi（與 iCloud，不含 `_original/`）；備份確認後刪光榮 28 款在 repo 裡的 `roms/`、`output/`，狀態改成「封存」。
5. 非光榮作品（yokoyama2、tenbu、chrono）的封存；yokoyama2 有 captures，要寫來源表。
