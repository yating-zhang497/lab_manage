<template>
  <div class="login-bg">
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>
    <div class="login-card">
      <div class="login-header">
        <div class="login-logo">
          <Logo :size="30" gradient />
        </div>
        <h2>课题组信息管理系统</h2>
        <p class="login-sub">实验室信息一站式管理平台</p>
      </div>
      <el-form @submit.prevent="doLogin" class="login-form">
        <el-form-item>
          <el-input
            v-model="form.username"
            placeholder="账号（学号/工号）"
            size="large"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="doLogin"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="login-btn"
          :loading="loading"
          @click="doLogin"
        >
          登 录
        </el-button>
      </el-form>
      <div class="login-footer">
        <span>© {{ new Date().getFullYear() }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import api, { setAuth } from '../api'
import Logo from '../components/Logo.vue'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function doLogin() {
  if (!form.username || !form.password) return ElMessage.warning('请输入账号和密码')
  loading.value = true
  try {
    const { data } = await api.post('/auth/login', form)
    setAuth(data.token, { username: data.username, role: data.role })
    if (data.must_change_password) {
      ElMessage.warning('当前为初始密码，请尽快在右上角修改密码')
    }
    router.push('/')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-bg {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, #0d1424 0%, #16223c 55%, #1b2a44 100%);
  position: relative;
  overflow: hidden;
}
.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.13;
  animation: float 12s ease-in-out infinite;
  will-change: transform;
}
.orb-1 {
  width: 520px;
  height: 520px;
  background: #3b82f6;
  top: -160px;
  left: -110px;
  animation-delay: 0s;
}
.orb-2 {
  width: 420px;
  height: 420px;
  background: #6366f1;
  bottom: -120px;
  right: -90px;
  animation-delay: -4s;
}
.orb-3 {
  width: 300px;
  height: 300px;
  background: #22d3ee;
  bottom: 28%;
  left: 18%;
  opacity: 0.07;
  animation-delay: -8s;
}
@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(18px, -18px) scale(1.04); }
  66% { transform: translate(-10px, 14px) scale(0.96); }
}

.login-card {
  width: 400px;
  max-width: calc(100vw - 32px);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(20px);
  box-shadow: 0 24px 64px rgba(2, 8, 23, 0.45);
  padding: 36px 36px 26px;
  position: relative;
  z-index: 1;
  animation: card-in 0.55s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}
.login-logo {
  width: 54px;
  height: 54px;
  margin: 0 auto 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 15px;
  background: var(--hpgc-primary-soft);
}
.login-header h2 {
  margin: 0 0 6px;
  color: #111827;
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 0.3px;
}
.login-sub {
  margin: 0;
  color: #9ca3af;
  font-size: 13px;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 18px;
}
.login-form :deep(.el-input__wrapper) {
  border-radius: 10px;
  padding: 4px 12px;
  box-shadow: 0 0 0 1px #e5e7eb inset;
  transition: box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #c3cad6 inset;
}
.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset,
    0 0 0 3px rgba(59, 130, 246, 0.12);
}

.login-btn {
  width: 100%;
  height: 42px;
  margin-top: 4px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 4px;
  border-radius: 10px;
}

.login-footer {
  text-align: center;
  margin-top: 22px;
  color: #c3c9d4;
  font-size: 12px;
}
</style>
