<template>
  <div class="attachment-area">
    <h4>附件（{{ list.length }}）
      <span style="float: right">
        <el-button size="small" :disabled="!selected.length" @click="downloadSelected">
          下载选中<template v-if="selected.length">（{{ selected.length }}）</template>
        </el-button>
        <el-button v-if="isAdmin" size="small" type="primary" plain @click="uploadVisible = !uploadVisible">+ 上传</el-button>
      </span>
    </h4>

    <div v-if="uploadVisible && isAdmin" class="upload-box">
      <div
        class="drop-zone"
        :class="{ 'is-dragover': dragover }"
        @dragover.prevent="dragover = true"
        @dragleave="dragover = false"
        @drop.prevent="onDrop"
      >
        <el-icon class="drop-icon"><UploadFilled /></el-icon>
        <p>拖拽文件到此处，或 <el-button type="primary" text @click="$refs.fileInput.click()">点击选择</el-button></p>
        <p class="muted" style="font-size: 12px; margin: 4px 0 0">支持 PDF / Word / Excel / 图片</p>
      </div>
      <input ref="fileInput" type="file" :accept="ACCEPT" multiple style="display: none" @change="onFileSelect" />
    </div>

    <el-table :data="list" v-loading="loading" size="small" stripe @selection-change="onSelectionChange">
      <el-table-column type="selection" width="40" />
      <el-table-column label="文件名" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="clickable-link" @click="preview(row)">{{ row.filename }}</span>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="80">
        <template #default="{ row }">{{ formatSize(row.size) }}</template>
      </el-table-column>
      <el-table-column label="上传时间" width="150">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" link @click="downloadOne(row)">下载</el-button>
          <el-button v-if="isAdmin" size="small" type="danger" link @click="removeOne(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import api, { downloadFile, downloadPost, isAdmin } from '../api'
import { formatSize, formatTime } from '../utils/format'

const props = defineProps({
  entity: { type: String, required: true },
  entityId: { type: Number, default: null },
})

const list = ref([])
const loading = ref(false)
const selected = ref([])
const uploadVisible = ref(false)
const dragover = ref(false)

const ALLOWED_EXTS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
const ACCEPT = ALLOWED_EXTS.join(',')

async function load() {
  if (!props.entityId) return
  loading.value = true
  try {
    const { data } = await api.get(`/attachments/${props.entity}/${props.entityId}`)
    list.value = data
  } finally {
    loading.value = false
  }
}

watch(() => props.entityId, load, { immediate: true })

function onSelectionChange(rows) {
  selected.value = rows
}

function onFileSelect(e) {
  handleFiles(Array.from(e.target.files))
  e.target.value = ''
}

function onDrop(e) {
  dragover.value = false
  const files = Array.from(e.dataTransfer.files).filter((f) =>
    ALLOWED_EXTS.some((ext) => f.name.toLowerCase().endsWith(ext))
  )
  if (!files.length) return ElMessage.warning('请拖拽支持的文件类型（PDF / Word / Excel / 图片）')
  handleFiles(files)
}

async function handleFiles(files) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  try {
    await api.post(`/attachments/${props.entity}/${props.entityId}`, fd)
    ElMessage.success(`上传 ${files.length} 个文件`)
    uploadVisible.value = false
    load()
  } catch {
    /* axios 拦截器已提示 */
  }
}

async function preview(row) {
  try {
    const res = await api.get(`/attachments/${row.id}/file`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    window.open(url, '_blank')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch {
    ElMessage.error('预览失败')
  }
}

async function downloadOne(row) {
  await downloadFile(`/attachments/${row.id}/file`, row.filename)
}

async function downloadSelected() {
  if (!selected.value.length) return
  if (selected.value.length === 1) {
    await downloadOne(selected.value[0])
    return
  }
  await downloadPost('/attachments/batch-download', 'attachments.zip', {
    attachment_ids: selected.value.map((r) => r.id),
  })
}

async function removeOne(row) {
  await ElMessageBox.confirm(`确认删除 ${row.filename}？`, '删除', { type: 'warning' })
  await api.delete(`/attachments/${row.id}`)
  ElMessage.success('已删除')
  load()
}
</script>

<style scoped>
.attachment-area {
  margin-top: 16px;
}
.upload-box {
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid #f0f1f5;
  border-radius: 6px;
  background: #fafbfc;
}
</style>
