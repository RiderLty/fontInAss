<script setup>
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { debounce } from "lodash-es";

const { t } = useI18n();

const props = defineProps({
  saturation: { type: Number, default: 1.0 },
  brightness: { type: Number, default: 1.0 },
});

const emit = defineEmits(["update:saturation", "update:brightness", "committed-change"]);

const originalColor = ref("#ffffff");
const activeSlider = ref("saturation");

const satValue = computed({
  get: () => props.saturation,
  set: (v) => emit("update:saturation", v),
});

const briValue = computed({
  get: () => props.brightness,
  set: (v) => emit("update:brightness", v),
});

// Color math helpers (ported from color.html)
function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) }
    : { r: 0, g: 0, b: 0 };
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

const adjustedColor = computed(() => {
  const rgb = hexToRgb(originalColor.value);
  const hsb = rgbToHsb(rgb.r, rgb.g, rgb.b);
  const adjS = hsb.s * satValue.value;
  const adjB = hsb.b * briValue.value;
  const adjRgb = hsbToRgb(hsb.h, adjS, adjB);
  return `rgb(${adjRgb.r}, ${adjRgb.g}, ${adjRgb.b})`;
});

const satDisplay = computed(() => satValue.value.toFixed(2));
const briDisplay = computed(() => briValue.value.toFixed(2));

const emitCommitted = debounce((s, b) => {
  emit("committed-change", { saturation: s, brightness: b });
}, 300);

function onSatInput(v) {
  satValue.value = v;
}

function onSatChange(v) {
  satValue.value = v;
  emitCommitted(v, briValue.value);
}

function onBriInput(v) {
  briValue.value = v;
}

function onBriChange(v) {
  briValue.value = v;
  emitCommitted(satValue.value, v);
}

function resetAll() {
  satValue.value = 1.0;
  briValue.value = 1.0;
  emitCommitted.cancel();
  emit("committed-change", { saturation: 1.0, brightness: 1.0 });
}

// Color picker
const colorPickerRef = ref(null);
function openColorPicker() {
  colorPickerRef.value?.click();
}
function onColorPick(e) {
  originalColor.value = e.target.value;
}

// Keyboard handling (scoped to component root)
function onKeyDown(e) {
  if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter"].includes(e.key)) return;
  e.stopPropagation();
  e.preventDefault();

  if (e.key === "ArrowUp" || e.key === "ArrowDown") {
    activeSlider.value = activeSlider.value === "saturation" ? "brightness" : "saturation";
  } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    const step = e.key === "ArrowLeft" ? -0.05 : 0.05;
    if (activeSlider.value === "saturation") {
      const nv = Math.max(0, Math.min(1, satValue.value + step));
      satValue.value = parseFloat(nv.toFixed(2));
    } else {
      const nv = Math.max(0, Math.min(1, briValue.value + step));
      briValue.value = parseFloat(nv.toFixed(2));
    }
  } else if (e.key === "Enter") {
    openColorPicker();
  }
}

function onKeyUp(e) {
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    e.stopPropagation();
  }
}
</script>

<template>
  <div class="hdr-adjust" @keydown="onKeyDown" @keyup="onKeyUp" tabindex="0">
    <!-- Color preview -->
    <div class="hdr-preview">
      <div class="hdr-color-box" :style="{ backgroundColor: originalColor }" @click="openColorPicker">
        <input
          ref="colorPickerRef"
          type="color"
          :value="originalColor"
          class="hdr-color-picker"
          @input="onColorPick"
        />
      </div>
      <span class="hdr-arrow">↓</span>
      <div class="hdr-color-box" :style="{ backgroundColor: adjustedColor }"></div>
    </div>

    <!-- Value display -->
    <div class="hdr-values">
      <span>{{ t('hdrSaturation') }} x{{ satDisplay }}</span>
      <span style="margin: 0 8px;">|</span>
      <span>{{ t('hdrBrightness') }} x{{ briDisplay }}</span>
    </div>

    <!-- Sliders -->
    <div class="hdr-sliders">
      <div class="hdr-slider-row">
        <span class="hdr-slider-label">{{ t('hdrSaturation') }}</span>
        <a-slider
          :min="0" :max="1" :step="0.01"
          :value="satValue"
          @input="onSatInput"
          @change="onSatChange"
          class="hdr-slider"
        />
      </div>
      <div class="hdr-slider-row">
        <span class="hdr-slider-label">{{ t('hdrBrightness') }}</span>
        <a-slider
          :min="0" :max="1" :step="0.01"
          :value="briValue"
          @input="onBriInput"
          @change="onBriChange"
          class="hdr-slider"
        />
      </div>
    </div>

    <!-- Reset -->
    <a-button size="small" @click="resetAll" class="hdr-reset-btn">{{ t('hdrReset') }}</a-button>
  </div>
</template>

<style scoped>
.hdr-adjust {
  outline: none;
}

.hdr-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 12px;
}

.hdr-color-box {
  width: 60px;
  height: 60px;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  transition: transform 0.15s;
}

.hdr-color-box:hover {
  transform: scale(1.05);
}

.hdr-color-picker {
  position: absolute;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}

.hdr-arrow {
  font-size: 18px;
  color: #999;
}

.hdr-values {
  text-align: center;
  color: #BDBDBD;
  font-size: 14px;
  margin-bottom: 12px;
}

.hdr-sliders {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hdr-slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hdr-slider-label {
  min-width: 60px;
  font-size: 13px;
  color: #BDBDBD;
  white-space: nowrap;
}

.hdr-slider {
  flex: 1;
}

.hdr-reset-btn {
  margin-top: 8px;
}
</style>
