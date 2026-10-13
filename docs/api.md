# API 規格（草稿）

前後端共用的介面約定。**目前是草稿**：內容依照前端 8 支畫面的需要起草，
文末「待確認」的項目定案前，前後端都不要當成定案實作。

改動規則：這份文件改了，`frontend/src/types/album.ts` 和後端要一起跟上。

## 通則

### 位址

- 所有 API 都在 `/api` 底下，例如 `GET /api/photos`。
- 開發時前端（`localhost:5173`）透過 Vite 的 proxy 把 `/api` 轉給 Flask，不必處理 CORS。

### 格式

- 請求與回應都是 JSON（上傳照片例外，用 `multipart/form-data`）。
- 欄位名稱用 **camelCase**（`thumbnailUrl`），跟前端型別一致。Flask 端輸出時自行轉換。
- 時間一律 ISO 8601 並帶時區，例如 `2026-10-17T18:42:00+08:00`。
- id 一律是字串，前端不假設它的格式。

### 照片網址

- 回應裡的 `url`、`displayUrl`、`thumbnailUrl` 都是**可以直接使用的網址**：開發時是 `/media/...` 這樣的路徑，
  換成雲端儲存後會是 `https://...` 的完整網址。前端兩種都直接放進 `<img src>` 即可。
- 前端不自己組網址。後端換儲存位置（本機磁碟 → 雲端）時，前端完全不用改。

### 身分

賓客不註冊、不設密碼，流程如下：

1. 賓客掃會場的 QR code，打開 `https://<網站>/?code=<活動碼>`。
   QR code 裡裝的就是這個網址，活動碼是網址的一部分。
2. 在歡迎頁輸入暱稱後，前端呼叫 `POST /api/guests`，拿到一組 `token`。
3. 前端把 `token` 存在手機（localStorage），之後每個請求都帶上：

   ```
   Authorization: Bearer <token>
   ```

4. 沒帶或帶錯 `token` 的請求一律回 `401`，前端導回歡迎頁。

**換瀏覽器或換裝置**：在「我的」頁產生一個「接續連結」（也可以顯示成 QR code），
在另一個瀏覽器或電腦打開，就會變成同一位賓客。連結裡放的是**一次性、30 分鐘內有效的接續碼**，
不是 token 本身——網址會留在瀏覽紀錄、可能被轉傳，直接放 token 等於把身分永久交出去。

**每個裝置各有自己的 token**：用接續連結在電腦上登入後，手機原本的 token 仍然有效，兩邊都是同一位賓客。

沒有用接續連結就換手機或清除瀏覽器資料，會變成新的賓客，這是刻意接受的取捨（見 `backend/README.md`）。

### 分頁

列表類 API 用 cursor 分頁。cursor 是後端給的一個「書籤」字串，前端看不懂也不需要懂，
只要原封不動地傳回去：

```
GET /api/photos?limit=30                      ← 第一頁，不帶 cursor
GET /api/photos?limit=30&cursor=<nextCursor>  ← 下一頁，帶上一頁回傳的 nextCursor
```

```json
{ "items": [ ... ], "nextCursor": "eyJ0IjoiMjAyNi0xMC0xN1QxODo0MiJ9" }
```

`nextCursor` 為 `null` 代表沒有下一頁。`limit` 預設 30、上限 100。

**為什麼不用「第幾頁」或「從第幾張開始」**：婚禮當下一直有人在上傳。
如果用「從第 30 張開始」，你看完第一頁時前面又多了 5 張新照片，第二頁就會重複看到 5 張舊的。
cursor 記的是「上一頁最後一張是哪張」，不管前面新增多少張，下一頁都從那張之後接著算。

### 錯誤

HTTP 狀態碼表示錯誤類別，回應內容固定是這個形狀：

```json
{ "error": { "code": "photo_not_found", "message": "找不到這張照片" } }
```

- `code`：給程式判斷用的英文代碼，由本專案自訂。
- `message`：可以直接顯示給賓客看的中文訊息。

下表的狀態碼都是 HTTP 標準定義的，不是自訂的：

