<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { deleteBlessing } from '@/api/blessings'
import { fetchKahootSettings, saveKahootSettings, type KahootSettings } from '@/api/config'
import { ApiError } from '@/api/client'
import { fetchMe, type MyStats } from '@/api/guests'
import type { PhotoFilter } from '@/api/photos'
import BlessingComposer from '@/components/BlessingComposer.vue'
import BlessingNote from '@/components/BlessingNote.vue'
import ContinueSheet from '@/components/ContinueSheet.vue'
import InstallGuide from '@/components/InstallGuide.vue'
import KahootLink from '@/components/KahootLink.vue'
import PhotoTile from '@/components/PhotoTile.vue'
import ProfileSheet from '@/components/ProfileSheet.vue'
import TextSizePicker from '@/components/TextSizePicker.vue'
import { setSharedKahootUrl } from '@/composables/useAlbumConfig'
import { useInfiniteScroll } from '@/composables/useInfiniteScroll'
import { installGuideKind } from '@/composables/usePlatform'
import {
  ensureBlessingsLoaded,
  getBlessingList,
  loadMoreBlessings,
  removeBlessing,
} from '@/stores/blessingLists'
import { ensureLoaded, filterToQuery, getPhotoList, loadMore } from '@/stores/photoLists'
import { session, setAdmin, setGuestId, setProfile } from '@/stores/session'
import type { Blessing } from '@/types/album'

const nickname = computed(() => session.nickname || '賓客')
const initial = computed(() => nickname.value[0] ?? '賓')

const stats = ref<MyStats>({ uploaded: 0, favorited: 0, likesReceived: 0, blessings: 0 })

/** 設計稿的第 4 個 tab 原本標「收藏」，收藏收進這裡當分頁 */
const tabs = [
  { id: 'uploaded', label: '我上傳的', stat: 'uploaded' },
  { id: 'favorites', label: '收藏', stat: 'favorited' },
  { id: 'blessings', label: '我的祝福', stat: 'blessings' },
] as const

type TabId = (typeof tabs)[number]['id']
const activeTab = ref<TabId>('uploaded')

/**
 * 兩個照片分頁各自是一串照片列表。點進照片詳情時帶同樣的條件（例如 ?favorited=true），
 * 左右滑就只在這一串裡換。
 */
const PHOTO_FILTERS: Partial<Record<TabId, PhotoFilter>> = {
  uploaded: { uploader: 'me' },
  favorites: { favorited: 'true' },
}
const photoFilter = computed(() => PHOTO_FILTERS[activeTab.value])
const photos = computed(() => (photoFilter.value ? getPhotoList(photoFilter.value) : null))

/** 「我的祝福」：GET /api/blessings?guest=me */
const MY_BLESSINGS = { guest: 'me' as const }
const myBlessings = getBlessingList(MY_BLESSINGS)

watch(
  activeTab,
  () => {
    if (photoFilter.value) ensureLoaded(photoFilter.value)
    else ensureBlessingsLoaded(MY_BLESSINGS)
  },
  { immediate: true },
)

const sentinel = ref<HTMLElement>()
useInfiniteScroll(sentinel, async () => {
  if (photoFilter.value) {
    const list = photos.value!
    if (list.loading) return false
    await loadMore(photoFilter.value)
    return !list.done && !list.error
  }
  if (myBlessings.loading) return false
  await loadMoreBlessings(MY_BLESSINGS)
  return !myBlessings.done && !myBlessings.error
})

function refreshMe() {
  fetchMe()
    .then((me) => {
      stats.value = me.stats
      // 以後端為準，例如在別的裝置改過名字
      setProfile(me.guest.nickname, me.guest.relation ?? '')
      setGuestId(me.guest.id)
      setAdmin(me.isAdmin)
    })
    .catch(() => {
      // 統計數字拿不到就先顯示 0，不擋住整頁
    })
}

onMounted(refreshMe)

// --- 修改、刪除自己的祝福 -------------------------------------------------

const composing = ref(false)
const editing = ref<Blessing | null>(null)

function edit(blessing: Blessing) {
  editing.value = blessing
  composing.value = true
}

