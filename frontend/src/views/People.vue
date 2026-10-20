<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <!-- 筛选标签行：覆盖下方列表的全部列，点击即过滤 -->
      <FilterTags :fields="listFields" :rows="rows" :model="localFilter" />

      <div class="toolbar">
        <div class="toolbar-filters">
          <el-input
            v-model="filter.keyword"
            class="tb-search"
            placeholder="搜索姓名 / 英文名 / 学号"
            clearable
            :prefix-icon="Search"
            @keyup.enter="load"
          />
        </div>
        <div class="toolbar-actions">
          <span class="result-count">共 {{ displayRows.length }} 条</span>
          <el-button :disabled="selectedRows.length !== 1" @click="openDetail(selectedRows[0])">详情</el-button>
          <el-button :disabled="!isAdmin || selectedRows.length !== 1" @click="openForm(selectedRows[0])">编辑</el-button>
          <el-button type="danger" plain :disabled="!isAdmin || !selectedRows.length" @click="removeSelected">
            删除<template v-if="selectedRows.length">（{{ selectedRows.length }}）</template>
          </el-button>
          <el-button :disabled="!selectedRows.length" :loading="zipping" @click="batchDownloadAttachments">
            下载附件<template v-if="selectedRows.length">（{{ selectedRows.length }}）</template>
          </el-button>
          <span class="tb-divider"></span>
          <el-dropdown trigger="click" @command="onImportExport">
            <el-button>
              导入 / 导出<el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="template" :icon="Download">下载导入模板</el-dropdown-item>
                <el-dropdown-item command="import" :icon="Upload" :disabled="!isAdmin">批量导入…</el-dropdown-item>
                <el-dropdown-item command="export" :icon="DocumentCopy" divided>导出当前结果</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button type="primary" :disabled="!isAdmin" @click="openForm()">
            <el-icon style="margin-right: 4px"><Plus /></el-icon>新增人员
          </el-button>
          <el-button v-if="sort.sortState.value.length" plain size="small" @click="sort.restoreDefault()">恢复默认视图</el-button>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table
        :data="pagedRows"
        v-loading="loading"
        stripe
        style="cursor: pointer"
        @row-dblclick="openDetail"
        @selection-change="handleSelectionChange"
      >
        <template #empty>
          <div class="empty-state">
            <div class="empty-icon">👤</div>
            <p>暂无人员数据</p>
            <p class="muted">点击右上角「新增人员」添加第一条记录</p>
          </div>
        </template>
        <el-table-column type="selection" width="45" />
        <el-table-column type="index" width="50" align="center" label="#" :index="i => indexFrom + i + 1" />
        <el-table-column
          v-for="f in listFields"
          :key="f.key"
          :prop="f.key"
          :label="f.label"
          :min-width="calcColWidth(rows, f)"
        >
          <template #header>
            <div class="sort-header" @click.stop="sort.toggle(f.key)">
              {{ f.label }}
              <span v-if="sort.priority(f.key)" class="sort-badge">{{ sort.orderOf(f.key) === 'ascending' ? '↑' : '↓' }}{{ sort.priority(f.key) }}</span>
            </div>
          </template>
          <template #default="{ row }">
            <el-tag
              v-if="f.dtype === 'select' && fieldValue(row, f)"
              size="small"
              effect="plain"
              :type="tagTypeFor(f, fieldValue(row, f))"
            >{{ fieldValue(row, f) }}</el-tag>
            <template v-else>{{ fieldValue(row, f) ?? '-' }}</template>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pagination"
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        @size-change="resetPage"
      />
    </el-card>

    <el-dialog v-model="formVisible" :title="form.id ? '编辑人员' : '新增人员'" width="680px">
      <el-form :model="form" label-width="100px">
        <DynamicFormFields :fields="formFields" :model="form" :required-keys="['uid']" />
        <el-form-item label="姓名变体">
          <div style="width: 100%">
            <div v-for="(v, i) in form.name_variants" :key="i" style="display: flex; gap: 8px; margin-bottom: 6px">
              <el-input v-model="v.name_text" placeholder="论文中出现的其他英文写法" style="width: 300px" />
              <el-button type="danger" plain @click="form.name_variants.splice(i, 1)">移除</el-button>
            </div>
            <el-button size="small" @click="form.name_variants.push({ name_text: '', kind: '' })">+ 添加变体</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- People Drawer -->
    <el-drawer v-model="detailVisible" :title="detail?.name || detail?.uid" size="46%">
      <template v-if="detail">
        <div class="person-header">
          <div class="person-avatar" :style="{ background: avatarColor(detail.name) }">
            {{ initials(detail.name) }}
          </div>
          <div class="person-info">
            <h2>{{ detail.name }}</h2>
            <p class="muted">{{ detail.english_name || '-' }}</p>
          </div>
        </div>
        <el-descriptions :column="2" border size="small" style="margin: 16px 0">
          <el-descriptions-item
            v-for="f in formFields"
            :key="f.key"
            :label="f.label"
            :span="isWideField(f) ? 2 : 1"
          >
            <el-tag v-if="f.dtype === 'select' && fieldValue(detail, f)" size="small" effect="plain" :type="tagTypeFor(f, fieldValue(detail, f))">{{ fieldValue(detail, f) }}</el-tag>
            <span v-else class="detail-text">{{ fieldValue(detail, f) ?? '-' }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <!-- Name Variants -->
        <h4 style="margin-top: 16px">姓名变体</h4>
        <div v-if="detail.name_variants && detail.name_variants.length" style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px">
          <el-tag v-for="v in detail.name_variants" :key="v.id" size="small">{{ v.name_text }}</el-tag>
        </div>
        <span v-else class="muted">-</span>

        <!-- Awards -->
        <!-- Awards (read-only, managed in Awards module) -->
        <h4>奖励荣誉 ({{ detailAwards.length }})</h4>
        <el-table :data="detailAwards" size="small">
          <el-table-column prop="award_name" label="奖项名称" show-overflow-tooltip />
          <el-table-column prop="level" label="等级" width="80" />
          <el-table-column prop="rank" label="本人排名" width="80" />
          <el-table-column prop="award_date" label="获奖时间" width="100" />
          <el-table-column prop="issuer" label="颁奖单位" width="120" show-overflow-tooltip />
        </el-table>

        <!-- Projects -->
        <h4 style="margin-top: 16px">参与项目 ({{ detailProjects.length }})</h4>
        <el-table :data="detailProjects" size="small">
          <el-table-column prop="project_no" label="项目编号" width="110" />
          <el-table-column prop="name" label="名称" show-overflow-tooltip />
          <el-table-column prop="category" label="类别" width="80" />
          <el-table-column prop="role" label="角色" width="80" />
        </el-table>

        <AttachmentArea entity="people" :entity-id="detail.id" />
      </template>
    </el-drawer>

    <ImportDialog
      v-model:visible="importVisible"
      title="批量导入人员"
      upload-url="/import/people"
      template-url="/import/template/people"
      template-name="人员导入模板.xlsx"
      @done="load"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, DocumentCopy, Download, Plus, Search, Upload } from '@element-plus/icons-vue'
