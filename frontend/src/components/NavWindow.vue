<!-- frontend/src/components/NavWindow.vue -->
<script setup>
import { useNavWindow } from '@/lib/useNavWindow'
import NavView from '@/views/NavView.vue' // NavViewは常に表示されるので直接インポート

const {
  hasRoute,
  isNavWindowVisible,
  isNavWindowFullScreen,
  navWindowStyle,
  toggleNavWindow,
  openNavFullScreen,
  startDrag,
} = useNavWindow()
</script>

<template>
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
        <span class="nav-window__title">Guidance Map</span>
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
/* PlanView.vueからnav-window関連のスタイルを全てコピー */
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
  padding: 12px 18px;
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.85), rgba(30, 64, 175, 0.82));
  border-bottom: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 18px 18px 0 0;
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.35);
  backdrop-filter: blur(14px);
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
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(15, 118, 110, 0.78));
  border-radius: 0;
}

.nav-window__title {
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.26em;
  text-transform: uppercase;
  color: #e2e8f0;
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
