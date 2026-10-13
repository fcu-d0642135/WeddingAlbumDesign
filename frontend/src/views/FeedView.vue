<script lang="ts">
import { ref } from 'vue'

// 放在元件外面：從照片詳情返回首頁時，仍停在原本選的分類
const activeChip = ref('all')
</script>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchStats, type PhotoFilter } from '@/api/photos'
import PhotoTile from '@/components/PhotoTile.vue'
import { useInfiniteScroll } from '@/composables/useInfiniteScroll'
import { wedding } from '@/config/wedding'
import { ensureLoaded, filterToQuery, getPhotoList, loadMore, reload } from '@/stores/photoLists'
import type { AlbumStats } from '@/types/album'

type Chip = { id: string; label: string; filter: PhotoFilter }

/** 篩選交給後端（GET /api/photos 的參數），每個 chip 各自是一串快取的列表 */
const chips: Chip[] = [
  { id: 'all', label: '全部', filter: {} },
  { id: 'engagement', label: '訂婚・迎娶', filter: { tag: 'engagement' } },
  { id: 'banquet', label: '宴客', filter: { tag: 'banquet' } },
  { id: 'video', label: '影片', filter: { kind: 'video' } },
]

const filter = computed(() => chips.find((c) => c.id === activeChip.value)!.filter)
const list = computed(() => getPhotoList(filter.value))

// 兩欄瀑布流：依序左右分配。載入下一頁時只往後加，已經排好的不會跳動
const columnA = computed(() => list.value.items.filter((_, i) => i % 2 === 0))
const columnB = computed(() => list.value.items.filter((_, i) => i % 2 === 1))

const stats = ref<AlbumStats | null>(null)

function select(chip: Chip) {
  activeChip.value = chip.id
  ensureLoaded(chip.filter)
}

async function more() {
  // 正在載入就不重複觸發；載完由那一次負責接著檢查
  if (list.value.loading) return false
  await loadMore(filter.value)
  return !list.value.done && !list.value.error
}

function retry() {
  reload(filter.value)
}

const sentinel = ref<HTMLElement>()
useInfiniteScroll(sentinel, more)

onMounted(() => {
  ensureLoaded(filter.value)
  fetchStats()
    .then((s) => (stats.value = s))
    .catch(() => {
      // 統計數字只是裝飾，拿不到就不顯示
    })
})

function ratioOf(p: { width: number; height: number }) {
  return `${p.width}/${p.height}`
}
</script>

<template>
  <main class="feed">
    <header class="head">
      <div class="head-row">
        <div>
          <p class="date-en">{{ wedding.dateDisplayEn }}</p>
          <h1 class="names">
            {{ wedding.groomName }} <span class="amp">&amp;</span> {{ wedding.brideName }}
          </h1>
          <p v-if="stats" class="stats">
            共 {{ stats.photoCount }} 張回憶 · {{ stats.guestCount }} 位賓客
          </p>
        </div>
      </div>

      <div class="chips">
        <button
          v-for="c in chips"
          :key="c.id"
          type="button"
          class="chip"
          :class="{ active: activeChip === c.id }"
          @click="select(c)"
        >
          {{ c.label }}
        </button>
      </div>
    </header>

    <div class="masonry">
      <div class="column">
        <RouterLink
          v-for="p in columnA"
          :key="p.id"
          class="card"
          :to="{ name: 'photo-detail', params: { photoId: p.id }, query: filterToQuery(filter) }"
        >
          <PhotoTile :photo="p" :index="list.items.indexOf(p)" :ratio="ratioOf(p)" />
          <div class="card-foot">
            <span class="avatar">{{ p.uploader.nickname[0] }}</span>
            {{ p.uploader.nickname }}
          </div>
        </RouterLink>
      </div>
      <div class="column">
        <RouterLink
          v-for="p in columnB"
          :key="p.id"
          class="card"
          :to="{ name: 'photo-detail', params: { photoId: p.id }, query: filterToQuery(filter) }"
        >
          <PhotoTile :photo="p" :index="list.items.indexOf(p)" :ratio="ratioOf(p)" />
          <div class="card-foot">
            <span class="avatar">{{ p.uploader.nickname[0] }}</span>
            {{ p.uploader.nickname }}
          </div>
        </RouterLink>
      </div>
    </div>

    <p v-if="list.loaded && list.items.length === 0" class="status">
      {{ activeChip === 'all' ? '還沒有照片，成為第一個分享回憶的人吧' : '這個分類還沒有照片' }}
    </p>
    <p v-else-if="list.error" class="status">
      {{ list.error }}
      <button class="retry" type="button" @click="retry">重試</button>
    </p>
    <p v-else-if="list.loading" class="status">載入中…</p>

    <!-- 捲到這裡附近就載入下一頁 -->
    <div ref="sentinel" class="sentinel" />
  </main>
</template>

<style scoped>
.status {
  margin: 24px 0;
  text-align: center;
  font-size: 13px;
  color: var(--c-ink-mute);
}

.retry {
  margin-left: 8px;
  padding: 4px 12px;
  border: 1px solid var(--c-line-strong);
  border-radius: 12px;
  background: transparent;
  font-size: 12px;
  color: var(--c-ink);
}

.sentinel {
  height: 1px;
}

.feed {
  background: var(--c-bg);
  min-height: var(--screen-h);
}

.head {
  padding: calc(var(--page-top) + 24px) 20px 16px;
}

.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.date-en {
  margin: 0;
  font-family: var(--f-display);
  font-style: italic;
  font-size: 12px;
  letter-spacing: 3px;
  color: var(--c-gold);
}

.names {
  margin: 4px 0 0;
  font-family: var(--f-serif);
  font-size: 26px;
  font-weight: 500;
  letter-spacing: 1px;
}

.amp {
  font-family: var(--f-display);
  font-style: italic;
  color: var(--c-rose);
}

.stats {
  margin: 4px 0 0;
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--c-ink-mute);
}



.chips {
  margin-top: 18px;
  display: flex;
  gap: 8px;
  overflow-x: auto;
  /* 隱藏水平捲軸，手機上用手勢滑 */
  scrollbar-width: none;
}

.chips::-webkit-scrollbar {
  display: none;
}

.chip {
  flex-shrink: 0;
  padding: 6px 14px;
  border-radius: 14px;
  border: 1px solid var(--c-line);
  background: transparent;
  color: var(--c-ink-soft);
  font-size: 11px;
  letter-spacing: 1px;
  white-space: nowrap;
}

.chip.active {
  background: var(--c-ink);
  border-color: transparent;
  color: var(--c-bg);
}

.masonry {
  padding: 0 16px;
  display: flex;
  gap: 10px;
}

.column {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  /* 兩欄等寬，內容才不會把欄位撐開 */
  min-width: 0;
}

.card {
  border-radius: 12px;
  overflow: hidden;
  background: var(--c-card);
  box-shadow: var(--shadow-card);
}

.card-foot {
  padding: 8px 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--c-ink-soft);
}

.avatar {
  width: 16px;
  height: 16px;
  border-radius: 8px;
  background: var(--c-bg-deep);
  color: var(--c-ink);
  font-family: var(--f-serif);
  font-size: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