async function remove(blessing: Blessing) {
  const question =
    blessing.guest.id === session.guestId
      ? '確定要刪除這則祝福嗎？刪除後無法復原。'
      : `以管理員身分刪除「${blessing.guest.nickname}」的祝福？刪除後無法復原。`
  if (!window.confirm(question)) return
  try {
    await deleteBlessing(blessing.id)
    removeBlessing(blessing.id)
    refreshMe()
  } catch (e) {
    window.alert(e instanceof ApiError ? e.message : '刪除失敗，請稍後再試')
  }
}

const continueOpen = ref(false)
const profileOpen = ref(false)

// --- 管理員：設定 Kahoot! 連結 ---------------------------------------------
// 連結可以提早貼上存好，到時候只要打開開關，大家的按鈕就會出現

const kahoot = ref<KahootSettings>({ url: null, enabled: false })
const kahootDraft = ref('')
const kahootSaving = ref(false)
const kahootMessage = ref('')

function applyKahoot(settings: KahootSettings) {
  kahoot.value = settings
  kahootDraft.value = settings.url ?? ''
  setSharedKahootUrl(settings.enabled ? settings.url : null)
}

// 是不是管理員要等 refreshMe 問過後端才確定
watch(
  () => session.isAdmin,
  (isAdmin) => {
    if (!isAdmin) return
    fetchKahootSettings()
      .then(applyKahoot)
      .catch(() => {
        // 拿不到就先顯示空的，儲存時以後端為準
      })
  },
  { immediate: true },
)

function kahootDoneMessage({ url, enabled }: KahootSettings) {
  if (!url) return '已拿掉，按鈕不再顯示'
  if (!enabled) return '連結已存好，打開開關後大家才會看到按鈕'
  return '按鈕已顯示。其他人重新整理或切換頁面就會看到'
}

async function saveKahoot(url: string, enabled: boolean) {
  kahootSaving.value = true
  kahootMessage.value = ''
  try {
    const saved = await saveKahootSettings({ url, enabled })
    applyKahoot(saved)
    kahootMessage.value = kahootDoneMessage(saved)
  } catch (e) {
    kahootMessage.value = e instanceof ApiError ? e.message : '儲存失敗，請稍後再試'
  } finally {
    kahootSaving.value = false
  }
}

/** 「加到主畫面」：手機、而且還沒從主畫面打開時才有這個入口 */
const guideKind = installGuideKind()
const guideOpen = ref(false)
</script>

