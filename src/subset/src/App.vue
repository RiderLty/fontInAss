<script setup>
import { useTheme } from './composables/useTheme'

const { algorithm } = useTheme()
</script>

<template>
  <a-config-provider :theme="{ algorithm }">
    <router-view />
  </a-config-provider>
</template>