| 狀態碼 | 標準名稱 | 本專案何時用 |
| --- | --- | --- |
| `400` | Bad Request | 欄位缺漏或格式錯（例如祝福超過字數） |
| `401` | Unauthorized | 沒帶 token、token 無效、活動碼錯誤 |
| `403` | Forbidden | 有身分但沒權限（例如刪別人的照片） |
| `404` | Not Found | 東西不存在 |
| `413` | Content Too Large | 上傳的檔案太大 |
| `415` | Unsupported Media Type | 不支援的檔案格式 |
| `429` | Too Many Requests | 短時間內上傳太多（防止灌爆） |

## 資料形狀

### Guest

```json
{ "id": "g_1", "nickname": "小慧", "relation": "新娘的大學同學" }
```

`relation`（與新人的關係）是選填的自由文字，可能沒有。

### Photo

```json
{
  "id": "p_1",
  "kind": "photo",
  "url": "https://…/p_1/original.heic",
  "displayUrl": "https://…/p_1/display.jpg",
  "thumbnailUrl": "https://…/p_1/thumb.jpg",
  "width": 3024,
  "height": 4032,
  "durationSeconds": null,
  "uploader": { "id": "g_1", "nickname": "小慧" },
  "uploadedAt": "2026-10-17T18:42:00+08:00",
  "takenAt": "2026-10-17T18:40:12+08:00",
  "blessing": "祝你們白頭偕老！",
  "likeCount": 12,
  "likedByMe": false,
  "favoritedByMe": false,
  "tag": "banquet"
}
```

- `kind`：`photo` 或 `video`。`durationSeconds`（影片長度，秒，到小數一位）只有影片才有，照片是 `null`。
- **影片**沿用同一個形狀：`thumbnailUrl`、`displayUrl` 是**封面**（JPEG），`url` 是影片原檔（MP4 或 MOV，不轉檔），
  **播放用 `url`**。`width` / `height` 是畫面尺寸，已依拍攝方向轉正。
- 三種網址，**依用途選用**：
  - `thumbnailUrl`：長邊 480px 的 JPEG。**列表一律用這個。**
  - `displayUrl`：長邊 1600px 的 JPEG。**照片詳情等放大檢視用這個。**
  - `url`：原檔，格式就是賓客上傳的格式（可能是 HEIC，很多瀏覽器打不開）。照片只用在下載與匯出，**不要拿來顯示**；
    影片則是拿來播放的檔案（見上方）。
- `width` / `height`：原圖尺寸（已依拍攝方向轉正），前端拿來算比例排版，**一定要有**。
- `takenAt`：從 EXIF 讀出來的拍攝時間，讀不到就是 `null`。
- `tag`：`engagement`（訂婚・迎娶）、`banquet`（宴客）其中一個，上傳時由賓客選。
- `likedByMe`：我有沒有按讚。讚是**公開的**，所有人都看得到 `likeCount`，會算進上傳者的「獲得的讚」。
- `favoritedByMe`：我有沒有收藏。收藏是**私人的**書籤，只出現在自己「我的 → 收藏」，別人看不到、也不計數。

> 跟前端現況的差異：
> - `album.ts` 目前是 `tags: PhotoTag[]`（可多選），這裡改成單選的 `tag`。
> - `album.ts` 有 `location`（拍攝地點），這裡拿掉了。所有環節都在同一個婚宴會館，
>   地點不會提供任何資訊；照片是哪個環節拍的，看 `tag` 就知道。

### Blessing

```json
{
  "id": "b_1",
  "guest": { "id": "g_2", "nickname": "阿凱" },
  "text": "祝你們白頭偕老！",
  "createdAt": "2026-10-17T19:30:00+08:00",
  "editedAt": null,
  "photoId": "p_2"
}
```

- `photoId` 為 `null` 代表是留言牆上的獨立祝福，沒有附照片。
- `editedAt`：最後一次修改的時間，沒改過是 `null`。前端可以用它標示「已編輯」。

### WeddingPhoto

婚紗照是新人自己的照片，沒有上傳者、按讚、收藏，所以**不沿用 Photo**，另外定義。
婚紗集**不分系列**，所有婚紗照是同一串，依匯入時的檔名排序。

```json
{ "id": "wp_1", "displayUrl": "https://…", "thumbnailUrl": "https://…", "width": 3000, "height": 2000 }
```

婚紗集僅供觀賞，所以**不提供原檔網址**。

