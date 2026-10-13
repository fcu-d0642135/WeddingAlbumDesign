<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { createBlessing } from '@/api/blessings'
import { ApiError } from '@/api/client'
import { fetchConfig } from '@/api/config'
import { uploadWithRetry } from '@/api/upload'
import MediaPreview from '@/components/MediaPreview.vue'
import { FALLBACK, useAlbumConfig } from '@/composables/useAlbumConfig'
import { addBlessing } from '@/stores/blessingLists'
import { invalidateAll } from '@/stores/photoLists'
import {
  describeMedia,
  resetUploadFlow,
  sizeProblem,
  session,
  uploadFlow,
  type PickedMedia,
} from '@/stores/session'
import type { PhotoTag, UploadStatus } from '@/types/album'

const router = useRouter()
const albumConfig = useAlbumConfig()

/** 跟首頁的篩選 chips 同一套分類 */
const tagOptions: { id: PhotoTag; label: string }[] = [
  { id: 'engagement', label: '訂婚・迎娶' },
  { id: 'banquet', label: '宴客' },
]

const selected = computed(() =>
  uploadFlow.selectedIds
    .map((id) => uploadFlow.picked.find((p) => p.id === id))
    .filter((p): p is PickedMedia => Boolean(p)),
)

const count = computed(() => selected.value.length)
const summary = computed(() => describeMedia(selected.value))
const hasVideo = computed(() => selected.value.some((p) => p.kind === 'video'))

const nickname = computed(() => session.nickname || '賓客')
const initial = computed(() => nickname.value[0] ?? '賓')

const blessingLength = computed(() => uploadFlow.draft.blessing.length)

// --- 祝福輸入框下方的符號 -------------------------------------------------

const MARKS = ['♥', '♡', '✿']
const blessingEl = ref<HTMLTextAreaElement>()

/** 插在游標的位置（有選取文字就取代），而不是一律加在最後；插完游標停在符號後面 */
async function insertMark(mark: string) {
  const el = blessingEl.value
  const text = uploadFlow.draft.blessing
  // 還沒點過輸入框時沒有游標，就加在最後
  const start = el?.selectionStart ?? text.length
  const end = el?.selectionEnd ?? text.length
  const next = text.slice(0, start) + mark + text.slice(end)
  if (next.length > albumConfig.maxBlessingLength) return

  uploadFlow.draft.blessing = next
  await nextTick()
  if (el) {
    el.focus()
    el.setSelectionRange(start + mark.length, start + mark.length)
  }
}

onMounted(() => {
  // 直接開這個網址（重新整理、分享連結）時沒有選到的檔案，退回第一步
  if (uploadFlow.picked.length === 0) router.replace({ name: 'upload' })
})

function addMore() {
  router.back()
}

// --- 上傳 -----------------------------------------------------------------

interface Task {
  status: UploadStatus
  /** 0–100 */
  progress: number
  errorMessage?: string
  /** 上傳成功後拿到的照片 id，祝福要掛在第一張上 */
  photoId?: string
  /** 失敗後正在等著自動重試 */
  retrying?: boolean
}

/** 每張照片的上傳狀態，key 是 PickedMedia.id */
const tasks = reactive<Record<string, Task>>({})
const retrying = computed(() => selected.value.some((p) => tasks[p.id]?.retrying))
const running = ref(false)

const failedCount = computed(
  () => selected.value.filter((p) => tasks[p.id]?.status === 'failed').length,
)
const doneCount = computed(
  () => selected.value.filter((p) => tasks[p.id]?.status === 'succeeded').length,
)

/** 失敗的原因通常都一樣（例如截止上傳、網路斷了），顯示第一個就好 */
const failedMessage = computed(() => {
  if (running.value || failedCount.value === 0) return ''
  const first = selected.value.find((p) => tasks[p.id]?.status === 'failed')
  const reason = first ? tasks[first.id]?.errorMessage : ''
  return `有 ${failedCount.value} 個檔案沒有傳成功：${reason}`
})

/** 照片都傳完了，但祝福沒送出去 */
const blessingError = ref('')

const submitLabel = computed(() => {
  if (running.value) return `上 傳 中 ${doneCount.value} / ${count.value}`
  if (blessingError.value) return '重 新 送 出 祝 福'
  if (failedCount.value > 0) return `重 試 ${failedCount.value} 個`
  return `上 傳 ${summary.value}`
})

/**
 * 在手機上先讀影片長度。超過上限就不必傳了：影片動輒上百 MB，傳完才被後端拒絕太浪費。
 * 讀不到（例如這支手機解不開這種格式）就回 null，交給後端判斷。
 */
function readDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const video = document.createElement('video')
    const url = URL.createObjectURL(file)
    const done = (value: number | null) => {
      URL.revokeObjectURL(url)
      video.removeAttribute('src')
      resolve(value)
    }
    video.preload = 'metadata'
    video.muted = true
    video.onloadedmetadata = () => done(Number.isFinite(video.duration) ? video.duration : null)
    video.onerror = () => done(null)
    setTimeout(() => done(null), 5000)
    video.src = url
  })
}

function formatSeconds(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (!m) return `${s} 秒`
  return s ? `${m} 分 ${s} 秒` : `${m} 分鐘`
}

/** 傳之前先在手機上擋掉的情況，回傳要顯示的原因；沒問題回傳空字串 */
async function precheck(item: PickedMedia, config: typeof FALLBACK): Promise<string> {
  // 選取頁已經擋過一次；這裡再檢查是因為後端設定可能在那之後才載入
  const tooLarge = sizeProblem(item, config)
  if (tooLarge) return tooLarge
  if (item.kind === 'video') {
    const seconds = await readDuration(item.file)
    // 跟後端一樣留一秒誤差
    if (seconds !== null && seconds > config.maxVideoSeconds + 1) {
      return `影片太長了，請剪到 ${formatSeconds(config.maxVideoSeconds)}以內再上傳`
    }
  }
  return ''
}

async function upload() {
  if (running.value) return
  running.value = true

  const config = await fetchConfig().catch(() => FALLBACK)
  const tag = uploadFlow.draft.tag
  // 已經傳成功的不重傳；按「重試」時只會跑失敗的那幾張
  const pending = selected.value.filter((p) => tasks[p.id]?.status !== 'succeeded')
  for (const item of pending) tasks[item.id] = { status: 'pending', progress: 0 }
  // 照片、影片各排各的隊：影片一次只傳一支，不會卡住後面的照片
  const photoQueue = pending.filter((p) => p.kind !== 'video')
  const videoQueue = pending.filter((p) => p.kind === 'video')

  // 碰到「截止上傳」「傳太多」這種後面每張都會失敗的錯誤，就不再送了
  let stopReason = ''

  async function worker(queue: PickedMedia[]) {
    for (let item = queue.shift(); item; item = queue.shift()) {
      const task = tasks[item.id]!
      if (stopReason) {
        Object.assign(task, { status: 'failed', errorMessage: stopReason })
        continue
      }
      // 先在手機上擋掉太大、太長的檔案，不必浪費流量傳到一半才被拒絕
      const problem = await precheck(item, config)
      if (problem) {
        Object.assign(task, { status: 'failed', errorMessage: problem })
        continue
      }

      task.status = 'uploading'
      try {
        const photo = await uploadWithRetry(
          item.file,
          tag,
          (percent) => {
            task.progress = percent
            if (percent > 0) task.retrying = false
          },
          () => (task.retrying = true),
        )
        Object.assign(task, { status: 'succeeded', progress: 100, photoId: photo.id, retrying: false })
      } catch (e) {
        const message = e instanceof ApiError ? e.message : '上傳失敗，請稍後再試'
        Object.assign(task, { status: 'failed', errorMessage: message, retrying: false })
        if (e instanceof ApiError && [401, 403, 429].includes(e.status)) stopReason = message
      }
    }
  }

  // 同時傳幾個由後端設定決定，不要一次全送：會互搶網路，每個都變慢
  const pool = (queue: PickedMedia[], size: number) =>
    Array.from({ length: Math.max(1, size) }, () => worker(queue))
  await Promise.all([
    ...pool(photoQueue, config.uploadConcurrency),
    ...pool(videoQueue, config.videoUploadConcurrency),
  ])
  running.value = false

  if (doneCount.value > 0) invalidateAll()
  if (failedCount.value === 0) await finish()
}

/**
 * 照片傳完之後：有寫祝福就送出，掛在這批第一張成功的照片上（只送一次，
 * 不然一次傳 10 張，同一句祝福會在留言牆出現 10 次）。送出失敗就留在這頁，照片不必重傳。
 */
async function finish() {
  const text = uploadFlow.draft.blessing.trim()
  const first = selected.value.map((p) => tasks[p.id]?.photoId).find(Boolean)
  if (text && first) {
    running.value = true
    blessingError.value = ''
    try {
      addBlessing(await createBlessing(text, first))
      invalidateAll() // 照片上多了祝福
    } catch (e) {
      blessingError.value =
        '檔案都上傳好了，但祝福沒有送出：' +
        (e instanceof ApiError ? e.message : '請稍後再試')
      return
    } finally {
      running.value = false
    }
  }
  resetUploadFlow()
  router.push({ name: 'feed' })
}

