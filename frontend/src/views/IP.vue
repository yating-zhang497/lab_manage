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
            placeholder="搜索产权名称 / 登记号"
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
          <el-button plain :disabled="!isAdmin" @click="rematchInventors">重新匹配发明人</el-button>
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
            <el-icon style="margin-right: 4px"><Plus /></el-icon>新增
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
        @row-dblclick="openDetail"
        style="cursor: pointer"
        @selection-change="handleSelectionChange"
      >
        <template #empty>
          <div class="empty-state">
            <div class="empty-icon">🏅</div>
            <p>暂无知识产权数据</p>
            <p class="muted">点击右上角「新增」添加第一条记录</p>
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
              <template v-if="f.key === 'ip_type'">
                <el-tag size="small" :type="{ patent: 'primary', software_copyright: 'success' }[row.ip_type] || 'info'" effect="plain">
                  {{ { patent: '专利', software_copyright: '软著', other: '其他' }[row.ip_type] || row.ip_type }}
                </el-tag>
              </template>
              <el-tag
                v-else-if="f.dtype === 'select' && fieldValue(row, f)"
                size="small"
                effect="plain"
                :type="tagTypeFor(f, fieldValue(row, f))"
              >{{ fieldValue(row, f) }}</el-tag>
              <template v-else>{{ fieldValue(row, f) ?? '-' }}</template>
            </template>
          </el-table-column>
          <el-table-column label="发明人" min-width="220">
            <template #default="{ row }">
              <template v-if="row.inventors?.length">
                <el-tag
                  v-for="v in row.inventors"
                  :key="v.id"
                  size="small"
                  :type="v.person_id ? 'success' : 'info'"
                  effect="plain"
                  style="margin-right: 4px; margin-bottom: 2px"
                >{{ v.person_name || v.inventor_name }}</el-tag>
              </template>
              <span v-else class="muted">-</span>
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

    <el-dialog v-model="formVisible" :title="form.id ? '编辑知识产权' : '新增知识产权'" width="640px">
      <el-form :model="form" label-width="100px">
        <DynamicFormFields :fields="formFields" :model="form" :required-keys="['title']" />
        <el-form-item label="发明人">
          <div style="width: 100%">
            <div v-for="(v, i) in form.inventors" :key="i" style="display: flex; gap: 8px; margin-bottom: 6px; align-items: center">
              <span class="muted" style="width: 56px">发明人{{ i + 1 }}</span>
              <el-input v-model="v.inventor_name" placeholder="姓名或英文名" style="width: 170px" />
              <el-select v-model="v.person_id" filterable clearable placeholder="自动匹配，可手动调整" style="width: 210px">
                <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.english_name || p.uid})`" :value="p.id" />
              </el-select>
              <el-checkbox v-model="v.is_first">第一</el-checkbox>
              <el-button type="danger" link @click="form.inventors.splice(i, 1)">移除</el-button>
            </div>
            <el-button size="small" @click="form.inventors.push({ id: null, inventor_name: '', person_id: null, seq: form.inventors.length + 1, is_first: form.inventors.length === 0 })">+ 添加发明人</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" :title="detail?.title" size="44%">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 16px">
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

        <h4>发明人/著作权人
          <span style="float: right">
            <el-button size="small" :disabled="!selectedInventor" type="danger" link @click="removeInventor(selectedInventor)">移除选中</el-button>
            <el-button size="small" type="primary" plain @click="invVisible = true">+ 添加</el-button>
          </span>
        </h4>
        <el-table
          :data="detail.inventors"
          size="small"
          highlight-current-row
          @current-change="(row) => (selectedInventor = row)"
        >
          <el-table-column prop="seq" label="序" width="50" />
          <el-table-column label="姓名">
            <template #default="{ row }">
              <span v-if="row.person_id" class="clickable-link" @click="openPersonDrawer(row.person_id)">{{ row.inventor_name }}</span>
              <span v-else>{{ row.inventor_name }}</span>
              <el-tag v-if="row.person_name" size="small" type="success" style="margin-left: 6px">{{ row.person_name }}</el-tag>
              <el-tag v-if="row.is_first" size="small" type="warning" style="margin-left: 6px">第一</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <h4>基金标注
          <span style="float: right">
            <el-button size="small" :disabled="!selectedIpFunding" type="danger" link @click="removeIpFunding(selectedIpFunding)">移除选中</el-button>
            <el-button size="small" type="primary" plain @click="fundVisible = true">+ 添加</el-button>
          </span>
        </h4>
        <el-table
          :data="detail.funding"
          size="small"
          highlight-current-row
          @current-change="(row) => (selectedIpFunding = row)"
        >
          <el-table-column label="项目编号">
            <template #default="{ row }">
              <span v-if="row.project_id" class="clickable-link" @click="openProjectDrawer(row.project_id)">{{ row.project_name || row.funding_no }}</span>
              <span v-else>{{ row.funding_no || '-' }}</span>
            </template>
          </el-table-column>
        </el-table>

        <AttachmentArea entity="ip" :entity-id="detail.id" />
      </template>
    </el-drawer>

    <el-dialog v-model="invVisible" title="添加发明人" width="440px">
      <el-form label-width="90px">
        <el-form-item label="姓名">
          <el-input v-model="newInv.inventor_name" />
        </el-form-item>
        <el-form-item label="关联人员">
          <el-select v-model="newInv.person_id" filterable clearable style="width: 100%">
            <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.uid})`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="newInv.seq" :min="1" />
        </el-form-item>
        <el-form-item label="第一发明人">
          <el-switch v-model="newInv.is_first" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="invVisible = false">取消</el-button>
        <el-button type="primary" @click="addInventor">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="fundVisible" title="添加基金标注" width="440px">
      <el-form label-width="90px">
        <el-form-item label="项目">
          <el-select v-model="newFund.project_id" filterable clearable placeholder="选择项目" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="`${p.project_no} ${p.name || ''}`" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fundVisible = false">取消</el-button>
        <el-button type="primary" @click="addIpFunding">确定</el-button>
      </template>
    </el-dialog>

    <ImportDialog
      v-model:visible="importVisible"
      title="批量导入知识产权"
      upload-url="/import/ip"
      template-url="/import/template/ip"
      template-name="知识产权导入模板.xlsx"
      @done="load"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, DocumentCopy, Download, Plus, Search, Upload } from '@element-plus/icons-vue'
