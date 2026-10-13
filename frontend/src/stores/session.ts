import { reactive } from 'vue'
import type { UploadDraft } from '@/types/album'

/**
 * 跨頁共用的一點點狀態。目前只有「賓客資料」與「上傳流程」兩件事，
 * 用 reactive 就夠了，還不需要 Pinia。之後狀態變複雜再換。
 */

const NICKNAME_KEY = 'wedding-album:nickname'
const RELATION_KEY = 'wedding-album:relation'
const TOKEN_KEY = 'wedding-album:token'
const GUEST_ID_KEY = 'wedding-album:guest-id'
const ADMIN_KEY = 'wedding-album:admin'
const EVENT_CODE_KEY = 'wedding-album:event-code'

function read(key: string): string {
  try {
    return localStorage.getItem(key) ?? ''
  } catch {
    // 無痕模式或封鎖 site data 時 localStorage 會直接 throw
    return ''
  }
}

function write(key: string, value: string) {
  try {
    if (value) localStorage.setItem(key, value)
    else localStorage.removeItem(key)
  } catch {
    // 存不進去也無所謂，只是下次要重新加入
  }
}

/**
 * 活動碼來自會場 QR code 的網址（?code=...），第一次打開時記下來，之後加入相簿要用。
 * 開發時沒有 QR code，用後端開發模式的預設值 "dev"；展示版沒有後端，隨便一個值都能加入。
 */
function initialEventCode(): string {
  const fromUrl = new URLSearchParams(window.location.search).get('code')
  if (fromUrl) {
    write(EVENT_CODE_KEY, fromUrl)
    return fromUrl
  }
  const fallback = import.meta.env.DEV || import.meta.env.MODE === 'demo' ? 'dev' : ''
  return read(EVENT_CODE_KEY) || fallback
}

export const session = reactive({
  /** 後端發的身分代號。有它才算加入了相簿，見 docs/api.md 的「身分」 */
  token: read(TOKEN_KEY),
  /** 自己的賓客 id，用來判斷哪些祝福是自己寫的（才顯示修改、刪除） */
  guestId: read(GUEST_ID_KEY),
  /** 管理員可以刪除任何照片與祝福。以後端 /api/me 的 isAdmin 為準，這裡只是記一份 */
  isAdmin: read(ADMIN_KEY) === '1',
  eventCode: initialEventCode(),
  /** 賓客自己輸入的暱稱，這個 app 沒有帳號密碼 */
  nickname: read(NICKNAME_KEY),
  /** 與新人的關係，選填，例如「新娘的大學同學」 */
  relation: read(RELATION_KEY),
})

/** 暱稱與關係以後端回傳的為準，這裡只是存一份在手機上，畫面不必每次都問後端 */
export function setProfile(nickname: string, relation: string) {
  session.nickname = nickname
  session.relation = relation
  write(NICKNAME_KEY, nickname)
  write(RELATION_KEY, relation)
}

export function setToken(token: string) {
  session.token = token
  write(TOKEN_KEY, token)
}

export function setGuestId(id: string) {
  session.guestId = id
  write(GUEST_ID_KEY, id)
}

export function setAdmin(isAdmin: boolean) {
  session.isAdmin = isAdmin
  write(ADMIN_KEY, isAdmin ? '1' : '')
}

/** token 失效時清掉身分。暱稱留著，重新加入時歡迎頁可以直接帶入 */
export function clearToken() {
  session.token = ''
  session.guestId = ''
  session.isAdmin = false
  write(TOKEN_KEY, '')
  write(GUEST_ID_KEY, '')
  write(ADMIN_KEY, '')
}

/** 使用者從系統選取器挑到的檔案 */
export interface PickedMedia {
  id: string
  file: File
  /** createObjectURL 產生的預覽網址，用完要 revoke */
  previewUrl: string
}

/**
 * 上傳流程：選照片（第一步）→ 寫祝福（第二步）。
 * 檔案放在這裡而不是各自的元件裡，否則離開選擇頁時 object URL 會被回收，
 * 第二步就拿不到預覽了。
 */
export const uploadFlow = reactive({
  picked: [] as PickedMedia[],
  selectedIds: [] as string[],
  draft: emptyDraft(),
})

function emptyDraft(): UploadDraft {
  return { blessing: '', tag: 'banquet' }
}

function revokePicked() {
  for (const p of uploadFlow.picked) URL.revokeObjectURL(p.previewUrl)
}

export function setPicked(items: PickedMedia[]) {
  revokePicked()
  uploadFlow.picked = items
}

export function resetUploadFlow() {
  revokePicked()
  uploadFlow.picked = []
  uploadFlow.selectedIds = []
  uploadFlow.draft = emptyDraft()
}
