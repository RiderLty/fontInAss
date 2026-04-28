<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { Modal, message } from 'ant-design-vue'
import { useMissLogs } from '../composables/useMissLogs'

const { t } = useI18n()

const viewMode = ref('fonts') // fonts | urls | glyphs
const searchQuery = ref('')
const sortField = ref('last_seen')
const sortOrder = ref('desc')
const detailFont = ref(null)
const detailUrl = ref(null)
const drawerVisible = ref(false)
const drawerGlyphs = ref([])

// Virtual scroll table height
const tableWrap = ref(null)
const tableHeight = ref(400)
let resizeObserver = null

const updateTableHeight = () => {
  nextTick(() => {
    if (tableWrap.value) {
      tableHeight.value = tableWrap.value.clientHeight
    }
  })
}

onMounted(() => {
  resizeObserver = new ResizeObserver(updateTableHeight)
  if (tableWrap.value) resizeObserver.observe(tableWrap.value)
})

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect()
})

const {
  summary, fonts, urls, fontDetail, urlDetail, glyphs,
  loading: missLoading,
  fetchSummary, fetchFonts, fetchUrls, fetchFontDetail,
  fetchUrlDetail, fetchGlyphs, fetchAllGlyphs,
  deleteUrl, clearAll,
} = useMissLogs()

const loadMissData = () => {
  fetchSummary()
  if (viewMode.value === 'fonts') fetchFonts(sortField.value, sortOrder.value, searchQuery.value)
  else if (viewMode.value === 'urls') fetchUrls(sortField.value, sortOrder.value)
  else if (viewMode.value === 'glyphs') fetchAllGlyphs(sortField.value, sortOrder.value, searchQuery.value)
  nextTick(updateTableHeight)
}

const switchView = (mode) => {
  viewMode.value = mode
  detailFont.value = null
  detailUrl.value = null
  drawerVisible.value = false
  searchQuery.value = ''
  sortField.value = 'last_seen'
  sortOrder.value = 'desc'
  loadMissData()
}

const handleSort = (field) => {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
  loadMissData()
}

const openFontDetail = async (fontName) => {
  detailFont.value = fontName
  detailUrl.value = null
  drawerVisible.value = true
  await fetchFontDetail(fontName)
  await fetchGlyphs(fontName)
  drawerGlyphs.value = [...glyphs.value]
}

const openUrlDetail = async (url) => {
  detailUrl.value = url
  detailFont.value = null
  drawerVisible.value = true
  await fetchUrlDetail(url)
}

const handleDeleteUrl = async (url) => {
  await deleteUrl(url)
  message.success('OK')
  loadMissData()
}

const handleClearAll = () => {
  Modal.confirm({
    title: t('missLogConfirmClear'),
    onOk: async () => {
      await clearAll()
      message.success('OK')
      loadMissData()
    },
  })
}

const handleSearch = () => {
  if (viewMode.value === 'fonts') {
    fetchFonts(sortField.value, sortOrder.value, searchQuery.value)
  } else if (viewMode.value === 'glyphs') {
    fetchAllGlyphs(sortField.value, sortOrder.value, searchQuery.value)
  }
}

const sortIcon = (field) => {
  if (sortField.value !== field) return ''
  return sortOrder.value === 'desc' ? ' ↓' : ' ↑'
}

const formatTime = (iso) => {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString()
}

const truncateUrl = (url, max = 60) => {
  if (!url || url.length <= max) return url || '-'
  return '...' + url.slice(url.length - max + 3)
}

const splitChars = (chars) => {
  if (!chars) return []
  return [...chars]
}

const copyText = async (text) => {
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text)
    } else {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.cssText = 'position:fixed;left:-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    message.success(t('copied'))
  } catch {
    message.error(t('copyFail'))
  }
}

const drawerTitle = computed(() => {
  if (detailFont.value) return detailFont.value
  if (detailUrl.value) return truncateUrl(detailUrl.value, 80)
  return ''
})

const scrollConfig = computed(() => ({ y: tableHeight.value }))
const headerClick = (field) => ({ style: 'cursor: pointer', onClick: () => handleSort(field) })

loadMissData()
</script>

