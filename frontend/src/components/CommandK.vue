<template>
  <teleport to="body">
    <transition name="cmdk-fade">
      <div v-if="open" class="cmdk-overlay" @click.self="close">
        <div class="cmdk-panel" @keydown="onKeydown">
          <!-- Search input -->
          <div class="cmdk-input-row">
            <el-icon class="cmdk-search-icon"><Search /></el-icon>
            <input
              ref="inputRef"
              v-model="query"
              class="cmdk-input"
              placeholder="搜索人员 / 项目 / 论文 / 知识产权..."
              autocomplete="off"
              @keydown.stop
            />
            <kbd class="cmdk-esc-hint">ESC</kbd>
          </div>

          <!-- Results -->
          <div v-if="query.length > 0" class="cmdk-results">
            <div v-if="loading" class="cmdk-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
            </div>
            <template v-else>
              <template v-if="hasResults">
                <div v-for="(items, type) in groups" :key="type">
                  <div v-if="items.length" class="cmdk-group">
                    <div class="cmdk-group-label">{{ GROUP_LABELS[type] }}</div>
                    <div
                      v-for="(item, idx) in items"
                      :key="item.id"
                      class="cmdk-item"
                      :class="{ 'is-selected': isSelected(type, idx) }"
                      @click="select(type, item)"
                      @mouseenter="setCursor(type, idx)"
                    >
                      <el-icon class="cmdk-item-icon">{{ GROUP_ICONS[type] }}</el-icon>
                      <div class="cmdk-item-body">
                        <div class="cmdk-item-title">{{ getTitle(type, item) }}</div>
                        <div class="cmdk-item-sub">{{ getSub(type, item) }}</div>
                      </div>
                      <el-icon v-if="isSelected(type, idx)" class="cmdk-enter-hint"><Right /></el-icon>
                    </div>
                  </div>
                </div>
              </template>
              <div v-else class="cmdk-empty">无结果</div>
            </template>
          </div>

          <!-- Footer hint -->
          <div class="cmdk-footer">
            <span><kbd>↑↓</kbd> 导航</span>
            <span><kbd>↵</kbd> 打开</span>
            <span><kbd>ESC</kbd> 关闭</span>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Right, Search, Loading } from '@element-plus/icons-vue'
import api from '../api'

const GROUP_LABELS = { people: '人员', projects: '项目', papers: '论文', ip: '知识产权' }
const GROUP_ICONS = { people: '👤', projects: '📁', papers: '📄', ip: '🏅' }

const open = ref(false)
const query = ref('')
const loading = ref(false)
const results = ref({ people: [], projects: [], papers: [], ip: [] })

// cursor: { type, index }
const cursor = ref({ type: null, index: 0 })

const inputRef = ref(null)

const groups = computed(() => results.value)
const hasResults = computed(() => Object.values(results.value).some((g) => g.length > 0))

function isSelected(type, idx) {
  return cursor.value.type === type && cursor.value.index === idx
}

function getTitle(type, item) {
  if (type === 'people') return item.name || item.uid
  if (type === 'projects') return item.name || item.project_no
  if (type === 'papers') return item.title
  if (type === 'ip') return item.title
  return ''
}

function getSub(type, item) {
  if (type === 'people') return `${item.degree_type || ''} · ${item.status || ''}`.replace(/^ · | · $/g, '')
  if (type === 'projects') return item.project_no
  if (type === 'papers') return `${item.venue || ''} ${item.year ? '· ' + item.year : ''}`
  if (type === 'ip') return { patent: '专利', software_copyright: '软著', other: '其他' }[item.ip_type] || ''
  return ''
}

// ─── Public API ───────────────────────────────────────────────
function openPanel() {
  open.value = true
  query.value = ''
  results.value = { people: [], projects: [], papers: [], ip: [] }
  nextTick(() => inputRef.value?.focus())
}

function close() {
  open.value = false
}

// ─── Keyboard & Search ────────────────────────────────────────
let debounceTimer = null

watch(query, (val) => {
  clearTimeout(debounceTimer)
  if (!val.trim()) {
    results.value = { people: [], projects: [], papers: [], ip: [] }
    loading.value = false
    return
  }
  loading.value = true
  debounceTimer = setTimeout(() => fetchResults(val), 300)
})

async function fetchResults(q) {
  try {
    const { data } = await api.get('/search', { params: { q, limit: 5 } })
    results.value = data
    // reset cursor to first group with results
    const firstType = ['people', 'projects', 'papers', 'ip'].find((t) => data[t]?.length)
    cursor.value = { type: firstType || null, index: 0 }
  } catch {
    results.value = { people: [], projects: [], papers: [], ip: [] }
  } finally {
    loading.value = false
  }
}

