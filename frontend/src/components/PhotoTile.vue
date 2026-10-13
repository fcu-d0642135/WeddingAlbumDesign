<script setup lang="ts">
import { computed } from 'vue'
import type { TileImage } from '@/types/album'

/**
 * 相片格。漸層佔位圖墊在底下：沒有圖檔時直接顯示它，有圖檔時在載入完成前先看到它。
 */
const props = withDefaults(
  defineProps<{
    photo?: TileImage
    /** 沒有 photo 時用來挑漸層色 */
    index?: number
    /** CSS aspect-ratio，例如 '4/5'；'auto' 表示由外層控制高度 */
    ratio?: string
    label?: string
    /** 載顯示用的大圖而不是縮圖。只有放大檢視（照片詳情、婚紗集）才用 */
    full?: boolean
  }>(),
  { ratio: '4/5', index: 0 },
)

// 設計稿的 10 組佔位漸層
const GRADIENTS: [string, string][] = [
  ['#E8D4C8', '#C9A48E'],
  ['#D4B8A8', '#A88876'],
  ['#EAD9C5', '#C2A179'],
  ['#D9C2B0', '#A88562'],
  ['#E5D0BE', '#B8967A'],
  ['#DBC5B2', '#9C7E68'],
  ['#EFDFC9', '#C49E7C'],
  ['#E0CAB8', '#A8836A'],
  ['#E8D8C5', '#BC9778'],
  ['#D6BCA9', '#9D7B62'],
]

const src = computed(() => (props.full ? props.photo?.displayUrl : props.photo?.thumbnailUrl) || '')

const gradient = computed(() => {
  const [a, b] = GRADIENTS[(props.index ?? 0) % GRADIENTS.length]
  return `linear-gradient(135deg, ${a} 0%, ${b} 100%)`
})

const aspectRatio = computed(() => (props.ratio === 'auto' ? undefined : props.ratio))

/** 列表上的影片標一個播放角標與長度（1:05）；放大檢視時不標 */
const videoBadge = computed(() => {
  if (props.full || props.photo?.kind !== 'video') return null
  const total = Math.round(props.photo.durationSeconds ?? 0)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
})
</script>

<template>
  <div class="tile" :style="{ aspectRatio, background: gradient }">
    <img v-if="src" :src="src" :alt="photo?.blessing ?? ''" loading="lazy" decoding="async" />
    <div v-else class="texture" />
    <span v-if="label" class="label">{{ label }}</span>
    <span v-if="videoBadge !== null" class="video-badge">
      <svg viewBox="0 0 12 12" fill="#fff" aria-hidden="true"><path d="M3 2v8l7-4z" /></svg>
      {{ videoBadge }}
    </span>
    <slot />
  </div>
</template>

<style scoped>
.tile {
  position: relative;
  width: 100%;
  overflow: hidden;
}

.tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 佔位圖上的細斜紋，讓色塊不會太死 */
.texture {
  position: absolute;
  inset: 0;
  opacity: 0.25;
  background-image: repeating-linear-gradient(
    45deg,
    transparent 0 14px,
    rgba(255, 255, 255, 0.08) 14px 15px
  );
}

.video-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.5);
  font-size: 9px;
  color: #fff;
}

.video-badge svg {
  width: 9px;
  height: 9px;
}

.label {
  position: absolute;
  bottom: 8px;
  left: 10px;
  font-family: ui-monospace, 'SF Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.5px;
  color: rgba(255, 255, 255, 0.7);
}
</style>
