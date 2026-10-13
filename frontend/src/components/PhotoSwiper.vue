<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import PhotoTile from '@/components/PhotoTile.vue'
import type { TileImage } from '@/types/album'

export interface SwiperSlide {
  key: string
  /** 寬 / 高 */
  ratio: number
  photo?: TileImage
  /** 沒有 photo 時給 PhotoTile 挑漸層色 */
  index?: number
  /** 影片的播放網址。有的話，目前這張改放播放器，封面用 photo 的顯示圖 */
  video?: string
}

/**
 * 左右滑動換張。用原生 scroll-snap，手機上的慣性與回彈都交給瀏覽器，
 * 不必自己算手勢。每張照片等比縮放到剛好塞進自己那一格。
 */
const props = defineProps<{ slides: SwiperSlide[] }>()
const current = defineModel<number>({ required: true })

const track = ref<HTMLElement>()

/**
 * 播不了的影片（例如舊 Android 解不開 iPhone 的 HEVC）。不提供下載，只說明一下。
 * 換張時播放器會被拿掉，影片也就跟著停了。
 */
const unplayable = ref(new Set<string>())

function indexFromScroll() {
  const el = track.value
  if (!el || el.clientWidth === 0) return current.value
  return Math.round(el.scrollLeft / el.clientWidth)
}

/**
 * 程式自己捲過去的目標。平滑捲動途中會經過別張的位置，
 * 這段期間的 scroll 事件不能拿來改 current，否則會被拉回上一張。
 */
let target: number | null = null

function scrollToCurrent(behavior: ScrollBehavior) {
  const el = track.value
  // 已經在位置上就不會有 scroll 事件，也就不需要擋
  if (!el || Math.abs(el.scrollLeft - current.value * el.clientWidth) < 1) return
  target = current.value
  el.scrollTo({ left: current.value * el.clientWidth, behavior })
}

/** 使用者自己動手（觸控、滾輪）就交還給手勢，不再等程式的捲動結束 */
function release() {
  target = null
}

function onScroll() {
  const el = track.value
  if (!el) return
  if (target !== null) {
    if (Math.abs(el.scrollLeft - target * el.clientWidth) < 1) target = null
    return
  }
  const i = indexFromScroll()
  if (i !== current.value) current.value = i
}

// 外部改了 current（鍵盤、網址）才需要捲過去；滑動造成的變化已經在定位上了
watch(current, (i) => {
  if (indexFromScroll() !== i) scrollToCurrent('smooth')
})

// 桌機沒有觸控，補上方向鍵
function onKey(e: KeyboardEvent) {
  if (e.key === 'ArrowLeft' && current.value > 0) current.value--
  if (e.key === 'ArrowRight' && current.value < props.slides.length - 1) current.value++
}

onMounted(() => {
  scrollToCurrent('instant')
  window.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div
    ref="track"
    class="track"
    @scroll.passive="onScroll"
    @touchstart.passive="release"
    @wheel.passive="release"
  >
    <div v-for="(s, i) in slides" :key="s.key" class="slide">
      <!-- 影片：只有目前這張放播放器，按下播放才開始下載（preload="none"），左右兩張先顯示封面 -->
      <div
        v-if="s.video && i === current"
        class="photo player"
        :style="{ '--ratio': s.ratio, aspectRatio: String(s.ratio) }"
      >
        <video
          :src="s.video"
          :poster="s.photo?.displayUrl"
          controls
          playsinline
          preload="none"
          @error="unplayable.add(s.key)"
        />
        <p v-if="unplayable.has(s.key)" class="unplayable">這支影片在你的裝置上無法播放</p>
      </div>
      <!-- 只畫目前這張和左右各一張，相片多的時候才不會一次全部載入 -->
      <PhotoTile
        v-else-if="Math.abs(i - current) <= 1"
        class="photo"
        :photo="s.photo"
        full
        :index="s.index ?? i"
        :ratio="String(s.ratio)"
        :style="{ '--ratio': s.ratio }"
      />
    </div>
  </div>
</template>

<style scoped>
.track {
  height: 100%;
  display: flex;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  overscroll-behavior-x: contain;
  scrollbar-width: none;
}

.track::-webkit-scrollbar {
  display: none;
}

.slide {
  flex: 0 0 100%;
  scroll-snap-align: center;
  /* 一次只滑一張，快速甩動也不會跳過 */
  scroll-snap-stop: always;
  container-type: size;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 等比縮放到剛好塞進這一格：寬度取「格寬」與「格高 × 寬高比」的較小值 */
.photo {
  width: min(100cqw, 100cqh * var(--ratio));
}

.player {
  position: relative;
  background: #000;
}

.player video {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.unplayable {
  position: absolute;
  left: 50%;
  bottom: 16px;
  transform: translateX(-50%);
  margin: 0;
  padding: 6px 14px;
  border-radius: 14px;
  background: rgba(0, 0, 0, 0.6);
  white-space: nowrap;
  font-size: 12px;
  color: #fff;
}
</style>
