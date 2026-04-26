<script setup>
import { onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfig } from '../composables/useConfig'
import { message } from 'ant-design-vue'

const { t } = useI18n()
const { config, loading, fetchConfig, updateConfig, deleteConfig } = useConfig()

const configEntries = computed(() => {
  return Object.entries(config.value).map(([key, info]) => ({
    key,
    ...info,
  }))
})

const sourceColor = (source) => {
  switch (source) {
    case 'yaml': return 'blue'
    case 'env': return 'orange'
    case 'default': return 'default'
    default: return 'default'
  }
}

const sourceLabel = (source) => {
  switch (source) {
    case 'yaml': return t('sourceYaml')
    case 'env': return t('sourceEnv')
    case 'default': return t('sourceDefault')
    default: return source
  }
}

const coerceValue = (value, type) => {
  if (value === null || value === undefined || value === '') return null
  if (type === 'integer') {
    const n = parseInt(value)
    return isNaN(n) ? null : n
  }
  if (type === 'float') {
    const n = parseFloat(value)
    return isNaN(n) ? null : n
  }
  if (type === 'boolean') return !!value
  return value
}

const handleSave = async (key, value) => {
  const info = config.value[key]
  const coerced = coerceValue(value, info.type)
  if (coerced === null && info.type !== 'string') {
    message.warning(t('settingsInvalidValue'))
    return
  }
  const result = await updateConfig(key, coerced)
  if (result.success) {
    message.success(t('settingsSaved'))
  } else {
    message.error(result.error || t('settingsSaveFailed'))
  }
}

const handleReset = async (key) => {
  const result = await deleteConfig(key)
  if (result.success) {
    message.success(t('settingsResetDone'))
  }
}

onMounted(() => {
  fetchConfig()
})
</script>

<template>
  <div style="padding: 16px; height: 100vh; box-sizing: border-box; overflow: hidden;">
    <a-spin :spinning="loading" style="height: 100%;">
      <a-card :title="t('settingsTitle')" style="height: 100%; overflow: hidden;" :body-style="{ height: 'calc(100% - 57px)', display: 'flex', flexDirection: 'column', padding: '12px 16px', overflow: 'hidden' }">
        <a-table
          :data-source="configEntries"
          :columns="[
            { title: t('settingsKey'), dataIndex: 'key', width: 220 },
            { title: t('settingsValue'), dataIndex: 'value', width: 250 },
            { title: t('settingsSource'), dataIndex: 'source', width: 150 },
            { title: t('settingsDesc'), dataIndex: 'description' },
            { title: t('action'), key: 'action', width: 150 },
          ]"
          :pagination="false"
          size="small"
          row-key="key"
          :scroll="{ y: 'calc(100vh - 280px)' }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'source'">
              <a-tag :color="sourceColor(record.source)">{{ sourceLabel(record.source) }}</a-tag>
            </template>
            <template v-else-if="column.dataIndex === 'value'">
              <!-- Boolean -->
              <template v-if="record.type === 'boolean'">
                <a-switch
                  :checked="record.value"
                  @change="(checked) => handleSave(record.key, checked)"
                />
              </template>
              <!-- Enum -->
              <template v-else-if="record.type === 'enum'">
                <a-select
                  :value="record.value"
                  style="width: 140px"
                  @change="(val) => handleSave(record.key, val)"
                >
                  <a-select-option v-for="v in record.enum_values" :key="v" :value="v">{{ v }}</a-select-option>
                </a-select>
              </template>
              <!-- Number -->
              <template v-else-if="record.type === 'integer' || record.type === 'float'">
                <a-input-number
                  :value="record.value"
                  :min="record.min"
                  :max="record.max"
                  style="width: 140px"
                  @blur="(e) => handleSave(record.key, e.target.value)"
                  @press-enter="(e) => handleSave(record.key, e.target.value)"
                />
              </template>
              <!-- String -->
              <template v-else>
                <a-input
                  :value="record.value"
                  style="width: 200px"
                  @blur="(e) => handleSave(record.key, e.target.value)"
                  @press-enter="(e) => handleSave(record.key, e.target.value)"
                />
              </template>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button size="small" @click="handleReset(record.key)">{{ t('settingsReset') }}</a-button>
            </template>
          </template>
        </a-table>
      </a-card>
    </a-spin>
  </div>
</template>

<style scoped>
:deep(.ant-table-wrapper) {
  flex: 1;
  min-height: 0;
  border-radius: 8px;
  overflow: hidden;
}
:deep(.ant-table-body) {
  overflow-y: auto !important;
}
:deep(.ant-table-thead th) {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #fafafa;
}
</style>
