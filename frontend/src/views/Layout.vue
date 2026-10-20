<template>
  <el-container class="app-shell">
    <!-- Sidebar (icon-only) -->
    <el-aside width="60px" class="sidebar">
      <div class="logo-mark" title="课题组信息管理系统">
        <Logo :size="23" />
      </div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="transparent"
        text-color="#8b96ad"
        active-text-color="#ffffff"
        class="sidebar-icon"
      >
        <el-menu-item v-for="item in navItems" :key="item.path" :index="item.path">
          <el-tooltip :content="item.label" placement="right" :show-after="250" effect="dark">
            <el-icon><component :is="item.icon" /></el-icon>
          </el-tooltip>
        </el-menu-item>
      </el-menu>
      <div v-if="adminItems.length" class="sidebar-divider"></div>
      <el-menu
        v-if="adminItems.length"
        :default-active="$route.path"
        router
        background-color="transparent"
        text-color="#8b96ad"
        active-text-color="#ffffff"
        class="sidebar-icon"
      >
        <el-menu-item v-for="item in adminItems" :key="item.path" :index="item.path">
          <el-tooltip :content="item.label" placement="right" :show-after="250" effect="dark">
            <el-icon><component :is="item.icon" /></el-icon>
          </el-tooltip>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- Main area -->
    <el-container>
      <el-header class="header">
        <span class="page-title">{{ $route.meta.title }}</span>
        <div class="header-right">
          <!-- Search trigger -->
          <button class="search-btn" @click="commandK.openPanel()">
            <el-icon><Search /></el-icon>
            <span>搜索</span>
            <kbd class="kbd">⌘K</kbd>
          </button>

          <!-- User menu -->
          <el-dropdown trigger="click" @command="onUserCommand">
            <div class="user-chip">
              <span class="user-avatar">{{ avatarText }}</span>
              <span class="user-name">{{ user.username }}</span>
              <el-icon class="user-caret"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <div class="user-dropdown-head">
                  <div class="user-dropdown-name">{{ user.username }}</div>
                  <el-tag size="small" :type="user.role === 'admin' ? 'warning' : 'info'" effect="light">
                    {{ user.role === 'admin' ? '管理员' : '只读' }}
                  </el-tag>
                </div>
                <el-dropdown-item command="password" divided :icon="Key">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" :icon="SwitchButton" class="logout-item">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>

  <!-- Command K global search -->
  <CommandK ref="commandK" @select="onSearchSelect" />

  <!-- Password dialog -->
  <el-dialog v-model="pwVisible" title="修改密码" width="400px">
    <el-form label-width="80px">
      <el-form-item label="原密码">
        <el-input v-model="pw.old_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="pw.new_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="确认">
        <el-input v-model="pw.confirm" type="password" show-password />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="pwVisible = false">取消</el-button>
      <el-button type="primary" @click="changePassword">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  User, FolderOpened, Document, Medal, Filter, Search,
  DocumentCopy, ArrowDown, Key, SwitchButton, Trophy,
} from '@element-plus/icons-vue'
import api, { clearAuth, currentUser, isAdmin } from '../api'
import CommandK from '../components/CommandK.vue'
import Logo from '../components/Logo.vue'

const router = useRouter()
const user = currentUser
const commandK = ref(null)
const pwVisible = ref(false)
const pw = reactive({ old_password: '', new_password: '', confirm: '' })

const allNavItems = [
  { path: '/people',   label: '人员',       icon: User },
  { path: '/projects', label: '项目',       icon: FolderOpened },
  { path: '/papers',   label: '论文',       icon: Document },
  { path: '/ip',       label: '知识产权',   icon: Medal },
  { path: '/awards',   label: '奖励荣誉',   icon: Trophy },
  { path: '/pdfs',     label: '文献库',     icon: DocumentCopy, adminOnly: true },
  { path: '/query',    label: '筛选与导出', icon: Filter,      adminOnly: true },
]
const navItems = computed(() => allNavItems.filter((i) => isAdmin.value || !i.adminOnly))

const adminItems = computed(() =>
  isAdmin.value
    ? [
        { path: '/fields',   label: '字段管理',   icon: SwitchButton },
        { path: '/archives', label: '数据存档',   icon: FolderOpened },
        { path: '/users',    label: '账号管理',   icon: User },
      ]
    : []
)

