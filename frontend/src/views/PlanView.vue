<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useNavStore } from '@/stores/nav'
import { usePosition } from '@/lib/usePosition'
import NavView from '@/views/NavView.vue'

const nav = useNavStore()
const router = useRouter()
const { lang, isRouteLoading, error, plan } = storeToRefs(nav)
const { currentPos } = usePosition()

const pois = ref([])
const selectedIds = ref([])

const hasError = computed(() => !!error.value)
const hasNoPosition = computed(() => !currentPos.value)
const hasRoute = computed(() => !!plan.value?.route)

const isNavWindowVisible = ref(false)
const isNavWindowFullScreen = ref(false)

const MIN_NAV_WIDTH = 320
const MIN_NAV_HEIGHT = 320

const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 1280
const viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 720

const defaultNavWidth = clamp(
  viewportWidth > MIN_NAV_WIDTH + 48 ? Math.min(420, viewportWidth - 48) : MIN_NAV_WIDTH,
  MIN_NAV_WIDTH,
  Math.max(MIN_NAV_WIDTH, viewportWidth - 32)
)
const defaultNavHeight = clamp(
  viewportHeight > MIN_NAV_HEIGHT + 96 ? Math.min(640, viewportHeight - 80) : MIN_NAV_HEIGHT,
  MIN_NAV_HEIGHT,
  Math.max(MIN_NAV_HEIGHT, viewportHeight - 32)
)

const navWindow = reactive({
  x: clamp(
    Math.round((viewportWidth - defaultNavWidth) / 2),
    16,
    Math.max(16, viewportWidth - defaultNavWidth - 16)
  ),
  y: clamp(
    Math.round((viewportHeight - defaultNavHeight) / 2),
    16,
    Math.max(16, viewportHeight - defaultNavHeight - 16)
  ),
  width: defaultNavWidth,
  height: defaultNavHeight,
  dragging: false,
  dragOffsetX: 0,
  dragOffsetY: 0,
})

const navWindowStyle = computed(() => {
  if (isNavWindowFullScreen.value) {
    return {
      left: '0',
      top: '0',
      width: '100vw',
      height: '100vh',
      transform: 'translate3d(0, 0, 0)',
      opacity: '1',
      '--nav-window-offset': '0'
    }
  }

  const hiddenOffsetPx = (() => {
    const baseOffset = navWindow.width + 56
    if (typeof window === 'undefined') return `${baseOffset}px`
    const viewportWidth = window.innerWidth
    const distanceToViewportEdge = Math.max(0, viewportWidth - navWindow.x)
    return `${Math.max(baseOffset, distanceToViewportEdge + 40)}px`
  })()

  return {
    left: `${navWindow.x}px`,
    top: `${navWindow.y}px`,
    width: `${navWindow.width}px`,
    height: `${navWindow.height}px`,
    transform: 'translate3d(var(--nav-window-offset, 0), 0, 0)',
    '--nav-window-offset': isNavWindowVisible.value ? '0' : hiddenOffsetPx,
    opacity: isNavWindowVisible.value ? '1' : '0'
  }
})

let previousUserSelect = ''
const previousWindowState = reactive({ x: navWindow.x, y: navWindow.y, width: navWindow.width, height: navWindow.height })

// --- POIデータ読み込み ---
onMounted(async () => {
  try {
    const res = await fetch('/pois.json', { cache: 'no-cache' })
    pois.value = await res.json()
  } catch (e) {
    console.error('[plan] failed to load pois.json', e)
  }

  ensureNavWindowBounds()
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', handleWindowResize)
  }
})

onBeforeUnmount(() => {
  endPointerInteraction()
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', handleWindowResize)
  }
})

// --- UI用ヘルパー関数 ---
function displayName(p) {
  const o = p.official_name || {}
  return o[lang.value] || o.ja || p.spot_id
}

function nameById(id) {
  const p = pois.value.find((x) => x.spot_id === id)
  return p ? displayName(p) : id
}

// --- 選択・並べ替えロジック ---
function toggleSpot(id) {
  const i = selectedIds.value.indexOf(id)
  if (i >= 0) {
    selectedIds.value.splice(i, 1)
  } else {
    selectedIds.value.push(id)
  }
}

function move(i, d) {
  const j = i + d
  if (j < 0 || j >= selectedIds.value.length) return
  const temp = selectedIds.value[i]
  selectedIds.value[i] = selectedIds.value[j]
  selectedIds.value[j] = temp
}

function remove(i) {
  selectedIds.value.splice(i, 1)
}

/**
 * ルート計画の作成をストアのアクションに依頼する
 */
