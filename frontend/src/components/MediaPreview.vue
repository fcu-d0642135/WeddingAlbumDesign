<script setup lang="ts">
import type { PickedMedia } from '@/stores/session'

/**
 * 選到的檔案還沒上傳前的預覽（選擇頁、祝福頁共用）。
 * 影片用 <video> 顯示第一格：網址加 #t=0.1，iPhone 才會畫出畫面，不然是一片黑。
 */
defineProps<{ item: PickedMedia }>()
</script>

<template>
  <video
    v-if="item.kind === 'video'"
    class="media"
    :src="item.previewUrl + '#t=0.1'"
    muted
    playsinline
    preload="metadata"
  />
  <img v-else class="media" :src="item.previewUrl" alt="" />
</template>

<style scoped>
.media {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  /* 預覽只是看，不要讓 <video> 吃掉點擊（外層是勾選按鈕） */
  pointer-events: none;
}
</style>
