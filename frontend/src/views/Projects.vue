<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <!-- 筛选标签行：覆盖下方列表的全部列，点击即过滤 -->
      <FilterTags :fields="filterFields" :rows="rows" :model="localFilter" />

      <div class="toolbar">
        <div class="toolbar-filters">
          <el-input
            v-model="filter.keyword"
            class="tb-search"
            placeholder="搜索项目名称 / 编号"
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
            <el-icon style="margin-right: 4px"><Plus /></el-icon>新增项目
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
        @selection-change="handleSelectionChange"
        @row-dblclick="openDetail"
        style="cursor: pointer"
      >
        <template #empty>
          <div class="empty-state">
            <div class="empty-icon">📁</div>
            <p>暂无项目数据</p>
            <p class="muted">点击右上角「新增项目」添加第一条记录</p>
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
            <el-tag
              v-else-if="f.dtype === 'boolean'"
              size="small"
              :type="fieldValue(row, f) ? 'danger' : 'info'"
              effect="plain"
            >{{ fieldValue(row, f) ? '关注' : '-' }}</el-tag>
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

    <el-dialog v-model="formVisible" :title="form.id ? '编辑项目' : '新增项目'" width="680px">
      <el-form :model="form" label-width="100px">
        <DynamicFormFields :fields="formFields" :model="form" :required-keys="['project_no']" />
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <ImportDialog
      v-model:visible="importVisible"
      title="批量导入项目"
      upload-url="/import/projects"
      template-url="/import/template/projects"
      template-name="项目导入模板.xlsx"
      @done="load"
    />

    <el-drawer v-model="detailVisible" :title="detail?.name || detail?.project_no" size="50%">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
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

        <h4>成员
          <el-button size="small" :disabled="!selectedMember" type="danger" link style="float: right" @click="removeMember(selectedMember)">移除选中</el-button>
        </h4>
        <el-table
          :data="detail.members"
          size="small"
          highlight-current-row
          @current-change="(row) => (selectedMember = row)"
        >
          <el-table-column label="成员">
            <template #default="{ row }">
              <span v-if="row.person_id" class="clickable-link" @click="openPersonDrawer(row.person_id)">{{ row.person_name }}</span>
              <span v-else>{{ row.person_name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="role" label="角色" width="100" />
          <el-table-column prop="note" label="备注" />
        </el-table>
        <div style="display: flex; gap: 8px; margin-top: 8px">
          <el-select v-model="newMember.person_id" placeholder="选择人员" filterable style="width: 220px">
            <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.uid})`" :value="p.id" />
          </el-select>
          <el-select v-model="newMember.role" placeholder="角色" style="width: 130px">
            <el-option value="负责人" />
            <el-option value="成员" />
          </el-select>
          <el-button type="primary" @click="addMember">添加成员</el-button>
        </div>

        <h4>资助论文（{{ detailPapers.length }}）</h4>
        <el-table :data="detailPapers" size="small">
          <el-table-column prop="title" label="标题" show-overflow-tooltip />
          <el-table-column prop="year" label="年份" width="70" />
          <el-table-column prop="funding_seq" label="标注" width="70">
            <template #default="{ row }">{{ row.funding_seq ?? '-' }}</template>
          </el-table-column>
        </el-table>

        <AttachmentArea entity="projects" :entity-id="detail.id" />
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, DocumentCopy, Download, Plus, Search, Upload } from '@element-plus/icons-vue'
import api, { downloadFile, downloadPost, isAdmin } from '../api'
import ImportDialog from '../components/ImportDialog.vue'
import AttachmentArea from '../components/AttachmentArea.vue'
import FilterTags from '../components/FilterTags.vue'
import DynamicFormFields from '../components/DynamicFormFields.vue'
import {
  fieldValue, calcColWidth, makeSorter, tagTypeFor, toUpdateBody, packExtra, isWideField,
} from '../utils/fieldColumns'
import { useListPage } from '../utils/useListPage'

const router = useRouter()

const rows = ref([])
const loading = ref(false)
const localFilter = reactive({})  // 本地过滤字段
const filter = reactive({ keyword: '' })

// 本地过滤：基于 rows 数据在前端过滤所有非服务器字段（支持多选）
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


// Auto-apply filter on input change (no need to click "查询")
watch(filter, () => load(), { deep: true })

const formVisible = ref(false)
const saving = ref(false)
const emptyForm = () => ({
  project_no: '', name: '', category: '', source: '',
  duration: '', status: '', budget_no: '',
  targets: '', targets_done: '',
  budget_total: null, budget_ours: null, budget_received: null,
  notes: '', extra: {},
})
const form = reactive(emptyForm())

const detailVisible = ref(false)
const detail = ref(null)
const detailPapers = ref([])
const people = ref([])
const newMember = reactive({ person_id: null, role: '成员' })
const importVisible = ref(false)
const allFields = ref([])
const formFields = computed(() => allFields.value.filter((f) => f.enabled !== false))
const listFields = computed(() =>
  allFields.value.filter((f) => f.enabled !== false && f.show_in_list !== false)
)
// 客户端分页 + 多列排序（composable 统一管理）
const { sort, currentPage, pageSize, total, pagedRows, indexFrom, resetPage } = useListPage({
  viewKey: 'projects',
  listFields,
  displayRows,
})
// 筛选标签覆盖列表的全部列
const filterFields = listFields
const selectedRows = ref([])
const selectedMember = ref(null)

function clean(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== '' && v != null))
}

async function load() {
  loading.value = true
  resetPage()
  try {
    const { data } = await api.get('/projects', { params: clean(filter) })
    rows.value = data
    selectedRows.value = []
  } finally {
    loading.value = false
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

function openForm(row) {
  Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, emptyForm(), row ? { ...row, ...(row.extra || {}), extra: { ...(row.extra || {}) } } : {})
  formVisible.value = true
}

async function save() {
  if (!form.project_no?.trim()) return ElMessage.warning('项目编号为必填唯一标识')
  saving.value = true
  try {
    const body = packExtra(form, allFields.value)
    if (form.id) {
      await api.put(`/projects/${form.id}`, toUpdateBody(clean(body), 'project_no'))
    } else {
      await api.post('/projects', clean(body))
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
    await ElMessageBox.confirm(`确认删除项目 ${rows[0].name || rows[0].project_no}？`, '删除', { type: 'warning' })
    await api.delete(`/projects/${rows[0].id}`)
  } else {
    await ElMessageBox.confirm(`确认删除选中的 ${rows.length} 个项目？`, '批量删除', { type: 'warning' })
    await api.post('/projects/batch-delete', rows.map((r) => r.id))
  }
  ElMessage.success(`已删除 ${rows.length} 个项目`)
  load()
}

const zipping = ref(false)
async function batchDownloadAttachments() {
  if (!selectedRows.value.length) return
  zipping.value = true
  try {
    await downloadPost('/attachments/download-by-records', 'projects-attachments.zip', {
      entity: 'projects',
      ids: selectedRows.value.map((r) => r.id),
    })
  } finally {
    zipping.value = false
  }
}

async function openDetail(row) {
  if (!row) return
  const [{ data }, papers, plist] = await Promise.all([
    api.get(`/projects/${row.id}`),
    api.get(`/projects/${row.id}/papers`),
    api.get('/people'),
  ])
  detail.value = data
  detailPapers.value = papers.data
  people.value = plist.data
  detailVisible.value = true
}

async function addMember() {
  if (!newMember.person_id) return ElMessage.warning('请选择人员')
  await api.post(`/projects/${detail.value.id}/members`, { ...newMember })
  ElMessage.success('已添加')
  const { data } = await api.get(`/projects/${detail.value.id}`)
  detail.value = data
  selectedMember.value = null
}

async function removeMember(row) {
  if (!row) return
  await api.delete(`/projects/${detail.value.id}/members/${row.id}`)
  const { data } = await api.get(`/projects/${detail.value.id}`)
  detail.value = data
  selectedMember.value = null
}

function openPersonDrawer(personId) {
  if (!personId) return
  router.push('/people')
  setTimeout(() => {
    window.dispatchEvent(new CustomEvent('drawer:open', { detail: { type: 'people', id: personId } }))
  }, 50)
}

async function downloadTemplate() {
  await downloadFile('/import/template/projects', '项目导入模板.xlsx')
}

function onImportExport(cmd) {
  if (cmd === 'template') downloadTemplate()
  else if (cmd === 'import') importVisible.value = true
  else if (cmd === 'export') exportCurrent()
}

async function exportCurrent() {
  await downloadPost('/export/custom', '项目导出.xlsx', {
    type: 'projects',
    columns: listFields.value.map((f) => (f.key.startsWith('cf_') ? 'extra:' + f.key : f.key)),
    ids: displayRows.value.map((r) => r.id),
  })
}

onMounted(() => {
  load()
  loadFields('projects')
  window.addEventListener('drawer:open', onDrawerOpen)
  window.addEventListener('fields-changed', onFieldsChanged)
})

function loadFields(entity) {
  api.get('/fields', { params: { entity } }).then((r) => {
    allFields.value = r.data
  })
}

function onFieldsChanged(e) {
  if (e.detail?.entity === 'projects') loadFields('projects')
}

onUnmounted(() => {
  window.removeEventListener('drawer:open', onDrawerOpen)
  window.removeEventListener('fields-changed', onFieldsChanged)
})

async function onDrawerOpen(e) {
  const { type, id } = e.detail
  if (type === 'projects') {
    await openDetail({ id })
  }
}
</script>

<style scoped>
.detail-text {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
