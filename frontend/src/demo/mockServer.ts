/**
 * 展示版用的假後端：照著 docs/api.md 的行為，在瀏覽器裡回應 /api 的請求。
 * 只有 `npm run build:demo`（vite 的 mode 為 demo）會用到，正常的 build 不會打包進去。
 *
 * 資料只存在記憶體，重新整理就回到初始的假資料；身分（token）仍記在手機上，
 * 所以重新整理後還是同一位賓客，只是剛上傳的照片、留言不見了。
 */
import { session } from '@/stores/session'
import type { Blessing, Guest, Page, Photo, PhotoTag, WeddingPhoto } from '@/types/album'
import { BLESSINGS, GUESTS, LIKES, PHOTOS, WEDDING, gradientImage, sizeOf } from './fixtures'

export interface MockResponse {
  status: number
  data: unknown
}

interface DemoGuest extends Guest {
  isAdmin: boolean
}

interface DemoPhoto extends Omit<Photo, 'uploader' | 'likeCount' | 'likedByMe' | 'favoritedByMe'> {
  uploaderId: string
  likedBy: Set<string>
  favoritedBy: Set<string>
}

const ADMIN_CODE = 'admin'
const TAGS: PhotoTag[] = ['engagement', 'welcome', 'ceremony', 'banquet']
const MINUTE = 60_000

let nextId = 1
const newId = (prefix: string) => `${prefix}_demo${nextId++}`

const guests = new Map<string, DemoGuest>()
const photos: DemoPhoto[] = []
const blessings: Blessing[] = []
const weddingPhotos: WeddingPhoto[] = []
/** 接續碼 → 賓客 id */
const transferCodes = new Map<string, string>()
let kahootUrl: string | null = null

function seed() {
  const seeded = GUESTS.map(([nickname, relation]) => {
    const guest: DemoGuest = { id: newId('g'), nickname, isAdmin: false }
    if (relation) guest.relation = relation
    guests.set(guest.id, guest)
    return guest
  })

  // 最早的一張在 2 小時前，之後每 10 分鐘一張
  const started = Date.now() - 120 * MINUTE
  PHOTOS.forEach(([uploader, w, h, tag], i) => {
    const { width, height } = sizeOf(w, h)
    const image = gradientImage(width, height, i)
    photos.unshift({
      id: newId('p'),
      kind: 'photo',
      url: image,
      displayUrl: image,
      thumbnailUrl: image,
      width,
      height,
      durationSeconds: null,
      uploaderId: seeded[uploader]!.id,
      uploadedAt: new Date(started + 10 * MINUTE * i).toISOString(),
      takenAt: null,
      tag,
      likedBy: new Set(),
      favoritedBy: new Set(),
    })
  })
  // photos 是新到舊，seed 的索引是舊到新
  const byIndex = (i: number) => photos[photos.length - 1 - i]!

  BLESSINGS.forEach(([author, text, photoIndex], i) => {
    blessings.push({
      id: newId('b'),
      guest: toGuest(seeded[author]!),
      text,
      createdAt: new Date(Date.now() - 5 * MINUTE * i).toISOString(),
      editedAt: null,
      photoId: photoIndex === null ? null : byIndex(photoIndex).id,
    })
  })
  for (const [guest, photoIndex] of LIKES) byIndex(photoIndex).likedBy.add(seeded[guest]!.id)

  WEDDING.forEach(([w, h], i) => {
    const { width, height } = sizeOf(w, h)
    const image = gradientImage(width, height, i + 3)
    weddingPhotos.push({ id: newId('wp'), displayUrl: image, thumbnailUrl: image, width, height })
  })
}
seed()

// ── 共用 ──────────────────────────────────────────────

const ok = (data: unknown, status = 200): MockResponse => ({ status, data })
const fail = (status: number, code: string, message: string): MockResponse => ({
  status,
  data: { error: { code, message } },
})

function toGuest(g: DemoGuest): Guest {
  return g.relation
    ? { id: g.id, nickname: g.nickname, relation: g.relation }
    : { id: g.id, nickname: g.nickname }
}

function toPhoto(p: DemoPhoto, viewerId: string): Photo {
  const { uploaderId, likedBy, favoritedBy, ...rest } = p
  return {
    ...rest,
    uploader: toGuest(guests.get(uploaderId)!),
    blessing: blessings.find((b) => b.photoId === p.id)?.text ?? null,
    likeCount: likedBy.size,
    likedByMe: likedBy.has(viewerId),
    favoritedByMe: favoritedBy.has(viewerId),
  }
}

