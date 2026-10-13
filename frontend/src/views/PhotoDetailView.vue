<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/api/client'
import { deletePhoto, fetchPhoto, setFavorited, setLiked } from '@/api/photos'
import PhotoSwiper from '@/components/PhotoSwiper.vue'
import {
  ensureLoaded,
  filterFromQuery,
  getPhotoList,
  loadMore,
  removePhoto,
  updatePhoto,
} from '@/stores/photoLists'
import { session } from '@/stores/session'
import type { Photo } from '@/types/album'

const props = defineProps<{ photoId: string }>()
const route = useRoute()
const router = useRouter()

/**
 * 左右滑動要在哪一串照片裡換張：由網址上的篩選條件決定（例如 ?uploader=me、?tag=banquet），
 * 跟列表頁用的是同一份快取，所以從哪裡點進來，就在那一串裡滑。
 */
const filter = computed(() => filterFromQuery(route.query))
const list = computed(() => getPhotoList(filter.value))

/** 直接打開分享連結、而那張不在列表已載入的範圍時，單獨抓這一張來顯示 */
const single = ref<Photo | null>(null)
const missing = ref(false)
const loadError = ref('')

const inList = computed(() => list.value.items.some((p) => p.id === props.photoId))
const photos = computed(() => (inList.value ? list.value.items : single.value ? [single.value] : []))

watch(
  () => props.photoId,
  async (id) => {
    if (inList.value) return
    missing.value = false
    loadError.value = ''
    await ensureLoaded(filter.value)
    if (list.value.items.some((p) => p.id === id)) return
    try {
      single.value = await fetchPhoto(id)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) missing.value = true
      else loadError.value = e instanceof ApiError ? e.message : '載入失敗，請稍後再試'
    }
  },
  { immediate: true },
)

const index = computed(() => photos.value.findIndex((p) => p.id === props.photoId))
const photo = computed(() => photos.value[index.value])

// 滑到倒數第三張就先載下一頁，滑到底時通常已經接上了
watch(index, (i) => {
  const l = list.value
  if (inList.value && !l.done && i >= l.items.length - 3) loadMore(filter.value)
})

/** 「3 / 30+」：還有下一頁沒載時，總數後面加 + */
const counter = computed(() => {
  if (!inList.value) return ''
  const l = list.value
  return `${index.value + 1} / ${l.items.length}${l.done ? '' : '+'}`
})

const slides = computed(() =>
  photos.value.map((p) => ({
    key: p.id,
    photo: p,
    ratio: p.width / p.height,
    video: p.kind === 'video' ? p.url : undefined,
  })),
)

/** 滑到別張時換掉網址，返回鍵才會直接回相簿，而不是一張張倒退 */
const current = computed({
  get: () => index.value,
  set: (i) => {
    const next = photos.value[i]
    if (next) {
      router.replace({ name: 'photo-detail', params: { photoId: next.id }, query: route.query })
    }
  },
})

const takenLabel = computed(() => {
  const p = photo.value
  if (!p) return ''
  const d = new Date(p.uploadedAt)
  return (
    String(d.getMonth() + 1) +
    '/' +
    d.getDate() +
    ' · ' +
    String(d.getHours()).padStart(2, '0') +
    ':' +
    String(d.getMinutes()).padStart(2, '0')
  )
})

function close() {
  if (window.history.state?.back) router.back()
  else router.push({ name: 'feed' })
}

// --- 按讚、收藏 -----------------------------------------------------------

/** 把更新後的照片換進所有列表（以及單獨抓來的那張），畫面上每個地方的數字才一致 */
function apply(p: Photo) {
  updatePhoto(p)
  if (single.value?.id === p.id) single.value = p
}

const actionError = ref('')
/** 同一張照片的請求還沒回來前，不接受下一次點擊，避免回應順序錯亂 */
const pending = new Set<string>()

/**
 * 先把畫面改掉（樂觀更新），按下去立刻有反應；再送給後端，以後端回傳的為準。
 * 失敗就改回原樣並顯示原因。
 */
async function toggle(change: (p: Photo) => Photo, send: (p: Photo) => Promise<Photo>) {
  const before = photo.value
  if (!before || pending.has(before.id)) return
  pending.add(before.id)
  actionError.value = ''
  const optimistic = change(before)
  apply(optimistic)
  try {
    apply(await send(optimistic))
  } catch (e) {
    apply(before)
    actionError.value = e instanceof ApiError ? e.message : '操作失敗，請稍後再試'
  } finally {
    pending.delete(before.id)
  }
}

function toggleLike() {
  toggle(
    (p) => ({ ...p, likedByMe: !p.likedByMe, likeCount: p.likeCount + (p.likedByMe ? -1 : 1) }),
    (p) => setLiked(p.id, p.likedByMe),
  )
}

