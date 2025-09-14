<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch  } from "vue";
import { useI18n } from "vue-i18n";
import JSZip from "jszip";
import { saveAs } from "file-saver";
import { message } from "ant-design-vue";
import { debounce } from "lodash-es";
import copy from "copy-to-clipboard";

// 导入方法
import { analyseAss, uudecode } from "../assets/subtitles-octopus.js";

const { t, locale } = useI18n();

// ========= 设置相关 =========
const settingsVisible = ref(false);
const settings = reactive({
  SRT_2_ASS_FORMAT: "",
  SRT_2_ASS_STYLE: "",
  RENAMED_FONT_RESTORE: false,
  CLEAR_FONTS: false,
  DOWNLOAD_PARSE_FONTS: false, // 下载时解析内嵌字体
  CLEAR_SUCCESS_AFTER_DOWNLOAD: true, //下载后清除下载的文件列表
  STRICT_MODE: true, // 严格模式，缺一字体不可
});

// 预设
const formatPresets = [
  "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
];

const stylePresets = [
  "Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1",
];

const openSettings = () => { settingsVisible.value = true; };

const loadSettings = () => {
  let cached = localStorage.getItem("subset_settings");
  if (cached) Object.assign(settings, JSON.parse(cached));
  // 先看本地是否存过语言选择
  const savedLocale = localStorage.getItem("locale");
  if (savedLocale) {
      locale.value = savedLocale;
  } else {
    // 没存过就自动检测浏览器语言
    const browserLang = navigator.language || navigator.userLanguage;
    if (browserLang && browserLang.toLowerCase().startsWith("en")) {
        locale.value = "en-US";
      } else {
        locale.value = "zh-CN"; // 默认中文
      }
  }
};

// 自动保存到 localStorage（防抖）
const saveSettingsToLocal = debounce(() => {
  localStorage.setItem("subset_settings", JSON.stringify(settings));
  // console.log("settings 已保存到 localStorage");
}, 300);

// 监听方法
const initSettingsWatchers = () => {
  // 深度监听 settings
  watch(
      settings,
      saveSettingsToLocal,
      { deep: true}
  );

  // 监听语言变化
  watch(locale, (newVal) => {
    localStorage.setItem("locale", newVal);
    // console.log("locale 已保存到 localStorage:", newVal);
  });
};

// UTF-8 字符串 -> Base64
function base64Utf8Encode(str) {
  const bytes = new TextEncoder().encode(str);
  return btoa(String.fromCharCode(...bytes));
}

// Base64 -> UTF-8 字符串
function base64Utf8Decode(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new TextDecoder().decode(bytes);
}

// ========= 文件处理 =========
const files = ref([]);
const dragActive = ref(false);
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
let dragCounter = 0;

const uploadFile = async (fileObj) => {
  try {
    const headers = {
      "Content-Type": "application/octet-stream",
      "X-Srt-Format": settings.SRT_2_ASS_FORMAT ? base64Utf8Encode(settings.SRT_2_ASS_FORMAT) : "",
      "X-Srt-Style": settings.SRT_2_ASS_STYLE ? base64Utf8Encode(settings.SRT_2_ASS_STYLE) : "",
      "X-Renamed-Restore": settings.RENAMED_FONT_RESTORE ? "1" : "0",
      "X-Clear-Fonts": settings.CLEAR_FONTS ? "1" : "0",
      "X-Fonts-Check": settings.STRICT_MODE ? "1" : "0",
    };

    const response = await fetch(`${API_BASE_URL}/api/subset`, {
      method: "POST",
      headers,
      body: fileObj.arrayBuffer,
    });

    const arrayBuffer = await response.arrayBuffer();
    fileObj.resultBytes = new Uint8Array(arrayBuffer);

    const code = response.headers.get("X-Code");
    const msgHeader = response.headers.get("X-Message");
    let msgArr = [];
    if (msgHeader) {
      const decoded = base64Utf8Decode(msgHeader);
      const parsed = JSON.parse(decoded);
      msgArr = Array.isArray(parsed) ? parsed : [parsed];
    }
    //console.log("X-Code:", code, typeof code);
    if (code) {
      fileObj.status =  t(code) !== code ? t(code) : t("statusError");
      fileObj.msg = msgArr.length ? msgArr : "";
      // fileObj.resultBytes = resultBytes && resultBytes.length > 0 ? resultBytes : null;
    }
  } catch (e) {
    fileObj.status = t("statusError");
    fileObj.msg = [String(e.message || e)];
  }
};