/** cursor 就是下一頁從第幾筆開始，展示版不必防止新增造成的位移 */
function paginate<T>(items: T[], query: URLSearchParams): Page<T> {
  const start = Number(query.get('cursor') ?? 0) || 0
  const limit = Math.min(Number(query.get('limit') ?? 30) || 30, 100)
  const end = start + limit
  return { items: items.slice(start, end), nextCursor: end < items.length ? String(end) : null }
}

/**
 * token 的內容就是賓客 id。重新整理後記憶體清空，但手機上的 token 還在，
 * 這時用手機上記的暱稱把同一位賓客補回來。
 */
function guestFromToken(token: string): DemoGuest | null {
  const id = token.startsWith('demo:') ? token.slice(5) : ''
  if (!id) return null
  let guest = guests.get(id)
  if (!guest) {
    guest = { id, nickname: session.nickname || '賓客', isAdmin: session.isAdmin }
    if (session.relation) guest.relation = session.relation
    guests.set(id, guest)
  }
  return guest
}

function cleanProfile(
  body: Record<string, unknown>,
): { nickname?: string; relation?: string } | MockResponse {
  const nickname = typeof body.nickname === 'string' ? body.nickname.trim() : undefined
  const relation = typeof body.relation === 'string' ? body.relation.trim() : undefined
  if (nickname !== undefined && !nickname) return fail(400, 'nickname_required', '請輸入暱稱')
  if (nickname && nickname.length > 20) return fail(400, 'nickname_too_long', '暱稱最多 20 個字')
  if (relation && relation.length > 30) return fail(400, 'relation_too_long', '關係最多 30 個字')
  return { nickname, relation }
}

function cleanText(body: Record<string, unknown>): string | MockResponse {
  const text = typeof body.text === 'string' ? body.text.trim() : ''
  if (!text) return fail(400, 'text_required', '請寫下祝福')
  if (text.length > 200) return fail(400, 'text_too_long', '祝福最多 200 個字')
  return text
}

const isResponse = (v: unknown): v is MockResponse =>
  typeof v === 'object' && v !== null && 'status' in v && 'data' in v

// ── 不需要 token ─────────────────────────────────────

function join(body: Record<string, unknown>): MockResponse {
  const profile = cleanProfile({ nickname: '', ...body })
  if (isResponse(profile)) return profile
  const guest: DemoGuest = { id: newId('g'), nickname: profile.nickname!, isAdmin: false }
  if (profile.relation) guest.relation = profile.relation
  guests.set(guest.id, guest)
  return ok({ token: 'demo:' + guest.id, guest: toGuest(guest) }, 201)
}

function claim(body: Record<string, unknown>): MockResponse {
  const code = String(body.transferCode ?? '')
    .trim()
    .toUpperCase()
  const guestId = transferCodes.get(code)
  if (!guestId) return fail(401, 'invalid_transfer_code', '接續碼不正確或已經用過')
  transferCodes.delete(code)
  return ok({ token: 'demo:' + guestId, guest: toGuest(guests.get(guestId)!) })
}

function config(): MockResponse {
  return ok({
    maxPhotoBytes: 30 * 1024 * 1024,
    maxVideoBytes: 200 * 1024 * 1024,
    maxUploadsPerHour: 300,
    uploadConcurrency: 3,
    maxBlessingLength: 200,
    uploadsOpen: true,
    kahootUrl,
  })
}

// ── 身分 ──────────────────────────────────────────────

function me(guest: DemoGuest): MockResponse {
  const mine = photos.filter((p) => p.uploaderId === guest.id)
  return ok({
    guest: toGuest(guest),
    isAdmin: guest.isAdmin,
    stats: {
      uploaded: mine.length,
      favorited: photos.filter((p) => p.favoritedBy.has(guest.id)).length,
      likesReceived: mine.reduce((sum, p) => sum + p.likedBy.size, 0),
      blessings: blessings.filter((b) => b.guest.id === guest.id).length,
    },
  })
}

function updateMe(guest: DemoGuest, body: Record<string, unknown>): MockResponse {
  const profile = cleanProfile(body)
  if (isResponse(profile)) return profile
  if (profile.nickname) guest.nickname = profile.nickname
  if (profile.relation !== undefined) guest.relation = profile.relation || undefined
  return ok({ guest: toGuest(guest) })
}

