# backend

Python 3.14 + Flask。API 規格寫在 [docs/api.md](../docs/api.md)（目前是草稿）。

## 環境需求

Python 3.14。套件用 pip + `requirements.txt` 管理。

## 第一次設定

以下指令都在 `backend/` 底下執行（Windows）：

```bash
py -3.14 -m venv .venv
```

啟動虛擬環境（Git Bash 用 `source .venv/Scripts/activate`，cmd 用 `.venv\Scripts\activate`），再安裝套件：

```bash
pip install -r requirements-dev.txt
```

`flask` 指令會自動讀 `.flaskenv`，以開發模式啟動，所以不必加 `--app app --debug`。

| 指令 | 用途 |
| --- | --- |
| `flask run` | 開發伺服器（http://localhost:5000），改程式會自動重啟 |
| `flask seed` | 建立測試用的賓客、照片、祝福與讚，並印出兩組 token。加 `--reset` 會先清空所有資料。只能在開發模式執行 |
| `flask import-wedding 資料夾` | 匯入婚紗照，見下方「匯入婚紗照」。加 `--replace` 先清掉舊的、`--dry-run` 只預覽 |
| `flask import-blessings 檔案.csv` | 匯入婚禮前收到的祝福留言，見下方「預先匯入祝福」。加 `--dry-run` 只預覽不寫入 |
| `pytest` | 跑全部測試 |

## 結構

```
backend/
├── app/
│   ├── __init__.py    # create_app()：組裝 Flask app
│   ├── config.py      # 設定與各種上限，都可用環境變數覆蓋
│   ├── errors.py      # 錯誤一律回 { "error": { code, message } }
│   ├── db.py          # 資料庫連線
│   ├── models.py      # 資料表
│   ├── auth.py        # 發 token、驗 token（@require_guest）
│   ├── storage.py     # 照片檔的存放與網址，換雲端儲存只改這裡
│   ├── images.py      # 照片轉檔：轉正方向、讀拍攝時間、產生顯示用與縮圖
│   ├── videos.py      # 影片：讀長度與拍攝時間、抓封面（不轉檔）
│   ├── pagination.py  # 列表 API 共用的 cursor 分頁
│   ├── seed.py        # flask seed 的測試資料
│   ├── import_blessings.py  # flask import-blessings
│   ├── import_wedding.py    # flask import-wedding
│   └── api/           # 一類功能一個模組，都掛在 /api 底下
├── tests/
├── .flaskenv              # flask 指令的開發設定（只放可公開的內容）
├── requirements.txt       # 正式環境的套件
└── requirements-dev.txt   # 開發用（pytest 等），會連同 requirements.txt 一起裝
```

## 設定（環境變數）

| 名稱 | 預設 | 說明 |
| --- | --- | --- |
| `EVENT_CODE` | 開發時為 `dev` | QR code 網址裡的活動碼。**沒設又不是開發模式就拒絕啟動** |
| `ADMIN_CODE` | 開發時為 `admin` | 開通管理員的代碼（`/admin?code=…`）。正式環境沒設就沒有管理員，不影響賓客使用 |
| `DATABASE_URL` | `sqlite:///wedding.db` | 相對路徑放在 `instance/` 底下 |
| `MEDIA_DIR` | `instance/media/` | 照片檔存放的資料夾 |
| `MEDIA_BASE_URL` | `/media` | 回給前端的照片網址開頭。換成雲端儲存時改成 CDN 網址 |

各種上限（同時上傳數、檔案大小、截止上傳）也都能用環境變數調整，名稱見 `app/config.py`。

## 資料庫

- 開發用的資料庫在 `instance/wedding.db`，照片檔在 `instance/media/`，都已被 git 忽略。
- SQLite 開了 WAL 模式，`wedding.db` 旁邊會多出 `wedding.db-wal`、`wedding.db-shm`，三個檔是一組。
  **備份時不要只複製 `wedding.db`**（最近寫入的資料可能還在 `-wal` 裡）：先停掉後端再複製三個檔，
  或在執行中用 `sqlite3 wedding.db ".backup 備份檔.db"`。
- 時間一律以**不帶時區的 UTC** 存進資料庫，回給前端時才轉成台灣時間（`+08:00`）。
- 開發時照片檔由 Flask 的 `/media/...` 送出；正式環境改由網頁伺服器或雲端儲存直接提供。
- 啟動時會自動建立還不存在的資料表，並替既有的資料表補上**可以是空值的新欄位**（例如影片長度）。
  其他改動（改型別、刪欄位、新增必填欄位）不會自動套用，刪掉 `instance/wedding.db` 再啟動即可（開發資料會一起清掉）。
