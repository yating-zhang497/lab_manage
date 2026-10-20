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
            placeholder="搜索奖项名称 / 颁奖单位"
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
          <el-button plain :disabled="!isAdmin" :loading="rematching" @click="rematchRecipients">重新匹配获奖人</el-button>
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
            <div class="empty-icon">🏆</div>
            <p>暂无奖励荣誉数据</p>
            <p class="muted">点击右上角「新增」添加第一条记录</p>
          </div>
        </template>
        <el-table-column type="selection" width="45" />
        <el-table-column type="index" width="50" align="center" label="#" :index="i => indexFrom + i + 1" />
        <el-table-column prop="award_name" label="奖项名称" min-width="200" show-overflow-tooltip>
          <template #header>
            <div class="sort-header" @click.stop="sort.toggle('award_name')">
              奖项名称
              <span v-if="sort.priority('award_name')" class="sort-badge">{{ sort.orderOf('award_name') === 'ascending' ? '↑' : '↓' }}{{ sort.priority('award_name') }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="等级" width="90">
          <template #header>
            <div class="sort-header" @click.stop="sort.toggle('level')">
              等级
              <span v-if="sort.priority('level')" class="sort-badge">{{ sort.orderOf('level') === 'ascending' ? '↑' : '↓' }}{{ sort.priority('level') }}</span>
            </div>
          </template>
          <template #default="{ row }">
            <el-tag v-if="row.level" size="small" effect="plain">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="award_date" label="获奖时间" width="110">
          <template #header>
            <div class="sort-header" @click.stop="sort.toggle('award_date')">
              获奖时间
              <span v-if="sort.priority('award_date')" class="sort-badge">{{ sort.orderOf('award_date') === 'ascending' ? '↑' : '↓' }}{{ sort.priority('award_date') }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="获奖人" min-width="200">
          <template #default="{ row }">
            <el-tag
              v-for="r in row.recipients"
              :key="r.id"
              size="small"
              :type="r.person_id ? 'success' : 'info'"
              style="margin-right: 4px; margin-bottom: 2px"
            >{{ r.person_name || r.recipient_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="issuer" label="颁奖单位" min-width="140" show-overflow-tooltip>
          <template #header>
            <div class="sort-header" @click.stop="sort.toggle('issuer')">
              颁奖单位
              <span v-if="sort.priority('issuer')" class="sort-badge">{{ sort.orderOf('issuer') === 'ascending' ? '↑' : '↓' }}{{ sort.priority('issuer') }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="获奖作品" min-width="150" show-overflow-tooltip>
          <template #header>
            <div class="sort-header" @click.stop="sort.toggle('summary')">
              获奖作品
              <span v-if="sort.priority('summary')" class="sort-badge">{{ sort.orderOf('summary') === 'ascending' ? '↑' : '↓' }}{{ sort.priority('summary') }}</span>
            </div>
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

    <!-- Edit Dialog -->
    <el-dialog v-model="formVisible" :title="form.id ? '编辑奖励荣誉' : '新增奖励荣誉'" width="680px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="奖项名称" required>
          <el-input v-model="form.award_name" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="奖励等级">
              <el-select v-model="form.level" clearable style="width: 100%">
                <el-option v-for="s in ['特等奖', '一等奖', '二等奖', '三等奖', '其他']" :key="s" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="获奖时间">
              <el-date-picker v-model="form.award_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="颁奖单位">
              <el-input v-model="form.issuer" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="证书编号">
              <el-input v-model="form.cert_no" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="公示链接">
          <el-input v-model="form.pr_url" placeholder="https://" />
        </el-form-item>
        <el-form-item label="所有获奖人">
          <el-input v-model="form.all_awardees" type="textarea" :rows="1" placeholder="可填全部获奖人姓名，用分号分隔" />
        </el-form-item>
        <el-form-item label="获奖作品">
          <el-input v-model="form.summary" type="textarea" :rows="2" />
        </el-form-item>
        <el-divider content-position="left">获奖人</el-divider>
        <div v-for="(r, i) in form.recipients" :key="i" style="display: flex; gap: 8px; margin-bottom: 8px; align-items: center">
          <el-input v-model="r.recipient_name" placeholder="姓名" style="width: 200px" />
          <el-select v-model="r.person_id" filterable clearable placeholder="关联人员（可选）" style="width: 220px">
            <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.uid})`" :value="p.id" />
          </el-select>
          <el-input v-model="r.rank" placeholder="如1/12" style="width: 100px" />
          <el-button type="danger" link @click="form.recipients.splice(i, 1)">移除</el-button>
        </div>
        <el-button size="small" @click="form.recipients.push({ recipient_name: '', person_id: null, rank: null, seq: form.recipients.length + 1 })">+ 添加获奖人</el-button>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- Detail Drawer -->
    <el-drawer v-model="detailVisible" :title="detail?.award_name || '详情'" size="44%">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="奖项名称" :span="2">{{ detail.award_name }}</el-descriptions-item>
          <el-descriptions-item label="奖励等级">{{ detail.level || '-' }}</el-descriptions-item>
          <el-descriptions-item label="获奖时间">{{ detail.award_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="颁奖单位">{{ detail.issuer || '-' }}</el-descriptions-item>
          <el-descriptions-item label="证书编号">{{ detail.cert_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="公示链接" :span="2">
            <a v-if="detail.pr_url" :href="detail.pr_url" target="_blank">{{ detail.pr_url }}</a>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="所有获奖人" :span="2">{{ detail.all_awardees || '-' }}</el-descriptions-item>
          <el-descriptions-item label="获奖作品" :span="2">{{ detail.summary || '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin-top: 16px">获奖人</h4>
        <el-table :data="detail.recipients" size="small">
          <el-table-column prop="recipient_name" label="姓名">
            <template #default="{ row }">
              <span v-if="row.person_id" class="clickable-link" @click="openPersonDrawer(row.person_id)">{{ row.recipient_name }}</span>
              <span v-else>{{ row.recipient_name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="rank" label="排名" width="80" />
          <el-table-column label="关联人员" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.person_name" size="small" type="success">{{ row.person_name }}</el-tag>
              <span v-else class="muted">未关联</span>
            </template>
          </el-table-column>
        </el-table>

        <h4 style="margin-top: 16px">附件</h4>
        <AttachmentArea entity="awards" :entity-id="detail.id" />
      </template>
    </el-drawer>

    <ImportDialog
      v-model:visible="importVisible"
      title="批量导入奖励荣誉"
      upload-url="/import/awards"
      template-url="/import/template/awards"
      template-name="奖励荣誉导入模板.xlsx"
      @done="load"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, DocumentCopy, Download, Plus, Search, Upload } from '@element-plus/icons-vue'
import api, { downloadFile, downloadPost, isAdmin } from '../api'
import ImportDialog from '../components/ImportDialog.vue'
import AttachmentArea from '../components/AttachmentArea.vue'
import FilterTags from '../components/FilterTags.vue'
import { fieldValue } from '../utils/fieldColumns'
import { useListPage } from '../utils/useListPage'

const rows = ref([])
const loading = ref(false)
const people = ref([])
const filter = reactive({ keyword: '' })
const localFilter = reactive({})          // 列筛选（key -> 已选值数组），由 FilterTags 维护
const selectedRows = ref([])
const allFields = ref([])                  // 字段定义（字段管理驱动）

const displayRows = computed(() => {
  let r = rows.value
  if (filter.keyword) {
    const kw = filter.keyword.toLowerCase()
    r = r.filter(a =>
      (a.award_name || '').toLowerCase().includes(kw) ||
      (a.issuer || '').toLowerCase().includes(kw) ||
      (a.summary || '').toLowerCase().includes(kw)
    )
  }
  for (const [key, val] of Object.entries(localFilter)) {
    if (!val || !val.length) continue
    const f = listFields.value.find((x) => x.key === key)
    r = r.filter((a) => f && val.includes(fieldValue(a, f)))
  }
  return r
})

const listFields = computed(() =>
  allFields.value.filter((f) => f.enabled !== false && f.show_in_list !== false)
)
// 客户端分页 + 多列排序（composable 统一管理）
const { sort, currentPage, pageSize, total, pagedRows, indexFrom, resetPage } = useListPage({
  viewKey: 'awards',
  listFields,
  displayRows,
})

const formVisible = ref(false)
const saving = ref(false)
const emptyForm = () => ({
  award_name: '', level: '', award_date: null, issuer: '',
  cert_no: '', pr_url: '', all_awardees: '', summary: '', recipients: [],
})
const form = reactive(emptyForm())

const detailVisible = ref(false)
const detail = ref(null)
const importVisible = ref(false)
const rematching = ref(false)
const zipping = ref(false)

async function load() {
  loading.value = true
  resetPage()
  try {
    const { data } = await api.get('/awards')
    rows.value = data
  } finally {
    loading.value = false
  }
}

async function loadPeople() {
  const { data } = await api.get('/people')
  people.value = data
}

function handleSelectionChange(val) {
  selectedRows.value = val
}

function openForm(row) {
  Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, emptyForm(), row ? {
    ...row,
    recipients: (row.recipients || []).map(r => ({
      id: r.id, recipient_name: r.recipient_name, person_id: r.person_id,
      rank: r.rank, seq: r.seq,
    })),
  } : {})
  formVisible.value = true
}

async function save() {
  if (!form.award_name?.trim()) return ElMessage.warning('请填写奖项名称')
  saving.value = true
  try {
    const body = {
      award_name: form.award_name,
      level: form.level || null,
      award_date: form.award_date || null,
      issuer: form.issuer || null,
      cert_no: form.cert_no || null,
      pr_url: form.pr_url || null,
      all_awardees: form.all_awardees || null,
      summary: form.summary || null,
      recipients: (form.recipients || [])
        .filter(r => r.recipient_name?.trim())
        .map((r, i) => ({
          seq: i + 1,
          recipient_name: r.recipient_name.trim(),
          person_id: r.person_id || null,
          rank: r.rank || null,
        })),
    }
    if (form.id) {
      await api.put(`/awards/${form.id}`, body)
    } else {
      await api.post('/awards', body)
    }
    formVisible.value = false
    await load()
    ElMessage.success('保存成功')
  } finally {
    saving.value = false
  }
}

async function openDetail(row) {
  if (!row) return
  const { data } = await api.get(`/awards/${row.id}`)
  detail.value = data
  detailVisible.value = true
}

async function removeSelected() {
  const rows = selectedRows.value
  if (!rows.length) return
  await ElMessageBox.confirm(`确认删除选中的 ${rows.length} 条奖励荣誉记录？`, '删除', { type: 'warning' })
  await api.post('/awards/batch-delete', rows.map(r => r.id))
  await load()
  ElMessage.success('删除成功')
}

async function rematchRecipients() {
  rematching.value = true
  try {
    const { data } = await api.post('/awards/rematch-recipients')
    ElMessage.success(`已匹配 ${data.matched} 条获奖人记录`)
    await load()
  } finally {
    rematching.value = false
  }
}

async function batchDownloadAttachments() {
  if (!selectedRows.value.length) return
  zipping.value = true
  try {
    await downloadPost('/attachments/download-by-records', 'awards-attachments.zip', {
      entity: 'awards',
      ids: selectedRows.value.map((r) => r.id),
    })
  } finally {
    zipping.value = false
  }
}

async function onImportExport(cmd) {
  if (cmd === 'template') {
    await downloadFile('/import/template/awards', '奖励荣誉导入模板.xlsx')
  } else if (cmd === 'import') {
    importVisible.value = true
  } else if (cmd === 'export') {
    await downloadPost('/export/custom', '奖励荣誉导出.xlsx', {
      type: 'awards',
      columns: listFields.value.map((f) => (f.key.startsWith('cf_') ? 'extra:' + f.key : f.key)),
      ids: displayRows.value.map((r) => r.id),
    })
  }
}

function openPersonDrawer(personId) {
  if (!personId) return
  window.dispatchEvent(new CustomEvent('drawer:open', { detail: { type: 'people', id: personId } }))
}

async function loadFields() {
  const { data } = await api.get('/fields', { params: { entity: 'awards' } })
  allFields.value = data
}

// 字段管理改动后实时刷新筛选行
window.addEventListener('fields-changed', (e) => {
  if (e.detail?.entity === 'awards') loadFields()
})

onMounted(() => {
  load()
  loadPeople()
  loadFields()
})
</script>
