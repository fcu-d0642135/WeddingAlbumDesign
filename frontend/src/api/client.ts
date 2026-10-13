/**
 * 所有 API 呼叫都走這裡：帶上 token、把錯誤統一成 ApiError。
 * 規格見 docs/api.md。網址一律是相對路徑 /api/...，開發時由 Vite 轉給 Flask。
 */
import { session } from '@/stores/session'

export class ApiError extends Error {
  constructor(
    /** HTTP 狀態碼；連不上伺服器時是 0 */
    readonly status: number,
    /** 後端給的錯誤代碼，例如 invalid_event_code */
    readonly code: string,
    /** 可以直接顯示給賓客看的中文訊息 */
    message: string,
  ) {
    super(message)
  }
}

type Query = Record<string, string | number | undefined>

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Query
}

/** token 失效時要做的事（清掉身分、回歡迎頁），由 main.ts 註冊，避免這裡直接依賴 router */
let onUnauthorized: () => void = () => {}

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

/**
 * 把錯誤回應轉成 ApiError。帶了 token 卻被拒絕時，代表 token 已失效
 * （例如開發時重建了資料庫），順便觸發重新加入。上傳（XHR）也共用這段。
 */
export function toApiError(status: number, data: unknown): ApiError {
  const error = (data as { error?: { code?: string; message?: string } } | null)?.error
  // 只有 token 本身失效（unauthorized）才清掉身分；接續碼、活動碼錯誤也是 401，
  // 但那時手上的 token 還是好的，不能因此把人登出
  if (status === 401 && session.token && error?.code === 'unauthorized') onUnauthorized()
  // 413 又沒有後端的錯誤內容：還沒到 Flask，就被前面的網頁伺服器（例如 nginx）以請求太大擋下
  if (!error && status === 413) {
    return new ApiError(status, 'file_too_large', '檔案太大了')
  }
  // 502/503/504 又沒有後端的錯誤內容：請求根本沒到 Flask（後端沒開、正在重啟、主機掛了）。
  // 520～527 是 Cloudflare 自己的錯誤，例如後端太忙、超過 100 秒沒回應時的 524
  if (!error && ((status >= 502 && status <= 504) || (status >= 520 && status <= 527))) {
    return new ApiError(status, 'server_unavailable', '暫時連不上伺服器，請稍後再試')
  }
  return new ApiError(
    status,
    error?.code ?? 'unknown_error',
    error?.message ?? '發生錯誤，請稍後再試',
  )
}

function buildQuery(query?: Query) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? '?' + qs : ''
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  // 展示版（npm run build:demo）沒有後端，改由 src/demo/ 的假後端回應。
  // 條件直接寫在這裡，正常 build 時整段連同 src/demo/ 會被拿掉
  if (import.meta.env.MODE === 'demo') {
    const { mockRequest } = await import('@/demo/mockServer')
    const res = await mockRequest(
      options.method ?? 'GET',
      path + buildQuery(options.query),
      options.body,
    )
    if (res.status >= 400) throw toApiError(res.status, res.data)
    return res.data as T
  }

  const headers: Record<string, string> = {}
  if (session.token) headers.Authorization = 'Bearer ' + session.token
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  let res: Response
  try {
    res = await fetch('/api' + path + buildQuery(options.query), {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch {
    throw new ApiError(0, 'network_error', '網路連線不穩，請稍後再試')
  }

  const data = await res.json().catch(() => null)

  if (!res.ok) throw toApiError(res.status, data)

  return data as T
}