function createTransferCode(guest: DemoGuest): MockResponse {
  const chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
  const code = Array.from(
    { length: 8 },
    () => chars[Math.floor(Math.random() * chars.length)],
  ).join('')
  transferCodes.set(code, guest.id)
  return ok({ code, expiresAt: new Date(Date.now() + 30 * MINUTE).toISOString() }, 201)
}

function becomeAdmin(guest: DemoGuest, body: Record<string, unknown>): MockResponse {
  if (body.adminCode !== ADMIN_CODE) return fail(403, 'invalid_admin_code', '管理員代碼不正確')
  guest.isAdmin = true
  return ok({ guest: toGuest(guest), isAdmin: true })
}

// ── 相簿 ──────────────────────────────────────────────

function listPhotos(guest: DemoGuest, query: URLSearchParams): MockResponse {
  const tag = query.get('tag')
  const kind = query.get('kind')
  const uploader = query.get('uploader') === 'me' ? guest.id : query.get('uploader')
  const today = new Date().toDateString()
  const items = photos.filter(
    (p) =>
      (!tag || p.tag === tag) &&
      (!kind || p.kind === kind) &&
      (!uploader || p.uploaderId === uploader) &&
      (query.get('favorited') !== 'true' || p.favoritedBy.has(guest.id)) &&
      (query.get('date') !== 'today' || new Date(p.uploadedAt).toDateString() === today),
  )
  return ok(
    paginate(
      items.map((p) => toPhoto(p, guest.id)),
      query,
    ),
  )
}

function stats(): MockResponse {
  return ok({
    photoCount: photos.length,
    guestCount: guests.size,
    blessingCount: blessings.length,
    blessingGuestCount: new Set(blessings.map((b) => b.guest.id)).size,
  })
}

function photoAction(guest: DemoGuest, method: string, id: string, action?: string): MockResponse {
  const photo = photos.find((p) => p.id === id)
  if (!photo) return fail(404, 'photo_not_found', '找不到這張照片')

  if (!action && method === 'GET') return ok(toPhoto(photo, guest.id))
  if (!action && method === 'DELETE') {
    if (photo.uploaderId !== guest.id && !guest.isAdmin) {
      return fail(403, 'not_your_photo', '只能刪除自己上傳的照片')
    }
    photos.splice(photos.indexOf(photo), 1)
    for (const b of blessings) if (b.photoId === id) b.photoId = null
    return ok(null, 204)
  }

  const set = action === 'like' ? photo.likedBy : action === 'favorite' ? photo.favoritedBy : null
  if (!set || (method !== 'PUT' && method !== 'DELETE')) return notFound()
  if (method === 'PUT') set.add(guest.id)
  else set.delete(guest.id)
  return ok(toPhoto(photo, guest.id))
}

/** 上傳不走 JSON，由 api/upload.ts 直接呼叫。照片用 object URL 顯示，重新整理就消失 */
export async function mockUpload(file: File, tag: PhotoTag): Promise<MockResponse> {
  const guest = guestFromToken(session.token)
  if (!guest) return fail(401, 'unauthorized', '請重新加入相簿')
  if (!TAGS.includes(tag)) return fail(400, 'invalid_tag', '分類不正確')
  if (!file.type.startsWith('image/')) return fail(415, 'unsupported_format', '只能上傳照片')

  const url = URL.createObjectURL(file)
  const { width, height } = await imageSize(url)
  const photo: DemoPhoto = {
    id: newId('p'),
    kind: 'photo',
    url,
    displayUrl: url,
    thumbnailUrl: url,
    width,
    height,
    durationSeconds: null,
    uploaderId: guest.id,
    uploadedAt: new Date().toISOString(),
    takenAt: null,
    tag,
    likedBy: new Set(),
    favoritedBy: new Set(),
  }
  photos.unshift(photo)
  return ok(toPhoto(photo, guest.id), 201)
}

function imageSize(url: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight })
    // HEIC 等瀏覽器看不懂的格式讀不到尺寸，當成直式照片
    img.onerror = () => resolve({ width: 1200, height: 1600 })
    img.src = url
  })
}

// ── 設定 ──────────────────────────────────────────────

