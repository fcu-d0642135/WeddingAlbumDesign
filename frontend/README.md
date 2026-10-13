# frontend

Vue 3 + TypeScript + Vite，以 PWA 形式提供。

## 環境需求

Node.js `^20.19.0 || >=22.12.0`（Vite 8 的要求，建議 Node 24 LTS）。

```bash
cd frontend
npm install
npm run dev
```

| 指令 | 用途 |
| --- | --- |
| `npm run dev` | 開發伺服器（http://localhost:5173） |
| `npm run build` | 型別檢查 + 產出 `dist/` |
| `npm run build:demo` | 產出展示版，見下方「展示版」 |
| `npm run preview` | 預覽 build 產物 |
| `npm run type-check` | 只跑 `vue-tsc -b` |
| `npm run lint` | ESLint 檢查並自動修正 |
| `npm run format` | Prettier 格式化 |

## 慣例

- `@/` 指向 `src/`。
- 呼叫 API 一律寫相對路徑 `/api/...`。開發時 Vite 會轉給 `localhost:5000` 的 Flask，
  要用到 API 的畫面得先把後端跑起來（見 `backend/README.md`）。
- 所有 API 呼叫都經過 `src/api/client.ts`，它負責帶 token、把錯誤統一成 `ApiError`。
- 活動碼從會場 QR code 的網址 `?code=...` 讀取並記在手機上；開發時沒有 QR code，自動用後端的開發值 `dev`。
- 色票與版面尺寸的唯一來源是 `src/assets/tokens.css`，不要在元件裡寫死顏色。
- 佔滿螢幕高度一律用 `var(--screen-h)`，**不要直接寫 `100dvh`**：字體大小（`stores/textSize.ts`）用 CSS zoom 放大整個畫面，
  `100dvh` 會跟著被放大而超出螢幕，`--screen-h` 有除回去。
  `docs/design/extracted/` 裡的 `A` 物件是設計稿的凍結快照，不是現行來源。
- 照片列表一律透過 `src/stores/photoLists.ts` 取得：同樣的篩選條件共用同一份快取，
  照片詳情頁靠網址上的條件（例如 `?uploader=me`）找到使用者是從哪一串點進來的，左右滑只在那一串裡換。

## 展示版

給還沒架後端時讓別人看畫面用，網址：https://fcu-d0642135.github.io/WeddingAlbumDesign/

這個 repo 沒開 GitHub Pages，展示版放在可以開 Pages 的
[fcu-d0642135/WeddingAlbumDesign](https://github.com/fcu-d0642135/WeddingAlbumDesign) 的 `demo` 分支：

- 部署用的 workflow（`.github/workflows/deploy-demo.yml`）只放在 `demo` 分支，**不要合併進 `master`**。
- 把 `demo` 推到 WeddingAlbumDesign 的 `demo` 分支，那邊的 GitHub Actions 就會用 `npm run build:demo` 建置並部署。
- 要更新展示網站時，把 `master` 合併進 `demo`，再推上去。
- 不接後端。`import.meta.env.MODE === 'demo'` 時，`api/client.ts` 與 `api/upload.ts` 改呼叫
  `src/demo/mockServer.ts` 這個假後端，行為照 `docs/api.md`；假資料照搬後端的 `flask seed`。
  正常的 `npm run build` 不會打包 `src/demo/`。
- 資料只在記憶體，**重新整理就回到初始資料**（身分仍記在手機上）。上傳的照片只在自己的瀏覽器看得到。
- 管理員代碼是 `admin`（`/admin?code=admin`）。
- Kahoot! 一開始就帶範例連結 `https://kahoot.it/` 並打開開關，打開網站就看得到按鈕；用管理員身分可以關掉或換連結。
- 網站放在 `/<repo 名稱>/` 底下，由環境變數 `BASE_PATH` 決定（`vite.config.ts`，部署時自動帶 repo 名稱）。
  在 Git Bash 裡自己設 `BASE_PATH` 時要加 `MSYS_NO_PATHCONV=1`，否則會被轉成 Windows 路徑。
- 改了 API 行為（`docs/api.md`）時，`src/demo/mockServer.ts` 也要跟著改，展示版才不會跟實際行為不一致。

## PWA

- `vite-plugin-pwa`，`registerType: 'autoUpdate'`
- 相片走執行期快取（`CacheFirst`，上限 300 張／30 天），不進 precache
- 影片原檔不經過 Service Worker：播放時瀏覽器用 Range 一段一段要，被 SW 攔下來 iPhone 會播不了。
  `runtimeCaching` 只比對 `thumb.jpg`／`display.jpg`，新增規則時不要把 `/media/` 整個包進去
- `public/` 下的圖示都是從原始設計圖 `docs/design/app-icon.webp` 裁切、縮放出來的，分兩種：
  - `pwa-192x192.png`、`pwa-512x512.png`、`favicon.png`：跟原圖一樣，保留金邊，圓角外面透明。
  - `apple-touch-icon.png`、`pwa-maskable-512x512.png`：去掉金邊、填滿整個正方形。
    iPhone 和 Android 放到主畫面時會自己裁圓角，原圖若已經有圓角，就會露出黑邊或變成兩層圓角。
    `pwa-maskable-512x512.png` 另外把圖縮到 80%、四周補上背景色，因為有些 Android 會裁成圓形，滿版會切到字。
- iOS 沒有安裝提示 API，需另外做「加到主畫面」的引導畫面

## 已知的坑

- `vite.config.ts` 的 `devOptions.enabled` 讓 Service Worker 在 dev 也註冊。
  改了程式碼沒生效時，先到 DevTools → Application → Service Workers 點 Unregister。
