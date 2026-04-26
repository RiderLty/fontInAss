<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const collapsed = ref(false)

const menuItems = computed(() => [
  { key: '/dashboard', label: t('navDashboard'), icon: '📊' },
  { key: '/subset', label: t('navSubset'), icon: '📁' },
  { key: '/hdr', label: t('navHdr'), icon: '🎨' },
  { key: '/settings', label: t('navSettings'), icon: '⚙️' },
])

const selectedKeys = computed(() => [route.path])

const onMenuClick = ({ key }) => {
  router.push(key)
}
</script>

<template>
  <a-layout style="min-height: 100vh">
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
    </a-layout-sider>
    <a-layout>
      <a-layout-content style="margin: 0; padding: 0; overflow: auto;">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<style scoped>
:deep(.ant-layout-sider) {
  background: #001529;
}
:deep(.ant-layout) {
  background: #f0f2f5;
}
</style>
