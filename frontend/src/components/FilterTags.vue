<template>
  <div v-if="fields.length" class="filter-tags-row" ref="rowEl">
    <span class="filter-tags-label">筛选</span>
    <button
      v-for="f in fields"
      :key="f.key"
      type="button"
      class="filter-chip"
      :class="{ 'is-picked': picked(f.key).length, 'is-open': activeKey === f.key }"
      :title="`${f.label}：${summary(f.key)}`"
      @mousedown.prevent="toggle(f.key, $event)"
    >
      <span class="fc-label">{{ f.label }}</span>
      <span class="fc-value">{{ summary(f.key) }}</span>
      <!-- 已选时只显示「清除」，未选时只显示「展开」，两个图标不并存 -->
      <el-icon
        v-if="picked(f.key).length"
        class="fc-clear"
        title="清除该筛选"
        @mousedown.stop.prevent="clear(f.key)"
      ><Close /></el-icon>
      <el-icon v-else class="fc-caret" :class="{ 'is-open': activeKey === f.key }"><ArrowDown /></el-icon>
    </button>
    <transition name="ft-fade">
      <el-button v-if="hasActive" size="small" link type="primary" @click="clearAll">清除全部</el-button>
    </transition>

    <transition name="ft-pop">
      <div v-if="activeField" ref="dropdownEl" class="filter-dropdown" :style="dropdownStyle" @mousedown.stop>
        <div class="filter-search">
          <el-input v-model="search" size="small" placeholder="搜索选项…" clearable :prefix-icon="Search" />
        </div>
        <div class="filter-list">
          <div
            class="filter-option"
            :class="{ active: !picked(activeField.key).length }"
            @click.stop="clear(activeField.key)"
          >全部</div>
          <div
            v-for="opt in activeOptions"
            :key="String(opt.value)"
            class="filter-option"
            :class="{ active: picked(activeField.key).includes(opt.value) }"
            @click.stop="toggleValue(activeField.key, opt.value)"
          ><span class="filter-check">{{ picked(activeField.key).includes(opt.value) ? '✓' : '' }}</span><span class="filter-option-text">{{ opt.text }}</span></div>
          <div v-if="!activeOptions.length" class="filter-option is-empty">无可选值</div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ArrowDown, Close, Search } from '@element-plus/icons-vue'
import { makeFilters, valueLabel } from '../utils/fieldColumns'

// model 为父组件的 reactive 对象（key -> 已选值数组），直接就地修改
const props = defineProps({
  fields: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  model: { type: Object, required: true },
})

const rowEl = ref(null)
const dropdownEl = ref(null)
const activeKey = ref(null)
const search = ref('')
const dropdownStyle = ref({})

const activeField = computed(() => props.fields.find((f) => f.key === activeKey.value) || null)

const activeOptions = computed(() => {
  if (!activeField.value) return []
  const opts = makeFilters(props.rows, activeField.value)
  const kw = search.value.trim().toLowerCase()
  if (!kw) return opts
  return opts.filter((o) => o.text.toLowerCase().includes(kw))
})

const hasActive = computed(() => props.fields.some((f) => picked(f.key).length > 0))

function picked(key) {
  const v = props.model[key]
  return Array.isArray(v) ? v : []
}

function summary(key) {
  const vals = picked(key)
  if (!vals.length) return '全部'
  if (vals.length === 1) {
    const f = props.fields.find((x) => x.key === key)
    return String(valueLabel(f, vals[0]))
  }
  return `已选${vals.length}项`
}

function toggle(key, e) {
  if (activeKey.value === key) {
    activeKey.value = null
    return
  }
  activeKey.value = key
  search.value = ''
  const rect = e.currentTarget.getBoundingClientRect()
  // 贴着标签下方弹出；靠近视口右/下边缘时回收，避免溢出屏幕
  const left = Math.min(rect.left, window.innerWidth - 240)
  const maxH = Math.max(180, window.innerHeight - rect.bottom - 16)
  dropdownStyle.value = {
    top: `${rect.bottom + 4}px`,
    left: `${Math.max(8, left)}px`,
    maxHeight: `${Math.min(360, maxH)}px`,
  }
}

function toggleValue(key, value) {
  const cur = picked(key).slice()
  const idx = cur.indexOf(value)
  if (idx >= 0) cur.splice(idx, 1)
  else cur.push(value)
  props.model[key] = cur
}

function clear(key) {
  props.model[key] = []
}

function clearAll() {
  props.fields.forEach((f) => { props.model[f.key] = [] })
}

function close() {
  activeKey.value = null
}

function onDocMousedown(e) {
  if (!activeKey.value) return
  if (rowEl.value && rowEl.value.contains(e.target)) return
  close()
}