function setKahoot(guest: DemoGuest, body: Record<string, unknown>): MockResponse {
  if (!guest.isAdmin) return fail(403, 'not_admin', '只有管理員可以設定')
  const url = typeof body.url === 'string' ? body.url.trim() : ''
  if (url && (!/^https?:\/\//.test(url) || url.length > 500)) {
    return fail(400, 'invalid_url', '請輸入 http:// 或 https:// 開頭的網址')
  }
  kahootUrl = url || null
  return ok({ kahootUrl })
}

// ── 祝福 ──────────────────────────────────────────────

function listBlessings(guest: DemoGuest, query: URLSearchParams): MockResponse {
  const items =
    query.get('guest') === 'me' ? blessings.filter((b) => b.guest.id === guest.id) : blessings
  return ok(paginate(items, query))
}

function createBlessing(guest: DemoGuest, body: Record<string, unknown>): MockResponse {
  const text = cleanText(body)
  if (isResponse(text)) return text
  const photoId = typeof body.photoId === 'string' ? body.photoId : null
  if (photoId) {
    const photo = photos.find((p) => p.id === photoId)
    if (!photo) return fail(404, 'photo_not_found', '找不到這張照片')
    if (photo.uploaderId !== guest.id)
      return fail(403, 'not_your_photo', '只能在自己的照片上留祝福')
  }
  const blessing: Blessing = {
    id: newId('b'),
    guest: toGuest(guest),
    text,
    createdAt: new Date().toISOString(),
    editedAt: null,
    photoId,
  }
  blessings.unshift(blessing)
  return ok(blessing, 201)
}

function blessingAction(
  guest: DemoGuest,
  method: string,
  id: string,
  body: Record<string, unknown>,
) {
  const index = blessings.findIndex((b) => b.id === id)
  const blessing = blessings[index]
  if (!blessing) return fail(404, 'blessing_not_found', '找不到這則祝福')
  const mine = blessing.guest.id === guest.id

  if (method === 'DELETE') {
    if (!mine && !guest.isAdmin) return fail(403, 'not_your_blessing', '只能刪除自己的祝福')
    blessings.splice(index, 1)
    return ok(null, 204)
  }
  if (method !== 'PATCH') return notFound()
  if (!mine) return fail(403, 'not_your_blessing', '只能修改自己的祝福')
  const text = cleanText(body)
  if (isResponse(text)) return text
  // 內容沒變不算修改；換成新物件，避免改到畫面上已經拿到的那一份
  const updated =
    text === blessing.text ? blessing : { ...blessing, text, editedAt: new Date().toISOString() }
  blessings[index] = updated
  return ok(updated)
}

// ── 路由 ──────────────────────────────────────────────

const notFound = () => fail(404, 'not_found', '找不到這個東西')

function route(
  method: string,
  path: string,
  query: URLSearchParams,
  body: Record<string, unknown>,
) {
  if (method === 'POST' && path === '/guests') return join(body)
  if (method === 'POST' && path === '/guests/claim') return claim(body)
  if (method === 'GET' && path === '/config') return config()

  const guest = guestFromToken(session.token)
  if (!guest) return fail(401, 'unauthorized', '請重新加入相簿')

  const key = `${method} ${path}`
  if (key === 'GET /me') return me(guest)
  if (key === 'PATCH /me') return updateMe(guest, body)
  if (key === 'POST /me/transfer-codes') return createTransferCode(guest)
  if (key === 'POST /me/admin') return becomeAdmin(guest, body)
  if (key === 'PUT /settings/kahoot') return setKahoot(guest, body)
  if (key === 'GET /stats') return stats()
  if (key === 'GET /photos') return listPhotos(guest, query)
  if (key === 'GET /wedding-photos') return ok({ items: weddingPhotos })
  if (key === 'GET /blessings') return listBlessings(guest, query)
  if (key === 'POST /blessings') return createBlessing(guest, body)

  const photoMatch = path.match(/^\/photos\/([^/]+)(?:\/(like|favorite))?$/)
  if (photoMatch)
    return photoAction(guest, method, decodeURIComponent(photoMatch[1]!), photoMatch[2])
  const blessingMatch = path.match(/^\/blessings\/([^/]+)$/)
  if (blessingMatch)
    return blessingAction(guest, method, decodeURIComponent(blessingMatch[1]!), body)

  return notFound()
}

/** 模擬網路延遲，讓載入中的畫面也看得到 */
const delay = () => new Promise((resolve) => setTimeout(resolve, 150 + Math.random() * 250))

/** url 是 /api 後面那段，例如 /photos?tag=banquet */
export async function mockRequest(
  method: string,
  url: string,
  body: unknown,
): Promise<MockResponse> {
  await delay()
  const parsed = new URL(url, 'http://demo')
  const data = (typeof body === 'object' && body !== null ? body : {}) as Record<string, unknown>
  return route(method, parsed.pathname, parsed.searchParams, data)
}
