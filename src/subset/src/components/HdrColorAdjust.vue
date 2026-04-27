<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { useI18n } from "vue-i18n";
import { debounce } from "lodash-es";

const { t } = useI18n();

const props = defineProps({
  saturation: { type: Number, default: 1.0 },
  brightness: { type: Number, default: 1.0 },
});

const emit = defineEmits(["update:saturation", "update:brightness", "committed-change"]);

// --- State ---
const hexInput = ref("#FFFFFF");
const previewText = ref("我能吞下玻璃而不伤身体");
const isRealFullscreen = ref(false);
const panelCollapsed = ref(false);
const containerRef = ref(null);

// --- v-model ---
const satValue = computed({
  get: () => props.saturation,
  set: (v) => emit("update:saturation", v),
});
const briValue = computed({
  get: () => props.brightness,
  set: (v) => emit("update:brightness", v),
});

// --- Color math ---
function hexToRgb(hex) {
  const r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return r
    ? { r: parseInt(r[1], 16), g: parseInt(r[2], 16), b: parseInt(r[3], 16) }
    : { r: 0, g: 0, b: 0 };
}

function rgbToHex(r, g, b) {
  return "#" + [r, g, b].map(c => Math.round(c).toString(16).padStart(2, "0")).join("").toUpperCase();
}

function rgbToHsb(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const d = max - min;
  let h = 0, s = max === 0 ? 0 : d / max, v = max;
  if (max !== min) {
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }
  return { h, s, b: v };
}

function hsbToRgb(h, s, b) {
  const k = (n) => (n + h * 6) % 6;
  const f = (n) => b * (1 - s * Math.max(0, Math.min(k(n), 4 - k(n), 1)));
  return {
    r: Math.round(f(5) * 255),
    g: Math.round(f(3) * 255),
    b: Math.round(f(1) * 255),
  };
}

// --- Computed ---
const origRgb = computed(() => hexToRgb(hexInput.value));
const origHsb = computed(() => rgbToHsb(origRgb.value.r, origRgb.value.g, origRgb.value.b));

function applyMapping(s, sf) {
  if (sf <= 1.0) return s * sf;
  return (1 - s) * (sf - 1) + s;
}

const adjHsb = computed(() => ({
  h: origHsb.value.h,
  s: origHsb.value.s === 0 ? 0 : Math.min(Math.max(applyMapping(origHsb.value.s, satValue.value), 0), 1),
  b: Math.min(Math.max(origHsb.value.b * briValue.value, 0), 1),
}));
const adjRgb = computed(() => hsbToRgb(adjHsb.value.h, adjHsb.value.s, adjHsb.value.b));
const adjHex = computed(() => rgbToHex(adjRgb.value.r, adjRgb.value.g, adjRgb.value.b));

// sRGB → Display P3
function srgbToP3css(r, g, b) {
  const R = r / 255, G = g / 255, B = b / 255;
  const p3r = 0.8225 * R + 0.1774 * G + 0.0001 * B;
  const p3g = 0.0332 * R + 0.9669 * G + 0.0000 * B;
  const p3b = 0.0170 * R + 0.0724 * G + 0.9107 * B;
  return `color(display-p3 ${p3r.toFixed(4)} ${p3g.toFixed(4)} ${p3b.toFixed(4)})`;
}
const origP3 = computed(() => srgbToP3css(origRgb.value.r, origRgb.value.g, origRgb.value.b));
const adjP3 = computed(() => srgbToP3css(adjRgb.value.r, adjRgb.value.g, adjRgb.value.b));

const satDisplay = computed(() => satValue.value.toFixed(2));
const briDisplay = computed(() => briValue.value.toFixed(2));

// --- HDR detection via CSS media query ---
const hdrMedia = window.matchMedia?.('(dynamic-range: high)');
const gamutP3 = window.matchMedia?.('(color-gamut: p3)');
const gamut2020 = window.matchMedia?.('(color-gamut: rec2020)');

const hdrInfo = ref({
  hdr: hdrMedia?.matches ?? false,
  gamut: gamut2020?.matches ? 'Rec. 2020' : gamutP3?.matches ? 'Display P3' : 'sRGB',
});

function updateHdrInfo() {
  const hdr = hdrMedia?.matches ?? false;
  const gamut = gamut2020?.matches ? 'Rec. 2020' : gamutP3?.matches ? 'Display P3' : 'sRGB';
  hdrInfo.value = { hdr, gamut };
}

onMounted(() => {
  hdrMedia?.addEventListener('change', updateHdrInfo);
  gamutP3?.addEventListener('change', updateHdrInfo);
  gamut2020?.addEventListener('change', updateHdrInfo);
});
onBeforeUnmount(() => {
  hdrMedia?.removeEventListener('change', updateHdrInfo);
  gamutP3?.removeEventListener('change', updateHdrInfo);
  gamut2020?.removeEventListener('change', updateHdrInfo);
});

// --- Color input ---
const colorPickerRef = ref(null);
function openColorPicker() { colorPickerRef.value?.click(); }
function onColorPick(e) { hexInput.value = e.target.value; }