import api, { downloadFile, downloadPost, isAdmin } from '../api'
import ImportDialog from '../components/ImportDialog.vue'
import DynamicFormFields from '../components/DynamicFormFields.vue'
import AttachmentArea from '../components/AttachmentArea.vue'
import FilterTags from '../components/FilterTags.vue'
import {
  fieldValue, calcColWidth, makeSorter, tagTypeFor, toUpdateBody, packExtra, isWideField,
} from '../utils/fieldColumns'
import { useListPage } from '../utils/useListPage'

const rows = ref([])         // 原始数据（服务器过滤后）
const loading = ref(false)
const filter = reactive({ keyword: '' })  // 服务器端过滤字段（其余列走顶部筛选标签）
const localFilter = reactive({})          // 列筛选（key -> 已选值数组），由 FilterTags 维护

// 合并过滤：先按 keyword 过滤后的 rows，再用 localFilter 过滤（支持多选）
const displayRows = computed(() => {
  let result = rows.value
  for (const [key, val] of Object.entries(localFilter)) {
    if (!val || !val.length) continue
    result = result.filter((row) => {
      const f = allFields.value.find((f) => f.key === key)
      return f && val.includes(fieldValue(row, f))
    })
  }
  return result
})

// Auto-apply keyword filter on input change
watch(filter, () => load(), { deep: true })

const formVisible = ref(false)
const saving = ref(false)
const emptyForm = () => ({
  uid: '', name: '', english_name: '', degree_type: '', status: '',
  current_activity: '', phone: '', email: '',
  research_direction: '', name_variants: [], extra: {},
})
const form = reactive(emptyForm())

const detailVisible = ref(false)
const detail = ref(null)
const detailProjects = ref([])
const detailAwards = ref([])
const selectedRows = ref([])

const importVisible = ref(false)
// 字段定义驱动：表单字段=启用的全部字段；列表列=show_in_list的字段
const allFields = ref([])
const formFields = computed(() => allFields.value.filter((f) => f.enabled !== false))
const listFields = computed(() =>
  allFields.value.filter((f) => f.enabled !== false && f.show_in_list !== false)
)
// 客户端分页 + 多列排序（composable 统一管理）
const { sort, currentPage, pageSize, total, pagedRows, indexFrom, resetPage } = useListPage({
  viewKey: 'people',
  listFields,
  displayRows,
})