function onKeydown(e) {
  if (e.key === 'Escape') { close(); return }
  if (e.key === 'ArrowDown') { moveCursor(1); return }
  if (e.key === 'ArrowUp') { moveCursor(-1); return }
  if (e.key === 'Enter') { confirmCursor(); return }
}

function moveCursor(dir) {
  const types = ['people', 'projects', 'papers', 'ip']
  const flat = types.flatMap((t) => results.value[t].map((item) => ({ type: t, item })))
  if (!flat.length) return

  const currentIdx = flat.findIndex(
    (f) => f.type === cursor.value.type && f.item === results.value[cursor.value.type][cursor.value.index]
  )
  const nextIdx = Math.max(0, Math.min(flat.length - 1, currentIdx + dir))
  const next = flat[nextIdx]
  cursor.value = { type: next.type, index: results.value[next.type].indexOf(next.item) }
}

function setCursor(type, idx) {
  cursor.value = { type, index: idx }
}

function confirmCursor() {
  const { type, index } = cursor.value
  if (!type) return
  const item = results.value[type][index]
  if (item) select(type, item)
}

const emit = defineEmits(['select'])

function select(type, item) {
  emit('select', { type, id: item.id })
  close()
}

// ─── Global Ctrl+K listener ───────────────────────────────────
function onGlobalKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    open.value ? close() : openPanel()
  }
}

onMounted(() => document.addEventListener('keydown', onGlobalKeydown))
onUnmounted(() => document.removeEventListener('keydown', onGlobalKeydown))

defineExpose({ openPanel })
</script>

<style scoped>
.cmdk-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 22, 35, 0.6);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
}

.cmdk-panel {
  width: 640px;
  max-width: 95vw;
  background: #1b2334;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 24px 60px rgba(2, 8, 23, 0.55);
  overflow: hidden;
  font-family: var(--el-font-family);
}

.cmdk-input-row {
  display: flex;
  align-items: center;
  padding: 14px 18px;
  gap: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.cmdk-search-icon {
  color: #6b7a99;
  font-size: 18px;
  flex-shrink: 0;
}

.cmdk-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-size: 17px;
  color: #e4e8f0;
  caret-color: #3b82f6;
}

.cmdk-input::placeholder {
  color: #5a6480;
}

.cmdk-esc-hint {
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 5px;
  padding: 2px 7px;
  font-size: 11px;
  color: #6b7a99;
  font-family: inherit;
  flex-shrink: 0;
}

.cmdk-results {
  max-height: 400px;
  overflow-y: auto;
  padding: 6px 0;
}

.cmdk-loading {
  padding: 24px;
  text-align: center;
  color: #6b7a99;
  font-size: 14px;
}

.cmdk-empty {
  padding: 24px;
  text-align: center;
  color: #5a6480;
  font-size: 14px;
}

.cmdk-group {
  padding: 0 8px;
}

.cmdk-group-label {
  padding: 10px 10px 4px;
  font-size: 11px;
  color: #5a6480;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.cmdk-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
}

.cmdk-item:hover,
.cmdk-item.is-selected {
  background: rgba(59, 130, 246, 0.16);
}

.cmdk-item-icon {
  font-size: 18px;
  flex-shrink: 0;
  width: 24px;
  text-align: center;
}

.cmdk-item-body {
  flex: 1;
  min-width: 0;
}

.cmdk-item-title {
  font-size: 14px;
  color: #e4e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cmdk-item-sub {
  font-size: 12px;
  color: #6b7a99;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cmdk-enter-hint {
  color: #3b82f6;
  font-size: 14px;
  flex-shrink: 0;
}

.cmdk-footer {
  display: flex;
  gap: 20px;
  padding: 10px 18px;
  border-top: 1px solid rgba(255,255,255,0.08);
  font-size: 12px;
  color: #5a6480;
}

.cmdk-footer kbd {
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 4px;
  padding: 1px 5px;
  font-family: inherit;
  margin-right: 4px;
}

/* Transition */
.cmdk-fade-enter-active,
.cmdk-fade-leave-active {
  transition: opacity 0.15s ease;
}
.cmdk-fade-enter-active .cmdk-panel,
.cmdk-fade-leave-active .cmdk-panel {
  transition: transform 0.15s ease, opacity 0.15s ease;
}
.cmdk-fade-enter-from,
.cmdk-fade-leave-to {
  opacity: 0;
}
.cmdk-fade-enter-from .cmdk-panel,
.cmdk-fade-leave-to .cmdk-panel {
  transform: scale(0.96) translateY(-8px);
  opacity: 0;
}
</style>
