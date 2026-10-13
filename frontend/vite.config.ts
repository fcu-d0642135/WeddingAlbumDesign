import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

// 網站所在的路徑，結尾要有斜線。GitHub Pages 的展示版放在 /<repo 名稱>/ 底下，由部署流程設定
const base = process.env.BASE_PATH || '/'

export default defineConfig({
  base,
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      // 讓 Service Worker 在 dev 也能跑，方便在手機上驗證安裝流程
      devOptions: { enabled: true, type: 'module' },
      includeAssets: ['favicon.png', 'apple-touch-icon.png'],
      manifest: {
        name: '婚禮相簿',
        short_name: '婚禮相簿',
        description: '婚禮相片分享相簿',
        lang: 'zh-Hant',
        display: 'standalone',
        orientation: 'portrait',
        start_url: base,
        scope: base,
        theme_color: '#FAF6F0',
        background_color: '#FAF6F0',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'pwa-maskable-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        // 正式環境前後端同網域：直接打開 API 或照片網址時，要交給後端，不能被換成前端頁面
        navigateFallbackDenylist: [/^\/api\//, /^\/media\//],
        // 相片走執行期快取，不進 precache（precache 會在安裝時全部下載）
        runtimeCaching: [
          {
            // 只快取縮圖與顯示圖（後端固定命名成 thumb.jpg／display.jpg）。
            // 原檔動輒數 MB，存進來很快就把手機的快取空間吃光
            urlPattern: ({ url }) => /\/(thumb|display)\.jpg$/.test(url.pathname),
            handler: 'CacheFirst',
            options: {
              cacheName: 'photo-cache',
              expiration: {
                maxEntries: 300,
                maxAgeSeconds: 60 * 60 * 24 * 30,
                purgeOnQuotaError: true,
              },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            // 字型的樣式表：內容會隨瀏覽器支援度變動，用 SWR
            urlPattern: /^https:\/\/fonts\.googleapis\.com\//,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'google-fonts-stylesheets' },
          },
          {
            // 字型檔本身不會變，快取一年，離線時中文字才不會掉字
            urlPattern: /^https:\/\/fonts\.gstatic\.com\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-webfonts',
              expiration: { maxEntries: 60, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // 開發時把 /api 與照片檔 /media 轉給本機的 Flask（backend/），前端一律寫相對路徑，不必處理 CORS
    proxy: { '/api': 'http://localhost:5000', '/media': 'http://localhost:5000' },
  },
})