function skip() {
  uploadFlow.draft.blessing = ''
  upload()
}

// 傳到一半離開會中斷上傳，先確認
onBeforeRouteLeave(() => {
  if (!running.value) return true
  return window.confirm('還在上傳中，離開會中斷上傳。確定要離開嗎？')
})
</script>

<template>
  <main class="edit">
    <header class="head">
      <button class="back" type="button" @click="router.back()">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
        >
          <path d="M15 6l-6 6 6 6" />
        </svg>
        返回
      </button>
      <h1>留下祝福</h1>
      <button class="skip" type="button" :disabled="running" @click="skip">跳過</button>
    </header>

    <section class="preview">
      <p class="preview-label">{{ summary }} · 將公開分享</p>
      <div class="preview-row">
        <div v-for="item in selected" :key="item.id" class="thumb">
          <MediaPreview :item="item" />
          <template v-if="tasks[item.id]">
            <span
              v-if="tasks[item.id]!.status === 'uploading' || tasks[item.id]!.status === 'pending'"
              class="thumb-progress"
              :style="{ width: tasks[item.id]!.progress + '%' }"
            />
            <span v-else-if="tasks[item.id]!.status === 'succeeded'" class="thumb-badge ok">✓</span>
            <span v-else class="thumb-badge fail" :title="tasks[item.id]!.errorMessage">!</span>
          </template>
        </div>
        <button
          v-if="!running"
          class="thumb add"
          type="button"
          aria-label="再選照片或影片"
          @click="addMore"
        >
          ＋
        </button>
      </div>
      <p v-if="hasVideo" class="video-hint">影片比較大，上傳時請停留在這一頁，也不要關掉螢幕。</p>
      <p v-if="retrying" class="video-hint">現在上傳的人比較多，稍等一下會自動重新上傳…</p>
      <p v-if="blessingError" class="upload-error" role="alert">{{ blessingError }}</p>
      <p v-if="failedMessage" class="upload-error" role="alert">
        {{ failedMessage }}
        <!-- 壞掉的檔案怎麼重試都不會成功，給一條出路 -->
        <button v-if="doneCount > 0" class="give-up" type="button" @click="finish">
          略過失敗的，回相簿
        </button>
      </p>
    </section>

    <section class="block">
      <div class="identity">
        <span class="identity-avatar">{{ initial }}</span>
        <div class="identity-text">
          <p class="identity-label">以此暱稱發布</p>
          <p class="identity-name">{{ nickname }}</p>
        </div>
        <button class="identity-change" type="button" @click="router.push({ name: 'welcome' })">
          更改
        </button>
      </div>
    </section>

    <section class="block">
      <div class="card">
        <div class="card-head">
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 21s-7-5-7-11a4 4 0 017-2.5A4 4 0 0119 10c0 6-7 11-7 11z" />
          </svg>
          <span>寫下你的祝福（選填）</span>
        </div>

        <textarea
          ref="blessingEl"
          v-model="uploadFlow.draft.blessing"
          class="blessing"
          :maxlength="albumConfig.maxBlessingLength"
          placeholder="願你們的愛情&#10;如同今日的天氣&#10;晴朗、明亮、永遠溫暖"
          rows="4"
        />

        <div class="card-foot">
          <!-- mousedown.prevent：按符號時輸入框不會失焦，游標位置與手機鍵盤都留著 -->
          <div class="marks">
            <button
              v-for="m in MARKS"
              :key="m"
              type="button"
              @mousedown.prevent
              @click="insertMark(m)"
            >
              {{ m }}
            </button>
          </div>
          <span class="counter">{{ blessingLength }} / {{ albumConfig.maxBlessingLength }}</span>
        </div>
      </div>

      <fieldset class="settings">
        <legend class="settings-label">這些是在哪個環節拍的？</legend>
        <div class="tags">
          <label
            v-for="t in tagOptions"
            :key="t.id"
            class="tag"
            :class="{ active: uploadFlow.draft.tag === t.id }"
          >
            <input v-model="uploadFlow.draft.tag" type="radio" name="tag" :value="t.id" />
            {{ t.label }}
          </label>
        </div>
      </fieldset>
    </section>

    <div class="submit-bar">
      <button class="submit" type="button" :disabled="count === 0 || running" @click="upload">
        {{ submitLabel }}
      </button>
    </div>
  </main>
</template>

<style scoped>
.edit {
  min-height: var(--screen-h);
  background: var(--c-bg);
  color: var(--c-ink);
  padding-bottom: 120px;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(var(--page-top) + 24px) 16px 12px;
  border-bottom: 1px solid var(--c-line);
}

.head h1 {
  margin: 0;
  font-family: var(--f-serif);
  font-size: 16px;
  font-weight: 500;
}

