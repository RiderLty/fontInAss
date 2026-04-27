<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfig } from '../composables/useConfig'
import HdrColorAdjust from '../components/HdrColorAdjust.vue'

const { t } = useI18n()
const { config, fetchConfig } = useConfig()

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

const saturation = ref(1.0)
const brightness = ref(1.0)

const loadValues = () => {
  if (config.value.HDR_SATURATION) saturation.value = config.value.HDR_SATURATION.value
  if (config.value.HDR_BRIGHTNESS) brightness.value = config.value.HDR_BRIGHTNESS.value
}

const onCommitted = ({ saturation: s, brightness: b }) => {
  fetch(`${API_BASE_URL}/api/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updates: { HDR_SATURATION: s, HDR_BRIGHTNESS: b } }),
  }).catch(() => {})
}

onMounted(async () => {
  await fetchConfig()
  loadValues()
})
</script>

<template>
  <div style="padding: 16px; height: 100vh; box-sizing: border-box;">
    <HdrColorAdjust
      v-model:saturation="saturation"
      v-model:brightness="brightness"
      @committed-change="onCommitted"
    />
  </div>
</template>
