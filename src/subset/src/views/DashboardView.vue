<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSSE } from '../composables/useSSE'

const { t } = useI18n()
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

const { messages, connected, clearMessages } = useSSE(`${API_BASE_URL}/api/logs/stream`)

const paused = ref(false)
const logContainer = ref(null)
const status = ref(null)

// Auto-scroll to bottom
watch(messages, async () => {
  if (!paused.value && logContainer.value) {
    await nextTick()
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}, { deep: true })

const levelColor = (level) => {
  switch (level) {
    case 'ERROR': return '#ff4d4f'
    case 'WARNING': return '#faad14'
    case 'INFO': return '#52c41a'
    case 'DEBUG': return '#1890ff'
    default: return '#d9d9d9'
  }
}

const fetchStatus = async () => {
  try {
    const resp = await fetch(`${API_BASE_URL}/api/status`)
    status.value = await resp.json()
  } catch (e) {
    console.error('Failed to fetch status:', e)
  }
}

const formatUptime = (seconds) => {
  if (!seconds) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

fetchStatus()
</script>

<template>
  <div style="padding: 16px; height: 100%; display: flex; flex-direction: column;">
    <!-- Status Cards -->
    <a-row :gutter="16" style="margin-bottom: 16px;">
      <a-col :span="6">
        <a-card size="small">
          <a-statistic :title="t('statusVersion')" :value="status?.version || '-'" />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small">
          <a-statistic :title="t('statusUptime')" :value="formatUptime(status?.uptime_seconds)" />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small">
          <a-statistic :title="t('statusPython')" :value="status?.python_version || '-'" />
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small">
          <a-statistic :title="t('statusLogLevel')" :value="status?.log_level || '-'" />
        </a-card>
      </a-col>
    </a-row>

    <!-- Log Viewer -->
    <a-card :title="t('dashboardLogs')" size="small" style="flex: 1; display: flex; flex-direction: column;" :body-style="{ flex: 1, display: 'flex', flexDirection: 'column', padding: '8px' }">
      <template #extra>
        <a-space>
          <a-tag :color="connected ? 'green' : 'red'">
            {{ connected ? t('sseConnected') : t('sseDisconnected') }}
          </a-tag>
          <a-button size="small" @click="paused = !paused">
            {{ paused ? t('logResume') : t('logPause') }}
          </a-button>
          <a-button size="small" @click="clearMessages">{{ t('logClear') }}</a-button>
        </a-space>
      </template>
      <div
        ref="logContainer"
        style="flex: 1; overflow-y: auto; background: #1e1e1e; border-radius: 4px; padding: 8px; font-family: 'Courier New', monospace; font-size: 12px; min-height: 300px;"
      >
        <div v-if="messages.length === 0" style="color: #666; text-align: center; padding: 40px;">
          {{ t('logWaiting') }}
        </div>
        <div v-for="(msg, i) in messages" :key="i" style="padding: 1px 0; white-space: pre-wrap; word-break: break-all;">
          <span style="color: #666;">{{ msg.time }}</span>
          <span :style="{ color: levelColor(msg.level), margin: '0 6px', fontWeight: 'bold' }">{{ msg.level }}</span>
          <span style="color: #d4d4d4;">{{ msg.message }}</span>
        </div>
      </div>
    </a-card>
  </div>
</template>
