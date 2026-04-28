<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useTheme } from '../composables/useTheme'

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const collapsed = ref(false)
const isMobile = ref(false)
const drawerOpen = ref(false)
const { themeMode, cycleTheme } = useTheme()

const menuItems = computed(() => [
  { key: '/dashboard', label: t('navDashboard'), icon: '📊' },
  { key: '/miss-logs', label: t('navMissLogs'), icon: '🔍' },
  { key: '/subset', label: t('navSubset'), icon: '📁' },
  { key: '/hdr', label: t('navHdr'), icon: '🎨' },
  { key: '/settings', label: t('navSettings'), icon: '⚙️' },
])

const selectedKeys = computed(() => [route.path])

const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) {
    drawerOpen.value = false
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', checkMobile)
})

watch(() => route.path, () => {
  if (isMobile.value) {
    drawerOpen.value = false
  }
})

const onMenuClick = ({ key }) => {
  router.push(key)
}

const toggleLocale = () => {
  locale.value = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  localStorage.setItem('locale', locale.value)
}

const localeLabel = computed(() => locale.value === 'zh-CN' ? 'Switch to English' : '切换至中文')

const themeIcon = computed(() => {
  if (themeMode.value === 'light') return '☀️'
  if (themeMode.value === 'dark') return '🌙'
  return '💻'
})

const themeLabel = computed(() => t('theme' + themeMode.value.charAt(0).toUpperCase() + themeMode.value.slice(1)))
</script>

<template>
  <!-- Mobile: drawer sidebar -->
  <template v-if="isMobile">
    <a-layout style="height: 100vh">
      <a-layout-header style="background: #001529; padding: 0 16px; display: flex; align-items: center; justify-content: space-between; height: 48px; line-height: 48px;">
        <span style="color: #fff; font-weight: bold; font-size: 16px;">FontInAss</span>
        <a-button type="text" style="color: #fff; font-size: 18px;" @click="drawerOpen = true">☰</a-button>
      </a-layout-header>
      <a-layout-content style="height: calc(100vh - 48px); overflow: auto;">
        <router-view />
      </a-layout-content>
    </a-layout>
    <a-drawer
      :open="drawerOpen"
      placement="left"
      :closable="false"
      :width="240"
      :body-style="{ padding: 0, background: '#001529' }"
      @close="drawerOpen = false"
    >
      <div style="height: 32px; margin: 12px; color: #fff; font-weight: bold; font-size: 16px; text-align: center;">
        FontInAss
      </div>
      <a-menu
        theme="dark"
        mode="inline"
        :selected-keys="selectedKeys"
        @click="onMenuClick"
      >
        <a-menu-item v-for="item in menuItems" :key="item.key">
          <span>{{ item.icon }} {{ item.label }}</span>
        </a-menu-item>
      </a-menu>
      <div style="position: absolute; bottom: 0; left: 0; right: 0; padding: 8px; text-align: center; border-top: 1px solid rgba(255,255,255,0.1);">
        <a-button type="text" style="color: rgba(255,255,255,0.65); width: 100%;" @click="cycleTheme">
          {{ themeIcon }} {{ themeLabel }}
        </a-button>
        <a-button type="text" style="color: rgba(255,255,255,0.65); width: 100%;" @click="toggleLocale">
          {{ localeLabel }}
        </a-button>
      </div>
    </a-drawer>
  </template>

  <!-- Desktop: fixed sidebar -->
  <template v-else>
    <a-layout style="height: 100vh">
      <a-layout-sider
        v-model:collapsed="collapsed"
        :trigger="null"
        collapsible
        theme="dark"
        :width="200"
        :collapsed-width="60"
      >
        <div style="height: 32px; margin: 12px; color: #fff; font-weight: bold; font-size: 16px; white-space: nowrap; overflow: hidden; text-align: center;">
          <span v-if="!collapsed">FontInAss</span>
          <span v-else>FiA</span>
        </div>
        <a-menu
          theme="dark"
          mode="inline"
          :selected-keys="selectedKeys"
          @click="onMenuClick"
        >
          <a-menu-item v-for="item in menuItems" :key="item.key">
            <span>{{ item.icon }} {{ item.label }}</span>
          </a-menu-item>
        </a-menu>
        <div style="position: absolute; bottom: 0; left: 0; right: 0; padding: 8px; text-align: center; border-top: 1px solid rgba(255,255,255,0.1);">
          <a-button type="text" style="color: rgba(255,255,255,0.65); width: 100%;" @click="cycleTheme">
            {{ themeIcon }} {{ themeLabel }}
          </a-button>
          <a-button type="text" style="color: rgba(255,255,255,0.65); width: 100%;" @click="toggleLocale">
            {{ localeLabel }}
          </a-button>
        </div>
      </a-layout-sider>
      <a-layout style="height: 100vh">
        <a-layout-content style="height: 100vh; overflow: auto;">
          <router-view />
        </a-layout-content>
      </a-layout>
    </a-layout>
  </template>
</template>

<style scoped>
:deep(.ant-layout-sider) {
  background: #001529;
  position: relative;
}
</style>
