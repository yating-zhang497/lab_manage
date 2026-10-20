// 客户端分页 + 多列排序 composable：5 个列表页（People/Papers/Projects/IP/Awards）共用。
//
// 封装：currentPage / pageSize / total / pagedRows / indexFrom / sort / resetPage
// - total = sort.sortedRows.length（基于 displayRows 排序后的总数）
// - pagedRows = sort.sortedRows 切片（当前页）
// - indexFrom = 当前页起始序号（配合 el-table type="index" 跨页连续编号）
// - watch(total)：筛选/排序导致总数变化时，把 currentPage 收束到合理范围
// - resetPage()：load 函数开头调用，确保切换筛选条件后回到第 1 页
import { computed, ref, watch } from 'vue'
import { useMultiSort } from './useMultiSort'

export function useListPage({ viewKey, listFields, displayRows }) {
  const currentPage = ref(1)
  const pageSize = ref(20)

  const sort = useMultiSort(viewKey, listFields, displayRows)

  const total = computed(() => sort.sortedRows.value.length)
  const pagedRows = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return sort.sortedRows.value.slice(start, start + pageSize.value)
  })
  const indexFrom = computed(() => (currentPage.value - 1) * pageSize.value)

  watch(total, () => {
    const maxPage = Math.max(1, Math.ceil(total.value / pageSize.value))
    if (currentPage.value > maxPage) currentPage.value = maxPage
  })

  function resetPage() {
    currentPage.value = 1
  }

  return { sort, currentPage, pageSize, total, pagedRows, indexFrom, resetPage }
}