const avatarText = computed(() => (user.username || '?').slice(0, 1).toUpperCase())

function onUserCommand(cmd) {
  if (cmd === 'password') pwVisible.value = true
  else if (cmd === 'logout') logout()
}

function onSearchSelect({ type, id }) {
  // Navigate to the module's list and open its Drawer via event bus
  const routes = { people: '/people', projects: '/projects', papers: '/papers', ip: '/ip' }
  if (routes[type]) {
    router.push(routes[type])
    // Small delay to let the view mount, then trigger drawer open
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent('drawer:open', { detail: { type, id } }))
    }, 50)
  }
}

async function changePassword() {
  if (pw.new_password !== pw.confirm) return ElMessage.error('两次输入的新密码不一致')
  await api.post('/auth/change-password', {
    old_password: pw.old_password,
    new_password: pw.new_password,
  })
  ElMessage.success('密码已修改')
  pwVisible.value = false
  Object.assign(pw, { old_password: '', new_password: '', confirm: '' })
}

function logout() {
  api.post('/auth/logout').catch(() => {})
  clearAuth()
  router.push('/login')
}
</script>

<style scoped>
.app-shell {
  height: 100vh;
  height: 100dvh;
}

/* ─── Sidebar ─────────────────────────────────────────── */
.sidebar {
  background: #171d2b;
  display: flex;
  flex-direction: column;
}

.logo-mark {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #d7deeb;
  cursor: default;
  user-select: none;
  transition: color 0.2s;
}
.logo-mark:hover {
  color: #ffffff;
}

.sidebar-divider {
  height: 1px;
  margin: 8px 14px;
  background: rgba(255, 255, 255, 0.07);
}

.sidebar-icon {
  border-right: none;
  --el-menu-hover-bg-color: transparent;
}
:deep(.el-menu-item) {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  margin: 4px auto;
  border-radius: 11px;
  transition: background-color 0.2s, color 0.2s, transform 0.15s;
}
:deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.07);
  color: #e5ebf5;
}
:deep(.el-menu-item.is-active) {
  background: var(--el-color-primary);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}
:deep(.el-menu-item .el-icon) {
  font-size: 18px;
  margin: 0;
}

/* ─── Header ──────────────────────────────────────────── */
.header {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eceef2;
  padding: 0 20px;
  height: 56px;
  z-index: 10;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  letter-spacing: 0.2px;
}

.search-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #f4f5f8;
  border: 1px solid transparent;
  border-radius: 9px;
  padding: 6px 12px;
  color: #6b7280;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
}
.search-btn:hover {
  background: var(--hpgc-primary-soft);
  border-color: #bfdbfe;
  color: var(--el-color-primary);
}
.search-btn:active {
  transform: scale(0.97);
}
.kbd {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 11px;
  font-family: inherit;
  margin-left: 2px;
}

/* ─── User chip ───────────────────────────────────────── */
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 4px;
  border-radius: 999px;
  cursor: pointer;
  transition: background-color 0.18s;
  outline: none;
}
.user-chip:hover {
  background: #f4f5f8;
}
.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  flex-shrink: 0;
}
.user-name {
  font-size: 13px;
  color: #374151;
  font-weight: 500;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-caret {
  font-size: 12px;
  color: #9ca3af;
  transition: transform 0.2s;
}

.main {
  --el-main-padding: 16px 20px;
}

@media (max-width: 768px) {
  .header {
    padding: 8px 12px;
  }
  .main {
    --el-main-padding: 10px;
  }
  .page-title {
    font-size: 14px;
  }
  .search-btn span,
  .search-btn .kbd {
    display: none;
  }
  .user-name {
    display: none;
  }
  .user-chip {
    padding: 4px;
  }
  .user-caret {
    display: none;
  }
}
</style>

<style>
/* 用户下拉（teleport 到 body，需全局样式） */
.user-dropdown-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 12px 10px;
}
.user-dropdown-name {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}
.el-dropdown-menu__item.logout-item {
  color: #ef4444;
}
.el-dropdown-menu__item.logout-item:not(.is-disabled):hover {
  background: #fdecec;
  color: #ef4444;
}
</style>