async function submitPlan() {
  if (hasNoPosition.value) {
    alert('現在地が取得できていません。ブラウザのGPS利用を許可してください。')
    return
  }

  const { lat, lng } = currentPos.value
  const planOptions = {
    language: lang.value,
    origin: {
      lat,
      lon: lng
    },
    waypoints: selectedIds.value.map((id) => ({ spot_id: id }))
  }

  await nav.fetchRoute(planOptions, { navigate: false })
  isNavWindowVisible.value = true
  isNavWindowFullScreen.value = false
  ensureNavWindowBounds()
}

function toggleNavWindow() {
  if (!hasRoute.value) return
  isNavWindowVisible.value = !isNavWindowVisible.value
  if (isNavWindowVisible.value) {
    ensureNavWindowBounds()
  } else {
    endPointerInteraction()
    isNavWindowFullScreen.value = false
  }
}

function openNavFullScreen() {
  if (!isNavWindowFullScreen.value) {
    previousWindowState.x = navWindow.x
    previousWindowState.y = navWindow.y
    previousWindowState.width = navWindow.width
    previousWindowState.height = navWindow.height
    isNavWindowFullScreen.value = true
    endPointerInteraction()
  } else {
    isNavWindowFullScreen.value = false
    navWindow.x = previousWindowState.x
    navWindow.y = previousWindowState.y
    navWindow.width = previousWindowState.width
    navWindow.height = previousWindowState.height
    ensureNavWindowBounds()
  }
}

function startDrag(event) {
  if (!isNavWindowVisible.value || isNavWindowFullScreen.value || typeof window === 'undefined') return
  event.preventDefault()
  event.stopPropagation()
  navWindow.dragging = true
  navWindow.dragOffsetX = event.clientX - navWindow.x
  navWindow.dragOffsetY = event.clientY - navWindow.y
  lockUserSelect()
  event.currentTarget?.setPointerCapture?.(event.pointerId)
  attachGlobalPointerListeners()
}

function attachGlobalPointerListeners() {
  if (typeof window === 'undefined') return
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', endPointerInteraction)
}

function onPointerMove(event) {
  if (typeof window === 'undefined') return
  if (navWindow.dragging) {
    event.preventDefault()
    const maxX = Math.max(16, window.innerWidth - navWindow.width - 16)
    const maxY = Math.max(16, window.innerHeight - navWindow.height - 16)
    navWindow.x = clamp(event.clientX - navWindow.dragOffsetX, 16, maxX)
    navWindow.y = clamp(event.clientY - navWindow.dragOffsetY, 16, maxY)
  }
}

function endPointerInteraction() {
  if (navWindow.dragging) {
    navWindow.dragging = false
  }
  if (typeof window !== 'undefined') {
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', endPointerInteraction)
  }
  unlockUserSelect()
}

function lockUserSelect() {
  if (typeof document === 'undefined') return
  previousUserSelect = document.body.style.userSelect
  document.body.style.userSelect = 'none'
}

function unlockUserSelect() {
  if (typeof document === 'undefined') return
  document.body.style.userSelect = previousUserSelect || ''
}

function handleWindowResize() {
  ensureNavWindowBounds()
}

function ensureNavWindowBounds() {
  if (typeof window === 'undefined' || isNavWindowFullScreen.value) return
  navWindow.width = clamp(navWindow.width, MIN_NAV_WIDTH, Math.max(MIN_NAV_WIDTH, window.innerWidth - 32))
  navWindow.height = clamp(navWindow.height, MIN_NAV_HEIGHT, Math.max(MIN_NAV_HEIGHT, window.innerHeight - 32))
  navWindow.x = clamp(navWindow.x, 16, Math.max(16, window.innerWidth - navWindow.width - 16))
  navWindow.y = clamp(navWindow.y, 16, Math.max(16, window.innerHeight - navWindow.height - 16))
}

function clamp(value, min, max) {
  if (Number.isNaN(value)) return min
  return Math.min(Math.max(value, min), max)
}

watch(hasRoute, (available) => {
  if (available) {
    ensureNavWindowBounds()
  } else {
    isNavWindowVisible.value = false
    isNavWindowFullScreen.value = false
  }
})

watch(plan, (value) => {
  if (!value) {
    isNavWindowVisible.value = false
    isNavWindowFullScreen.value = false
  }
})

watch(isNavWindowVisible, (visible) => {
  if (visible) {
    ensureNavWindowBounds()
  } else {
    endPointerInteraction()
    isNavWindowFullScreen.value = false
  }
})
</script>