const uploadFile = async (fileObj) => {
  try {
    const headers = {
      "Content-Type": "application/octet-stream",
      "X-Srt-Format": settings.SRT_2_ASS_FORMAT ? base64Utf8Encode(settings.SRT_2_ASS_FORMAT) : "",
      "X-Srt-Style": settings.SRT_2_ASS_STYLE ? base64Utf8Encode(settings.SRT_2_ASS_STYLE) : "",
      "X-Renamed-Restore": settings.RENAMED_FONT_RESTORE ? "1" : "0",
      "X-Clear-Fonts": settings.CLEAR_FONTS ? "1" : "0",
      "X-Fonts-Check": settings.STRICT_MODE ? "1" : "0",
    };

    const response = await fetch(`${API_BASE_URL}/api/subset`, {
      method: "POST",
      headers,
      body: fileObj.arrayBuffer,
    });

    const arrayBuffer = await response.arrayBuffer();
    const resultBytes = new Uint8Array(arrayBuffer);

    const code = response.headers.get("X-Code");
    const msgHeader = response.headers.get("X-Message");
    let msgArr = [];
    if (msgHeader) {
      const decoded = base64Utf8Decode(msgHeader);
      const parsed = JSON.parse(decoded);
      msgArr = Array.isArray(parsed) ? parsed : [parsed];
    }
    //console.log("X-Code:", code, typeof code);
    if (code) {
      fileObj.status =  t(code) !== code ? t(code) : t("statusError");
      fileObj.msg = msgArr.length ? msgArr : "";
      fileObj.resultBytes = resultBytes && resultBytes.length > 0 ? resultBytes : null;
    }
  } catch (e) {
    fileObj.status = t("statusError");
    fileObj.msg = [String(e.message || e)];
  }
};

const handleClickUpload = async () => {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".ass,.srt,.ssa";
  input.multiple = true;
  input.onchange = async (e) => {
    const selectedFiles = e.target.files;
    if (!selectedFiles || selectedFiles.length === 0) return;
    await processFiles(selectedFiles);
  };
  input.click();
};

const removeFile = (record) => { files.value = files.value.filter((f) => f.key !== record.key); };
const removeAll = () => { files.value = []; };

const retryFailed = async () => {
  const failedFiles = files.value.filter((f) => f.status === t("statusError"));
  if (failedFiles.length === 0) {
    message.info(t("noFailed"));
    return;
  }
  const promises = [];
  failedFiles.forEach((f) => {
    f.status = t("statusRetrying");
    promises.push(uploadFile(f));
  });
  await Promise.all(promises);
  message.success(t("retryDone"));
};

// 下载文件
const downloadAll = async () => {
  let processedFiles = [];

  for (let f of files.value) {
    if (!f.resultBytes) continue; // 有 resultBytes 才下载
    const baseName = f.name.replace(/(\.\w+)$/, "");
    let ext = (f.origExt || "").toLowerCase();
    if (ext === ".srt") ext = ".ass";
    else if (ext !== ".ass" && ext !== ".ssa") ext = ".ass";
    const finalName = `${baseName}.subset${ext}`;

    // 收集处理结果
    processedFiles.push({
      name: finalName,
      bytes: f.resultBytes,
      baseName,
      fonts: settings.DOWNLOAD_PARSE_FONTS ? (() => {
        try {
          const decoder = new TextDecoder("utf-8");
          const assContent = decoder.decode(f.resultBytes);
          return analyseAss(assContent, true);
        } catch (e) {
          console.warn(`解析内嵌字体失败: ${f.name}`, e);
          return [];
        }
      })() : []
    });
  }

  if (processedFiles.length === 0) {
    message.warning(t("noDownloadable"));
    return;
  }

  // 判断是否需要打包
  const needZip =
      processedFiles.length > 1 ||
      processedFiles.some(f => f.fonts.length > 0);

  if (!needZip) {
    // 只有一个文件且没有字体 → 直接下载
    const f = processedFiles[0];
    saveAs(new Blob([f.bytes]), f.name);
  } else {
    // 打包 zip
    const zip = new JSZip();
    processedFiles.forEach((pf) => {
      zip.file(pf.name, pf.bytes);
      if (pf.fonts.length > 0) {
        const fontFolder = zip.folder(pf.baseName + ".subset");
        pf.fonts.forEach((font) => {
          fontFolder.file(`${font.name}`, uudecode(font.data));
        });
      }
    });
    const content = await zip.generateAsync({ type: "blob" });
    saveAs(content, "subset.zip");
  }

  if (settings.CLEAR_SUCCESS_AFTER_DOWNLOAD) {
    files.value = files.value.filter(f => !f.resultBytes);
  }
};