import api, { downloadFile, downloadPost, isAdmin } from '../api'
import DynamicFormFields from '../components/DynamicFormFields.vue'
import ImportDialog from '../components/ImportDialog.vue'
import AttachmentArea from '../components/AttachmentArea.vue'
import FilterTags from '../components/FilterTags.vue'
import {
  fieldValue, calcColWidth, makeSorter, tagTypeFor, toUpdateBody, packExtra, isWideField,
} from '../utils/fieldColumns'
import { useListPage } from '../utils/useListPage'

const router = useRouter()

const rows = ref([])
const loading = ref(false)
const localFilter = reactive({})
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


// Auto-apply filter on dropdown selection / input change (no need to click "查询")
watch(filter, () => load(), { deep: true })

const people = ref([])
const projects = ref([])

const formVisible = ref(false)
const importVisible = ref(false)
const saving = ref(false)
const emptyForm = () => ({
  ip_type: 'patent', title: '', grant_date: null, applicant: '', notes: '', extra: {},
  inventors: [],
})
const form = reactive(emptyForm())
let origInventors = []

const detailVisible = ref(false)
const detail = ref(null)
const invVisible = ref(false)
const fundVisible = ref(false)
const newInv = reactive({ inventor_name: '', person_id: null, seq: 1, is_first: false })
const newFund = reactive({ project_id: null, funding_no: '' })
const allFields = ref([])
const formFields = computed(() => allFields.value.filter((f) => f.enabled !== false))
const listFields = computed(() =>
  allFields.value.filter((f) => f.enabled !== false && f.show_in_list !== false)
)
// 客户端分页 + 多列排序（composable 统一管理）
const { sort, currentPage, pageSize, total, pagedRows, indexFrom, resetPage } = useListPage({
  viewKey: 'ip',
  listFields,
  displayRows,
})
// 筛选标签覆盖列表的全部列（ip_type 原始值为编码，由 VALUE_LABELS 映射为中文显示）
const filterFields = listFields
const selectedRows = ref([])
const selectedInventor = ref(null)
const selectedIpFunding = ref(null)