function onHexInput(e) {
  let v = e.target.value.trim();
  if (!v.startsWith("#")) v = "#" + v;
  if (/^#[0-9a-fA-F]{6}$/.test(v)) hexInput.value = v.toUpperCase();
}
function onHexBlur(e) {
  let v = e.target.value.trim();
  if (!v.startsWith("#")) v = "#" + v;
  if (/^#[0-9a-fA-F]{6}$/.test(v)) hexInput.value = v.toUpperCase();
  else e.target.value = hexInput.value;
}

// --- Browser Fullscreen ---
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    containerRef.value?.requestFullscreen();
  } else {
    document.exitFullscreen();
  }
}

function onFullscreenChange() {
  isRealFullscreen.value = !!document.fullscreenElement;
}

onMounted(() => document.addEventListener("fullscreenchange", onFullscreenChange));
onBeforeUnmount(() => document.removeEventListener("fullscreenchange", onFullscreenChange));

// --- Commit ---
const emitCommitted = debounce((s, b) => {
  emit("committed-change", { saturation: s, brightness: b });
}, 300);

function onSatInput(v) { satValue.value = v; }
function onSatChange(v) { satValue.value = v; emitCommitted(v, briValue.value); }
function onBriInput(v) { briValue.value = v; }
function onBriChange(v) { briValue.value = v; emitCommitted(satValue.value, v); }

function resetAll() {
  satValue.value = 1.0;
  briValue.value = 1.0;
  emitCommitted.cancel();
  emit("committed-change", { saturation: 1.0, brightness: 1.0 });
}

defineExpose({ toggleFullscreen });
</script>

<template>
  <div ref="containerRef" class="hdr-container" :class="{ 'hdr-container--real-fs': isRealFullscreen }">
    <!-- Subtitle previews -->
    <div class="hdr-subtitles">
      <div class="hdr-sub-line" :style="{ color: origP3 }">{{ previewText }}</div>
      <div class="hdr-sub-line" :style="{ color: adjP3 }">{{ previewText }}</div>
    </div>

    <!-- Floating adjustment panel -->
    <div class="hdr-panel" :class="{ 'hdr-panel--collapsed': panelCollapsed }" @click.stop>
      <!-- Header (hidden when collapsed) -->
      <div v-show="!panelCollapsed" class="hdr-panel-header">
        <span>{{ t('hdrTitle') }}</span>
        <div class="hdr-panel-header-right">
          <span class="hdr-env-tag" :class="hdrInfo.hdr ? 'hdr-env-tag--on' : 'hdr-env-tag--off'">
            <span class="hdr-env-dot"></span>
            {{ hdrInfo.hdr ? 'HDR' : 'SDR' }} · {{ hdrInfo.gamut }}
          </span>
          <a-button size="small" type="text" @click="toggleFullscreen" class="hdr-fs-btn">
            {{ isRealFullscreen ? '✕' : '⛶' }}
          </a-button>
        </div>
      </div>

      <!-- Panel body (collapsible) -->
      <Transition name="hdr-collapse">
        <div v-show="!panelCollapsed" class="hdr-panel-body">
          <!-- Color row -->
          <div class="hdr-color-row">
            <div class="hdr-dot" :style="{ backgroundColor: hexInput }" @click="openColorPicker">
              <input ref="colorPickerRef" type="color" :value="hexInput" class="hdr-picker-hidden" @input="onColorPick" />
            </div>
            <input
              class="hdr-hex-input"
              :value="hexInput"
              @input="onHexInput"
              @blur="onHexBlur"
              @keydown.enter="(e) => e.target.blur()"
              maxlength="7"
              spellcheck="false"
            />
            <span class="hdr-arrow">→</span>
            <div class="hdr-dot" :style="{ backgroundColor: adjHex }"></div>
            <span class="hdr-hex-label">{{ adjHex }}</span>
          </div>

          <!-- Sliders -->
          <div class="hdr-slider-row">
            <span class="hdr-slider-label">S x{{ satDisplay }}</span>
            <a-slider :min="0" :max="2" :step="0.01" :value="satValue" @input="onSatInput" @change="onSatChange" class="hdr-slider" />
          </div>
          <div class="hdr-slider-row">
            <span class="hdr-slider-label">V x{{ briDisplay }}</span>
            <a-slider :min="0" :max="1" :step="0.01" :value="briValue" @input="onBriInput" @change="onBriChange" class="hdr-slider" />
          </div>

          <!-- Text input -->
          <div class="hdr-text-row">
            <input class="hdr-text-input" v-model="previewText" :placeholder="t('hdrTextPlaceholder')" spellcheck="false" />
          </div>

          <div class="hdr-bottom-row">
            <a-button size="small" @click="resetAll" class="hdr-reset">{{ t('hdrReset') }}</a-button>
            <span class="hdr-collapse-toggle" @click="panelCollapsed = true">▴</span>
          </div>
        </div>
      </Transition>

      <!-- Collapsed: only HDR indicator + expand -->
      <div v-if="panelCollapsed" class="hdr-collapsed-bar">
        <span class="hdr-env-tag" :class="hdrInfo.hdr ? 'hdr-env-tag--on' : 'hdr-env-tag--off'">
          <span class="hdr-env-dot"></span>
          {{ hdrInfo.hdr ? 'HDR' : 'SDR' }} · {{ hdrInfo.gamut }}
        </span>
        <span class="hdr-collapse-toggle" @click="panelCollapsed = false">▾</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hdr-container {
  position: relative;
  width: 100%;
  height: 100%;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 8px;
}

