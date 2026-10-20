<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <!-- 筛选标签行：列表列 + 期刊/会议类型，点击即过滤 -->
      <FilterTags :fields="filterFields" :rows="rows" :model="localFilter" />

      <div class="toolbar">
        <div class="toolbar-filters">
          <el-input
            v-model="filter.keyword"
            class="tb-search"
            placeholder="搜索标题 / 期刊会议"
            clearable
            :prefix-icon="Search"
            @keyup.enter="load"
          />
          <el-select v-model="filter.person_id" filterable clearable placeholder="作者" style="width: 160px">
            <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.uid})`" :value="p.id" />
          </el-select>
          <el-select v-model="filter.project_id" filterable clearable placeholder="项目" style="width: 200px">
            <el-option v-for="p in projects" :key="p.id" :label="`${p.project_no} ${p.name || ''}`" :value="p.id" />
          </el-select>
        </div>
        <div class="toolbar-actions">
          <span class="result-count">共 {{ displayRows.length }} 条</span>
          <el-button :disabled="selectedRows.length !== 1" @click="openDetail(selectedRows[0])">详情</el-button>
          <el-button :disabled="!isAdmin || selectedRows.length !== 1" @click="openForm(selectedRows[0])">编辑</el-button>
          <el-button type="danger" plain :disabled="!isAdmin || !selectedRows.length" @click="removeSelected">
            删除<template v-if="selectedRows.length">（{{ selectedRows.length }}）</template>
          </el-button>
          <span class="tb-divider"></span>
          <el-dropdown trigger="click" @command="onImportExport">
            <el-button>
              导入 / 导出<el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="template" :icon="Download">下载导入模板（CSV/Excel）</el-dropdown-item>
                <el-dropdown-item command="import" :icon="Upload" :disabled="!isAdmin">导入 CSV / Excel…</el-dropdown-item>
                <el-dropdown-item command="bibTemplate" :icon="Download">下载 BibTeX 示例</el-dropdown-item>
                <el-dropdown-item command="importBib" :icon="Upload" :disabled="!isAdmin">导入 BibTeX / Better BibTeX…</el-dropdown-item>
                <el-dropdown-item command="export" :icon="DocumentCopy" divided>导出当前结果</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button
            type="success"
            plain
            :disabled="!isAdmin || !displayRows.length"
            :loading="extracting"
            @click="batchExtract"
          >
            AI提取{{ selectedRows.length ? `（${selectedRows.length}）` : `全部（${displayRows.length}）` }}
          </el-button>
          <el-button plain :disabled="!isAdmin" :loading="rematching" @click="rematchAuthors">重新匹配作者</el-button>
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
            <div class="empty-icon">📄</div>
            <p>暂无论文数据</p>
            <p class="muted">通过导入添加：右上角「导入 / 导出」→ 下载模板对照填写，再导入 CSV/Excel 或 BibTeX</p>
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

    <el-dialog v-model="formVisible" :title="form.id ? '编辑论文' : '新增论文'" width="700px">
      <el-form :model="form" label-width="100px">
        <DynamicFormFields :fields="formFields" :model="form" :required-keys="['title']" :exclude-keys="['project_no_1', 'project_no_2', 'project_no_3', 'venue', 'authors_raw']" />
        <el-form-item label="项目编号">
          <div style="width: 100%">
            <div v-for="(fn, i) in form.funding" :key="i" style="display: flex; gap: 8px; margin-bottom: 6px; align-items: center">
              <span class="muted" style="width: 70px">项目{{ i + 1 }}</span>
              <el-select v-model="fn.project_id" filterable clearable placeholder="选择项目" style="width: 280px">
                <el-option v-for="p in projects" :key="p.id" :label="`${p.project_no} ${p.name || ''}`" :value="p.id" />
              </el-select>
              <span class="muted">排序</span>
              <el-input-number v-model="fn.seq" :min="1" :controls="false" style="width: 80px" />
              <el-button type="danger" link @click="form.funding.splice(i, 1)">移除</el-button>
            </div>
            <el-button size="small" @click="form.funding.push({ id: null, project_id: null, funding_no: '', seq: form.funding.length + 1 })">+ 添加项目</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" :title="detail?.title" size="56%">
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

        <h4>作者
          <span style="float: right">
            <el-button size="small" :disabled="!selectedAuthor" type="danger" link @click="removeAuthor(selectedAuthor)">移除选中</el-button>
            <el-button size="small" type="primary" plain @click="authorFormVisible = true">+ 添加作者</el-button>
          </span>
        </h4>
        <el-table
          :data="detail.authors"
          size="small"
          highlight-current-row
          @current-change="(row) => (selectedAuthor = row)"
        >
          <el-table-column prop="seq" label="序" width="50" />
          <el-table-column label="姓名" min-width="140">
            <template #default="{ row }">
              {{ row.author_name }}
            </template>
          </el-table-column>
          <el-table-column label="关联人员" width="220">
            <template #default="{ row }">
              <el-select
                v-model="row.person_id"
                filterable
                clearable
                placeholder="未关联"
                style="width: 100%"
                @change="updateAuthorPerson(row)"
              >
                <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.uid})`" :value="p.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="通讯" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.is_corresponding" size="small" type="warning" style="cursor: pointer" @click="toggleCorresponding(row)">通讯</el-tag>
              <el-button v-else size="small" link type="info" @click="toggleCorresponding(row)">标记</el-button>
            </template>
          </el-table-column>
        </el-table>

        <h4>基金标注
          <span style="float: right">
            <el-button size="small" :disabled="!selectedFunding" type="danger" link @click="removeFunding(selectedFunding)">移除选中</el-button>
            <el-button size="small" type="primary" plain @click="newFunding.project_id = null, newFunding.funding_no = '', newFunding.seq = 0, fundingFormVisible = true">+ 添加基金</el-button>
          </span>
        </h4>
        <el-table
          :data="detail.funding"
          size="small"
          highlight-current-row
          @current-change="(row) => (selectedFunding = row)"
        >
          <el-table-column label="项目编号">
            <template #default="{ row }">
              <span v-if="row.project_id" class="clickable-link" @click="openProjectDrawer(row.project_id)">{{ row.funding_no }}</span>
              <span v-else>{{ row.funding_no || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="项目名称">
            <template #default="{ row }">
              <span v-if="row.project_id" class="clickable-link" @click="openProjectDrawer(row.project_id)">{{ row.project_name }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="seq" label="标注序" width="80">
            <template #default="{ row }">{{ row.seq || '-' }}</template>
          </el-table-column>
          <el-table-column label="来源" width="140">
            <template #default="{ row }">
              <el-tag size="small" :type="row.source === 'auto' ? 'warning' : ''">
                {{ row.source === 'auto' ? 'AI提取' : '手工' }}{{ row.confirmed ? '' : '·待确认' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <!-- PDFs -->
        <div class="section">
          <h4>PDF 文件
            <el-button size="small" type="primary" plain style="float: right" @click="openPdfUpload">+ 上传 PDF</el-button>
            <el-button size="small" type="primary" plain style="float: right; margin-right: 6px" @click="openLinkPdfDialog">+ 关联已有 PDF</el-button>
          </h4>
          <el-alert
            v-if="paperPdfs.length > 1"
            type="warning"
            :closable="false"
            show-icon
            title="该论文关联了多个 PDF，请核查"
            description="每篇论文通常只对应一个 PDF，请删除多余的（保留最匹配的那份）。"
            style="margin-bottom: 8px"
          />
          <div v-if="paperPdfs.length" class="pdf-list">
            <div v-for="pdf in paperPdfs" :key="pdf.id" class="pdf-item">
              <el-icon><Document /></el-icon>
              <span class="pdf-name clickable-link" @click="previewPdf(pdf)">{{ pdf.filename }}</span>
              <span class="muted">{{ formatSize(pdf.size) }}</span>
              <el-button size="small" type="danger" link style="margin-left: 4px" @click="removePdf(pdf)">删除</el-button>
            </div>
          </div>
          <span v-else class="muted">暂无 PDF</span>
        </div>
      </template>
    </el-drawer>

    <ImportDialog
      v-model:visible="importTableVisible"
      title="批量导入论文（CSV/Excel）"
      upload-url="/import/papers"
      template-url="/import/template/papers"
      template-name="论文导入模板.xlsx"
      @done="load"
    />
    <ImportDialog
      v-model:visible="importBibVisible"
      title="导入 BibTeX / Better BibTeX"
      upload-url="/import/papers/bib"
      accept=".bib,.txt"
      @done="load"
    />

    <el-dialog v-model="authorFormVisible" title="添加作者" width="460px">
      <el-form label-width="90px">
        <el-form-item label="作者姓名">
          <el-input v-model="newAuthor.author_name" placeholder="例: Fu, Haohuan" />
        </el-form-item>
        <el-form-item label="关联人员">
          <el-select v-model="newAuthor.person_id" filterable clearable style="width: 100%">
            <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.english_name || p.uid})`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="newAuthor.seq" :min="1" />
        </el-form-item>
        <el-form-item label="通讯作者">
          <el-switch v-model="newAuthor.is_corresponding" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="authorFormVisible = false">取消</el-button>
        <el-button type="primary" @click="addAuthor">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="fundingFormVisible" title="添加基金标注" width="460px">
      <el-form label-width="90px">
        <el-form-item label="项目">
          <el-select v-model="newFunding.project_id" filterable clearable placeholder="选择项目" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="`${p.project_no} ${p.name || ''}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标注顺序">
          <el-input-number v-model="newFunding.seq" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fundingFormVisible = false">取消</el-button>
        <el-button type="primary" @click="addFunding">确定</el-button>
      </template>
    </el-dialog>

    <!-- PDF upload dialog -->
    <el-dialog v-model="pdfUploadVisible" title="上传论文 PDF" width="440px">
      <div
        class="drop-zone"
        :class="{ 'is-dragover': pdfDragover }"
        @dragover.prevent="pdfDragover = true"
        @dragleave.prevent="pdfDragover = false"
        @drop.prevent="onPdfDrop"
      >
        <el-icon class="drop-icon"><UploadFilled /></el-icon>
        <p>拖拽 PDF 文件到此处，或 <el-button type="primary" text @click="$refs.pdfFileInput.click()">点击选择</el-button></p>
      </div>
      <input ref="pdfFileInput" type="file" accept=".pdf" style="display: none" @change="onPdfFileSelect" />
      <p v-if="pdfUploadStatus" class="upload-status">{{ pdfUploadStatus }}</p>
      <template #footer>
        <el-button @click="pdfUploadVisible = false">关闭</el-button>
        <el-button type="primary" :disabled="!pendingPdfFile || pdfUploading" :loading="pdfUploading" @click="uploadPdfOnly">仅上传</el-button>
      </template>
    </el-dialog>

    <!-- Link existing PDF dialog -->
    <el-dialog v-model="linkPdfVisible" title="关联已有 PDF" width="500px">
      <el-input v-model="linkPdfKeyword" placeholder="搜索文件名…" clearable style="margin-bottom: 10px" />
      <el-table :data="linkablePdfs" size="small" max-height="300" v-loading="linkingPdfLoading" highlight-current-row @current-change="(r) => (linkPdfSelected = r)">
        <el-table-column prop="filename" label="文件名" show-overflow-tooltip />
        <el-table-column label="大小" width="80">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="140">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="linkPdfVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!linkPdfSelected" :loading="linkingPdfSaving" @click="confirmLinkPdf">确认关联</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, DocumentCopy, Download, Search, Upload, UploadFilled, Document } from '@element-plus/icons-vue'
import api, { downloadFile, downloadPost, isAdmin } from '../api'
import { formatSize, formatTime } from '../utils/format'
import ImportDialog from '../components/ImportDialog.vue'
import DynamicFormFields from '../components/DynamicFormFields.vue'
import FilterTags from '../components/FilterTags.vue'
import {
  fieldValue, calcColWidth, makeSorter, tagTypeFor, toUpdateBody, packExtra, isWideField,
} from '../utils/fieldColumns'
import { useListPage } from '../utils/useListPage'

const router = useRouter()

const rows = ref([])
const loading = ref(false)
const people = ref([])
const projects = ref([])
const filter = reactive({ keyword: '', person_id: null, project_id: null })
const localFilter = reactive({})  // 列筛选（key -> 已选值数组），由 FilterTags 维护

// 顶部筛选chip = 列表列 + 期刊/会议类型（venue_type 非列表列，注入伪字段供筛选）
const filterFields = computed(() => {
  const fs = [...listFields.value]
  if (!fs.some((f) => f.key === 'venue_type')) {
    const i = fs.findIndex((f) => f.key === 'venue')
    fs.splice(i < 0 ? fs.length : i + 1, 0, { key: 'venue_type', label: '类型', dtype: 'select' })
  }
  return fs
})

// 本地过滤：基于 rows 数据在前端过滤所有非服务器字段（支持多选）
const displayRows = computed(() => {
  let result = rows.value
  for (const [key, val] of Object.entries(localFilter)) {
    if (!val || !val.length) continue
    result = result.filter((row) => {
      const f = filterFields.value.find((f) => f.key === key)
      return f && val.includes(fieldValue(row, f))
    })
  }
  return result
})

// Auto-apply filter on dropdown selection / input change (no need to click "查询")
watch(filter, () => load(), { deep: true })

const formVisible = ref(false)
const saving = ref(false)
const emptyForm = () => ({
  title: '', doi: '', venue: '', venue_type: '', year: null,
  volume: '', issue: '', pages: '', authors_raw: '', acknowledgements: '',
  extra: {}, funding: [],
})
const form = reactive(emptyForm())
// 打开编辑时记录的基金标注原始状态，保存时用于差量同步
let origFunding = []

const detailVisible = ref(false)
const detail = ref(null)
const paperPdfs = ref([])
const pdfUploadVisible = ref(false)
const pdfDragover = ref(false)
const pdfUploadStatus = ref('')
const pdfUploading = ref(false)
const pendingPdfFile = ref(null)

// Link existing PDF dialog
const linkPdfVisible = ref(false)
const linkPdfKeyword = ref('')
const linkPdfSelected = ref(null)
const linkablePdfs = ref([])
const linkingPdfLoading = ref(false)
const linkingPdfSaving = ref(false)
const extracting = ref(false)
const rematching = ref(false)

watch(linkPdfKeyword, () => loadLinkablePdfs())

const authorFormVisible = ref(false)
const fundingFormVisible = ref(false)
const newAuthor = reactive({ author_name: '', person_id: null, seq: 1, is_corresponding: false })
const newFunding = reactive({ project_id: null, funding_no: '', seq: 0 })

const importTableVisible = ref(false)
const importBibVisible = ref(false)
const allFields = ref([])
const formFields = computed(() => allFields.value.filter((f) => f.enabled !== false))
const listFields = computed(() =>
  allFields.value.filter((f) => f.enabled !== false && f.show_in_list !== false)
)
// 客户端分页 + 多列排序（composable 统一管理）
const { sort, currentPage, pageSize, total, pagedRows, indexFrom, resetPage } = useListPage({
  viewKey: 'papers',
  listFields,
  displayRows,
})
const selectedRows = ref([])
const selectedAuthor = ref(null)
const selectedFunding = ref(null)

async function downloadTemplate() {
  await downloadFile('/import/template/papers', '论文导入模板.xlsx')
}

async function downloadBibTemplate() {
  await downloadFile('/import/template/papers/bib', '论文导入示例.bib')
}

function onImportExport(cmd) {
  if (cmd === 'template') downloadTemplate()
  else if (cmd === 'bibTemplate') downloadBibTemplate()
  else if (cmd === 'import') importTableVisible.value = true
  else if (cmd === 'importBib') importBibVisible.value = true
  else if (cmd === 'export') exportCurrent()
}

async function exportCurrent() {
  await downloadPost('/export/custom', '论文导出.xlsx', {
    type: 'papers',
    columns: listFields.value.map((f) => (f.key.startsWith('cf_') ? 'extra:' + f.key : f.key)),
    ids: displayRows.value.map((r) => r.id),
  })
}

function clean(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== '' && (Array.isArray(v) ? v.length : v != null)))
}

