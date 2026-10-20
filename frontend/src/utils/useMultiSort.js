// 多列排序 composable：支持按多字段叠加排序（先按字段1，再按字段2……），
// 排序状态持久化到 localStorage 并按账号隔离，提供"恢复默认"重置。
import { ref, computed, watch } from 'vue'
import { currentUser } from '../api'
import { fieldValue, compareValues } from './fieldColumns'

export function useMultiSort(viewKey, listFields, baseRows) {
  const sortState = ref([]) // [{ prop, order: 'ascending' | 'descending' }]

  const storageKey = () => `im_sort_${viewKey}_${currentUser.username || 'default'}`

  function load() {
    try {
      const saved = localStorage.getItem(storageKey())
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed)) sortState.value = parsed
      }
    } catch { /* ignore */ }
  }

  function save() {
    localStorage.setItem(storageKey(), JSON.stringify(sortState.value))
  }

  watch(sortState, save, { deep: true })
  load()

  function toggle(prop) {
    const existing = sortState.value.find((s) => s.prop === prop)
    if (!existing) {
      sortState.value.push({ prop, order: 'ascending' })
    } else if (existing.order === 'ascending') {
      existing.order = 'descending'
    } else {
      sortState.value = sortState.value.filter((s) => s.prop !== prop)
    }
  }

  function priority(prop) {
    const i = sortState.value.findIndex((s) => s.prop === prop)
    return i >= 0 ? i + 1 : 0
  }

  function orderOf(prop) {
    return sortState.value.find((s) => s.prop === prop)?.order || null
  }

  function restoreDefault() {
    sortState.value = []
  }

  const sortedRows = computed(() => {
    if (!sortState.value.length) return baseRows.value
    const arr = [...baseRows.value]
    arr.sort((a, b) => {
      for (const { prop, order } of sortState.value) {
        const f = listFields.value.find((x) => x.key === prop)
        if (!f) continue
        let cmp = compareValues(fieldValue(a, f), fieldValue(b, f))
        if (cmp !== 0) return order === 'descending' ? -cmp : cmp
      }
      return 0
    })
    return arr
  })

  return { toggle, priority, orderOf, restoreDefault, sortedRows, sortState }
}