<template>
  <main class="me">
    <div class="backdrop" />

    <button class="qr" type="button" aria-label="在其他裝置繼續" @click="continueOpen = true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <path d="M14 14h3v3M21 14v3M14 21h3M21 18v3" />
      </svg>
    </button>

    <ContinueSheet v-model="continueOpen" />
    <ProfileSheet v-model="profileOpen" />

    <header class="profile">
      <span class="avatar">{{ initial }}</span>
      <div class="name-row">
        <h1 class="name">{{ nickname }}</h1>
        <button class="edit" type="button" aria-label="編輯個人資料" @click="profileOpen = true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4 12.5-12.5z" />
          </svg>
        </button>
      </div>
      <p v-if="session.relation" class="relation">{{ session.relation }}</p>

      <div class="stats">
        <div class="stat">
          <p class="stat-n">{{ stats.uploaded }}</p>
          <p class="stat-l">已上傳</p>
        </div>
        <span class="stat-sep" />
        <div class="stat">
          <p class="stat-n">{{ stats.favorited }}</p>
          <p class="stat-l">收藏</p>
        </div>
        <span class="stat-sep" />
        <div class="stat">
          <p class="stat-n">{{ stats.likesReceived }}</p>
          <p class="stat-l">收到的讚</p>
        </div>
      </div>
    </header>

    <KahootLink class="kahoot-link" />

    <TextSizePicker class="text-size" />

    <section v-if="session.isAdmin" class="admin-box" aria-label="管理員設定">
      <h2>Kahoot! 連結（管理員）</h2>
      <p class="admin-hint">
        連結可以先貼上存好；打開下面的開關，所有人的歡迎頁與「我的」頁才會出現按鈕。
      </p>
      <input
        v-model="kahootDraft"
        class="admin-input"
        type="url"
        inputmode="url"
        placeholder="https://kahoot.it/?pin=…"
        aria-label="Kahoot! 連結"
      />
      <div class="admin-actions">
        <button
          class="admin-save"
          type="button"
          :disabled="kahootSaving || !kahootDraft.trim()"
          @click="saveKahoot(kahootDraft, kahoot.enabled)"
        >
          儲存
        </button>
        <button
          v-if="kahoot.url"
          class="admin-clear"
          type="button"
          :disabled="kahootSaving"
          @click="saveKahoot('', false)"
        >
          拿掉
        </button>
      </div>
      <!-- 開關只切換顯示，用的是已經存好的連結，不是輸入框裡還沒儲存的內容。
           prevent：等後端存好才跟著變，失敗時不會停在錯的狀態 -->
      <label class="admin-switch" :class="{ off: !kahoot.url }">
        <input
          type="checkbox"
          role="switch"
          :checked="kahoot.enabled"
          :disabled="kahootSaving || !kahoot.url"
          @click.prevent="saveKahoot(kahoot.url ?? '', !kahoot.enabled)"
        />
        <span class="switch-track" aria-hidden="true" />
        <span>{{ kahoot.url ? '顯示按鈕給大家' : '先儲存連結才能打開' }}</span>
      </label>
      <p v-if="kahootMessage" class="admin-hint">{{ kahootMessage }}</p>
    </section>

    <div v-if="guideKind" class="install">
      <InstallGuide v-if="guideOpen" :kind="guideKind" @close="guideOpen = false" />
      <button v-else class="install-btn" type="button" @click="guideOpen = true">
        加到主畫面，下次一點就能打開
      </button>
    </div>

    <nav class="tabs">
      <button
        v-for="t in tabs"
        :key="t.id"
        type="button"
        class="tab"
        :class="{ active: activeTab === t.id }"
        @click="activeTab = t.id"
      >
        {{ t.label }} <span class="tab-n">{{ stats[t.stat] }}</span>
      </button>
    </nav>

    <template v-if="photos && photoFilter">
      <div class="grid">
        <RouterLink
          v-for="(p, i) in photos.items"
          :key="p.id"
          class="cell"
          :to="{ name: 'photo-detail', params: { photoId: p.id }, query: filterToQuery(photoFilter) }"
        >
          <PhotoTile :photo="p" :index="i * 3" ratio="1/1" />
        </RouterLink>
      </div>
      <p v-if="photos.error" class="empty">{{ photos.error }}</p>
      <p v-else-if="photos.loaded && photos.items.length === 0" class="empty">
        {{ activeTab === 'uploaded' ? '你還沒有上傳照片' : '還沒有收藏，在照片右下角點書籤就能收藏' }}
      </p>
    </template>

    <template v-else>
      <ul class="notes">
        <BlessingNote
          v-for="(b, i) in myBlessings.items"
          :key="b.id"
          :blessing="b"
          :tilt="i % 2 === 0 ? 'left' : 'right'"
          @edit="edit"
          @delete="remove"
        />
      </ul>
      <p v-if="myBlessings.error" class="empty">{{ myBlessings.error }}</p>
      <p v-else-if="myBlessings.loaded && myBlessings.items.length === 0" class="empty">
        你還沒有留下祝福
      </p>
    </template>

    <!-- 捲到這裡附近就載入下一頁 -->
    <div ref="sentinel" class="sentinel" />

    <BlessingComposer v-model="composing" :editing="editing" @saved="refreshMe" />
  </main>
</template>

<style scoped>
.me {
  position: relative;
  min-height: var(--screen-h);
  background: var(--c-bg);
  color: var(--c-ink);
}

.backdrop {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 200px;
  background: linear-gradient(180deg, var(--c-bg-soft) 0%, var(--c-bg) 100%);
}

.qr {
  position: absolute;
  top: calc(var(--page-top) + 28px);
  right: 20px;
  z-index: 5;
  width: 36px;
  height: 36px;
  border-radius: 18px;
  background: var(--c-card);
  border: 1px solid var(--c-line);
  padding: 0;
  color: var(--c-ink);
  display: flex;
  align-items: center;
  justify-content: center;
}

.qr svg {
  width: 16px;
  height: 16px;
}

.profile {
  position: relative;
  padding-top: calc(var(--page-top) + 48px);
  text-align: center;
}

.avatar {
  width: 76px;
  height: 76px;
  border-radius: 38px;
  margin: 0 auto;
  background: var(--c-card);
  border: 2px solid var(--c-bg);
  box-shadow: var(--shadow-raised);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--f-serif);
  font-size: 32px;
}

