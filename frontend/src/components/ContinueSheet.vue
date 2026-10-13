<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ApiError } from '@/api/client'
import { createTransferCode } from '@/api/guests'

/**
 * 「在其他裝置繼續」：產生一條一次性連結，在別的瀏覽器或電腦打開就是同一位賓客。
 * 見 docs/api.md 的「換瀏覽器或換裝置」。
 */
const open = defineModel<boolean>({ required: true })

const link = ref('')
/** 接續碼本身。從主畫面打開的 app 沒有網址列，貼不了連結，要在那邊的歡迎頁輸入這 8 碼 */
const code = ref('')
const expiresAt = ref<Date | null>(null)
/** 剛剛複製的是哪一個，按鈕上顯示「已複製」 */
const copied = ref<'' | 'link' | 'code'>('')
const loading = ref(false)
const error = ref('')

const canShare = typeof navigator !== 'undefined' && 'share' in navigator

const expiresLabel = computed(() => {
  const d = expiresAt.value
  if (!d) return ''
  return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0')
})

// 每次打開都重新產生，舊的就不必擔心外流
watch(open, (isOpen) => {
  if (isOpen) generate()
})

async function generate() {
  link.value = ''
  code.value = ''
  copied.value = ''
  copyFailed.value = false
  error.value = ''
  loading.value = true
  try {
    const created = await createTransferCode()
    code.value = created.code
    // 連結由前端組：前後端可能不同網域，後端不知道前端的網址
    // BASE_URL 是網站所在的路徑（展示版放在 GitHub Pages 的 /<repo 名稱>/ 底下），結尾帶斜線
    link.value = `${window.location.origin}${import.meta.env.BASE_URL}continue?code=${created.code}`
    expiresAt.value = new Date(created.expiresAt)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '產生連結失敗，請稍後再試'
  } finally {
    loading.value = false
  }
}

/** 複製失敗時提示手動複製（連結那一格點一下就會整串選起來） */
const copyFailed = ref(false)

/**
 * 舊式的複製方法：放一個看不見的輸入框、選取、execCommand('copy')。
 * 不是 HTTPS（例如開發時用區網 IP 連）或瀏覽器太舊時，navigator.clipboard 不存在，靠這個備案。
 */
function legacyCopy(text: string): boolean {
  const el = document.createElement('textarea')
  el.value = text
  el.setAttribute('readonly', '')
  el.style.position = 'fixed'
  el.style.opacity = '0'
  document.body.appendChild(el)
  el.select()
  el.setSelectionRange(0, text.length) // iOS 只認這個
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(el)
  return ok
}

async function copy(which: 'link' | 'code') {
  const text = which === 'link' ? link.value : code.value
  copyFailed.value = false
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text)
      copied.value = which
      return
    }
  } catch {
    // 有 clipboard 但被拒絕（權限、瀏覽器限制），改用舊方法
  }
  const ok = legacyCopy(text)
  copied.value = ok ? which : ''
  copyFailed.value = !ok
}

async function share() {
  try {
    await navigator.share({ title: '婚禮相簿', url: link.value })
  } catch {
    // 使用者取消分享也會 throw，不用處理
  }
}
</script>

<template>
  <Transition name="sheet">
    <div v-if="open" class="overlay" @click.self="open = false">
      <section class="sheet" role="dialog" aria-label="在其他裝置繼續">
        <span class="grip" />
        <h2>在其他裝置繼續</h2>
        <p class="intro">
          想換瀏覽器，或回家用電腦上傳照片？<br />
          用下面任一種方式，就會延續你現在的身分。
        </p>

        <p v-if="loading" class="link muted">產生中…</p>
        <p v-else-if="error" class="link error" role="alert">
          {{ error }}
          <button class="retry" type="button" @click="generate">重試</button>
        </p>
        <template v-else>
          <!-- 方式一：瀏覽器、電腦，直接打開連結 -->
          <section class="way">
            <h3>在瀏覽器或電腦打開</h3>
            <!-- user-select: all，點一下就整串選起來，沒有剪貼簿權限時也能手動複製 -->
            <p class="link">{{ link }}</p>
            <div class="actions">
              <button class="primary" type="button" @click="copy('link')">
                {{ copied === 'link' ? '已複製' : '複製連結' }}
              </button>
              <button v-if="canShare" class="secondary" type="button" @click="share">分享</button>
            </div>
          </section>

          <!-- 方式二：主畫面的 app 沒有網址列，貼不了連結，改輸入接續碼 -->
          <section class="way">
            <h3>從主畫面打開的相簿</h3>
            <p class="way-hint">在那邊的歡迎頁點「已經加入過？」，輸入這組接續碼</p>
            <div class="code-box">
              <span class="code-value">{{ code }}</span>
              <button class="code-copy" type="button" @click="copy('code')">
                {{ copied === 'code' ? '已複製' : '複製接續碼' }}
              </button>
            </div>
          </section>

          <p v-if="copyFailed" class="note warn">這支手機不能自動複製，請長按連結或接續碼手動複製</p>
          <p class="note">{{ expiresLabel }} 前有效，只能使用一次。請不要傳給別人。</p>
        </template>

        <button class="close" type="button" @click="open = false">關閉</button>
      </section>
    </div>
  </Transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  /* 要蓋過 AppTabBar（30） */
  z-index: 40;
  display: flex;
  align-items: flex-end;
  background: rgba(61, 46, 38, 0.35);
}