<template>
  <div class="page">
    <header class="bar">
      <h1>ナビ計画</h1>
    </header>

    <section class="form">
      <div class="row">
        <label for="lang">表示言語</label>
        <select id="lang" v-model="lang">
          <option value="ja">日本語</option>
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
      </div>

      <div class="row">
        <label>スポット選択（複数可・順番に周遊）</label>
        <div class="chips">
          <button
            v-for="p in pois"
            :key="p.spot_id"
            @click="toggleSpot(p.spot_id)"
            :class="{ chip: true, on: selectedIds.includes(p.spot_id) }"
          >
            {{ displayName(p) }}
          </button>
        </div>
      </div>

      <div class="row" v-if="selectedIds.length > 0">
        <label>訪問順</label>
        <div class="reorder">
          <ul>
            <li v-for="(id, i) in selectedIds" :key="id">
              <span class="name">{{ i + 1 }}. {{ nameById(id) }}</span>
              <span class="ctrl">
                <button class="up" :disabled="i === 0" @click="move(i, -1)">↑</button>
                <button class="down" :disabled="i === selectedIds.length - 1" @click="move(i, 1)">
                  ↓
                </button>
                <button class="del" @click="remove(i)">×</button>
              </span>
            </li>
          </ul>
        </div>
      </div>

      <div v-if="hasError" class="error-box">
        <p>エラーが発生しました:</p>
        <pre>{{ nav.error }}</pre>
      </div>
      <div v-if="hasNoPosition" class="error-box">
        <p>現在地を取得中です...</p>
      </div>

      <div class="row">
        <button
          class="primary"
          :disabled="isRouteLoading || selectedIds.length === 0 || hasNoPosition"
          @click="submitPlan"
        >
          {{ isRouteLoading ? 'ルート作成中...' : 'ルートを作成して地図で確認' }}
        </button>
      </div>
    </section>
  </div>
  <button
    v-if="hasRoute"
    type="button"
    :class="[
      'nav-window__floating-toggle',
      isNavWindowVisible ? 'nav-window__floating-toggle--open' : 'nav-window__floating-toggle--closed'
    ]"
    :aria-expanded="isNavWindowVisible ? 'true' : 'false'"
    @click="toggleNavWindow"
  >
    <span class="sr-only">{{ isNavWindowVisible ? 'ナビを隠す' : 'ナビを表示' }}</span>
  </button>
  <Teleport to="body">
    <div
      v-if="hasRoute"
      :class="[
        'nav-window',
        {
          'nav-window--fullscreen': isNavWindowFullScreen,
          'nav-window--visible': isNavWindowVisible && !isNavWindowFullScreen,
          'nav-window--hidden': !isNavWindowVisible && !isNavWindowFullScreen
        }
      ]"
      role="dialog"
      :aria-modal="isNavWindowFullScreen ? 'true' : 'false'"
      :aria-hidden="(!isNavWindowVisible).toString()"
      :style="navWindowStyle"
    >
      <header
        :class="['nav-window__header', { 'nav-window__header--fullscreen': isNavWindowFullScreen }]"
        @pointerdown="startDrag"
      >
        <span class="nav-window__title">ナビプレビュー</span>
        <div class="nav-window__controls">
          <button
            type="button"
            :class="[
              'nav-window__control',
              'nav-window__control--fullscreen',
              { 'is-fullscreen': isNavWindowFullScreen }
            ]"
            @click.stop="openNavFullScreen"
          >
            <span class="sr-only">{{ isNavWindowFullScreen ? 'ウィンドウ化' : '全画面表示' }}</span>
          </button>
        </div>
      </header>
      <div class="nav-window__body">
        <NavView />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.page {
  max-width: 720px;
  margin: 0 auto;
  padding: 8px 12px 24px;
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.form {
  margin-top: 8px;
}
.row {
  margin: 16px 0;
}
label {
  display: block;
  margin-bottom: 8px;
  font-weight: bold;
}
select {
  padding: 8px;
  font-size: 16px;
  width: 100%;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  padding: 6px 12px;
  border: 1px solid #ccc;
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
}
.chip.on {
  background: #e8f0fe;
  border-color: #2563eb;
  color: #2563eb;
  font-weight: bold;
}
.reorder {
  margin-top: 16px;
}
.reorder ul {
  list-style: none;
  padding: 0;
  margin: 0;
  border: 1px solid #ccc;
  border-radius: 8px;
  overflow: hidden;
}
.reorder li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
}
.reorder li:last-child {
  border-bottom: none;
}
.reorder .name {
  font-size: 16px;
}
.reorder .ctrl {
  display: flex;
  gap: 4px;
}
.reorder .ctrl button {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  border: 1px solid #ccc;
  background: #f8f8f8;
  cursor: pointer;
}
.reorder .ctrl button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.reorder .ctrl button.del {
  border-color: #e11d48;
  color: #e11d48;
}