function clean(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== '' && (Array.isArray(v) ? v.length : v != null)))
}

async function load() {
  loading.value = true
  resetPage()
  try {
    const { data } = await api.get('/ip', { params: clean(filter) })
    rows.value = data
    selectedRows.value = []
  } finally {
    loading.value = false
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function downloadTemplate() {
  await downloadFile('/import/template/ip', '知识产权导入模板.xlsx')
}

function onImportExport(cmd) {
  if (cmd === 'template') downloadTemplate()
  else if (cmd === 'import') importVisible.value = true
  else if (cmd === 'export') exportCurrent()
}

async function exportCurrent() {
  await downloadPost('/export/custom', '知识产权导出.xlsx', {
    type: 'ip',
    columns: listFields.value.map((f) => (f.key.startsWith('cf_') ? 'extra:' + f.key : f.key)),
    ids: displayRows.value.map((r) => r.id),
  })
}

function openForm(row) {
  Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, emptyForm(), row ? {
    ...row,
    ...(row.extra || {}),                   // 展开extra字段到顶层，使自定义字段能绑定到表单
    extra: { ...(row.extra || {}) },
    inventors: (row.inventors || []).map((v) => ({
      id: v.id, inventor_name: v.inventor_name, person_id: v.person_id || null,
      seq: v.seq || 1, is_first: !!v.is_first,
    })),
  } : {})
  origInventors = form.inventors.map((v) => ({ ...v }))
  formVisible.value = true
}

async function syncInventors(ipId) {
  const current = form.inventors.filter((v) => (v.inventor_name || '').trim())
  const currentIds = new Set(current.map((v) => v.id).filter(Boolean))
  for (const o of origInventors) {
    if (o.id && !currentIds.has(o.id)) {
      await api.delete(`/ip/${ipId}/inventors/${o.id}`)
    }
  }
  for (let i = 0; i < current.length; i++) {
    const v = current[i]
    const payload = {
      inventor_name: v.inventor_name, person_id: v.person_id, seq: i + 1, is_first: v.is_first,
    }
    if (v.id) {
      const o = origInventors.find((x) => x.id === v.id)
      if (!o || o.inventor_name !== v.inventor_name || o.person_id !== v.person_id || o.is_first !== v.is_first) {
        await api.put(`/ip/${ipId}/inventors/${v.id}`, payload)
      }
    } else {
      await api.post(`/ip/${ipId}/inventors`, payload)
    }
  }
}

async function save() {
  if (!form.title?.trim()) return ElMessage.warning('产权名称为必填唯一标识')
  saving.value = true
  try {
    const packed = packExtra(form, allFields.value)
    if (form.id) {
      const body = toUpdateBody(clean(packed), 'title')
      delete body.inventors
      await api.put(`/ip/${form.id}`, body)
      await syncInventors(form.id)
    } else {
      const body = clean(packed)
      delete body.inventors
      const inventors = form.inventors
        .filter((v) => (v.inventor_name || '').trim())
        .map((v, i) => ({ inventor_name: v.inventor_name, person_id: v.person_id, seq: i + 1, is_first: v.is_first }))
      await api.post('/ip', { ...body, inventors })
    }
    ElMessage.success('已保存')
    formVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function rematchInventors() {
  const { data } = await api.post('/ip/rematch-inventors')
  ElMessage.success(`已匹配 ${data.matched} 条发明人记录`)
  load()
}

async function removeSelected() {
  const rows = selectedRows.value
  if (!rows.length) return
  if (rows.length === 1) {
    await ElMessageBox.confirm(`确认删除 ${rows[0].title || rows[0].id}？`, '删除', { type: 'warning' })
    await api.delete(`/ip/${rows[0].id}`)
  } else {
    await ElMessageBox.confirm(`确认删除选中的 ${rows.length} 条知识产权？`, '批量删除', { type: 'warning' })
    await api.post('/ip/batch-delete', rows.map((r) => r.id))
  }
  ElMessage.success(`已删除 ${rows.length} 条知识产权`)
  load()
}

const zipping = ref(false)
async function batchDownloadAttachments() {
  if (!selectedRows.value.length) return
  zipping.value = true
  try {
    await downloadPost('/attachments/download-by-records', 'ip-attachments.zip', {
      entity: 'ip',
      ids: selectedRows.value.map((r) => r.id),
    })
  } finally {
    zipping.value = false
  }
}

async function openDetail(row) {
  if (!row) return
  const [{ data }, plist, projlist] = await Promise.all([
    api.get(`/ip/${row.id}`),
    api.get('/people'),
    api.get('/projects'),
  ])
  detail.value = data
  people.value = plist.data
  projects.value = projlist.data
  detailVisible.value = true
}

async function refreshDetail() {
  const { data } = await api.get(`/ip/${detail.value.id}`)
  detail.value = data
  selectedInventor.value = null
  selectedIpFunding.value = null
}

async function addInventor() {
  if (!newInv.inventor_name) return ElMessage.warning('请填写姓名')
  await api.post(`/ip/${detail.value.id}/inventors`, clean(newInv))
  invVisible.value = false
  Object.assign(newInv, { inventor_name: '', person_id: null, seq: 1, is_first: false })
  refreshDetail()
}

async function removeInventor(row) {
  if (!row) return
  await api.delete(`/ip/${detail.value.id}/inventors/${row.id}`)
  refreshDetail()
}

async function addIpFunding() {
  if (!newFund.project_id) return ElMessage.warning('请选择项目')
  const p = projects.value.find((x) => x.id === newFund.project_id)
  await api.post(`/ip/${detail.value.id}/funding`, {
    project_id: newFund.project_id,
    funding_no: p?.project_no || '',
  })
  fundVisible.value = false
  Object.assign(newFund, { project_id: null, funding_no: '' })
  refreshDetail()
}

async function removeIpFunding(row) {
  if (!row) return
  await api.delete(`/ip/${detail.value.id}/funding/${row.id}`)
  refreshDetail()
}

function openPersonDrawer(personId) {
  if (!personId) return
  router.push('/people')
  setTimeout(() => {
    window.dispatchEvent(new CustomEvent('drawer:open', { detail: { type: 'people', id: personId } }))
  }, 50)
}

function openProjectDrawer(projectId) {
  router.push('/projects')
  setTimeout(() => {
    window.dispatchEvent(new CustomEvent('drawer:open', { detail: { type: 'projects', id: projectId } }))
  }, 50)
}

async function onDrawerOpen(e) {
  const { type, id } = e.detail
  if (type === 'ip') {
    await openDetail({ id })
  }
}

onMounted(() => {
  load()
  loadFields('ip')
  window.addEventListener('drawer:open', onDrawerOpen)
  window.addEventListener('fields-changed', onFieldsChanged)
})

function loadFields(entity) {
  api.get('/fields', { params: { entity } }).then((r) => {
    allFields.value = r.data
  })
}

function onFieldsChanged(e) {
  if (e.detail?.entity === 'ip') loadFields('ip')
}

onUnmounted(() => {
  window.removeEventListener('drawer:open', onDrawerOpen)
  window.removeEventListener('fields-changed', onFieldsChanged)
})
</script>

<style scoped>
.detail-text {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
