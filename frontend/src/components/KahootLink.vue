<script setup lang="ts">
import { useAlbumConfig } from '@/composables/useAlbumConfig'

/**
 * 「一起玩 Kahoot!」按鈕。連結由管理員在「我的」頁設定，沒設定或開關沒打開就不顯示。
 * 歡迎頁與「我的」頁共用。
 */
const config = useAlbumConfig()
</script>

<template>
  <a
    v-if="config.kahootUrl"
    class="kahoot"
    :href="config.kahootUrl"
    target="_blank"
    rel="noopener noreferrer"
  >
    <span class="kahoot-badge" aria-hidden="true">K!</span>
    <span class="kahoot-text">
      <b>一起玩 Kahoot!</b>
      <small>點這裡加入婚禮小遊戲</small>
    </span>
    <span class="kahoot-arrow" aria-hidden="true">›</span>
  </a>
</template>

<style scoped>
.kahoot {
  width: 100%;
  padding: 12px 16px;
  border-radius: 14px;
  background: var(--c-kahoot-soft);
  color: var(--c-ink);
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  box-shadow: var(--shadow-raised);
}

/* 品牌紫只用在小徽章：認得出是 Kahoot!，又不會一大塊深紫壓在米白的畫面中間 */
.kahoot-badge {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--c-kahoot);
  color: #fff;
  font-weight: 800;
  font-size: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kahoot-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  text-align: left;
}

.kahoot-text b {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.kahoot-text small {
  font-size: 11px;
  color: var(--c-ink-soft);
}

.kahoot-arrow {
  font-size: 22px;
  color: var(--c-kahoot);
}
</style>
