<template>
  <div>
    <el-card shadow="never">
      <template #header>
        字段管理
      </template>
      <el-tabs v-model="entity">
        <el-tab-pane label="人员" name="people" />
        <el-tab-pane label="项目" name="projects" />
        <el-tab-pane label="论文" name="papers" />
        <el-tab-pane label="知识产权" name="ip" />
        <el-tab-pane label="奖励荣誉" name="awards" />
      </el-tabs>

      <el-table :data="defs" v-loading="loading" row-key="key" :default-sort="{ prop: 'sort', order: 'ascending' }">
        <el-table-column label="排序" width="70">
          <template #default="{ row, $index }">
            <el-button link :disabled="$index === 0" @click="moveUp($index)" size="small">
              <el-icon><ArrowUp /></el-icon>
            </el-button>
            <el-button link :disabled="$index === defs.length - 1" @click="moveDown($index)" size="small">
              <el-icon><ArrowDown /></el-icon>
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="字段" min-width="200" sortable :sort-method="(a, b) => String(a.label || '').localeCompare(String(b.label || ''), 'zh-CN')">
          <template #default="{ row }">
            <span>{{ row.label }}</span>
            <span class="muted" style="margin-left: 6px">{{ row.key }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90" sortable :sort-method="(a, b) => String(a.dtype || '').localeCompare(String(b.dtype || ''))">
          <template #default="{ row }">{{ dtypeLabel(row.dtype) }}</template>
        </el-table-column>
        <el-table-column label="选项" min-width="180" sortable :sort-method="(a, b) => String(a.options ? a.options.join(',') : '').localeCompare(String(b.options ? b.options.join(',') : ''))">
          <template #default="{ row }">
            <template v-if="row.dtype === 'select'">
              <el-tag v-for="o in row.options" :key="o" size="small" style="margin-right: 4px">{{ o }}</el-tag>
            </template>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tooltip :disabled="!isUnique(row)" content="唯一标识字段，不能停用" placement="top">
              <el-switch :model-value="row.enabled !== false" :disabled="isUnique(row)" @change="(v) => toggleEnabled(row, v)" />
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="列表显示" width="95" sortable :sort-method="(a, b) => (a.show_in_list !== false ? 1 : 0) - (b.show_in_list !== false ? 1 : 0)">
          <template #default="{ row }">
            <el-tooltip content="开=显示在模块列表页，关=仅在详情/表单中" placement="top">
              <el-switch :model-value="row.show_in_list !== false" @change="(v) => toggleShow(row, v)" />
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" link @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-button type="primary" plain style="margin-top: 14px" @click="openAdd">
        <el-icon style="margin-right: 4px"><Plus /></el-icon>新增字段
      </el-button>
    </el-card>

    <el-dialog v-model="editVisible" title="编辑字段" width="520px">
      <el-form label-width="90px">
        <el-form-item label="字段key">
          <el-input :model-value="editRow?.key" disabled />
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="editForm.label" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="editForm.dtype" style="width: 100%">
            <el-option label="文本" value="text" />
            <el-option label="数字" value="number" />
            <el-option label="日期" value="date" />
            <el-option label="下拉选项" value="select" />
            <el-option label="布尔（开关）" value="boolean" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editForm.dtype === 'select'" label="选项">
          <el-select v-model="editForm.options" multiple filterable allow-create default-first-option placeholder="输入后回车添加" style="width: 100%">
            <el-option v-for="o in editForm.options" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="列表显示">
          <el-switch v-model="editForm.show_in_list" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="addVisible" title="新增字段" width="520px">
      <el-form label-width="90px">
        <el-form-item label="显示名称" required>
          <el-input v-model="addForm.label" placeholder="如：本科学校" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="addForm.dtype" style="width: 100%">
            <el-option label="文本" value="text" />
            <el-option label="数字" value="number" />
            <el-option label="日期" value="date" />
            <el-option label="下拉选项" value="select" />
            <el-option label="布尔（开关）" value="boolean" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="addForm.dtype === 'select'" label="选项">
          <el-select v-model="addForm.options" multiple filterable allow-create default-first-option placeholder="输入后回车添加" style="width: 100%">
            <el-option v-for="o in addForm.options" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="列表显示">
          <el-switch v-model="addForm.show_in_list" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" @click="addField">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, ArrowUp, Plus } from '@element-plus/icons-vue'
import api from '../api'

const entity = ref('people')
const defs = ref([])
const loading = ref(false)
const editVisible = ref(false)
const editRow = ref(null)
const editForm = reactive({ label: '', dtype: '', options: [], show_in_list: true })
const addVisible = ref(false)
const addForm = reactive({ label: '', dtype: 'text', options: [], show_in_list: false })

const DTYPE_LABEL = { text: '文本', number: '数字', date: '日期', select: '下拉', boolean: '开关' }
const dtypeLabel = (d) => DTYPE_LABEL[d] || d
const UNIQUE_KEYS = { people: 'uid', projects: 'project_no', papers: 'title', ip: 'title', awards: 'award_name' }
const isUnique = (row) => row.key === UNIQUE_KEYS[entity.value]

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/fields', { params: { entity: entity.value } })
    defs.value = data
  } finally {
    loading.value = false
  }
}