// 工具：判断单元格是否为空（数组/字符串都考虑）
const isEmptyCell = (value) => {
  if (value == null) return true;
  if (Array.isArray(value)) return value.every(v => v == null || v === "");
  return String(value).trim() === "";
};

// 点击单元格的统一入口（先判断是否为空）
const onCellClick = (value, columnKey) => {
  if (columnKey === "action") return;
  if (isEmptyCell(value)) return;
  // 把数组转换为多行文本，object 则 JSON.stringify
  let text;
  if (Array.isArray(value)) {
    text = value.join("\n");
  } else if (typeof value === "object") {
    try { text = JSON.stringify(value); } catch { text = String(value); }
  } else {
    text = String(value);
  }
  copyMessage(text);
};

const copyMessage = (text) => {
  if (copy(text)) {
    message.success(t("copied"));
  } else {
    message.error(t("copyFail"));
  }
};

// ========= 输入框预设逻辑 =========
const formatDropdownVisible = ref(false);
const styleDropdownVisible = ref(false);

const onFormatFocus = () => {
  if (!settings.SRT_2_ASS_FORMAT) {
    formatDropdownVisible.value = true;
  }
};

const onFormatBlur = () => {
  setTimeout(() => { formatDropdownVisible.value = false; }, 100);
};

const onFormatInput = (e) => {
  formatDropdownVisible.value = !e.target.value;
};

const selectFormatPreset = (preset) => {
  settings.SRT_2_ASS_FORMAT = preset;
  formatDropdownVisible.value = false;
};

const onStyleFocus = () => {
  if (!settings.SRT_2_ASS_STYLE) {
    styleDropdownVisible.value = true;
  }
};

const onStyleBlur = () => {
  setTimeout(() => { styleDropdownVisible.value = false; }, 100);
};

const onStyleInput = (e) => {
  styleDropdownVisible.value = !e.target.value;
};

const selectStylePreset = (preset) => {
  settings.SRT_2_ASS_STYLE = preset;
  styleDropdownVisible.value = false;
};

const canDownload = computed(() => files.value.some((f) => f.resultBytes));
const hasFailed = computed(() => files.value.some((f) => f.status === t("statusError")));

const columns = computed(() => [
  { title: t("filename"), dataIndex: "name", key: "name" },
  { title: t("status"), dataIndex: "status", key: "status" },
  { title: t("message"), dataIndex: "msg", key: "msg" },
  { title: t("action"), key: "action" },
]);

// 拖拽
const handleDragEnter = (e) => { e.preventDefault(); e.stopPropagation(); dragCounter++; dragActive.value = true; };
const handleDragOver = (e) => { e.preventDefault(); e.stopPropagation(); };
const handleDragLeave = (e) => { e.preventDefault(); e.stopPropagation(); dragCounter--; if (dragCounter <= 0) { dragActive.value = false; dragCounter = 0; } };
const handleDrop = async (e) => { e.preventDefault(); e.stopPropagation(); dragActive.value = false; dragCounter = 0; const droppedFiles = e.dataTransfer.files; if (!droppedFiles || droppedFiles.length === 0) return; await processFiles(droppedFiles); };
const preventDefault = (e) => { e.preventDefault(); e.stopPropagation(); };