<template>
  <div style="padding: 16px; height: 100vh; display: flex; flex-direction: column; box-sizing: border-box; overflow: hidden;">
    <a-card :title="t('missLogTitle')" size="small" style="flex: 1; min-height: 0; display: flex; flex-direction: column;" :body-style="{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: '12px', overflow: 'hidden' }">
      <template #extra>
        <a-space>
          <a-button size="small" @click="loadMissData">{{ t('missLogRefresh') }}</a-button>
          <a-button size="small" danger @click="handleClearAll">{{ t('missLogClearAll') }}</a-button>
        </a-space>
      </template>

      <!-- Summary Stats -->
      <a-row :gutter="16" style="margin-bottom: 16px; flex-shrink: 0;">
        <a-col :span="6">
          <a-card size="small" style="text-align: center;">
            <a-statistic :title="t('missLogTotalFonts')" :value="summary.total_fonts || 0" />
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small" style="text-align: center;">
            <a-statistic :title="t('missLogTotalUrls')" :value="summary.total_urls || 0" />
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small" style="text-align: center;">
            <a-statistic :title="t('missLogTotalGlyphs')" :value="summary.total_glyphs || 0" />
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small" style="text-align: center;">
            <a-statistic :title="t('missLogTotalEvents')" :value="summary.total_events || 0" />
          </a-card>
        </a-col>
      </a-row>

      <!-- View Mode Tabs + Search -->
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; flex-shrink: 0;">
        <a-radio-group v-model:value="viewMode" size="small" @change="(e) => switchView(e.target.value)">
          <a-radio-button value="fonts">{{ t('missLogByFont') }}</a-radio-button>
          <a-radio-button value="urls">{{ t('missLogByUrl') }}</a-radio-button>
          <a-radio-button value="glyphs">{{ t('missLogByGlyph') }}</a-radio-button>
        </a-radio-group>
        <a-input-search
          v-if="viewMode === 'fonts' || viewMode === 'glyphs'"
          v-model:value="searchQuery"
          :placeholder="t(viewMode === 'fonts' ? 'missLogSearch' : 'missLogSearchFont')"
          size="small"
          style="width: 200px;"
          @search="handleSearch"
          allow-clear
        />
      </div>

      <!-- Data Table -->
      <div ref="tableWrap" style="flex: 1; min-height: 0; overflow: hidden;">
        <!-- By Font -->
        <a-table
          v-if="viewMode === 'fonts'"
          :data-source="fonts"
          :pagination="false"
          size="small"
          row-key="font_name"
          :loading="missLoading"
          :locale="{ emptyText: t('missLogNoData') }"
          virtual
          :scroll="scrollConfig"
        >
          <a-table-column :title="t('missLogFontName')" data-index="font_name" :width="280">
            <template #default="{ record }">
              <a @click="openFontDetail(record.font_name)" style="cursor: pointer;">{{ record.font_name }}</a>
            </template>
          </a-table-column>
          <a-table-column data-index="total_count" :width="120" :title="t('missLogMissingCount') + sortIcon('total_count')" :custom-header-cell="() => headerClick('total_count')" />
          <a-table-column data-index="last_seen" :width="180" :title="t('missLogLastSeen') + sortIcon('last_seen')" :custom-header-cell="() => headerClick('last_seen')">
            <template #default="{ record }">{{ formatTime(record.last_seen) }}</template>
          </a-table-column>
        </a-table>

        <!-- By URL -->
        <a-table
          v-if="viewMode === 'urls'"
          :data-source="urls"
          :pagination="false"
          size="small"
          row-key="url"
          :loading="missLoading"
          :locale="{ emptyText: t('missLogNoData') }"
          virtual
          :scroll="scrollConfig"
        >
          <a-table-column :title="t('missLogUrl')" data-index="url" :width="300">
            <template #default="{ record }">
              <a-tooltip :title="record.url">
                <a @click="openUrlDetail(record.url)" style="cursor: pointer;">{{ truncateUrl(record.url) }}</a>
              </a-tooltip>
            </template>
          </a-table-column>
          <a-table-column data-index="font_count" :width="100" :title="t('missLogFontCount') + sortIcon('font_count')" :custom-header-cell="() => headerClick('font_count')" />
          <a-table-column data-index="last_seen" :width="180" :title="t('missLogLastSeen') + sortIcon('last_seen')" :custom-header-cell="() => headerClick('last_seen')">
            <template #default="{ record }">{{ formatTime(record.last_seen) }}</template>
          </a-table-column>
          <a-table-column :title="t('missLogAction')" :width="80">
            <template #default="{ record }">
              <a-button size="small" danger @click="handleDeleteUrl(record.url)">{{ t('missLogDelete') }}</a-button>
            </template>
          </a-table-column>
        </a-table>

        <!-- By Glyph -->
        <a-table
          v-if="viewMode === 'glyphs'"
          :data-source="glyphs"
          :pagination="false"
          size="small"
          :row-key="(r) => r.font_name + '|' + r.missing_chars"
          :loading="missLoading"
          :locale="{ emptyText: t('missLogNoData') }"
          virtual
          :scroll="scrollConfig"
        >
          <a-table-column :title="t('missLogFontName')" data-index="font_name" :width="200">
            <template #default="{ record }">
              <span @click="openFontDetail(record.font_name)" style="cursor: pointer; color: #1890ff;">{{ record.font_name }}</span>
            </template>
          </a-table-column>
          <a-table-column :title="t('missLogMissingChars')" data-index="missing_chars" :width="260">
            <template #default="{ record }">
              <span
                style="cursor: pointer; word-break: break-all; white-space: normal;"
                @click="copyText(record.missing_chars)"
              >
                <a-tag v-for="(ch, i) in splitChars(record.missing_chars)" :key="i" color="orange" style="margin-bottom: 2px;">{{ ch }}</a-tag>
              </span>
            </template>
          </a-table-column>
          <a-table-column data-index="total_count" :width="120" :title="t('missLogMissingCount') + sortIcon('total_count')" :custom-header-cell="() => headerClick('total_count')" />
          <a-table-column data-index="last_seen" :width="180" :title="t('missLogLastSeen') + sortIcon('last_seen')" :custom-header-cell="() => headerClick('last_seen')">
            <template #default="{ record }">{{ formatTime(record.last_seen) }}</template>
          </a-table-column>
        </a-table>
      </div>
    </a-card>

    <!-- Detail Drawer -->
    <a-drawer
      v-model:open="drawerVisible"
      :title="drawerTitle"
      placement="right"
      :width="500"
    >
      <!-- Font Detail -->
      <template v-if="detailFont && fontDetail">
        <a-descriptions :column="1" size="small" bordered style="margin-bottom: 16px;">
          <a-descriptions-item :label="t('missLogFontName')">{{ fontDetail.font_name }}</a-descriptions-item>
          <a-descriptions-item :label="t('missLogTotalEvents')">{{ fontDetail.total_count }}</a-descriptions-item>
          <a-descriptions-item :label="t('missLogLastSeen')">{{ formatTime(fontDetail.last_seen) }}</a-descriptions-item>
        </a-descriptions>

        <h4>{{ t('missLogReferencedUrls') }} ({{ fontDetail.urls?.length || 0 }})</h4>
        <a-table
          :data-source="fontDetail.urls || []"
          :pagination="false"
          size="small"
          row-key="url"
          style="margin-bottom: 16px;"
        >
          <a-table-column title="URL" data-index="url">
            <template #default="{ record }">
              <a-tooltip :title="record.url">
                <span>{{ truncateUrl(record.url) }}</span>
              </a-tooltip>
            </template>
          </a-table-column>
          <a-table-column :title="t('missLogMissingCount')" data-index="count" :width="80" />
        </a-table>

        <h4>{{ t('missLogGlyphDetail') }} ({{ drawerGlyphs?.length || 0 }})</h4>
        <a-table
          v-if="drawerGlyphs && drawerGlyphs.length > 0"
          :data-source="drawerGlyphs"
          :pagination="false"
          size="small"
          row-key="missing_chars"
          style="margin-bottom: 16px;"
        >
          <a-table-column :title="t('missLogMissingChars')" data-index="missing_chars">
            <template #default="{ record }">
              <a-tag color="orange">{{ record.missing_chars }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column :title="t('missLogMissingCount')" data-index="total_count" :width="80" />
          <a-table-column :title="t('missLogLastSeen')" data-index="last_seen" :width="160">
            <template #default="{ record }">{{ formatTime(record.last_seen) }}</template>
          </a-table-column>
        </a-table>
        <a-empty v-else :description="t('missLogNoData')" />
      </template>

      <!-- URL Detail -->
      <template v-if="detailUrl && urlDetail">
        <a-descriptions :column="1" size="small" bordered style="margin-bottom: 16px;">
          <a-descriptions-item :label="t('missLogUrl')">
            <a-tooltip :title="urlDetail.url">
              <span>{{ urlDetail.url }}</span>
            </a-tooltip>
          </a-descriptions-item>
        </a-descriptions>

        <h4>{{ t('missLogByFont') }} ({{ urlDetail.fonts?.length || 0 }})</h4>
        <a-table
          :data-source="urlDetail.fonts || []"
          :pagination="false"
          size="small"
          row-key="font_name"
          style="margin-bottom: 16px;"
        >
          <a-table-column :title="t('missLogFontName')" data-index="font_name">
            <template #default="{ record }">
              <a @click="openFontDetail(record.font_name)" style="cursor: pointer;">{{ record.font_name }}</a>
            </template>
          </a-table-column>
          <a-table-column :title="t('missLogMissingCount')" data-index="count" :width="80" />
        </a-table>

        <h4>{{ t('missLogGlyphDetail') }} ({{ urlDetail.glyphs?.length || 0 }})</h4>
        <a-table
          v-if="urlDetail.glyphs && urlDetail.glyphs.length > 0"
          :data-source="urlDetail.glyphs"
          :pagination="false"
          size="small"
          row-key="missing_chars"
        >
          <a-table-column :title="t('missLogFontName')" data-index="font_name" />
          <a-table-column :title="t('missLogMissingChars')" data-index="missing_chars">
            <template #default="{ record }">
              <a-tag color="orange">{{ record.missing_chars }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column :title="t('missLogMissingCount')" data-index="count" :width="80" />
        </a-table>
        <a-empty v-else :description="t('missLogNoData')" />
      </template>
    </a-drawer>
  </div>
</template>
