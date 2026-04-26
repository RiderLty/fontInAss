<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import HdrColorAdjust from '../components/HdrColorAdjust.vue'

const { t } = useI18n()

const saturation = ref(1.0)
const brightness = ref(1.0)
</script>

<template>
  <div style="padding: 24px;">
    <a-card :title="t('hdrTitle')" style="max-width: 500px;">
      <p style="color: #999; margin-bottom: 16px;">{{ t('hdrDesc') }}</p>
      <HdrColorAdjust
        v-model:saturation="saturation"
        v-model:brightness="brightness"
      />
    </a-card>
  </div>
</template>
