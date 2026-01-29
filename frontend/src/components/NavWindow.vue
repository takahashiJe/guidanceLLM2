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
  <Teleport to="body">
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
  </Teleport>
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
/* Styles for screen-reader-only content */
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

/* New styles for the floating toggle button */
.nav-window__floating-toggle {
  position: fixed;
  top: 92px; /* Adjusted position */
  right: 16px; /* Positioned fully inside the screen */
  z-index: 1300;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px; /* Adjusted width */
  height: 56px; /* Made it a square/circle */
  padding: 0;
  border-radius: 18px; /* Rounded square */
  border: none;
  background: linear-gradient(145deg, #3b82f6, #818cf8); /* Bright blue/purple gradient */
  color: white;
  cursor: pointer;
  box-shadow: -2px 4px 16px rgba(59, 130, 246, 0.3);
  transition: all 0.3s ease;
  animation: pulse-glow 2.5s infinite ease-in-out;
}

.nav-window__floating-toggle:hover {
  transform: translateY(-3px) scale(1.05);
  box-shadow: -4px 10px 24px rgba(99, 102, 241, 0.4);
}

.nav-window__floating-toggle:active {
  transform: translateY(0) scale(0.98);
}

/* Pulse animation for the button */
@keyframes pulse-glow {
  0%, 100% {
    box-shadow: -2px 4px 16px rgba(59, 130, 246, 0.3);
    transform: scale(1);
  }
  50% {
    box-shadow: -4px 8px 28px rgba(99, 102, 241, 0.5);
    transform: scale(1.05);
  }
}

/* Arrow icon inside the button */
.nav-window__floating-toggle::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 18px;
  height: 18px;
  border: 2.5px solid white;
  border-left: 0;
  border-bottom: 0;
  transform-origin: center;
  transform: translate(-60%, -50%) rotate(45deg); /* Centered and pointing right (for open state) */
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.nav-window__floating-toggle--closed::before {
  transform: translate(-40%, -50%) rotate(-135deg); /* Centered and pointing left (for closed state) */
}

/* --- The rest of the styles for the window are kept as they were --- */

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
