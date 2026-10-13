<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import MediaPreview from '@/components/MediaPreview.vue'
import { useAlbumConfig } from '@/composables/useAlbumConfig'
import { wedding } from '@/config/wedding'
import {
  TOO_LARGE_HINT,
  describeMedia,
  kindOf,
  setPicked,
  sizeProblem,
  uploadFlow,
  type PickedMedia,
} from '@/stores/session'

/**
 * 選擇要上傳的照片與影片。
 *
 * 設計稿畫的是「app 內直接瀏覽相機膠捲」，但網頁沒有任何 API 能列出使用者的相簿
 * ——瀏覽器只允許透過 <input type="file"> 叫出系統選取器。
 * 所以這裡改成：先叫系統選取器，選完後用同一套網格讓使用者檢視、取消勾選、決定順序。
 */

const router = useRouter()
const fileInput = ref<HTMLInputElement | null>(null)
const albumConfig = useAlbumConfig()

/** 超過單檔上限的檔案：在這裡就標出來、不能勾，不要等到上傳才失敗 */
function isTooLarge(item: PickedMedia) {
  return sizeProblem(item, albumConfig) !== ''
}

const tooLargeNotice = computed(() => {
  const items = picked.value.filter(isTooLarge)
  if (items.length === 0) return ''
  const videos = items.some((p) => p.kind === 'video')
  const photos = items.some((p) => p.kind !== 'video')
  const limits = [
    photos && `照片 ${Math.floor(albumConfig.maxPhotoBytes / 1024 / 1024)} MB`,
    videos && `影片 ${Math.floor(albumConfig.maxVideoBytes / 1024 / 1024)} MB`,
  ].filter(Boolean)
  return `有 ${describeMedia(items)}超過上限（${limits.join('、')}），沒辦法上傳。${TOO_LARGE_HINT}`
})

const picked = computed(() => uploadFlow.picked)
const selectedIds = computed({
  get: () => uploadFlow.selectedIds,
  set: (value: string[]) => (uploadFlow.selectedIds = value),
})

const selectedCount = computed(() => selectedIds.value.length)

const selectedPreviews = computed(() =>
  selectedIds.value
    .map((id) => picked.value.find((p) => p.id === id))
    .filter((p): p is PickedMedia => Boolean(p)),
)

function openPicker() {
  fileInput.value?.click()
}

function onFilesChosen(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  setPicked(
    files.map((file, i) => ({
      id: i + '-' + file.name + '-' + file.lastModified,
      file,
      kind: kindOf(file),
      previewUrl: URL.createObjectURL(file),
    })),
  )
  // 預設全選太大的以外的，超過張數上限的部分不選
  selectedIds.value = picked.value
    .filter((p) => !isTooLarge(p))
    .slice(0, wedding.maxUploadCount)
    .map((p) => p.id)
  input.value = ''
}

function toggle(id: string) {
  const i = selectedIds.value.indexOf(id)
  if (i >= 0) {
    selectedIds.value.splice(i, 1)
  } else if (selectedCount.value < wedding.maxUploadCount) {
    const item = picked.value.find((p) => p.id === id)
    if (item && isTooLarge(item)) return
    selectedIds.value.push(id)
  }
}

/** 選取順序即上傳順序，顯示在勾選圈裡 */
function orderOf(id: string) {
  const i = selectedIds.value.indexOf(id)
  return i >= 0 ? String(i + 1) : ''
}

function next() {
  if (selectedCount.value === 0) return
  router.push({ name: 'upload-edit' })
}
</script>

<template>
  <main class="picker">
    <header class="head">
      <button class="head-side" type="button" @click="router.back()">取消</button>
      <div class="head-center">
        <h1>選擇照片或影片</h1>
        <p>已選 {{ selectedCount }} / {{ wedding.maxUploadCount }}</p>
      </div>
      <button class="head-side next" type="button" :disabled="selectedCount === 0" @click="next">
        下一步
      </button>
    </header>

    <input
      ref="fileInput"
      type="file"
      accept="image/*,.heic,.heif,video/mp4,video/quicktime,.mov,.mp4"
      multiple
      hidden
      @change="onFilesChosen"
    />

    <div v-if="picked.length === 0" class="empty">
      <div class="empty-icon">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <rect x="3" y="3" width="18" height="18" rx="2.5" />
          <circle cx="9" cy="9" r="1.5" />
          <path d="M21 16l-5-5L5 21" />
        </svg>
      </div>
      <p class="empty-text">選一些今天拍的照片或影片<br />一起放進相簿裡</p>
      <button class="empty-btn" type="button" @click="openPicker">從手機選擇</button>
    </div>

    <template v-else>
      <div class="sources">
        <button class="source add" type="button" @click="openPicker">＋ 再選</button>
      </div>

      <p v-if="tooLargeNotice" class="too-large-notice">{{ tooLargeNotice }}</p>

      <div class="grid">
        <button
          v-for="item in picked"
          :key="item.id"
          type="button"
          class="cell"
          :class="{ blocked: isTooLarge(item) }"
          :aria-disabled="isTooLarge(item)"
          @click="toggle(item.id)"
        >
          <MediaPreview :item="item" />
          <span v-if="item.kind === 'video'" class="video-mark" aria-label="影片">
            <svg viewBox="0 0 12 12" fill="#fff"><path d="M3 2v8l7-4z" /></svg>
          </span>
          <span v-if="isTooLarge(item)" class="too-large">太大</span>
          <span v-else class="mark" :class="{ on: orderOf(item.id) !== '' }">{{
            orderOf(item.id)
          }}</span>
        </button>
      </div>

      <div v-if="selectedCount > 0" class="tray">
        <div class="tray-thumbs">
          <span
            v-for="(p, i) in selectedPreviews.slice(0, 4)"
            :key="p.id"
            class="tray-thumb"
            :style="{ marginLeft: i === 0 ? '0' : '-8px' }"
          >
            <MediaPreview :item="p" />
          </span>
        </div>
        <span class="tray-text">已選 {{ describeMedia(selectedPreviews) }}</span>
        <button class="tray-btn" type="button" @click="next">下一步 →</button>
      </div>
    </template>
  </main>