.back,
.skip {
  border: 0;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--c-ink-soft);
  min-width: 56px;
}

.back svg {
  width: 16px;
  height: 16px;
}

.skip {
  justify-content: flex-end;
  font-size: 13px;
  color: var(--c-ink-mute);
}

.preview {
  padding: 18px 16px 14px;
}

.preview-label {
  margin: 0 0 8px;
  font-size: 11px;
  letter-spacing: 1.5px;
  color: var(--c-ink-mute);
}

.preview-row {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
}

.preview-row::-webkit-scrollbar {
  display: none;
}

.thumb {
  position: relative;
  flex-shrink: 0;
  width: 64px;
  height: 80px;
  border-radius: 8px;
  border: 1px solid var(--c-line);
  overflow: hidden;
}


/* 上傳進度：沿著縮圖底部長出來的一條線 */
.thumb-progress {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 3px;
  background: var(--c-rose);
  transition: width 0.2s;
}

.thumb-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 18px;
  height: 18px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #fff;
}

.thumb-badge.ok {
  background: var(--c-rose);
}

.thumb-badge.fail {
  background: var(--c-ink);
}

.video-hint {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--c-ink-mute);
}

.upload-error {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--c-rose);
}

.give-up {
  margin-left: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  font-size: 12px;
  color: var(--c-ink-soft);
  text-decoration: underline;
}

.thumb.add {
  border: 1.5px dashed var(--c-ink-mute);
  background: transparent;
  color: var(--c-ink-mute);
  font-size: 22px;
  font-weight: 300;
  display: flex;
  align-items: center;
  justify-content: center;
}

.block {
  padding: 0 16px;
  margin-bottom: 14px;
}

.identity {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid var(--c-line);
  background: var(--c-card);
}

.identity-avatar {
  width: 30px;
  height: 30px;
  border-radius: 15px;
  background: var(--c-bg-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--f-serif);
  font-size: 13px;
}

.identity-text {
  flex: 1;
}

.identity-label {
  margin: 0;
  font-size: 10px;
  letter-spacing: 1px;
  color: var(--c-ink-mute);
}

.identity-name {
  margin: 1px 0 0;
  font-size: 14px;
}

.identity-change {
  border: 0;
  background: transparent;
  font-size: 11px;
  color: var(--c-rose);
}

.card {
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--c-line);
  background: var(--c-card);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--c-rose);
}

.card-head svg {
  width: 14px;
  height: 14px;
}

.blessing {
  border: 0;
  padding: 0;
  resize: none;
  background: transparent;
  font-family: var(--f-serif);
  font-size: 15px;
  line-height: 1.7;
  color: var(--c-ink);
  caret-color: var(--c-rose);
  min-height: 96px;
}

.blessing:focus {
  outline: none;
}

.blessing::placeholder {
  color: var(--c-ink-mute);
  opacity: 0.55;
}

.card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid var(--c-line);
}

.marks {
  display: flex;
  gap: 12px;
}

.marks button {
  border: 0;
  background: transparent;
  font-size: 14px;
  color: var(--c-ink-mute);
  padding: 0;
}

.counter {
  font-size: 10px;
  color: var(--c-ink-mute);
}

.settings {
  margin: 14px 0 0;
  padding: 12px 16px 14px;
  border-radius: 12px;
  border: 1px solid var(--c-line);
  background: var(--c-card);
}

.settings-label {
  float: left;
  width: 100%;
  margin-bottom: 10px;
  padding: 0;
  font-size: 13px;
}

/* 四個選項排一列太擠（「訂婚・迎娶」放不下），排成兩欄 */
.tags {
  clear: both;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

/* 單選用原生 radio 保留可存取性，外觀畫成 chip */
.tag {
  flex: 1;
  padding: 8px 0;
  border-radius: 16px;
  border: 1px solid var(--c-line-strong);
  text-align: center;
  font-size: 13px;
  letter-spacing: 1px;
  color: var(--c-ink-soft);
  cursor: pointer;
}

.tag input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.tag.active {
  border-color: transparent;
  background: var(--c-rose);
  color: #fff;
}

.tag:has(input:focus-visible) {
  outline: 2px solid var(--c-rose-soft);
  outline-offset: 2px;
}

.submit-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 12px 16px calc(var(--safe-bottom) + 28px);
  background: linear-gradient(180deg, transparent, var(--c-bg) 30%);
}

.submit {
  width: 100%;
  height: 50px;
  border: 0;
  border-radius: 25px;
  background: var(--c-rose);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 4px;
  box-shadow: var(--shadow-rose);
}

.submit:disabled {
  opacity: 0.45;
  box-shadow: none;
  cursor: default;
}
</style>