async function load() {
  loading.value = true
  resetPage()
  try {
    const { data } = await api.get('/papers', { params: clean(filter) })
    rows.value = data
    selectedRows.value = []
  } finally {
    loading.value = false
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function openForm(row) {
  origFunding = []
  Object.keys(form).forEach(k => delete form[k])
  if (row?.id) {
    // 编辑：用详情数据(PaperOut 完整字段)回填表单。列表行是精简 PaperListItem，
    // 只含 id/title/venue/year/ccf_class/venue_type，直接用会导致致谢、通讯作者等
    // AI 提取写入的字段在编辑框里为空，用户得重输。先拉详情再回填即可。
    const { data } = await api.get(`/papers/${row.id}`)
    Object.assign(form, emptyForm(), {
      ...data,
      ...(data.extra || {}),
      extra: { ...(data.extra || {}) },
      funding: [],
    })
    form.funding = data.funding.map((f) => ({
      id: f.id, funding_no: f.funding_no || '', seq: f.seq || 1, project_id: f.project_id || null,
    }))
    origFunding = form.funding.map((f) => ({ ...f }))
  } else {
    Object.assign(form, emptyForm())
  }
  formVisible.value = true
}

async function syncFunding(paperId) {
  const current = form.funding.filter((f) => (f.funding_no || '').trim() || f.project_id)
  const currentIds = new Set(current.map((f) => f.id).filter(Boolean))
  for (const o of origFunding) {
    if (o.id && !currentIds.has(o.id)) {
      await api.delete(`/papers/${paperId}/funding/${o.id}`)
    }
  }
  for (const f of current) {
    if (f.id) {
      const o = origFunding.find((x) => x.id === f.id)
      if (!o || o.funding_no !== f.funding_no || o.seq !== f.seq || o.project_id !== f.project_id) {
        await api.put(`/papers/${paperId}/funding/${f.id}`, {
          funding_no: f.funding_no, seq: f.seq, project_id: f.project_id, confirmed: true, source: 'manual',
        })
      }
    } else {
      await api.post(`/papers/${paperId}/funding`, {
        funding_no: f.funding_no, seq: f.seq, project_id: f.project_id, confirmed: true, source: 'manual',
      })
    }
  }
}

async function save() {
  if (!form.title?.trim()) return ElMessage.warning('论文标题为必填唯一标识')
  saving.value = true
  try {
    const packed = packExtra(form, allFields.value)
    if (form.id) {
      const body = toUpdateBody(clean(packed), 'title')
      delete body.funding
      await api.put(`/papers/${form.id}`, body)
      await syncFunding(form.id)
    } else {
      const body = clean(packed)
      delete body.funding
      const funding = form.funding
        .filter((f) => f.project_id)
        .map((f) => {
          const p = projects.value.find((x) => x.id === f.project_id)
          return { project_id: f.project_id, funding_no: p?.project_no || '', seq: f.seq || 1, confirmed: true, source: 'manual' }
        })
      await api.post('/papers', { ...body, funding })
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
    await ElMessageBox.confirm(`确认删除论文 ${rows[0].title || rows[0].id}？`, '删除', { type: 'warning' })
    await api.delete(`/papers/${rows[0].id}`)
  } else {
    await ElMessageBox.confirm(`确认删除选中的 ${rows.length} 篇论文？`, '批量删除', { type: 'warning' })
    await api.post('/papers/batch-delete', rows.map((r) => r.id))
  }
  ElMessage.success(`已删除 ${rows.length} 篇论文`)
  load()
}

async function batchExtract() {
  const ids = selectedRows.value.length
    ? selectedRows.value.map((r) => r.id)
    : displayRows.value.map((r) => r.id)
  if (!ids.length) return
  extracting.value = true
  try {
    const { data } = await api.post('/papers/batch-extract', ids)
    ElMessage.success(data.message)
  } catch (e) {
    const detail = e.response?.data?.detail
    if (detail) ElMessage.error('AI提取失败：' + (typeof detail === 'string' ? detail : JSON.stringify(detail)))
    else ElMessage.error('AI提取失败（网络错误）')
  } finally {
    extracting.value = false
  }
}

async function rematchAuthors() {
  rematching.value = true
  try {
    const { data } = await api.post('/papers/rematch-authors')
    ElMessage.success(`已匹配 ${data.matched} 条作者记录`)
    load()
  } finally {
    rematching.value = false
  }
}

async function openDetail(row) {
  if (!row || row.id == null) return
  const [{ data }, plist, projlist, pdfsData] = await Promise.all([
    api.get(`/papers/${row.id}`),
    api.get('/people'),
    api.get('/projects'),
    api.get('/pdfs', { params: { paper_id: row.id } }).catch(() => ({ data: { rows: [] } })),
  ])
  detail.value = data
  people.value = plist.data
  projects.value = projlist.data
  paperPdfs.value = pdfsData.data?.rows || []
  detailVisible.value = true
}

async function refreshDetail() {
  const { data } = await api.get(`/papers/${detail.value.id}`)
  detail.value = data
  selectedAuthor.value = null
  selectedFunding.value = null
}

async function addAuthor() {
  if (!newAuthor.author_name) return ElMessage.warning('请填写作者姓名')
  await api.post(`/papers/${detail.value.id}/authors`, clean(newAuthor))
  authorFormVisible.value = false
  Object.assign(newAuthor, { author_name: '', person_id: null, seq: 1, is_corresponding: false })
  refreshDetail()
}

async function removeAuthor(row) {
  if (!row) return
  await api.delete(`/papers/${detail.value.id}/authors/${row.id}`)
  refreshDetail()
}

async function toggleCorresponding(row) {
  await api.put(`/papers/${detail.value.id}/authors/${row.id}`, {
    author_name: row.author_name,
    person_id: row.person_id,
    seq: row.seq,
    is_corresponding: !row.is_corresponding,
    affiliation: row.affiliation ?? null,
  })
  refreshDetail()
}

async function updateAuthorPerson(row) {
  await api.put(`/papers/${detail.value.id}/authors/${row.id}`, {
    author_name: row.author_name,
    person_id: row.person_id || null,
    seq: row.seq,
    is_corresponding: row.is_corresponding,
    affiliation: row.affiliation ?? null,
  })
  refreshDetail()
}

async function addFunding() {
  if (!newFunding.project_id) return ElMessage.warning('请选择项目')
  const p = projects.value.find((x) => x.id === newFunding.project_id)
  await api.post(`/papers/${detail.value.id}/funding`, {
    project_id: newFunding.project_id,
    funding_no: p?.project_no || '',
    seq: newFunding.seq || 1,
    confirmed: true,
    source: 'manual',
  })
  fundingFormVisible.value = false
  Object.assign(newFunding, { project_id: null, funding_no: '', seq: 0 })
  refreshDetail()
}

async function removeFunding(row) {
  if (!row) return
  await api.delete(`/papers/${detail.value.id}/funding/${row.id}`)
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

// ─── PDF helpers ─────────────────────────────────────────────────────────
function openPdfUpload() {
  pdfUploadStatus.value = ''
  pendingPdfFile.value = null
  pdfUploadVisible.value = true
}

function onPdfFileSelect(e) {
  handlePdfFile(e.target.files[0])
  e.target.value = ''
}

function onPdfDrop(e) {
  pdfDragover.value = false
  handlePdfFile(e.dataTransfer.files[0])
}

function handlePdfFile(file) {
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.pdf')) return ElMessage.warning('仅支持 PDF 文件')
  pendingPdfFile.value = file
}

async function uploadPdfOnly() {
  if (!pendingPdfFile.value) return ElMessage.warning('请先选择 PDF 文件')
  if (!detail.value) return
  pdfUploading.value = true
  pdfUploadStatus.value = ''
  try {
    const fd = new FormData()
    fd.append('files', pendingPdfFile.value)
    await api.post(`/pdfs`, fd)
    pdfUploadStatus.value = '上传成功！'
    pendingPdfFile.value = null
    const { data } = await api.get('/pdfs', { params: { paper_id: detail.value.id } })
    paperPdfs.value = data.rows || []
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  } finally {
    pdfUploading.value = false
  }
}

async function removePdf(pdf) {
  await ElMessageBox.confirm(`确认删除 ${pdf.filename}？`, '删除', { type: 'warning' })
  await api.delete(`/pdfs/${pdf.id}`)
  ElMessage.success('已删除')
  const { data } = await api.get('/pdfs', { params: { paper_id: detail.value.id } })
  paperPdfs.value = data.rows || []
}

async function previewPdf(pdf) {
  const res = await api.get(`/pdfs/${pdf.id}/file`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  window.open(url, '_blank')
  URL.revokeObjectURL(url)
}

async function openLinkPdfDialog() {
  linkPdfKeyword.value = ''
  linkPdfSelected.value = null
  linkPdfVisible.value = true
  await loadLinkablePdfs()
}

async function loadLinkablePdfs() {
  linkingPdfLoading.value = true
  try {
    const params = { status: 'unmatched', page: 1, page_size: 100 }
    if (linkPdfKeyword.value) params.filename = linkPdfKeyword.value
    const { data } = await api.get('/pdfs', { params })
    // always filter client-side for paper_id == null (unmatched)
    linkablePdfs.value = (data.rows || []).filter((r) => r.paper_id == null)
  } finally {
    linkingPdfLoading.value = false
  }
}

async function confirmLinkPdf() {
  if (!linkPdfSelected.value) return ElMessage.warning('请先选择一个 PDF')
  linkingPdfSaving.value = true
  try {
    await api.put(`/pdfs/${linkPdfSelected.value.id}/link`, { paper_id: detail.value.id })
    ElMessage.success('已关联')
    linkPdfVisible.value = false
    // refresh pdf list in detail drawer
    const { data } = await api.get('/pdfs', { params: { paper_id: detail.value.id } })
    paperPdfs.value = data.rows || []
  } finally {
    linkingPdfSaving.value = false
  }
}

// 跨页跳转：带 id 打开详情；带 person_id / project_id 则改为按该作者/项目筛选列表
async function onDrawerOpen(e) {
  const { type, id, person_id: personId, project_id: projectId } = e.detail || {}
  if (type !== 'papers') return
  if (personId != null) {
    filter.person_id = personId
    return
  }
  if (projectId != null) {
    filter.project_id = projectId
    return
  }
  if (id != null) await openDetail({ id })
}

onMounted(() => {
  load()
  // 预加载人员/项目供顶部筛选下拉使用
  api.get('/people').then((r) => (people.value = r.data))
  api.get('/projects').then((r) => (projects.value = r.data))
  loadFields('papers')
  window.addEventListener('drawer:open', onDrawerOpen)
  window.addEventListener('fields-changed', onFieldsChanged)
})

function loadFields(entity) {
  api.get('/fields', { params: { entity } }).then((r) => {
    allFields.value = r.data
  })
}

function onFieldsChanged(e) {
  if (e.detail?.entity === 'papers') loadFields('papers')
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
.pdf-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pdf-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: #f7f8fa;
  border-radius: 8px;
  font-size: 13px;
  transition: background-color 0.18s;
}
.pdf-item:hover {
  background: #f0f3f8;
}
.pdf-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.section {
  margin-top: 20px;
}
.upload-status {
  margin-top: 10px;
  text-align: center;
  color: var(--el-color-success);
  font-size: 13px;
}
</style>
