import { reactive } from 'vue'
import { fetchConfig, type AlbumConfig } from '@/api/config'

/** 拿不到後端設定時的保底值，跟後端預設一致 */
export const FALLBACK: AlbumConfig = {
  maxPhotoBytes: 30 * 1024 * 1024,
  maxVideoBytes: 95 * 1024 * 1024,
  maxVideoSeconds: 180,
  maxUploadsPerHour: 300,
  uploadConcurrency: 3,
  videoUploadConcurrency: 1,
  maxBlessingLength: 200,
  uploadsOpen: true,
  kahootUrl: null,
}

/**
 * 全站共用一份：管理員在「我的」頁改了 Kahoot! 連結，同一頁上的按鈕馬上跟著變。
 * 一開始先用保底值，後端回來後換成真的；上限只在後端設定一份。
 */
const shared = reactive<AlbumConfig>({ ...FALLBACK })

/** 後端定義的各種上限與設定（GET /api/config）。每次用到都重新問一次，Kahoot! 連結才會是最新的 */
export function useAlbumConfig(): AlbumConfig {
  fetchConfig(true)
    .then((c) => Object.assign(shared, c))
    .catch(() => {
      // 拿不到就沿用目前的值，不擋住畫面
    })
  return shared
}

/** 管理員改了 Kahoot! 連結或開關後，直接更新共用的那份（開關關著就傳 null） */
export function setSharedKahootUrl(url: string | null) {
  shared.kahootUrl = url
}
