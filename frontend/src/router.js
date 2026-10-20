import { createRouter, createWebHistory } from 'vue-router'
import api, { getToken, clearAuth, currentUser } from './api'
import Layout from './views/Layout.vue'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/Login.vue') },
  {
    path: '/',
    component: Layout,
    redirect: '/papers',
    children: [
      { path: 'people', name: 'people', component: () => import('./views/People.vue'), meta: { title: '人员' } },
      { path: 'projects', name: 'projects', component: () => import('./views/Projects.vue'), meta: { title: '项目' } },
      { path: 'papers', name: 'papers', component: () => import('./views/Papers.vue'), meta: { title: '论文' } },
      { path: 'ip', name: 'ip', component: () => import('./views/IP.vue'), meta: { title: '知识产权' } },
      { path: 'awards', name: 'awards', component: () => import('./views/Awards.vue'), meta: { title: '奖励荣誉' } },
      { path: 'pdfs', name: 'pdfs', component: () => import('./views/PDFs.vue'), meta: { title: '文献库', adminOnly: true } },
      { path: 'query', name: 'query', component: () => import('./views/QueryExport.vue'), meta: { title: '筛选与导出', adminOnly: true } },
      { path: 'fields', name: 'fields', component: () => import('./views/FieldsAdmin.vue'), meta: { title: '字段管理', adminOnly: true } },
      { path: 'archives', name: 'archives', component: () => import('./views/Archives.vue'), meta: { title: '数据存档', adminOnly: true } },
      { path: 'users', name: 'users', component: () => import('./views/UserAdmin.vue'), meta: { title: '账号管理', adminOnly: true } },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

let authChecked = false

router.beforeEach(async (to) => {
  if (to.path === '/login') return getToken() ? '/' : undefined
  if (!getToken()) return '/login'
  // 每个会话首次进入时验证 token（过期/失效则直接回登录页，避免页面闪现报错）
  if (!authChecked) {
    try {
      await api.get('/auth/me')
      authChecked = true
    } catch {
      clearAuth()
      return '/login'
    }
  }
  // 只读用户禁止访问管理员专属模块，重定向到论文页
  if (to.meta?.adminOnly && currentUser.role !== 'admin') {
    return '/papers'
  }
})

export default router
