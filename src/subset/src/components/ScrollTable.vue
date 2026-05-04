<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, useAttrs } from 'vue'

defineOptions({ inheritAttrs: false })
const attrs = useAttrs()

const wrapperRef = ref(null)
const scrollY = ref(400)
let observer = null

const updateHeight = () => {
  nextTick(() => {
    if (!wrapperRef.value) return
    const header = wrapperRef.value.querySelector('.ant-table-thead')
    scrollY.value = wrapperRef.value.clientHeight - (header?.offsetHeight || 0)
  })
}

onMounted(() => {
  observer = new ResizeObserver(updateHeight)
  if (wrapperRef.value) observer.observe(wrapperRef.value)
})

onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <div ref="wrapperRef" class="scroll-table-wrapper">
    <a-table v-bind="attrs" :scroll="{ ...attrs.scroll, y: scrollY }">
      <template v-for="(_, name) in $slots" #[name]="scope">
        <slot :name="name" v-bind="scope || {}" />
      </template>
    </a-table>
  </div>
</template>

<style scoped>
.scroll-table-wrapper {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
:deep(.ant-table-wrapper) {
  flex: 1;
  min-height: 0;
}
:deep(.ant-table-body) {
  overflow-y: auto !important;
}
</style>
