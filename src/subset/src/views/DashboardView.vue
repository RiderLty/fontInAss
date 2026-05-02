<script setup>
import { ref, computed, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
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

const uptimeSeconds = ref(0)
let uptimeBase = 0
let uptimeFetchedAt = 0
let uptimeTimer = null

const fetchStatus = async () => {
  try {
    const resp = await fetch(`${API_BASE_URL}/api/status`)
    const data = await resp.json()
    status.value = data
    uptimeBase = data.uptime_seconds || 0
    uptimeFetchedAt = Date.now()
    uptimeSeconds.value = uptimeBase
  } catch (e) {
    console.error('Failed to fetch status:', e)
  }
}

const updateUptime = () => {
  if (uptimeFetchedAt) {
    uptimeSeconds.value = uptimeBase + Math.floor((Date.now() - uptimeFetchedAt) / 1000)
  }
}

const formatUptime = (seconds) => {
  if (!seconds) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

fetchStatus()
uptimeTimer = setInterval(updateUptime, 1000)

onBeforeUnmount(() => {
  if (uptimeTimer) clearInterval(uptimeTimer)
})
</script>

<template>
  <div style="padding: 16px; height: 100vh; display: flex; flex-direction: column; box-sizing: border-box; overflow: hidden;">
    <!-- Status Cards -->
    <a-row :gutter="[16, 16]" style="margin-bottom: 16px; flex-shrink: 0;">
      <a-col :xs="12" :sm="6" :md="4">
        <a-card size="small">
          <a-statistic :title="t('statusUptime')" :value="formatUptime(uptimeSeconds)" />
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="6" :md="4">
        <a-card size="small">
          <a-statistic :title="t('statusPython')" :value="status?.python_version || '-'" />
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="6" :md="4">
        <a-card size="small">
          <a-statistic :title="t('statusLogLevel')" :value="status?.log_level || '-'" />
        </a-card>
      </a-col>
      <a-col :xs="12" :sm="6" :md="12">
        <a-card size="small">
          <a-statistic :title="t('statusEmbyUrl')" :value="status?.emby_server_url || '-'" />
        </a-card>
      </a-col>
    </a-row>

    <!-- Live Logs -->
    <a-card :title="t('dashboardLogs')" size="small" style="flex: 1; min-height: 0; display: flex; flex-direction: column;" :body-style="{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: '8px' }">
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
        style="flex: 1; min-height: 0; overflow-y: auto; background: #1e1e1e; border-radius: 4px; padding: 8px; font-family: monospace; font-size: 12px;"
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
