<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <template #header><span class="step-title"><span class="step-no">1</span>筛选条件（跨表关联）</span></template>
      <el-form inline>
        <el-form-item label="导出对象">
          <el-radio-group v-model="entity" @change="onEntityChange">
            <el-radio-button value="papers">论文</el-radio-button>
            <el-radio-button value="people">人员</el-radio-button>
            <el-radio-button value="projects">项目</el-radio-button>
            <el-radio-button value="ip">知识产权</el-radio-button>
            <el-radio-button value="awards">奖励荣誉</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <template v-if="entity === 'papers'">
          <el-form-item label="作者">
            <el-select v-model="filters.person_id" filterable clearable placeholder="任意人员" style="width: 200px">
              <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.uid})`" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="作者角色">
            <el-select v-model="filters.author_role" clearable placeholder="任意" style="width: 130px">
              <el-option label="第一作者" value="first" />
              <el-option label="通讯作者" value="corresponding" />
              <el-option label="一作或通讯" value="first_or_corresponding" />
            </el-select>
          </el-form-item>
          <el-form-item label="标注项目">
            <el-select v-model="filters.project_id" filterable clearable placeholder="任意项目" style="width: 240px">
              <el-option v-for="p in projects" :key="p.id" :label="`${p.project_no} ${p.name || ''}`" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="filters.project_id" label="标注顺序">
            <el-select v-model="filters.funding_seq" clearable placeholder="任意" style="width: 90px">
              <el-option label="1" :value="1" />
              <el-option label="2" :value="2" />
              <el-option label="3" :value="3" />
            </el-select>
            <el-tooltip content="同时包含致谢中出现该项目编号、但尚未录入基金标注关系的论文" placement="top">
              <el-checkbox v-model="filters.include_ack_text" style="margin-left: 10px">含致谢提及</el-checkbox>
            </el-tooltip>
          </el-form-item>
          <el-form-item label="年份">
            <el-select v-model="filters.years" multiple clearable placeholder="全部" style="width: 160px">
              <el-option v-for="y in allYears" :key="y" :label="String(y)" :value="y" />
            </el-select>
            <el-input-number v-model="filters.year_min" :min="1900" :max="2100" :controls="false" placeholder="起" style="width: 90px; margin-left: 8px" />
            <span style="margin: 0 6px">~</span>
            <el-input-number v-model="filters.year_max" :min="1900" :max="2100" :controls="false" placeholder="止" style="width: 90px" />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="filters.venue_type" clearable placeholder="任意" style="width: 100px">
              <el-option value="期刊" />
              <el-option value="会议" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键词">
            <el-input v-model="filters.keyword" placeholder="标题/期刊/作者/致谢" clearable style="width: 180px" @keyup.enter="exportExcel" />
          </el-form-item>
        </template>

        <template v-else-if="entity === 'people'">
          <el-form-item label="状态">
            <el-select v-model="filters.status" clearable placeholder="任意" style="width: 130px">
              <el-option v-for="o in optionsOf('people', 'status')" :key="o" :value="o" />
            </el-select>
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="filters.degree_type" clearable placeholder="任意" style="width: 120px">
              <el-option v-for="o in optionsOf('people', 'degree_type')" :key="o" :value="o" />
            </el-select>
          </el-form-item>
          <el-form-item label="参与项目">
            <el-select v-model="filters.project_id" filterable clearable placeholder="任意项目" style="width: 240px">
              <el-option v-for="p in projects" :key="p.id" :label="`${p.project_no} ${p.name || ''}`" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="论文年份">
            <el-input-number v-model="filters.paper_year" :min="1900" :max="2100" controls-position="right" style="width: 110px" placeholder="任意" />
          </el-form-item>
          <el-form-item label="关键词">
            <el-input v-model="filters.keyword" placeholder="姓名/英文名/学号" clearable style="width: 180px" @keyup.enter="exportExcel" />
          </el-form-item>
        </template>

        <template v-else-if="entity === 'projects'">
          <el-form-item label="状态">
            <el-select v-model="filters.status" clearable placeholder="任意" style="width: 130px">
              <el-option v-for="o in optionsOf('projects', 'status')" :key="o" :value="o" />
            </el-select>
          </el-form-item>
          <el-form-item label="项目类别">
            <el-select v-model="filters.category" clearable placeholder="任意" style="width: 120px">
              <el-option v-for="o in optionsOf('projects', 'category')" :key="o" :value="o" />
            </el-select>
          </el-form-item>
          <el-form-item label="参与人员">
            <el-select v-model="filters.person_id" filterable clearable placeholder="任意人员" style="width: 200px">
              <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.uid})`" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="论文年份">
            <el-input-number v-model="filters.paper_year" :min="1900" :max="2100" controls-position="right" style="width: 110px" placeholder="任意" />
          </el-form-item>
          <el-form-item label="关键词">
            <el-input v-model="filters.keyword" placeholder="项目名称/编号" clearable style="width: 180px" @keyup.enter="exportExcel" />
          </el-form-item>
        </template>

        <template v-else-if="entity === 'awards'">
          <el-form-item label="获奖人">
            <el-select v-model="filters.person_id" filterable clearable placeholder="任意人员" style="width: 200px">
              <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.uid})`" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="等级">
            <el-select v-model="filters.level" clearable placeholder="全部" style="width: 120px">
              <el-option v-for="s in ['特等奖', '一等奖', '二等奖', '三等奖', '其他']" :key="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键词">
            <el-input v-model="filters.keyword" placeholder="奖项名称/颁奖单位" clearable style="width: 200px" @keyup.enter="exportExcel" />
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="类型">
            <el-select v-model="filters.ip_type" clearable placeholder="全部" style="width: 120px">
              <el-option label="专利" value="patent" />
              <el-option label="软著" value="software_copyright" />
              <el-option label="其他" value="other" />
            </el-select>
          </el-form-item>
          <el-form-item label="发明人">
            <el-select v-model="filters.person_id" filterable clearable placeholder="任意人员" style="width: 200px">
              <el-option v-for="p in people" :key="p.id" :label="`${p.name || ''} (${p.uid})`" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="标注项目">
            <el-select v-model="filters.project_id" filterable clearable placeholder="任意项目" style="width: 240px">
              <el-option v-for="p in projects" :key="p.id" :label="`${p.project_no} ${p.name || ''}`" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键词">
            <el-input v-model="filters.keyword" placeholder="产权名称/专利权人" clearable style="width: 200px" @keyup.enter="exportExcel" />
          </el-form-item>
        </template>

      </el-form>
    </el-card>

    <el-card shadow="never" class="step-card">
      <template #header>
        <span class="step-title"><span class="step-no">2</span>选择导出字段</span>
      </template>
      <div v-for="g in groups" :key="g.name" style="margin-bottom: 10px">
        <el-checkbox
          :model-value="isGroupAll(g)"
          :indeterminate="isGroupPartial(g)"
          @change="(v) => toggleGroup(g, v)"
        >
          <b>{{ g.name }}</b>
        </el-checkbox>
        <el-checkbox-group v-model="selectedCols" style="margin-left: 16px">
          <el-checkbox v-for="c in g.cols" :key="c.key" :value="c.key">{{ c.label }}</el-checkbox>
        </el-checkbox-group>
      </div>
      <div v-if="conflictDims.length > 1" style="margin-top: 10px">
        <el-alert
          type="error"
          :closable="false"
          show-icon
          title="当前字段组合无法导出"
          :description="`所选字段同时包含「${conflictDims.join('」「')}」多个多值关联维度，无法在同一张二维表中同时按两个维度展开（每行只能属于一个维度的某条记录）。请每次只保留一个维度的关联字段，其余维度分多次导出。`"
        />
      </div>
      <div style="margin-top: 8px">
        <el-button type="primary" :disabled="conflictDims.length > 1" @click="exportExcel">导出 Excel</el-button>
        <el-button v-if="entity === 'papers'" plain @click="exportBib">导出 BibTeX</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { downloadFile, downloadPost } from '../api'

const ENTITY_LABEL = { papers: '论文', people: '人员', projects: '项目', ip: '知识产权', awards: '奖励荣誉' }

const people = ref([])
const projects = ref([])
const fieldDefs = reactive({ people: [], projects: [] })
const allYears = ref([])
const columnDefs = ref([])
const selectedCols = ref([])
const entity = ref('papers')

const filters = reactive({
  person_id: null, author_role: '', project_id: null, funding_seq: null,
  include_ack_text: false, years: [], year_min: null, year_max: null,
    venue_type: '', keyword: '', ip_type: '', status: '', degree_type: '', category: '', level: '', paper_year: null,
  })

function optionsOf(ent, key) {
  const f = fieldDefs[ent].find((x) => x.key === key && x.dtype === 'select')
  return f?.options || []
}

function clean(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== '' && (Array.isArray(v) ? v.length : v != null) && v !== false))
}

function entityFilterParams() {
  if (entity.value === 'awards') {
    return clean({ level: filters.level, person_id: filters.person_id, keyword: filters.keyword })
  }
  if (entity.value === 'ip') {
    return clean({ ip_type: filters.ip_type, person_id: filters.person_id, project_id: filters.project_id, keyword: filters.keyword })
  }
  if (entity.value === 'people') {
    return clean({ status: filters.status, degree_type: filters.degree_type, project_id: filters.project_id, year: filters.paper_year, keyword: filters.keyword })
  }
  if (entity.value === 'projects') {
    return clean({ status: filters.status, category: filters.category, person_id: filters.person_id, year: filters.paper_year, keyword: filters.keyword })
  }
  return clean({
    person_id: filters.person_id, author_role: filters.author_role,
    project_id: filters.project_id, funding_seq: filters.funding_seq,
    include_ack_text: filters.include_ack_text || null,
    years: filters.years.length ? filters.years : null,
    year_min: filters.year_min, year_max: filters.year_max,
    venue_type: filters.venue_type, keyword: filters.keyword,
  })
}

async function loadColumns() {
  const { data } = await api.get('/export/columns', { params: { type: entity.value } })
  columnDefs.value = data
  // 默认选中模块字段与标量关联列；多值关联列由用户按需勾选（避免默认产生维度冲突）
  selectedCols.value = data.filter((c) => !c.dim).map((c) => c.key)
}

function resetFilters() {
  Object.assign(filters, {
    person_id: null, author_role: '', project_id: null, funding_seq: null,
    include_ack_text: false, years: [], year_min: null, year_max: null,
  venue_type: '', keyword: '', ip_type: '', status: '', degree_type: '', category: '', level: '', paper_year: null,
  })
}

async function onEntityChange() {
  resetFilters()
  await loadColumns()
  // 切换模块时重新加载字段定义（含选项），确保下拉筛选器实时反映字段变更
  const { data } = await api.get('/fields', { params: { entity: entity.value } })
  fieldDefs[entity.value] = data
  await loadYears()
}

const groups = computed(() => {
  const map = {}
  for (const c of columnDefs.value) {
    if (!map[c.group]) map[c.group] = { name: c.group, cols: [] }
    map[c.group].cols.push(c)
  }
  return Object.values(map)
})

// 已选字段涉及的"多值关联维度"；超过一个则对应关系无法在二维表中表达
const conflictDims = computed(() => {
  const dims = new Set()
  for (const c of columnDefs.value) {
    if (c.dim && selectedCols.value.includes(c.key)) dims.add(c.dim)
  }
  return [...dims]
})

function isGroupAll(g) {
  return g.cols.every((c) => selectedCols.value.includes(c.key))
}
function isGroupPartial(g) {
  const n = g.cols.filter((c) => selectedCols.value.includes(c.key)).length
  return n > 0 && n < g.cols.length
}
function toggleGroup(g, v) {
  const keys = g.cols.map((c) => c.key)
  selectedCols.value = v
    ? [...new Set([...selectedCols.value, ...keys])]
    : selectedCols.value.filter((k) => !keys.includes(k))
}

async function loadYears() {
  if (entity.value !== 'papers') {
    allYears.value = []
    return
  }
  const { data } = await api.get('/papers')
  const years = data.map((r) => r.year).filter((y) => y)
  allYears.value = [...new Set(years)].sort((a, b) => b - a)
}

async function exportExcel() {
  if (!selectedCols.value.length) return ElMessage.warning('请至少选择一个导出字段')
  const fname = ENTITY_LABEL[entity.value] + '导出.xlsx'
  await downloadPost('/export/custom', fname, {
    type: entity.value,
    columns: selectedCols.value,
    filters: entityFilterParams(),
  })
}

async function exportBib() {
  await downloadFile('/export/papers.bib', '论文导出.bib', entityFilterParams())
}

onMounted(async () => {
  const [p, proj, cols, pFields, projFields] = await Promise.all([
    api.get('/people'),
    api.get('/projects'),
    api.get('/export/columns', { params: { type: 'papers' } }),
    api.get('/fields', { params: { entity: 'people' } }),
    api.get('/fields', { params: { entity: 'projects' } }),
  ])
  people.value = p.data
  projects.value = proj.data
  columnDefs.value = cols.data
  selectedCols.value = cols.data.filter((c) => !c.dim).map((c) => c.key)
  fieldDefs.people = pFields.data
  fieldDefs.projects = projFields.data
  loadYears()
})
</script>

<style scoped>
.step-card {
  margin-top: 14px;
}
.step-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.step-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--hpgc-primary-soft);
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 600;
}
</style>
