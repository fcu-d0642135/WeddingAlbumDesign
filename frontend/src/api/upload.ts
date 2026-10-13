/**
 * 上傳照片或影片：POST /api/photos，一個請求一個檔案。見 docs/api.md 的「上傳」。
 * 是照片還是影片由後端看檔案內容判斷，這裡不必分。
 *
 * 用 XMLHttpRequest 而不是 fetch：fetch 拿不到上傳進度，每張照片就沒辦法有自己的進度條。
 */
import { session } from '@/stores/session'
import type { Photo, PhotoTag } from '@/types/album'
import { ApiError, toApiError } from './client'

/** 展示版：進度條假裝跑一秒左右，照片交給假後端 */
async function demoUpload(file: File, tag: PhotoTag, onProgress: (percent: number) => void) {
  for (let percent = 20; percent < 100; percent += 20) {
    await new Promise((resolve) => setTimeout(resolve, 150 + Math.random() * 150))
    onProgress(percent)
  }
  const { mockUpload } = await import('@/demo/mockServer')
  const res = await mockUpload(file, tag)
  if (res.status >= 400) throw toApiError(res.status, res.data)
  return res.data as Photo
}

export function uploadPhoto(
  file: File,
  tag: PhotoTag,
  /** 0–100 */
  onProgress: (percent: number) => void,
): Promise<Photo> {
  if (import.meta.env.MODE === 'demo') return demoUpload(file, tag, onProgress)

  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)
    form.append('tag', tag)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/photos')
    if (session.token) xhr.setRequestHeader('Authorization', 'Bearer ' + session.token)
    xhr.responseType = 'json'

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response as Photo)
      else reject(toApiError(xhr.status, xhr.response))
    }
    xhr.onerror = () => reject(new ApiError(0, 'network_error', '網路連線不穩，請稍後再試'))

    xhr.send(form)
  })
}

/** 第 1、2、3 次重試前各等多久。婚宴高峰時伺服器塞車，等久一點再試比較容易成功 */
const RETRY_DELAYS_MS = [3_000, 10_000, 30_000]

/** 網路斷線、伺服器太忙或逾時：等一下再試就可能成功。其他錯誤（格式不對、太大）怎麼試都一樣 */
function isRetryable(e: unknown) {
  return e instanceof ApiError && (e.code === 'network_error' || e.code === 'server_unavailable')
}

/**
 * 失敗時自動重試幾次，賓客不必自己按「重試」。
 * 重送是安全的：後端認得出同一個檔案，之前其實已經存好的話，會回傳那一張，不會變成兩張。
 */
export async function uploadWithRetry(
  file: File,
  tag: PhotoTag,
  onProgress: (percent: number) => void,
  /** 要開始第幾次重試時通知，畫面可以顯示「重新上傳中」 */
  onRetry: (attempt: number) => void,
): Promise<Photo> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await uploadPhoto(file, tag, onProgress)
    } catch (e) {
      const delay = RETRY_DELAYS_MS[attempt]
      if (delay === undefined || !isRetryable(e)) throw e
      onRetry(attempt + 1)
      onProgress(0)
      // 加一點隨機：大家同時失敗時，不要又同時重送
      await new Promise((resolve) => setTimeout(resolve, delay * (0.75 + Math.random() * 0.5)))
    }
  }
}
