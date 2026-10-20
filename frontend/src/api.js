import axios from 'axios'
import { ElMessage } from 'element-plus'
import { computed, reactive } from 'vue'

const api = axios.create({ baseURL: '/api', timeout: 300000 })

// 数组参数序列化为重复键（statuses=a&statuses=b），而非带括号的 statuses[]=a，
// 后者会被 FastAPI 的 List[str] = Query() 当成未知键而忽略（如文献库"未关联"筛选失效）
api.defaults.paramsSerializer = (params) => {
  const sp = new URLSearchParams()
  const visit = (key, val) => {
    if (val === undefined || val === null) return
    if (Array.isArray(val)) val.forEach((v) => visit(key, v))
    else sp.append(key, val)
  }
  Object.entries(params).forEach(([k, v]) => visit(k, v))
  return sp.toString()
}

export const currentUser = reactive(JSON.parse(localStorage.getItem('im_user') || '{}'))
export const isAdmin = computed(() => currentUser.role === 'admin')

export function getToken() {
  return localStorage.getItem('im_token') || ''
}
export function setAuth(token, user) {
  localStorage.setItem('im_token', token)
  localStorage.setItem('im_user', JSON.stringify(user))
  Object.assign(currentUser, user)
}
export function clearAuth() {
  localStorage.removeItem('im_token')
  localStorage.removeItem('im_user')
  Object.keys(currentUser).forEach((k) => delete currentUser[k])
}

api.interceptors.request.use((cfg) => {
  const t = getToken()
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const status = err.response?.status
    let detail = err.response?.data?.detail
    // blob responses (downloadPost) swallow JSON error bodies; parse them back out
    if (err.response?.data instanceof Blob && err.response.data.type && err.response.data.type.includes('json')) {
      try {
        const json = JSON.parse(await err.response.data.text())
        detail = json.detail
      } catch { /* not JSON, ignore */ }
    }
    let msg = detail || err.message
    if (Array.isArray(detail)) {
      msg = detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
    }
    if (status === 401 && location.pathname !== '/login') {
      clearAuth()
      location.href = '/login'
    } else if (msg) {
      ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    }
    return Promise.reject(err)
  }
)

export default api

function saveBlob(blob, filename) {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}

export async function downloadFile(url, filename, params = {}) {
  const res = await api.get(url, { params, responseType: 'blob' })
  saveBlob(res.data, filename)
}

export async function downloadPost(url, filename, body) {
  const res = await api.post(url, body, { responseType: 'blob' })
  saveBlob(res.data, filename)
}