> 跟前端現況的差異：`album.ts` 的 `WeddingCollection`（分系列）要改成直接一串 `WeddingPhoto[]`，
> 婚紗集頁的系列 chips 也要拿掉。

## API 列表

### 身分

| 方法 | 路徑 | 需要 token | 用途 |
| --- | --- | --- | --- |
| `POST` | `/api/guests` | ✗ | 加入相簿：用活動碼 + 暱稱，向後端領一組 token |
| `POST` | `/api/guests/claim` | ✗ | 用接續碼領回同一位賓客的 token |
| `GET` | `/api/me` | ✓ | 目前這位賓客的資料與統計 |
| `PATCH` | `/api/me` | ✓ | 改暱稱或與新人的關係 |
| `POST` | `/api/me/transfer-codes` | ✓ | 產生接續連結 |
| `POST` | `/api/me/admin` | ✓ | 用管理員代碼把自己開通成管理員 |

前兩支是「領 token」的 API。這時賓客手上還沒有 token，所以這兩支不檢查 token，
改用活動碼或接續碼確認對方有資格進來。

`POST /api/guests`

```json
// 請求：relation 可不帶
{ "eventCode": "A1B2C3", "nickname": "小慧", "relation": "新娘的大學同學" }

// 回應 201
{ "token": "…", "guest": { "id": "g_1", "nickname": "小慧", "relation": "新娘的大學同學" } }
```

- `nickname`：必填，前後空白會被去掉，最多 20 字。
- `relation`：選填，最多 30 字。空字串視同沒填。

| 錯誤 `code` | 狀態碼 | 何時 |
| --- | --- | --- |
| `invalid_event_code` | `401` | 活動碼沒帶或不正確 |
| `nickname_required` | `400` | 暱稱是空的 |
| `nickname_too_long` / `relation_too_long` | `400` | 超過字數 |

其他需要 token 的 API，沒帶或帶錯 token 一律回 `401`、`code` 為 `unauthorized`。

`PATCH /api/me`

```json
// 請求：只帶要改的欄位。relation 傳空字串代表清除
{ "nickname": "小明" }

// 回應 200
{ "guest": { "id": "g_1", "nickname": "小明", "relation": "新娘的大學同學" } }
```

欄位限制同 `POST /api/guests`。

`POST /api/me/transfer-codes`

```json
// 回應 201
{ "code": "7Q2K9MPX", "expiresAt": "2026-10-17T21:30:00+08:00" }
```

- 完整連結由**前端**組成 `https://<前端網址>/continue?code=7Q2K9MPX`：前後端可能不在同一個網域，後端不知道前端的網址。
- 接續碼 8 碼，不含容易看錯的 `0`、`O`、`1`、`I`、`L`。有效時間由後端設定 `TRANSFER_CODE_MINUTES` 決定，預設 30 分鐘。

`POST /api/guests/claim`

```json
// 請求：大小寫、前後空白都不影響
{ "transferCode": "7Q2K9MPX" }

// 回應 200：跟 POST /api/guests 一樣的形狀。接續碼用過一次就失效
{ "token": "…", "guest": { ... } }
```

| 錯誤 `code` | 狀態碼 | 何時 |
| --- | --- | --- |
| `invalid_transfer_code` | `401` | 接續碼不存在或已經用過 |
| `transfer_code_expired` | `401` | 接續碼過期 |

`GET /api/me`

```json
{
  "guest": { "id": "g_1", "nickname": "小慧", "relation": "新娘的大學同學" },
  "isAdmin": false,
  "stats": { "uploaded": 12, "favorited": 8, "likesReceived": 24, "blessings": 1 }
}
```

`isAdmin` 只回給本人，不會出現在別人看到的 Guest 資料裡。

`POST /api/me/admin`

```json
// 請求
{ "adminCode": "…" }

// 回應 200
{ "guest": { ... }, "isAdmin": true }
```

**管理員**可以刪除任何照片與任何祝福（包括預先匯入的），用來處理不適當的內容。不能修改別人的祝福內容。

- 怎麼成為管理員：先照一般流程加入相簿，再打開 `https://<網站>/admin?code=<管理員代碼>`。
  代碼由後端環境變數 `ADMIN_CODE` 設定，可以交給一兩位信任的朋友，婚禮當天新人不必自己處理。