// --- 刪除照片 -------------------------------------------------------------

const isMine = computed(() => !!photo.value && photo.value.uploader.id === session.guestId)
/** 上傳者刪自己的；管理員可刪任何一張。真正的權限由後端把關，這裡只決定要不要顯示選單 */
const canDelete = computed(() => isMine.value || session.isAdmin)
const deleteLabel = computed(() => {
  const label = photo.value?.kind === 'video' ? '刪除影片' : '刪除照片'
  return isMine.value ? label : label + '（管理員）'
})
const moreOpen = ref(false)
const deleting = ref(false)

// 換張時把選單收起來
watch(() => props.photoId, () => (moreOpen.value = false))

async function removeCurrent() {
  const target = photo.value
  if (!target || deleting.value) return
  const what = target.kind === 'video' ? '這支影片' : '這張照片'
  const question = isMine.value
    ? `確定要刪除${what}嗎？刪除後無法復原。`
    : `以管理員身分刪除「${target.uploader.nickname}」上傳的${what}？刪除後無法復原。`
  if (!window.confirm(question)) return

  deleting.value = true
  // 刪完要顯示同一串裡的下一張（沒有下一張就上一張）；這串只剩它的話就關掉
  const list = photos.value
  const i = list.findIndex((p) => p.id === target.id)
  const neighbor = list[i + 1] ?? list[i - 1]
  try {
    await deletePhoto(target.id)
    removePhoto(target.id)
    if (single.value?.id === target.id) single.value = null
    moreOpen.value = false
    if (neighbor) {
      router.replace({ name: 'photo-detail', params: { photoId: neighbor.id }, query: route.query })
    } else {
      close()
    }
  } catch (e) {
    actionError.value = e instanceof ApiError ? e.message : '刪除失敗，請稍後再試'
    moreOpen.value = false
  } finally {
    deleting.value = false
  }
}

function toggleFavorite() {
  toggle(
    (p) => ({ ...p, favoritedByMe: !p.favoritedByMe }),
    (p) => setFavorited(p.id, p.favoritedByMe),
  )
}
</script>

<template>
  <main v-if="photo" class="detail">
    <header class="bar">
      <button class="round" type="button" aria-label="關閉" @click="close">
        <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
      <span class="counter">{{ counter }}</span>
      <!-- 只有上傳者與管理員有選單；其他人留一塊空白，讓序號保持置中 -->
      <div v-if="canDelete" class="more">
        <button
          class="round"
          type="button"
          aria-label="更多"
          :aria-expanded="moreOpen"
          @click="moreOpen = !moreOpen"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="#fff"
            stroke-width="1.8"
            stroke-linecap="round"
          >
            <circle cx="5" cy="12" r="2" />
            <circle cx="12" cy="12" r="2" />
            <circle cx="19" cy="12" r="2" />
          </svg>
        </button>
        <div v-if="moreOpen" class="more-pop" role="menu">
          <button type="button" role="menuitem" :disabled="deleting" @click="removeCurrent">
            {{ deleting ? '刪除中…' : deleteLabel }}
          </button>
        </div>
      </div>
      <span v-else class="round-spacer" />
    </header>

    <div class="stage">
      <PhotoSwiper v-model="current" :slides="slides" />
    </div>

    <section class="panel">
      <span class="grip" />

      <div class="uploader">
        <RouterLink
          class="who"
          :to="{ name: 'guest-photos', params: { guestId: photo.uploader.id } }"
          :aria-label="'看' + photo.uploader.nickname + '拍的所有照片'"
        >
          <span class="avatar">{{ photo.uploader.nickname[0] }}</span>
          <div class="who-text">
            <p class="name">{{ photo.uploader.nickname }}</p>
            <p class="meta">{{ takenLabel }}</p>
          </div>
          <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M9 6l6 6-6 6" />
          </svg>
        </RouterLink>
        <button
          class="action"
          type="button"
          :aria-pressed="photo.favoritedByMe"
          :aria-label="photo.favoritedByMe ? '取消收藏' : '收藏'"
          @click="toggleFavorite"
        >
          <svg
            class="bookmark"
            :class="{ on: photo.favoritedByMe }"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linejoin="round"
          >
            <path d="M6 3h12v18l-6-4-6 4z" />
          </svg>
        </button>
        <button
          class="action"
          type="button"
          :aria-pressed="photo.likedByMe"
          :aria-label="photo.likedByMe ? '收回讚' : '按讚'"
          @click="toggleLike"
        >
          <svg
            class="heart"
            :class="{ on: photo.likedByMe }"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.8"
          >
            <path d="M12 21s-7-5-7-11a4 4 0 017-2.5A4 4 0 0119 10c0 6-7 11-7 11z" />
          </svg>
          <span class="likes">{{ photo.likeCount }}</span>
        </button>
      </div>
      <p v-if="actionError" class="action-error" role="alert">{{ actionError }}</p>

      <div v-if="photo.blessing" class="blessing">
        <!-- 上傳者就在正上方，這裡不再重複名字；標籤留著是為了卡片上緣的缺口裝飾 -->
        <span class="blessing-tag">祝福</span>
        <p class="blessing-text">{{ photo.blessing }}</p>
      </div>
    </section>
  </main>

  <!-- 照片被刪掉或網址打錯時，不要只留一片空白 -->
  <main v-else-if="missing || loadError" class="detail missing">
    <p>{{ missing ? '找不到這張照片' : loadError }}</p>
    <button class="missing-back" type="button" @click="close">回相簿</button>
  </main>

  <main v-else class="detail missing">
    <p>載入中…</p>
  </main>