button.primary {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  background: #1d4ed8;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
button.primary:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

.error-box {
  border: 1px solid #f87171;
  background-color: #fef2f2;
  color: #b91c1c;
  padding: 10px;
  border-radius: 6px;
  margin-top: 16px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.nav-window__floating-toggle {
  position: fixed;
  top: 120px;
  right: -32px;
  z-index: 1300;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 88px;
  height: 48px;
  padding: 0;
  border-radius: 999px 0 0 999px;
  border: 1px solid rgba(15, 23, 42, 0.3);
  border-right: none;
  background: rgba(15, 23, 42, 0.92);
  cursor: pointer;
  box-shadow: -6px 12px 22px rgba(15, 23, 42, 0.22);
  transition: background-color 0.25s ease, border-color 0.2s ease, transform 0.25s ease;
  overflow: visible;
}

.nav-window__floating-toggle:hover {
  background: rgba(30, 64, 175, 0.93);
  border-color: rgba(30, 64, 175, 0.6);
}

.nav-window__floating-toggle:focus-visible {
  outline: 2px solid rgba(168, 213, 255, 0.9);
  outline-offset: 3px;
}

.nav-window__floating-toggle:active {
  transform: translateX(-3px);
}

.nav-window__floating-toggle:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.nav-window__floating-toggle--open {
  background: rgba(15, 23, 42, 0.88);
}

.nav-window__floating-toggle--closed {
  background: rgba(30, 64, 175, 0.9);
  border-color: rgba(30, 64, 175, 0.6);
}

.nav-window__floating-toggle::before,
.nav-window__floating-toggle::after {
  content: '';
  position: absolute;
  pointer-events: none;
}

.nav-window__floating-toggle::before {
  top: 50%;
  left: 34px;
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.92);
  border-left: 0;
  border-bottom: 0;
  transform-origin: center;
  transform: translate(-50%, -50%) rotate(45deg);
  transition: transform 0.28s ease;
}

.nav-window__floating-toggle--closed::before {
  transform: translate(-50%, -50%) rotate(-135deg);
}

.nav-window__floating-toggle::after {
  inset: 12px;
  border-radius: 999px 0 0 999px;
  background: rgba(255, 255, 255, 0.22);
  filter: blur(18px);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.nav-window__floating-toggle:hover::after {
  opacity: 0.6;
}

.nav-window__controls {
  display: flex;
  align-items: center;
}

.nav-window__control {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.2);
  background: rgba(15, 23, 42, 0.1);
  color: rgba(15, 23, 42, 0.9);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1.15rem;
  transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.35s ease, box-shadow 0.2s ease;
}

.nav-window__control:hover {
  background: rgba(37, 99, 235, 0.2);
  border-color: rgba(37, 99, 235, 0.5);
  box-shadow: 0 3px 12px rgba(37, 99, 235, 0.28);
}

.nav-window__control:focus-visible {
  outline: 2px solid rgba(168, 213, 255, 0.9);
  outline-offset: 2px;
}

.nav-window__control:active {
  transform: scale(0.94);
}

.nav-window__control--fullscreen {
  transform: scale(1);
}

.nav-window__control--fullscreen::before {
  content: '⤢';
  line-height: 1;
}

.nav-window__control--fullscreen.is-fullscreen {
  transform: rotate(180deg) scale(1.08);
}

.nav-window__control--fullscreen.is-fullscreen::before {
  content: '⤡';
  transform: rotate(-180deg);
  display: inline-block;
}

.nav-window {
  position: fixed;
  z-index: 1200;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.28);
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  overflow: visible;
  backdrop-filter: blur(6px);
  transition:
    transform 0.32s ease,
    opacity 0.24s ease,
    width 0.38s cubic-bezier(0.22, 1, 0.36, 1),
    height 0.38s cubic-bezier(0.22, 1, 0.36, 1),
    top 0.38s cubic-bezier(0.22, 1, 0.36, 1),
    left 0.38s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: width, height, top, left, transform;
}

.nav-window--fullscreen {
  border-radius: 0;
  border: none;
  box-shadow: none;
  backdrop-filter: none;
}

.nav-window--visible {
  pointer-events: auto;
}

.nav-window--hidden {
  pointer-events: none;
}

.nav-window__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.12), rgba(37, 99, 235, 0));
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  cursor: grab;
  user-select: none;
  gap: 12px;
  touch-action: none;
}

.nav-window__header:active {
  cursor: grabbing;
}

.nav-window__header--fullscreen {
  cursor: default;
  background: rgba(15, 23, 42, 0.08);
}

.nav-window__title {
  font-size: 0.95rem;
  font-weight: 600;
  color: #0f172a;
}

.nav-window__body {
  flex: 1;
  min-height: 0;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  border-radius: 0 0 14px 14px;
  overflow: hidden;
}

.nav-window__body :deep(.nav-view) {
  height: 100% !important;
  width: 100%;
}

.nav-window__body :deep(.nav-container),
.nav-window__body :deep(.map-wrapper) {
  height: 100%;
}

.nav-window__body :deep(.toast-stack) {
  bottom: 16px;
  right: 16px;
}
</style>