- 沒設 `ADMIN_CODE` 時管理員功能關閉，不影響賓客使用（開發模式預設為 `admin`）。

| 錯誤 `code` | 狀態碼 | 何時 |
| --- | --- | --- |
| `invalid_admin_code` | `403` | 代碼不正確 |
| `admin_disabled` | `403` | 後端沒設 `ADMIN_CODE` |

### 相簿

| 方法 | 路徑 | 用途 |
| --- | --- | --- |
| `GET` | `/api/stats` | 首頁的統計數字 |
| `GET` | `/api/photos` | 照片列表（分頁） |
| `GET` | `/api/photos/{id}` | 單張照片 |
| `POST` | `/api/photos` | 上傳一個檔案 |
| `DELETE` | `/api/photos/{id}` | 刪除照片：上傳者刪自己的，管理員可刪任何一張。回 `204` |
| `PUT` | `/api/photos/{id}/like` | 按讚 |
| `DELETE` | `/api/photos/{id}/like` | 收回讚 |
| `PUT` | `/api/photos/{id}/favorite` | 收藏 |
| `DELETE` | `/api/photos/{id}/favorite` | 取消收藏 |

以上都需要 token。

`GET /api/stats`

```json
{ "photoCount": 247, "guestCount": 32, "blessingCount": 47, "blessingGuestCount": 30 }
```

- `guestCount`：透過 app 加入相簿的賓客人數（不論有沒有上傳），不含預先匯入的祝福作者。
- `blessingGuestCount`：留過祝福的人數，含預先匯入的。留言牆標題「30 位賓客留下了 47 則祝福」用這個。

`GET /api/photos` 的篩選參數（都可以不帶）：

| 參數 | 對應畫面 |
| --- | --- |
| `tag=engagement` / `banquet` | 首頁的「訂婚・迎娶／宴客」 |
| `kind=video` | 首頁的「影片」 |
| `date=today` | 今天上傳的（以台灣時間算）。首頁目前沒有用到：婚禮當天每張都是今天，事後又都不是 |
| `uploader=me` | 個人頁的「我上傳的」 |
| `uploader=<guestId>` | 照片詳情點上傳者 → 這個人拍的所有照片 |
| `favorited=true` | 個人頁的「收藏」 |

排序固定是上傳時間新到舊。

按讚、收藏用 `PUT` / `DELETE`：重複按不會出錯，網路不穩重送也安全。回應是更新後的 Photo。

**刪除照片**時，照片檔、讚、收藏一併刪掉。照片上附的祝福會**留在留言牆**，只是 `photoId` 變成 `null`：
照片不當不代表祝福也有問題。不是上傳者也不是管理員時回 `403`、`code` 為 `not_your_photo`。

### 上傳

`POST /api/photos`，`multipart/form-data`，**一個請求傳一個檔案**。
一次選 10 張就送 10 個請求。好處是每張都有自己的進度條，失敗時只要重傳那一張。

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| `file` | ✓ | 照片或影片檔。是哪一種**看檔案內容判斷** |
| `tag` | | `engagement` / `banquet`，預設 `banquet`（多數賓客只參加宴客） |

回應 `201`，內容是建立好的 Photo。

**同一位賓客傳了一模一樣的檔案**（看檔案內容的 SHA-256，不看檔名），回應 `200` 與**已經有的那張** Photo，不會新增。
所以前端遇到逾時、斷線可以放心重送：第一次其實已經存好的話，不會變成兩張。不同賓客傳同一個檔案（例如 LINE 轉傳）各算各的。

| 錯誤 `code` | 狀態碼 | 何時 |
| --- | --- | --- |
| `file_required` | `400` | 沒帶檔案 |
| `invalid_tag` | `400` | 分類不正確 |
| `uploads_closed` | `403` | 相簿已截止上傳（`uploadsOpen: false`） |
| `file_too_large` | `413` | 超過單檔上限 |
| `unsupported_format` | `415` | 不是支援的照片或影片格式，或檔案壞掉。**看檔案內容判斷**，副檔名、Content-Type 改了也沒用 |
| `video_too_long` | `400` | 影片超過長度上限 |
| `too_many_uploads` | `429` | 一小時內傳太多 |