/* 筆的按鈕放名字右邊，名字本身仍置中：左邊用等寬的空白抵銷 */
.name-row {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.name-row::before {
  content: '';
  width: 28px;
}

.edit {
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 14px;
  background: transparent;
  color: var(--c-ink-mute);
  display: flex;
  align-items: center;
  justify-content: center;
}

.edit svg {
  width: 14px;
  height: 14px;
}

.name {
  margin: 0;
  font-family: var(--f-serif);
  font-size: 20px;
  font-weight: 500;
  letter-spacing: 1px;
}

.relation {
  margin: 2px 0 0;
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--c-ink-mute);
}

.stats {
  margin: 18px 20px 0;
  padding: 14px 0;
  border-radius: 14px;
  border: 1px solid var(--c-line);
  background: var(--c-card);
  display: flex;
  justify-content: space-around;
}

.stat {
  flex: 1;
  text-align: center;
}

.stat-sep {
  width: 1px;
  background: var(--c-line);
}

.stat-n {
  margin: 0;
  font-family: var(--f-serif);
  font-size: 22px;
  font-weight: 500;
}

.stat-l {
  margin: 2px 0 0;
  font-size: 10px;
  letter-spacing: 1px;
  color: var(--c-ink-mute);
}

.kahoot-link {
  margin: 14px 20px 0;
  width: auto;
}

.text-size {
  margin: 14px 20px 0;
}

.admin-box {
  margin: 14px 20px 0;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px dashed var(--c-rose-soft);
  background: var(--c-card);
}

.admin-box h2 {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--c-rose);
}

.admin-hint {
  margin: 0 0 8px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--c-ink-mute);
}

/* 16px 以上 iOS 點進輸入框時才不會自動放大畫面 */
.admin-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--c-line);
  border-radius: 10px;
  background: var(--c-bg);
  font-size: 16px;
  color: var(--c-ink);
}

.admin-actions {
  margin: 8px 0;
  display: flex;
  gap: 8px;
}

.admin-save,
.admin-clear {
  height: 36px;
  padding: 0 18px;
  border-radius: 18px;
  font-size: 13px;
}

.admin-save {
  border: 0;
  background: var(--c-rose);
  color: #fff;
}

.admin-save:disabled {
  opacity: 0.45;
}

.admin-clear {
  border: 1px solid var(--c-line-strong);
  background: transparent;
  color: var(--c-ink-soft);
}

.admin-switch {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--c-ink);
}

.admin-switch.off {
  color: var(--c-ink-mute);
}

.admin-switch input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.switch-track {
  position: relative;
  width: 44px;
  height: 26px;
  border-radius: 13px;
  background: var(--c-line-strong);
  flex-shrink: 0;
  transition: background 0.2s;
}

.switch-track::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--shadow-raised);
  transition: transform 0.2s;
}

.admin-switch input:checked + .switch-track {
  background: var(--c-rose);
}

.admin-switch input:checked + .switch-track::after {
  transform: translateX(18px);
}

.admin-switch input:disabled + .switch-track {
  opacity: 0.45;
}

.admin-switch input:focus-visible + .switch-track {
  outline: 2px solid var(--c-rose);
  outline-offset: 2px;
}

.install {
  margin: 14px 20px 0;
}

.install-btn {
  width: 100%;
  padding: 10px;
  border: 1px dashed var(--c-line-strong);
  border-radius: 12px;
  background: transparent;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--c-ink-soft);
}

.tabs {
  margin-top: 20px;
  padding: 0 20px;
  display: flex;
  gap: 20px;
  border-bottom: 1px solid var(--c-line);
}

.tab {
  position: relative;
  padding: 0 0 10px;
  border: 0;
  background: transparent;
  font-size: 13px;
  color: var(--c-ink-mute);
}

.tab.active {
  color: var(--c-ink);
  font-weight: 500;
}

.tab.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--c-rose);
}

.tab-n {
  font-size: 10px;
  color: var(--c-ink-mute);
}

.grid {
  padding: 12px 16px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
}

.empty {
  margin: 32px 0;
  text-align: center;
  font-size: 13px;
  color: var(--c-ink-mute);
}

.notes {
  margin: 0;
  padding: 12px 16px;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sentinel {
  height: 80px;
}

.cell {
  border-radius: 6px;
  overflow: hidden;
}
</style>
