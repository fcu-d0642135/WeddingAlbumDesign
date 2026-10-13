/**
 * 上傳照片：POST /api/photos，一個請求一個檔案。見 docs/api.md 的「上傳」。
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
