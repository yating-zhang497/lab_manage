<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <div class="toolbar">
        <div class="toolbar-actions">
          <el-button type="primary" @click="openCreate">
            <el-icon style="margin-right: 4px"><Plus /></el-icon>新增账号
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="username" label="用户名" min-width="160" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.username === 'admin'" type="danger" size="small">超级管理员</el-tag>
            <el-tag v-else-if="row.role === 'admin'" type="warning" size="small">管理员</el-tag>
            <el-tag v-else type="info" size="small">只读</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="person_id" label="关联人员" width="120">
          <template #default="{ row }">{{ row.person_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.must_change_password" type="warning" size="small">待改密</el-tag>
            <el-tag v-else type="success" size="small">正常</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" @click="openResetPw(row)">重置密码</el-button>
            <el-button
              v-if="row.username !== 'admin'"
              size="small"
              type="danger"
              plain
              @click="remove(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增账号 -->
    <el-dialog v-model="createVisible" title="新增账号" width="420px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="createForm.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="初始密码" required>
          <el-input v-model="createForm.password" type="password" show-password placeholder="至少8位" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option value="readonly" label="只读用户" />
            <el-option value="admin" label="管理员" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createUser">创建</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="resetVisible" title="重置密码" width="420px">
      <el-form :model="resetForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input :model-value="resetForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input v-model="resetForm.password" type="password" show-password placeholder="至少8位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="resetPassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '../api'

const rows = ref([])
const loading = ref(false)
const saving = ref(false)

const createVisible = ref(false)
const createForm = reactive({ username: '', password: '', role: 'readonly' })

const resetVisible = ref(false)
const resetForm = reactive({ username: '', password: '' })

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/users')
    rows.value = data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(createForm, { username: '', password: '', role: 'readonly' })
  createVisible.value = true
}

async function createUser() {
  if (!createForm.username.trim()) return ElMessage.warning('用户名不能为空')
  if (createForm.password.length < 8) return ElMessage.warning('密码至少8位')
  saving.value = true
  try {
    const { data } = await api.post('/users', { ...createForm })
    ElMessage.success(`账号 ${data.username} 创建成功`)
    createVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

function openResetPw(row) {
  Object.assign(resetForm, { username: row.username, password: '' })
  resetVisible.value = true
}

async function resetPassword() {
  if (!resetForm.password || resetForm.password.length < 8) {
    return ElMessage.warning('密码至少8位')
  }
  saving.value = true
  try {
    await api.put(`/users/${resetForm.username}`, { password: resetForm.password })
    ElMessage.success('密码已重置')
    resetVisible.value = false
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除账号 ${row.username}？此操作不可恢复。`, '删除账号', {
    type: 'warning',
  })
  await api.delete(`/users/${row.username}`)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>