.sheet {
  width: 100%;
  padding: 12px 20px calc(var(--safe-bottom) + 20px);
  border-top-left-radius: 24px;
  border-top-right-radius: 24px;
  background: var(--c-bg);
  color: var(--c-ink);
  text-align: center;
}

.grip {
  display: block;
  width: 36px;
  height: 4px;
  border-radius: 2px;
  background: var(--c-line);
  margin: 0 auto 16px;
}

h2 {
  margin: 0;
  font-family: var(--f-serif);
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 1px;
}

.intro {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.8;
  color: var(--c-ink-soft);
}

.link {
  margin: 16px 0 0;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--c-line);
  background: var(--c-card);
  font-family: ui-monospace, 'SF Mono', monospace;
  font-size: 12px;
  word-break: break-all;
  user-select: all;
}

.link.muted {
  color: var(--c-ink-mute);
  font-family: inherit;
  user-select: none;
}

.link.error {
  color: var(--c-rose);
  font-family: inherit;
  user-select: none;
}

.retry {
  margin-left: 8px;
  padding: 2px 10px;
  border: 1px solid var(--c-line-strong);
  border-radius: 10px;
  background: transparent;
  font-size: 12px;
  color: var(--c-ink);
}

.primary:disabled,
.secondary:disabled {
  opacity: 0.45;
  box-shadow: none;
}

.way {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--c-line);
  text-align: left;
}

.way h3 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 500;
}

.way-hint {
  margin: 0 0 8px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--c-ink-mute);
}

.way .link {
  margin-top: 0;
}

.way .actions {
  margin-top: 10px;
}

.code-box {
  padding: 10px 12px 10px 14px;
  border-radius: 12px;
  border: 1px dashed var(--c-line-strong);
  display: flex;
  align-items: center;
  gap: 10px;
}

.code-value {
  flex: 1;
  font-family: ui-monospace, 'SF Mono', monospace;
  font-size: 20px;
  letter-spacing: 3px;
  user-select: all;
}

.code-copy {
  padding: 8px 12px;
  border: 1px solid var(--c-line-strong);
  border-radius: 16px;
  background: transparent;
  font-size: 12px;
  color: var(--c-ink);
  white-space: nowrap;
}

.note.warn {
  color: var(--c-rose);
}

.note {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--c-ink-mute);
}

.actions {
  margin-top: 18px;
  display: flex;
  gap: 10px;
}

.primary,
.secondary {
  flex: 1;
  height: 44px;
  border-radius: 22px;
  font-size: 13px;
  letter-spacing: 2px;
}

.primary {
  border: 0;
  background: var(--c-rose);
  color: #fff;
  box-shadow: var(--shadow-rose);
}

.secondary {
  border: 1px solid var(--c-line-strong);
  background: transparent;
  color: var(--c-ink);
}

.close {
  margin-top: 12px;
  border: 0;
  background: transparent;
  font-size: 13px;
  color: var(--c-ink-mute);
}

.sheet-enter-active,
.sheet-leave-active {
  transition: background 0.25s;
}

.sheet-enter-active .sheet,
.sheet-leave-active .sheet {
  transition: transform 0.25s ease-out;
}

.sheet-enter-from,
.sheet-leave-to {
  background: transparent;
}

.sheet-enter-from .sheet,
.sheet-leave-to .sheet {
  transform: translateY(100%);
}
</style>