- 正式上線前會加上 migration 工具，屆時改欄位就不必刪資料庫。

## 匯入婚紗照

新人的婚紗照（約 60 張）放在**同一個資料夾**，用 `flask import-wedding` 匯入。正式環境也能執行。

- **顯示順序依檔名**，數字照大小排（`2.jpg` 在 `10.jpg` 前面）。建議命名成 `01.jpg`、`02.jpg`…
- 只讀資料夾第一層的 JPEG、PNG、HEIC、WebP，其他檔案與子資料夾會略過。
- 有任何一張讀不了，整批都不匯入，並列出是哪幾張。
- 重複執行只會加入新的檔名；整批換掉請加 `--replace`。
- **原檔不保存**：婚紗集僅供觀賞，只產生顯示用（1600px）與縮圖。新人手上本來就有原檔。

## 預先匯入祝福

婚禮前收到的祝福（卡片、訊息）整理成 CSV，用 `flask import-blessings` 匯入，會出現在留言牆上。
正式環境也能執行。

```
名字,祝福,關係
阿凱,祝你們白頭偕老！,新郎的大學室友
美玲阿姨,新婚快樂,
```

- 「名字」必填，「關係」可以留空或整欄省略。用 Excel 存成「CSV UTF-8」即可。
- 有名字但「祝福」是空的那列會直接跳過，其他列照常匯入；匯入時會列出跳過了哪幾列。
- 檔案裡的順序就是留言牆上的順序，第一列在最上面。
- 任何一列有問題，整批都不匯入，並列出是哪幾列。
- 重複匯入同一個檔案不會重複新增。
- 匯入的作者不能登入；之後同名的人用手機加入，會是另一位賓客。

## 影片

- 影片**不轉檔**，原檔直接拿來播；後端只用 PyAV 讀長度、尺寸、拍攝時間，抓第一格當封面。
- 上限：`MAX_VIDEO_BYTES`（預設 95 MB，因為 Cloudflare 免費方案單一請求最多 100 MB）、`MAX_VIDEO_SECONDS`（預設 180 秒）。前端一次只傳一支（`VIDEO_UPLOAD_CONCURRENCY`）。
- 收到的檔案超過 500 KB 時，Werkzeug 會先寫進暫存檔，不會整支放在記憶體裡。
- **正式環境的網頁伺服器要放寬請求大小與逾時**（例如 nginx 的 `client_max_body_size 100m`），
  否則影片會在到達 Flask 之前就被擋下。會場網路慢時，一支 95 MB 的影片可能要傳好幾分鐘。
- 同一位賓客傳了一模一樣的檔案（看 SHA-256），回傳已經有的那張，不會新增：前端逾時自動重送時才不會重複。
  `photos` 表有 `(uploader_id, content_hash)` 的唯一索引，兩個請求同時寫入也只會留下一筆。

## 慣例

- **新增套件**：寫進 `requirements.txt`（開發才用的寫進 `requirements-dev.txt`），用 `==` 釘死版本，
  上方加一行註解說明用途。不要用 `pip freeze` 整包倒進去，會分不清哪些是自己要的。
- **改了程式就跑 `pytest`**。這個 repo 沒有 CI，測試是後端唯一的把關。

## 已定

- **資料庫**：SQLite（透過 SQLAlchemy 存取，之後要換 PostgreSQL 改動很小）。
- **上傳**：照片先傳給 Flask，再由 Flask 存檔。不讓手機直接傳到雲端儲存。
- **照片網址**：一律由 API 回傳，前端不自己組網址。
- **存檔**：包成獨立的一層。開發時存本機磁碟，之後換雲端只換這一層。
- **進入相簿**：會場提供 QR code。
- **賓客身分**：第一次進來時由後端發一個匿名代號，存在手機裡。不做帳號密碼。
  換手機或清除瀏覽器資料會變成新的賓客，這是刻意接受的取捨。

## 待決

- 正式環境的相片儲存（研究中，候選 AWS S3 等物件儲存）

`frontend/src/types/album.ts` 描述了前端目前假設的資料形狀，但那是前端單方面寫的，
不是雙方談好的 API 規格——要當規格用之前先確認。
