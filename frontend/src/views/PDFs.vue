<template>
  <div>
    <!-- Filter bar -->
    <el-card shadow="never" class="filter-card">
      <div class="toolbar">
        <div class="toolbar-filters">
          <el-select v-model="filter.statuses" multiple clearable collapse-tags collapse-tags-tooltip placeholder="关联状态" style="width: 170px" @change="page = 1; load()">
            <el-option label="未关联" value="unmatched" />
            <el-option label="已关联" value="matched" />
          </el-select>
        </div>
        <div class="toolbar-actions">
          <el-button :disabled="selected.length !== 1" @click="previewPdf(selected[0])">预览</el-button>
          <el-button :disabled="!hasSelection" @click="batchDownload">
            下载<template v-if="selected.length">（{{ selected.length }}）</template>
          </el-button>
          <el-button type="success" plain :disabled="!isAdmin" :loading="matching" @click="autoMatch">
            自动匹配<template v-if="selected.length">（{{ selected.length }}）</template>
          </el-button>
          <el-button :disabled="!isAdmin || selected.length === 0" @click="openLinkDialog">关联论文</el-button>
          <el-button type="danger" plain :disabled="!isAdmin || !hasSelection" @click="batchDelete">删除选中</el-button>
          <span class="tb-divider"></span>
          <el-button type="primary" :disabled="!isAdmin" @click="uploadVisible = !uploadVisible">
            <el-icon style="margin-right: 4px"><Upload /></el-icon>上传 PDF
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- Upload area -->
    <transition name="upload-slide">
    <el-card shadow="never" class="upload-card" v-if="uploadVisible">
      <div
        class="drop-zone"
        :class="{ 'is-dragover': dragover }"
        @dragover.prevent="dragover = true"
        @dragleave="dragover = false"
        @drop.prevent="onDrop"
      >
        <el-icon class="drop-icon"><UploadFilled /></el-icon>
        <p>拖拽 PDF 文件到此处，或 <el-button type="primary" text @click="$refs.fileInput.click()">点击选择</el-button></p>
      </div>
      <input ref="fileInput" type="file" accept=".pdf" multiple style="display: none" @change="onFileSelect" />
      <div v-if="uploadResults.length" class="upload-results">
        <div class="upload-results-header">
          <span>上传结果（{{ uploadResults.length }} 个文件）</span>
          <el-button size="small" @click="uploadResults = []">清除</el-button>
        </div>
        <el-table :data="uploadResults" size="small" max-height="280">
          <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'ok'" type="success" size="small">成功</el-tag>
              <el-tag v-else-if="row.status === 'duplicate'" type="info" size="small">已存在</el-tag>
              <el-tag v-else type="danger" size="small">{{ row.status === 'error' ? '失败' : '跳过' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="paper_title" label="匹配论文" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.paper_title" class="clickable-link" @click="jumpToPaper(row.paper_id)">{{ row.paper_title }}</span>
              <span v-else class="muted">未匹配</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div style="margin-top: 12px; text-align: right">
        <el-button @click="uploadVisible = false; uploadResults = []">收起</el-button>
      </div>
    </el-card>
    </transition>

    <!-- Upload progress dialog -->
    <el-dialog
      v-model="uploading"
      title="上传 PDF"
      width="440px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div class="upload-progress-body">
        <el-progress :percentage="uploadPercent" :stroke-width="14" :indeterminate="uploadPercent === 0" />
        <div class="upload-progress-count">
          <span class="big">{{ doneCount }}</span><span class="muted"> / {{ totalCount }} 个文件</span>
          <span class="upload-progress-tally">
            <el-tag type="success" size="small" effect="plain">成功 {{ okCount }}</el-tag>
            <el-tag type="info" size="small" effect="plain">已存在 {{ dupCount }}</el-tag>
            <el-tag v-if="failCount" type="danger" size="small" effect="plain">失败 {{ failCount }}</el-tag>
          </span>
        </div>
        <p class="muted upload-progress-cur">{{ currentLabel }}</p>
      </div>
    </el-dialog>

    <!-- PDF List -->
    <el-card shadow="never">
      <el-table
        :data="rows"
        v-loading="loading"
        @selection-change="onSelectionChange"
        stripe
      >
        <el-table-column type="selection" width="40" />
        <el-table-column label="#" width="50" align="center">
          <template #default="{ $index }">{{ (page - 1) * pageSize + $index + 1 }}</template>
        </el-table-column>
        <el-table-column prop="filename" label="文件名" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="clickable-link" @click="previewPdf(row)">{{ row.filename }}</span>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="90">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column label="关联论文" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.paper_id" class="clickable-link" @click="jumpToPaper(row.paper_id)">{{ row.paper_title }}</span>
            <span v-else class="muted">— 未关联 —</span>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>

    <!-- Link dialog -->
    <el-dialog v-model="linkVisible" title="关联 PDF 到论文" width="500px">
      <el-form label-width="80px">
        <el-form-item label="已选文件">{{ selected.length }} 个 PDF</el-form-item>
        <el-form-item label="关联论文">
          <el-select v-model="linkPaperId" filterable clearable placeholder="搜索论文标题" style="width: 100%">
            <el-option v-for="p in paperOptions" :key="p.id" :label="p.title" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="linkVisible = false">取消</el-button>
        <el-button type="primary" :loading="linkSaving" @click="confirmLink">确认关联</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, UploadFilled } from '@element-plus/icons-vue'
import api, { isAdmin } from '../api'
import { formatSize, formatTime } from '../utils/format'

const router = useRouter()

const rows = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(30)

const filter = reactive({ statuses: [] })
const selected = ref([])
const uploadVisible = ref(false)
const dragover = ref(false)
const uploadResults = ref([])
// Link dialog
const linkVisible = ref(false)
const linkSaving = ref(false)
const linkPaperId = ref(null)
const paperOptions = ref([])
const matching = ref(false)

// ─── Upload progress ────────────────────────────────────────────────────────
const uploading = ref(false)
const doneCount = ref(0)
const totalCount = ref(0)
const okCount = ref(0)
const dupCount = ref(0)
const failCount = ref(0)
const currentLabel = ref('')
const batchProgress = ref(0)          // 当前批次字节进度 0..1
const UPLOAD_BATCH = 8                // 每批上传文件数（平衡进度反馈与请求数）
const uploadPercent = computed(() => {
  if (!totalCount.value) return 0
  const remaining = totalCount.value - doneCount.value
  const cur = batchProgress.value * Math.min(UPLOAD_BATCH, remaining)
  return Math.round(((doneCount.value + cur) / totalCount.value) * 100)
})
const okTally = computed(() => uploadResults.value.filter(f => f.status === 'ok').length)

const hasSelection = computed(() => selected.value.length > 0)

// ─── Load ──────────────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filter.statuses.length) params.statuses = filter.statuses
    const { data } = await api.get('/pdfs', { params })
    rows.value = data.rows
    total.value = data.total
  } finally {
    loading.value = false
  }
}