</template>

<style scoped>
.picker {
  min-height: var(--screen-h);
  background: var(--c-bg);
  color: var(--c-ink);
  padding-bottom: 120px;
}

.head {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: calc(var(--page-top) + 24px) 16px 12px;
  background: var(--c-bg);
  border-bottom: 1px solid var(--c-line);
}

.head-side {
  border: 0;
  background: transparent;
  font-size: 14px;
  color: var(--c-ink-soft);
  min-width: 56px;
  text-align: left;
}

.head-side.next {
  text-align: right;
  font-size: 13px;
  font-weight: 500;
  color: var(--c-rose);
}

.head-side.next:disabled {
  color: var(--c-ink-mute);
  cursor: default;
}

.head-center {
  text-align: center;
}

.head-center h1 {
  margin: 0;
  font-family: var(--f-serif);
  font-size: 16px;
  font-weight: 500;
}

.head-center p {
  margin: 1px 0 0;
  font-size: 10px;
  letter-spacing: 1px;
  color: var(--c-ink-mute);
}

.empty {
  padding: 80px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  text-align: center;
}

.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 32px;
  background: var(--c-bg-soft);
  color: var(--c-ink-mute);
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-icon svg {
  width: 28px;
  height: 28px;
}

.empty-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.8;
  color: var(--c-ink-soft);
}

.empty-btn {
  border: 0;
  border-radius: 24px;
  padding: 14px 32px;
  background: var(--c-rose);
  color: #fff;
  font-size: 14px;
  letter-spacing: 2px;
  box-shadow: var(--shadow-rose);
}

.sources {
  display: flex;
  gap: 6px;
  padding: 14px 16px;
  overflow-x: auto;
  scrollbar-width: none;
}

.sources::-webkit-scrollbar {
  display: none;
}

.source {
  flex-shrink: 0;
  padding: 7px 14px;
  border-radius: 14px;
  border: 1px solid var(--c-line);
  background: var(--c-card);
  color: var(--c-ink-soft);
  font-size: 11px;
  letter-spacing: 1px;
}

.source.active {
  background: var(--c-ink);
  border-color: transparent;
  color: var(--c-bg);
}

.source.add {
  color: var(--c-rose);
}

.grid {
  padding: 0 8px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
}

.cell {
  position: relative;
  padding: 0;
  border: 0;
  background: var(--c-bg-soft);
  aspect-ratio: 1/1;
  overflow: hidden;
}

.too-large-notice {
  margin: 0 16px 12px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--c-rose);
}

/* 太大的檔案：蓋一層白霧，右上角標「太大」取代勾選圈 */
.cell.blocked::after {
  content: '';
  position: absolute;
  inset: 0;
  background: color-mix(in srgb, var(--c-bg) 55%, transparent);
}

.too-large {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 1;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--c-ink);
  font-size: 10px;
  letter-spacing: 1px;
  color: #fff;
}

/* 影片在左下角標一個播放符號，跟右上角的勾選圈分開 */
.video-mark {
  position: absolute;
  left: 6px;
  bottom: 6px;
  width: 20px;
  height: 20px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-mark svg {
  width: 9px;
  height: 9px;
}

.mark {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 22px;
  height: 22px;
  border-radius: 11px;
  border: 1.5px solid rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
}

.mark.on {
  border-color: transparent;
  background: var(--c-rose);
}



.tray {
  position: fixed;
  left: 16px;
  right: 16px;
  bottom: calc(var(--safe-bottom) + 24px);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px 10px 16px;
  border-radius: 28px;
  background: var(--c-ink);
  box-shadow: 0 12px 32px rgba(61, 46, 38, 0.25);
}

.tray-thumbs {
  display: flex;
}

.tray-thumb {
  width: 28px;
  height: 28px;
  border-radius: 14px;
  border: 1.5px solid var(--c-ink);
  overflow: hidden;
}

.tray-text {
  flex: 1;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--c-bg);
}

.tray-btn {
  border: 0;
  padding: 7px 14px;
  border-radius: 16px;
  background: var(--c-rose);
  color: #fff;
  font-size: 12px;
  letter-spacing: 1px;
}
</style>