// ─── Avatar helpers ────────────────────────────────────────────
const AVATAR_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
]

function initials(name) {
  if (!name) return '?'
  return name.slice(0, 2)
}

function avatarColor(name) {
  if (!name) return AVATAR_COLORS[0]
  const idx = name.charCodeAt(0) % AVATAR_COLORS.length
  return AVATAR_COLORS[idx]
}

// ─── Data loading ──────────────────────────────────────────────
function clean(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== '' && v != null))
}

async function load() {
  loading.value = true
  resetPage()
  try {
    const { data } = await api.get('/people', { params: clean(filter) })
    rows.value = data
    selectedRows.value = []
  } finally {
    loading.value = false
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

const zipping = ref(false)
async function batchDownloadAttachments() {
  if (!selectedRows.value.length) return
  zipping.value = true
  try {
    await downloadPost('/attachments/download-by-records', 'people-attachments.zip', {
      entity: 'people',
      ids: selectedRows.value.map((r) => r.id),
    })
  } finally {
    zipping.value = false
  }
}

async function downloadTemplate() {
  await downloadFile('/import/template/people', '人员导入模板.xlsx')
}

function onImportExport(cmd) {
  if (cmd === 'template') downloadTemplate()
  else if (cmd === 'import') importVisible.value = true
  else if (cmd === 'export') exportCurrent()
}

async function exportCurrent() {
  await downloadPost('/export/custom', '人员导出.xlsx', {
    type: 'people',
    columns: listFields.value.map((f) => (f.key.startsWith('cf_') ? 'extra:' + f.key : f.key)),
    ids: displayRows.value.map((r) => r.id),
  })
}

function openForm(row) {
  Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, emptyForm(), row ? {
    ...row,
    ...(row.extra || {}),
    extra: { ...(row.extra || {}) },
    name_variants: (row.name_variants || []).map((v) => ({ ...v })),
  } : {})
  formVisible.value = true
}

async function save() {
  if (!form.uid?.trim()) return ElMessage.warning('学号/工号为必填唯一标识')
  saving.value = true
  try {
    const body = packExtra(form, allFields.value)
    // 将 name_variants 和 awards 一起放入请求体，后端会整体替换
    if (form.id) {
      await api.put(`/people/${form.id}`, toUpdateBody(body, 'uid'))
    } else {
      await api.post('/people', clean(body))
    }
    ElMessage.success('已保存')
    formVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function removeSelected() {
  const rows = selectedRows.value
  if (!rows.length) return
  if (rows.length === 1) {
    await ElMessageBox.confirm(`确认删除 ${rows[0].name || rows[0].uid}？`, '删除', { type: 'warning' })
    await api.delete(`/people/${rows[0].id}`)
  } else {
    await ElMessageBox.confirm(`确认删除选中的 ${rows.length} 名人员？`, '批量删除', { type: 'warning' })
    await api.post('/people/batch-delete', rows.map((r) => r.id))
  }
  ElMessage.success(`已删除 ${rows.length} 名人员`)
  load()
}

async function openDetail(row) {
  if (!row) return
  const [{ data }, projects, awards] = await Promise.all([
    api.get(`/people/${row.id}`),
    api.get(`/people/${row.id}/projects`),
    api.get(`/people/${row.id}/awards`),
  ])
  detail.value = data
  detailProjects.value = projects.data
  detailAwards.value = awards.data
  detailVisible.value = true
}

async function onDrawerOpen(e) {
  const { type, id, person_id } = e.detail
  if (type === 'people' && id) {
    await openDetail({ id })
  }
}

onMounted(() => {
  load()
  loadFields('people')
  window.addEventListener('drawer:open', onDrawerOpen)
  window.addEventListener('fields-changed', onFieldsChanged)
})

function loadFields(entity) {
  api.get('/fields', { params: { entity } }).then((r) => {
    allFields.value = r.data
  })
}

function onFieldsChanged(e) {
  if (e.detail?.entity === 'people') loadFields('people')
}

onUnmounted(() => {
  window.removeEventListener('drawer:open', onDrawerOpen)
  window.removeEventListener('fields-changed', onFieldsChanged)
})
</script>

<style scoped>
.person-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid #f0f1f5;
  margin-bottom: 12px;
}
.person-avatar {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
}
.person-info h2 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}
.person-info .muted {
  color: #999;
  font-size: 13px;
  margin: 0;
}
.detail-text {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

<style>
.el-dialog__body {
  max-height: 70vh;
  overflow-y: auto;
}
</style>
