<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <div class="toolbar">
        <div class="toolbar-filters">
          <el-select v-model="filterEntity" clearable placeholder="全部模块" style="width: 140px" @change="load">
            <el-option label="人员" value="people" />
            <el-option label="项目" value="projects" />
            <el-option label="论文" value="papers" />
            <el-option label="知识产权" value="ip" />
          </el-select>
        </div>
        <div class="toolbar-actions">
          <el-button type="primary" @click="triggerExport">
            <el-icon style="margin-right: 4px"><Download /></el-icon>手动导出
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column label="模块" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ entityLabel(row.entity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="filename" label="文件名" min-width="260" />
        <el-table-column prop="size_bytes" label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.size_bytes) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="生成时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="来源" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_auto" type="success" size="small">自动</el-tag>
            <el-tag v-else type="info" size="small">手动</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by" label="操作人" width="120" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="download(row)">下载</el-button>
            <el-button type="danger" link @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 手动导出对话框 -->
    <el-dialog v-model="exportVisible" title="手动导出存档" width="400px">
      <el-form label-width="100px">
        <el-form-item label="选择模块">
          <el-select v-model="exportEntity" placeholder="请选择模块">
            <el-option label="人员" value="people" />
            <el-option label="项目" value="projects" />
            <el-option label="论文" value="papers" />
            <el-option label="知识产权" value="ip" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exportVisible = false">取消</el-button>
        <el-button type="primary" :loading="exporting" @click="doExport">确认导出</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import api from '../api'
import { formatSize } from '../utils/format'

const rows = ref([])
const loading = ref(false)
const filterEntity = ref('')
const exportVisible = ref(false)
const exportEntity = ref('')
const exporting = ref(false)

const ENTITY_LABELS = { people: '人员', projects: '项目', papers: '论文', ip: '知识产权' }

function entityLabel(e) { return ENTITY_LABELS[e] || e }

function formatTime(ts) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
}

async function load() {
  loading.value = true
  try {
    const params = filterEntity.value ? { entity: filterEntity.value } : {}
    const res = await api.get('/archives', { params })
    rows.value = res.data
  } finally {
    loading.value = false
  }
}

function triggerExport() {
  exportEntity.value = ''
  exportVisible.value = true
}

async function doExport() {
  if (!exportEntity.value) {
    ElMessage.warning('请先选择模块')
    return
  }
  exporting.value = true
  try {
    const res = await api.post(`/archives/${exportEntity.value}/export`)
    ElMessage.success('导出成功')
    exportVisible.value = false
    load()
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

async function download(row) {
  try {
    const res = await api.get(`/archives/${row.id}`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = row.filename
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('下载失败')
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除存档「${row.filename}」？`, '删除确认', { type: 'warning' })
  await api.delete(`/archives/${row.id}`)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>