// ─── Upload ────────────────────────────────────────────────────────────────
function onFileSelect(e) {
  handleFiles(Array.from(e.target.files))
  e.target.value = ''
}

function onDrop(e) {
  dragover.value = false
  const files = Array.from(e.dataTransfer.files).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
  if (!files.length) return ElMessage.warning('请拖拽 PDF 文件')
  handleFiles(files)
}

function handleFiles(files) {
  if (!files.length) return
  uploading.value = true
  totalCount.value = files.length
  doneCount.value = 0
  okCount.value = 0
  dupCount.value = 0
  failCount.value = 0
  batchProgress.value = 0
  currentLabel.value = '准备上传…'
  uploadResults.value = []
  ;(async () => {
    for (let i = 0; i < files.length; i += UPLOAD_BATCH) {
      const batch = files.slice(i, i + UPLOAD_BATCH)
      const end = Math.min(i + UPLOAD_BATCH, files.length)
      currentLabel.value = `正在上传第 ${i + 1}–${end} 个（共 ${files.length}）`
      batchProgress.value = 0
      const formData = new FormData()
      batch.forEach((f) => formData.append('files', f))
      try {
        const { data } = await api.post('/pdfs', formData, {
          onUploadProgress: (e) => {
            if (e.lengthComputable) batchProgress.value = e.loaded / e.total
          },
        })
        uploadResults.value.push(...data.files)
        okCount.value += data.files.filter((f) => f.status === 'ok').length
        dupCount.value += data.files.filter((f) => f.status === 'duplicate').length
        failCount.value += data.files.filter((f) => !['ok', 'duplicate'].includes(f.status)).length
      } catch {
        batch.forEach((f) => {
          uploadResults.value.push({ filename: f.name, status: 'error' })
          failCount.value += 1
        })
      }
      doneCount.value = end
    }
    uploading.value = false
    currentLabel.value = ''
    uploadVisible.value = true   // 展开结果区
    load()
    ElMessage.success(`上传完成，共 ${files.length} 个文件（成功 ${okCount.value}，已存在 ${dupCount.value}${failCount.value ? '，失败 ' + failCount.value : ''}）`)
  })()
}