// 统一字段更新——所有字段（不论来源）走同一条路径
async function saveField(row, patch) {
  await api.put(`/fields/${entity.value}/${row.key}`, patch)
  await load()
  window.dispatchEvent(new CustomEvent('fields-changed', { detail: { entity: entity.value } }))
}

async function toggleShow(row, v) {
  await saveField(row, { show_in_list: v })
}

async function toggleEnabled(row, v) {
  await saveField(row, { enabled: v })
}

function openEdit(row) {
  editRow.value = row
  editForm.label = row.label
  editForm.dtype = row.dtype
  editForm.options = [...(row.options || [])]
  editForm.show_in_list = row.show_in_list !== false
  editVisible.value = true
}

async function saveEdit() {
  if (!editForm.label.trim()) return ElMessage.warning('显示名称不能为空')
  const row = editRow.value
  await saveField(row, {
    label: editForm.label,
    dtype: editForm.dtype,
    options: editForm.dtype === 'select' ? editForm.options : [],
    show_in_list: editForm.show_in_list,
    sort: row.sort,
  })
  ElMessage.success('已保存')
  editVisible.value = false
}

function openAdd() {
  Object.assign(addForm, { label: '', dtype: 'text', options: [], show_in_list: false })
  addVisible.value = true
}

async function addField() {
  if (!addForm.label.trim()) return ElMessage.warning('显示名称不能为空')
  if (addForm.dtype === 'select' && !addForm.options.length) {
    return ElMessage.warning('下拉选项至少填一个')
  }
  await api.post('/fields', {
    entity: entity.value,
    label: addForm.label,
    dtype: addForm.dtype,
    options: addForm.options,
    show_in_list: addForm.show_in_list,
  })
  ElMessage.success('已添加')
  addVisible.value = false
  load()
  window.dispatchEvent(new CustomEvent('fields-changed', { detail: { entity: entity.value } }))
}

async function moveUp(index) {
  if (index <= 0) return
  const items = defs.value
  const a = items[index]     // 当前行（要上移的）
  const b = items[index - 1] // 上一行（要下移的）
  if (!a || !b) return

  // 交换a和b的位置
  await reorderAll(items, index - 1, index)
}

async function moveDown(index) {
  const items = defs.value
  if (index >= items.length - 1) return
  const a = items[index]     // 当前行（要下移的）
  const b = items[index + 1] // 下一行（要上移的）
  if (!a || !b) return

  // 交换a和b的位置
  await reorderAll(items, index, index + 1)
}

async function reorderAll(items, fromIdx, toIdx) {
  // 创建一个新的排序顺序：交换fromIdx和toIdx的位置，其他保持不变
  const newOrder = [...items]
  const [moved] = newOrder.splice(fromIdx, 1)
  newOrder.splice(toIdx, 0, moved)

  // 重新分配所有sort值（基于新位置的索引 * 10），所有字段统一走 PUT /fields/{entity}/{key}
  const promises = []
  for (let i = 0; i < newOrder.length; i++) {
    const field = newOrder[i]
    const newSort = i * 10
    promises.push(api.put(`/fields/${entity.value}/${field.key}`, { sort: newSort }))
  }

  await Promise.all(promises)
  await load()
}

watch(entity, load)
onMounted(load)
</script>

<style scoped>
.muted {
  color: #999;
  font-size: 12px;
  margin-left: 8px;
}
</style>