// 页面滚动会让固定定位的面板脱离标签，直接关闭；面板内部滚动除外
function onScroll(e) {
  if (dropdownEl.value && dropdownEl.value.contains(e.target)) return
  close()
}

// 字段列表变化（切换模块/字段管理改动）后，丢弃已不存在字段的筛选值
watch(() => props.fields.map((f) => f.key).join(','), () => {
  if (activeKey.value && !props.fields.some((f) => f.key === activeKey.value)) close()
})

onMounted(() => {
  document.addEventListener('mousedown', onDocMousedown)
  window.addEventListener('resize', close)
  window.addEventListener('scroll', onScroll, true)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', onDocMousedown)
  window.removeEventListener('resize', close)
  window.removeEventListener('scroll', onScroll, true)
})
</script>

<style scoped>
.filter-tags-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f2f3f7;
  position: relative;
}
.filter-tags-label {
  font-size: 12px;
  color: #b0b6c0;
  margin-right: 2px;
  user-select: none;
  letter-spacing: 2px;
}

/* ─── 筛选 chip ─────────────────────────────── */
.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 27px;
  padding: 0 9px;
  max-width: 280px;
  background: #f4f5f8;
  border: none;
  border-radius: 8px;
  font-family: inherit;
  font-size: 12.5px;
  color: #5b6472;
  cursor: pointer;
  outline: none;
  transition: background-color 0.18s, color 0.18s, box-shadow 0.18s, transform 0.1s;
}
.filter-chip:hover {
  background: #eceef4;
  color: #374151;
}
.filter-chip:active {
  transform: scale(0.97);
}
.filter-chip.is-open,
.filter-chip.is-picked {
  background: var(--hpgc-primary-soft);
  color: var(--el-color-primary);
}
.filter-chip.is-open {
  box-shadow: 0 0 0 1.5px var(--el-color-primary) inset;
}
.fc-label {
  opacity: 0.72;
  white-space: nowrap;
}
.fc-value {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
}
.filter-chip.is-picked .fc-label {
  opacity: 0.85;
}
/* 分隔点 */
.fc-label::after {
  content: '·';
  margin-left: 5px;
  opacity: 0.5;
}
.fc-caret {
  font-size: 11px;
  opacity: 0.55;
  flex-shrink: 0;
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.fc-caret.is-open {
  transform: rotate(180deg);
}
.fc-clear {
  font-size: 12px;
  flex-shrink: 0;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0.75;
  transition: background-color 0.15s, opacity 0.15s;
}
.fc-clear:hover {
  background: rgba(59, 130, 246, 0.18);
  opacity: 1;
}

/* ─── 下拉面板 ─────────────────────────────── */
.filter-dropdown {
  position: fixed;
  z-index: 9999;
  background: #fff;
  border: 1px solid #eceef2;
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12), 0 2px 6px rgba(15, 23, 42, 0.05);
  min-width: 200px;
  max-width: 360px;
  padding: 8px 0 6px;
  display: flex;
  flex-direction: column;
}
.filter-search {
  padding: 2px 10px 8px;
}
.filter-list {
  overflow-y: auto;
}
.filter-option {
  display: flex;
  align-items: center;
  padding: 7px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #4b5563;
  border-radius: 7px;
  margin: 0 6px;
  white-space: nowrap;
  transition: background-color 0.12s, color 0.12s;
}
.filter-option-text {
  overflow: hidden;
  text-overflow: ellipsis;
}
.filter-option:hover {
  background: #f5f7fa;
  color: var(--el-color-primary);
}
.filter-option.active {
  color: var(--el-color-primary);
  background: var(--hpgc-primary-soft);
  font-weight: 500;
}
.filter-option.is-empty {
  color: #c0c4cc;
  cursor: default;
}
.filter-option.is-empty:hover {
  background: transparent;
  color: #c0c4cc;
}
.filter-check {
  display: inline-block;
  width: 16px;
  flex-shrink: 0;
  color: var(--el-color-primary);
  font-weight: bold;
}

/* ─── 动效 ──────────────────────────────────── */
.ft-pop-enter-active {
  transition: opacity 0.16s ease, transform 0.16s cubic-bezier(0.16, 1, 0.3, 1);
}
.ft-pop-leave-active {
  transition: opacity 0.1s ease, transform 0.1s ease;
}
.ft-pop-enter-from,
.ft-pop-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
.ft-fade-enter-active,
.ft-fade-leave-active {
  transition: opacity 0.2s ease;
}
.ft-fade-enter-from,
.ft-fade-leave-to {
  opacity: 0;
}
</style>
