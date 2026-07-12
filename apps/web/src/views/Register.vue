<template>
  <div class="register-page">
    <el-card class="register-card" shadow="always">
      <div class="header">
        <el-icon class="logo"><Headset /></el-icon>
        <div>
          <h2>注册新账号</h2>
          <p>加入 kk-mis，开启高效办公</p>
        </div>
      </div>

      <el-steps :active="step" finish-status="success" align-center class="steps">
        <el-step title="账号" />
        <el-step title="信息" />
        <el-step title="确认" />
      </el-steps>

      <!-- 步骤1：账号信息 -->
      <el-form v-if="step === 0" ref="f1" :model="form" :rules="r1" label-position="top" size="large">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :prefix-icon="User" placeholder="3-50位字母/数字/下划线" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" :prefix-icon="Lock" type="password" show-password placeholder="至少6位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input v-model="form.confirm" :prefix-icon="Lock" type="password" show-password placeholder="再次输入密码" />
        </el-form-item>
      </el-form>

      <!-- 步骤2：个人信息 -->
      <el-form v-else-if="step === 1" ref="f2" :model="form" :rules="r2" label-position="top" size="large">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="真实姓名" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="选填" />
        </el-form-item>
      </el-form>

      <!-- 步骤3：确认 -->
      <div v-else class="confirm">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户名">{{ form.username }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ form.name }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ form.phone || '—' }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ form.email || '—' }}</el-descriptions-item>
        </el-descriptions>
        <p class="note">注册后获得「普通员工」权限，可使用工作台 / 会议纪要 / OA 办公等功能。</p>
      </div>

      <div class="actions">
        <el-button v-if="step > 0" @click="step--">上一步</el-button>
        <el-button v-if="step < 2" type="primary" @click="next">下一步</el-button>
        <el-button v-else type="primary" :loading="loading" @click="submit">完成注册</el-button>
      </div>

      <p class="to-login">已有账号？<router-link to="/login">直接登录</router-link></p>
      <el-divider>第三方登录</el-divider>
      <el-button class="oauth-btn" @click="oauthLogin('github')">GitHub 登录</el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Headset, Lock, User } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const step = ref(0)
const loading = ref(false)
const f1 = ref<FormInstance>()
const f2 = ref<FormInstance>()
const form = reactive<any>({ username: '', password: '', confirm: '', name: '', phone: '', email: '' })

const r1 = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]{3,50}$/, message: '3-50位字母/数字/下划线', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '至少6位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_r: any, v: string, cb: (e?: Error) => void) =>
        v === form.password ? cb() : cb(new Error('两次密码不一致')),
      trigger: 'blur',
    },
  ],
}
const r2 = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
}

async function next() {
  const f = step.value === 0 ? f1.value : f2.value
  if (!f) return
  await f.validate((valid) => {
    if (valid) step.value++
  })
}

async function submit() {
  loading.value = true
  try {
    await userStore.register({
      username: form.username,
      password: form.password,
      name: form.name,
      phone: form.phone || undefined,
      email: form.email || undefined,
    })
    ElMessage.success('注册成功，欢迎加入')
    router.push('/')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}

function oauthLogin(provider: string) {
  window.location.href = import.meta.env.BASE_URL + 'admin/api/v1/auth/oauth/' + provider + '/authorize'
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--el-bg-color-page) 0%, var(--el-color-primary-light-9) 100%);
}
.register-card {
  width: 440px;
  border-radius: 10px;
  padding: 12px 16px;
}
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.logo {
  font-size: 36px;
  color: var(--el-color-primary);
}
.header h2 {
  margin: 0;
  font-size: 20px;
}
.header p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.steps {
  margin-bottom: 24px;
}
.confirm .note {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
.to-login {
  text-align: center;
  margin: 16px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.to-login a {
  color: var(--el-color-primary);
  text-decoration: none;
}
.oauth-btn { width: 100%; margin-top: 4px; }
</style>
