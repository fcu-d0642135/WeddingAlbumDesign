# wedding-album

婚禮相簿專案。以 PWA 形式提供，賓客可加到手機主畫面使用。

前端展示版（假資料、不接後端）：https://fcu-d0642135.github.io/WeddingAlbumDesign/ ── 見 frontend/README.md 的「展示版」

前後端放在同一個 repo，但各自獨立：不共用依賴、不共用工具鏈、不共用建置。
根目錄沒有 task runner，所有指令都要先進到子專案目錄執行。

## 結構

```
wedding-album/
├── frontend/   # Vue 3 + TypeScript + Vite（PWA）── 見 frontend/README.md
├── backend/    # Python 3.14 + Flask ── 見 backend/README.md
└── docs/
    ├── api.md  # API 規格（前後端共用）
    └── design/ # 設計稿
```

語言／工具鏈專屬的設定（`package.json`、`.nvmrc`、`.gitignore` …）一律留在子專案內。
根目錄的 `.gitignore` 只處理環境變數與機密。

## 開發狀態

- [x] 前端骨架（路由、PWA、型別、lint）
- [x] 依風格 A 設計稿實作 8 支畫面（版面完成，互動多數尚未接線）
- [x] 後端選型（Python 3.14 + Flask）
- [x] 後端骨架（設定、錯誤格式、測試）
- [ ] API 規格（草稿：[docs/api.md](docs/api.md)，有待確認項目）
- [ ] 相片上傳

## Commit 訊息

[Conventional Commits](https://www.conventionalcommits.org/)：`<type>(<scope>): <中文描述>`
type 用 `feat` `fix` `refactor` `docs` `test` `chore`；scope 用 `frontend` `backend` `docs`，repo 層級的改動可省略。