祝福**不跟著照片一起送**：所有檔案都傳完後，前端再呼叫一次 `POST /api/blessings` 並帶上第一張的 `photoId`。
否則一次傳 10 張，同一句祝福會在留言牆上出現 10 次。

**檔案格式與大小（暫定，可隨時調整，見下方「設定」）**

| | 格式 | 單檔上限 |
| --- | --- | --- |
| 照片 | JPEG、PNG、HEIC、WebP | 30 MB |
| 影片 | MP4、MOV | 95 MB、180 秒 |

- **影片不轉檔**，原檔直接播。轉檔很吃 CPU，婚宴高峰會塞車；iPhone 拍的 HEVC 在 iPhone 與多數新的 Android 都能播，
  播不了的瀏覽器顯示封面與說明。後端只讀長度、尺寸、拍攝時間，抓第一格當封面。
- 參考：手機預設拍 1080p，每分鐘約 60 MB（iPhone HEVC）～130 MB（多數 Android 的 H.264），
  所以 95 MB 大約是 iPhone 1 分半、Android 45 秒。
- 影片上限 95 MB 是因為 **Cloudflare 免費方案單一請求最多 100 MB**，超過的在到達後端前就會被擋掉。

- **原檔原封不動保存**，之後要整批匯出給新人時拿到的就是原始畫質。
- 後端另外產生 JPEG 縮圖給畫面用。iPhone 的 HEIC 很多瀏覽器（例如 Android 的 Chrome）看不懂，
  不轉的話別人會看到破圖。

**同時上傳的人很多時**

- 前端：每支手機**同時最多傳 3 張照片**、**影片一次只傳 1 支**（`uploadConcurrency`、`videoUploadConcurrency`），其餘排隊。
  不要 10 張同時送，會互搶網路，每張都變慢。
- 前端：斷線、伺服器忙碌或逾時（`502`～`504`、Cloudflare 的 `520`～`527`）時，等 3、10、30 秒各自動重試一次，
  靠上面的「重複檔案合併」保證不會重複。
- 伺服器同時要處理的照片數 ≈ 正在上傳的手機數 × `uploadConcurrency`。處理一張 iPhone HEIC 約 1～2 秒 CPU，
  排隊太長會超過 Cloudflare 的 100 秒逾時；**塞車時把 `UPLOAD_CONCURRENCY` 調成 1**，每個人慢一點，但不會失敗。
- 後端：每位賓客每小時上限 300 個檔案（照片影片合計，暫定），超過回 `429`。正常賓客碰不到，主要是防活動碼外流後被灌爆。
- 真正的瓶頸通常是**會場網路**，不是 API。

### 設定

| 方法 | 路徑 | 需要 token | 用途 |
| --- | --- | --- | --- |
| `GET` | `/api/config` | ✗ | 前端要遵守的各種上限，以及管理員設定的 Kahoot! 連結 |
| `GET` | `/api/settings/kahoot` | ✓（管理員） | 目前存的 Kahoot! 連結與開關 |
| `PUT` | `/api/settings/kahoot` | ✓（管理員） | 設定 Kahoot! 連結與開關 |

```json
{
  "maxPhotoBytes": 31457280,
  "maxVideoBytes": 99614720,
  "maxVideoSeconds": 180,
  "maxUploadsPerHour": 300,
  "uploadConcurrency": 3,
  "videoUploadConcurrency": 1,
  "maxBlessingLength": 200,
  "uploadsOpen": true,
  "kahootUrl": "https://kahoot.it/?pin=1234567"
}
```

**所有上限都只在後端設定一份**，前端開啟時向這支 API 讀取，不寫死在前端程式裡。
婚禮當天要臨時調整（例如會場網路太慢，把同時上傳數從 3 降到 1），只要改後端設定、重新啟動後端，
不必重新部署前端，賓客重新整理頁面就會套用。

`uploadsOpen` 為 `false` 時代表相簿已截止上傳，前端隱藏上傳按鈕，`POST /api/photos` 回 `403`。

**Kahoot! 連結**：遊戲的 PIN 碼可能提早拿到、也可能到主持人開始遊戲時才知道，所以不寫在前端、也不放環境變數，
由**管理員在 app 裡設定**。連結和開關分開：連結可以先存好，**開關打開**後所有人（包括還沒加入的歡迎頁）才會透過
`kahootUrl` 拿到。沒有連結或開關關著時是 `null`，前端不顯示按鈕。