onMounted(() => {
  loadSettings();
  initSettingsWatchers();
  window.addEventListener("dragenter", handleDragEnter);
  window.addEventListener("dragover", handleDragOver);
  window.addEventListener("dragleave", handleDragLeave);
  window.addEventListener("drop", handleDrop);
  window.addEventListener("dragover", preventDefault);
  window.addEventListener("drop", preventDefault);
});

onBeforeUnmount(() => {
  window.removeEventListener("dragenter", handleDragEnter);
  window.removeEventListener("dragover", handleDragOver);
  window.removeEventListener("dragleave", handleDragLeave);
  window.removeEventListener("drop", handleDrop);
  window.removeEventListener("dragover", preventDefault);
  window.removeEventListener("drop", preventDefault);
});
</script>

<template>
  <div style="min-height: 100vh; padding: 20px">
    <a-space style="margin-bottom: 15px">
      <a-button type="primary" @click="handleClickUpload">{{ t('upload') }}</a-button>
      <a-button type="default" @click="retryFailed" :disabled="!hasFailed">{{ t('retry') }}</a-button>
      <a-button danger @click="removeAll" :disabled="files.length === 0">{{ t('removeAll') }}</a-button>
      <a-button type="primary" @click="downloadAll" :disabled="!canDownload">{{ t('download') }}</a-button>
      <a-button type="default" @click="openSettings">{{ t('settings') }}</a-button>
    </a-space>

    <transition name="fade">
      <div v-if="dragActive" class="dropzone"><p>{{ t('dropTip') }}</p></div>
    </transition>

    <a-table
        :columns="columns"
        :dataSource="files"
        :pagination="false"
        bordered
        style="margin-top: 10px;"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button size="small" type="link" danger @click="removeFile(record)">{{ t('delete') }}</a-button>
          </a-space>
        </template>
        <template v-else>
          <div
              class="cell-content"
              :class="{
          'cell-empty': isEmptyCell(record[column.dataIndex]),
          'cell-filename': column.dataIndex === 'name',
          'cell-status': column.dataIndex === 'status',
          'cell-msg': column.dataIndex === 'msg'
        }"
              @click="onCellClick(record[column.dataIndex], column.key)"
          >
            <template v-if="column.dataIndex === 'msg'">
              <div v-if="Array.isArray(record.msg)">
                <div v-for="(m, i) in record.msg" :key="i">{{ m }}</div>
              </div>
              <div v-else>{{ record.msg }}</div>
            </template>
            <template v-else>
              {{ record[column.dataIndex] }}
            </template>
          </div>
        </template>
      </template>
    </a-table>
    <a-modal
        v-model:open="settingsVisible"
        :title="t('modalTitle')"
        footer= ""
    >
      <a-form layout="vertical">
        <a-form-item>
          <template #label>
            <a-tooltip :title="t('srtFormatDesc')">
              {{ t('srtFormatLabel') }}
            </a-tooltip>
          </template>
          <a-dropdown
              :open="formatDropdownVisible"
              :trigger="[]"
              placement="bottomLeft"
          >
            <a-textarea
                class="textarea-input"
                v-model:value="settings.SRT_2_ASS_FORMAT"
                :placeholder="t('srtFormatPlaceholder')"
                :rows="2"
                @focus="onFormatFocus"
                @blur="onFormatBlur"
                @input="onFormatInput"
            />
            <template #overlay>
              <a-menu v-if="!settings.SRT_2_ASS_FORMAT">
                <a-menu-item
                    v-for="(f, idx) in formatPresets"
                    :key="idx"
                    class="a-dropdown-menu-item-long-text"
                    @mousedown.prevent="selectFormatPreset(f)"
                >
                  {{ f }}
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </a-form-item>

        <a-form-item>
          <template #label>
            <a-tooltip :title="t('srtStyleDesc')">
              {{ t('srtStyleLabel') }}
            </a-tooltip>
          </template>
          <a-dropdown
              :open="styleDropdownVisible"
              :trigger="[]"
              placement="bottomLeft"
          >
            <a-textarea
                class="textarea-input"
                v-model:value="settings.SRT_2_ASS_STYLE"
                :placeholder="t('srtStylePlaceholder')"
                :rows="2"
                @focus="onStyleFocus"
                @blur="onStyleBlur"
                @input="onStyleInput"
            />
            <template #overlay>
              <a-menu v-if="!settings.SRT_2_ASS_STYLE">
                <a-menu-item
                    v-for="(s, idx) in stylePresets"
                    :key="idx"
                    class="a-dropdown-menu-item-long-text"
                    @mousedown.prevent="selectStylePreset(s)"
                >
                  {{ s }}
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </a-form-item>

        <!-- 勾选开关改为两列一行 -->
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item>
              <template #label>
                <a-tooltip :title="t('restoreRenamedFontDesc')">
                  {{ t('restoreRenamedFont') }}
                </a-tooltip>
              </template>
              <a-switch v-model:checked="settings.RENAMED_FONT_RESTORE"/>
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item>
              <template #label>
                <a-tooltip :title="t('clearEmbeddedFontsDesc')">
                  {{ t('clearEmbeddedFonts') }}
                </a-tooltip>
              </template>
              <a-switch v-model:checked="settings.CLEAR_FONTS"/>
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item>
              <template #label>
                <a-tooltip :title="t('downloadFontsDesc')">
                  {{ t('downloadFonts') }}
                </a-tooltip>
              </template>
              <a-switch v-model:checked="settings.DOWNLOAD_PARSE_FONTS"/>
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item>
              <template #label>
                <a-tooltip :title="t('clearAfterDownloadDesc')">
                  {{ t('clearAfterDownload') }}
                </a-tooltip>
              </template>
              <a-switch v-model:checked="settings.CLEAR_SUCCESS_AFTER_DOWNLOAD"/>
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item>
              <template #label>
                <a-tooltip :title="t('strictModeDesc')">
                  {{ t('strictMode') }}
                </a-tooltip>
              </template>
              <a-switch v-model:checked="settings.STRICT_MODE"/>
            </a-form-item>
          </a-col>
        </a-row>

        <!-- 语言选择保持原样 -->
        <a-form-item>
          <template #label>
            <a-tooltip :title="t('languageDesc')">
              {{ t('languageLabel') }}
            </a-tooltip>
          </template>
          <a-select v-model:value="locale" allow-clear>
            <a-select-option value="zh-CN">中文</a-select-option>
            <a-select-option value="en-US">English</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>

    </a-modal>
  </div>