// ─── Batch operations ──────────────────────────────────────────────────────
function onSelectionChange(val) {
  selected.value = val
}

async function batchDelete() {
  await ElMessageBox.confirm(`确认删除选中的 ${selected.value.length} 个 PDF？`, '删除', { type: 'warning' })
  let ok = 0
  for (const row of selected.value) {
    try { await api.delete(`/pdfs/${row.id}`); ok++ } catch {}
  }
  ElMessage.success(`已删除 ${ok} 个文件`)
  selected.value = []
  load()
}

// ─── Preview ───────────────────────────────────────────────────────────────
async function previewPdf(row) {
  if (!row) return
  try {
    const res = await api.get(`/pdfs/${row.id}/file`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    window.open(url, '_blank')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch {
    ElMessage.error('预览失败')
  }
}

async function batchDownload() {
  if (!selected.value.length) return
  try {
    const ids = selected.value.map((r) => r.id).join(',')
    const res = await api.get(`/pdfs/batch-download?ids=${ids}`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'pdfs.zip'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch {
    ElMessage.error('下载失败')
  }
}

// ─── Link ──────────────────────────────────────────────────────────────────
async function autoMatch() {
  matching.value = true
  try {
    // 选中则只匹配选中（未关联的），否则匹配全部未关联
    const body = selected.value.length ? { ids: selected.value.map((r) => r.id) } : {}
    const { data } = await api.post('/pdfs/auto-match', body)
    const head = data.matched ? `已匹配 ${data.matched} 个 PDF` : '没有匹配到新的论文'
    ElMessage.success(
      data.unmatched_count ? `${head}，${data.unmatched_count} 个未匹配，可手动「关联论文」` : head
    )
    load()
  } finally {
    matching.value = false
  }
}

async function openLinkDialog() {
  linkPaperId.value = null
  linkVisible.value = true
  const { data } = await api.get('/papers', { params: { page: 1, page_size: 100 } })
  paperOptions.value = data
}

async function confirmLink() {
  if (!linkPaperId.value) return ElMessage.warning('请选择论文')
  linkSaving.value = true
  try {
    const ids = selected.value.map(r => r.id)
    const { data } = await api.put('/pdfs/batch-link', { attachment_ids: ids, paper_id: linkPaperId.value })
    ElMessage.success(`已关联 ${data.linked} 个 PDF`)
    linkVisible.value = false
    load()
  } finally {
    linkSaving.value = false
  }
}

// ─── Navigation ────────────────────────────────────────────────────────────
function jumpToPaper(paperId) {
  router.push('/papers')
  setTimeout(() => {
    window.dispatchEvent(new CustomEvent('drawer:open', { detail: { type: 'papers', id: paperId } }))
  }, 50)
}

// ─── Utils ─────────────────────────────────────────────────────────────────

onMounted(load)
</script>

<style scoped>
.upload-card {
  margin-bottom: 14px;
}
.upload-slide-enter-active {
  transition: opacity 0.25s ease, transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.upload-slide-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.upload-slide-enter-from,
.upload-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
.upload-results {
  margin-top: 16px;
  border-top: 1px solid #f0f1f5;
  padding-top: 12px;
}
.upload-results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 14px;
  color: #1f2937;
}
.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.upload-progress-body { padding: 4px 4px 0; }
.upload-progress-count {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
}
.upload-progress-count .big { font-size: 22px; font-weight: 700; color: var(--el-color-primary); }
.upload-progress-tally { margin-left: auto; display: inline-flex; gap: 6px; }
.upload-progress-cur { margin: 10px 0 0; font-size: 12.5px; }
</style>