`GET /api/settings/kahoot`、`PUT /api/settings/kahoot`

```json
// PUT 請求：整份覆蓋。url 傳空字串或 null 代表拿掉（開關也會一起關掉）；enabled 沒傳視為 false
{ "url": "https://kahoot.it/?pin=1234567", "enabled": true }

// 回應 200（GET 也是這個形狀）
{ "url": "https://kahoot.it/?pin=1234567", "enabled": true }
```

| 錯誤 `code` | 狀態碼 | 何時 |
| --- | --- | --- |
| `invalid_url` | `400` | 不是 `http://` 或 `https://` 開頭的網址，或超過 500 字 |
| `url_required` | `400` | 沒有連結卻要打開開關 |
| `invalid_body` | `400` | `enabled` 不是 `true`／`false` |
| `not_admin` | `403` | 不是管理員 |

### 祝福

| 方法 | 路徑 | 用途 |
| --- | --- | --- |
| `GET` | `/api/blessings` | 留言牆（分頁）；`guest=me` 只列自己的 |
| `POST` | `/api/blessings` | 留下祝福 |
| `PATCH` | `/api/blessings/{id}` | 修改自己的祝福，只能改 `text` |
| `DELETE` | `/api/blessings/{id}` | 刪除自己的祝福；管理員可刪任何一則。回 `204` |

`POST /api/blessings`

```json
// 請求：photoId 不帶就是留言牆上的獨立祝福
{ "text": "新婚快樂！", "photoId": "p_1" }

// 回應 201：建立好的 Blessing
```

- `text`：上限 200 字（`maxBlessingLength`），前後空白會被去掉。
- `photoId`：只能是**自己上傳的照片**。照片上的祝福就顯示在上傳者名字下方，看起來是上傳者說的話，所以不能掛到別人的照片上。

| 錯誤 `code` | 狀態碼 | 何時 |
| --- | --- | --- |
| `text_required` | `400` | 沒寫內容（只有空白也算） |
| `text_too_long` | `400` | 超過字數 |
| `photo_not_found` | `404` | `photoId` 指的照片不存在 |
| `not_your_photo` | `403` | `photoId` 是別人的照片 |
| `blessing_not_found` | `404` | 要改、刪的祝福不存在 |
| `not_your_blessing` | `403` | 要改、刪的是別人的祝福 |

修改時 `createdAt` 不變，所以留言牆上的順序不會因為改過而跳到最上面。
內容跟原本一樣時不算修改，`editedAt` 維持原樣。

**預先匯入的祝福**：婚禮前收到的祝福，可以用後端指令匯入（見 `backend/README.md`）。
它們的作者不是透過 app 加入的賓客，之後同名的人用手機加入，會被當成另一位賓客，
在自己的「我的祝福」裡看不到匯入的那則。

### 婚紗集

| 方法 | 路徑 | 用途 |
| --- | --- | --- |
| `GET` | `/api/wedding-photos` | 所有婚紗照 |

```json
{ "items": [ { "id": "wp_1", ... } ] }
```

婚紗照只有幾十張，一次全部回傳，不分頁（沒有 `nextCursor`）。

## 待確認

下面這些會影響 API 的樣子，定案後更新本文件：

1. **相簿開放期間。** 預計開放兩週到一個月。截止後要改成「只能看不能傳」（`uploadsOpen: false`），還是整站關閉？
2. **正式環境前後端是不是同一個網域？** 前端放 Cloudflare Pages、後端放別處的話，後端要開 CORS。

## 已決定不做

- **「不允許其他賓客看到」的照片**：設計稿的上傳頁有這個開關，目前沒有確認的需求，先不做。新人提出需要再加。
- **附加拍攝地點**：所有環節都在同一個會館，改用照片分類（`tag`）區分環節。
- **首頁的搜尋**：先拿掉按鈕，之後再決定要不要做。要做的話，打算做成「找賓客」：輸入暱稱，
  列出這個人拍的照片（`uploader=<guestId>` 已經有了，再加一支用暱稱找賓客的 API）。