</template>

<style scoped>
.detail {
  height: var(--screen-h);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--c-dark-bg);
  color: var(--c-dark-ink);
  position: relative;
}

.missing {
  align-items: center;
  justify-content: center;
  gap: 16px;
  font-size: 14px;
  color: var(--c-dark-ink-mute);
}

.missing-back {
  padding: 8px 20px;
  border: 1px solid var(--c-dark-line);
  border-radius: 18px;
  background: transparent;
  color: var(--c-dark-ink);
  font-size: 13px;
}

.bar {
  position: absolute;
  top: calc(var(--page-top) + 24px);
  left: 16px;
  right: 16px;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.round {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.round-spacer {
  width: 32px;
}

.more {
  position: relative;
}

.more-pop {
  position: absolute;
  top: 40px;
  right: 0;
  min-width: 160px;
  padding: 4px 0;
  border-radius: 10px;
  background: var(--c-card);
  box-shadow: var(--shadow-float);
}

.more-pop button {
  width: 100%;
  padding: 12px 16px;
  border: 0;
  background: transparent;
  text-align: left;
  font-size: 14px;
  color: var(--c-rose);
}

.round svg {
  width: 14px;
  height: 14px;
}

.counter {
  font-size: 11px;
  letter-spacing: 1px;
}

.stage {
  flex: 1;
  min-height: 0;
  padding: calc(var(--page-top) + 84px) 0 16px;
}

/* 留言區固定貼底；祝福太長時在面板內捲動，不把照片擠掉 */
.panel {
  flex-shrink: 0;
  max-height: calc(var(--screen-h) * 0.55);
  overflow-y: auto;
  background: var(--c-bg);
  color: var(--c-ink);
  border-top-left-radius: 24px;
  border-top-right-radius: 24px;
  padding: 20px 20px calc(var(--safe-bottom) + 32px);
}

.grip {
  display: block;
  width: 36px;
  height: 4px;
  border-radius: 2px;
  background: var(--c-line);
  margin: 0 auto 16px;
}

.uploader {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 18px;
  background: var(--c-bg-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--f-serif);
  font-size: 15px;
}

.who {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.chevron {
  width: 14px;
  height: 14px;
  color: var(--c-ink-mute);
}

.name {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

.meta {
  margin: 1px 0 0;
  font-size: 10px;
  letter-spacing: 0.5px;
  color: var(--c-ink-mute);
}

.action {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px;
  border: 0;
  background: transparent;
  color: var(--c-ink);
}

/* 沒按過是空心，按過填滿 */
.heart,
.bookmark {
  width: 20px;
  height: 20px;
  fill: none;
  transition: transform 0.15s;
}

.heart {
  color: var(--c-rose);
}

.bookmark {
  color: var(--c-ink-soft);
}

.heart.on,
.bookmark.on {
  fill: currentColor;
}

.action:active .heart,
.action:active .bookmark {
  transform: scale(0.85);
}

.likes {
  min-width: 1.5em;
  font-size: 12px;
  text-align: left;
}

.action-error {
  margin: -6px 0 10px;
  font-size: 11px;
  color: var(--c-rose);
}

.blessing {
  position: relative;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--c-bg-soft);
}

/* 標籤壓在卡片上緣，用底色蓋住邊框做出缺口 */
.blessing-tag {
  position: absolute;
  top: -8px;
  left: 16px;
  padding: 0 8px;
  background: var(--c-bg-soft);
  font-size: 10px;
  letter-spacing: 1.5px;
  color: var(--c-rose);
}

.blessing-text {
  margin: 0;
  font-family: var(--f-serif);
  font-size: 14px;
  line-height: 1.7;
  text-align: justify;
}
</style>