/* Browser fullscreen: remove border-radius, fill screen */
.hdr-container--real-fs {
  border-radius: 0;
}

/* Subtitles */
.hdr-subtitles {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 40px;
  user-select: none;
}
.hdr-sub-line {
  font-size: 36px;
  font-weight: bold;
  letter-spacing: 2px;
  transition: color 0.15s;
}
.hdr-container--real-fs .hdr-sub-line {
  font-size: 56px;
}

/* Panel */
.hdr-panel {
  position: absolute;
  bottom: 20px;
  right: 20px;
  width: 300px;
  background: rgba(20, 20, 40, 0.9);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 14px;
  color: #e0e0e0;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
  transition: width 0.25s ease, padding 0.25s ease;
}
.hdr-container--real-fs .hdr-panel {
  width: 340px;
  bottom: 24px;
  right: 24px;
}

.hdr-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
}
.hdr-fs-btn {
  color: #aaa !important;
  font-size: 18px !important;
  padding: 0 4px !important;
}
.hdr-fs-btn:hover { color: #fff !important; }

.hdr-panel-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.hdr-env-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
}
.hdr-env-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.hdr-env-tag--on {
  background: rgba(82, 196, 26, 0.15);
  color: #52c41a;
}
.hdr-env-tag--on .hdr-env-dot {
  background: #52c41a;
  box-shadow: 0 0 4px #52c41a;
}
.hdr-env-tag--off {
  background: rgba(255, 255, 255, 0.06);
  color: #888;
}
.hdr-env-tag--off .hdr-env-dot {
  background: #666;
}

/* Collapsed state */
.hdr-panel--collapsed {
  width: auto;
  padding: 8px 12px;
}
.hdr-collapsed-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.hdr-collapse-toggle {
  color: #666;
  font-size: 1.6rem;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 3px;
  transition: color 0.2s, background 0.2s;
  user-select: none;
  line-height: 1;
  flex-shrink: 0;
}
.hdr-collapse-toggle:hover {
  color: #ccc;
  background: rgba(255, 255, 255, 0.08);
}

.hdr-bottom-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.hdr-panel-body {
  overflow: hidden;
}

/* Collapse transition */
.hdr-collapse-enter-active {
  transition: max-height 0.25s ease-out, opacity 0.25s ease-out;
}
.hdr-collapse-leave-active {
  transition: max-height 0.2s ease-in, opacity 0.2s ease-in;
}
.hdr-collapse-enter-from,
.hdr-collapse-leave-to {
  max-height: 0;
  opacity: 0;
}
.hdr-collapse-enter-to,
.hdr-collapse-leave-from {
  max-height: 300px;
  opacity: 1;
}

/* Color row */
.hdr-color-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.hdr-dot {
  width: 20px;
  height: 20px;
  border-radius: 5px;
  cursor: pointer;
  position: relative;
  box-shadow: 0 0 6px rgba(255, 255, 255, 0.15);
  flex-shrink: 0;
}
.hdr-picker-hidden {
  position: absolute;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}
.hdr-hex-input {
  width: 80px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 5px;
  color: #e0e0e0;
  padding: 3px 6px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  outline: none;
}
.hdr-hex-input:focus { border-color: #4a9eff; }
.hdr-arrow { color: #666; font-size: 13px; }
.hdr-hex-label {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #ccc;
}

/* Sliders */
.hdr-slider-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.hdr-slider-label {
  min-width: 50px;
  font-size: 11px;
  color: #888;
  font-family: 'Courier New', monospace;
  white-space: nowrap;
}
.hdr-slider { flex: 1; }

/* Text input */
.hdr-text-row { margin-top: 6px; margin-bottom: 8px; }
.hdr-text-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 5px;
  color: #e0e0e0;
  padding: 4px 8px;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}
.hdr-text-input:focus { border-color: #4a9eff; }

.hdr-reset { margin-top: 0; }

/* --- HDR display enhancements --- */
@media (dynamic-range: high) {
  .hdr-sub-line {
    /* Use P3 red-gold for original text when HDR is available */
    filter: brightness(1.1) saturate(1.2);
  }
  .hdr-env-tag--on {
    background: color(display-p3 0.2 0.8 0.1 / 0.2);
    color: color(display-p3 0.4 1 0.2);
  }
  .hdr-env-tag--on .hdr-env-dot {
    background: color(display-p3 0.4 1 0.2);
    box-shadow: 0 0 6px color(display-p3 0.4 1 0.2);
  }
}
</style>