</template>

<style scoped>
.dropzone {
  position: fixed;
  top: 0; left: 0; width: 100%; height: 100%;
  border: 3px dashed #1890ff;
  background-color: rgba(24,144,255,0.1);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; color: #1890ff;
  z-index: 9999; pointer-events: none;
}

.fade-enter-active,.fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from,.fade-leave-to { opacity: 0; }

/* 保留换行并允许在必要处断行（兼容换行符和长单词/路径） */
.cell-content {
  white-space: pre-wrap;      /* 保留 \n，同时允许换行 */
  overflow-wrap: anywhere;    /* 在任何位置断行（在必要时） */
  word-break: break-all;      /* CJK/长串兜底断行 */
  padding: 6px 8px;
  line-height: 1.5;
}

/* 空单元格样式 */
.cell-empty {
  cursor: default !important;
  color: inherit;
}

/* 鼠标悬停效果（非空才高亮） */
.cell-content:not(.cell-empty):hover {
  background: #f6f6f6;
}

/* 文件名列最多 400px，超长换行 */
.cell-filename {
  max-width: 400px;
  overflow-wrap: break-word;
}

/* 状态列最多 120px */
.cell-status {
  max-width: 120px;
  overflow-wrap: break-word;
}

/* 提示列最多 500px */
.cell-msg {
  max-width: 500px;
  overflow-wrap: break-word;
}

/* 让单元格顶部对齐，视觉更好 */
:deep(.ant-table td),
:deep(.ant-table th) {
  vertical-align: top;
}

:deep(.a-dropdown-menu-item-long-text) {
  white-space: pre-wrap;
  overflow-wrap: break-word;
  word-break: break-all;
  max-width: 450px;
}

.textarea-input {
  word-break: break-all;
}

</style>
