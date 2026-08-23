<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { useSystemStore } from '@/stores'
import { useNotification } from '@/composables'

defineOptions({ name: 'LoginView' })

const router = useRouter()
const systemStore = useSystemStore()
const { success, error: showError } = useNotification()

const loading = ref(false)
const formValue = reactive({
  username: '',
  password: '',
})

async function handleLogin() {
  if (!formValue.username || !formValue.password) {
    showError('请填写完整信息')
    return
  }

  loading.value = true
  try {
    const res = await authApi.login(formValue)
    systemStore.loginSuccess(res.access_token, res.username)
    systemStore.connect()
    success('登录成功')
    router.push('/')
  } catch (err: any) {
    showError(err.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-app class="login-app">
    <v-main>
      <v-container fluid class="fill-height d-flex align-center justify-center">
        <v-card class="glass-card login-glass-panel pa-8" max-width="420" width="100%">
          <!-- 标题 -->
          <div class="text-center mb-6">
            <v-avatar class="liquid-avatar mb-4" size="64" rounded="xl">
              <img src="/favicon.svg" alt="番剧管家" class="app-logo" />
            </v-avatar>
            <h1 class="text-h5 font-weight-bold">番剧管家</h1>
            <p class="text-body-2 text-medium-emphasis mt-1">Anime Manager</p>
          </div>

          <!-- 表单 -->
          <v-form @submit.prevent="handleLogin">
            <v-text-field
              v-model="formValue.username"
              label="用户名"
              prepend-inner-icon="mdi-account"
              autocomplete="username"
              class="mb-3"
            />
            <v-text-field
              v-model="formValue.password"
              label="密码"
              type="password"
              prepend-inner-icon="mdi-lock"
              autocomplete="current-password"
              class="mb-4"
            />
            <v-btn
              type="submit"
              :loading="loading"
              block
              variant="tonal" color="primary"
              size="large"
              rounded="xl"
            >
              登 录
            </v-btn>

            <!-- 默认账号说明 -->
            <div class="text-center mt-4">
              <v-chip size="small" variant="tonal" color="info" label>
                <v-icon start size="14">mdi-information-outline</v-icon>
                默认账号: admin / admin123
              </v-chip>
            </div>
          </v-form>
        </v-card>
      </v-container>
    </v-main>
  </v-app>
</template>

<style scoped>
.app-logo {
  width: 40px;
  height: 40px;
  /* <img> 引入的 SVG 无法继承 currentColor，用 filter 着色 */
  filter: brightness(0) saturate(100%) invert(47%) sepia(98%) saturate(1925%) hue-rotate(234deg) brightness(96%) contrast(96%);
}

/* 登录页输入框 — 在玻璃面板上增加微底色，提升可读性 */
:deep(.v-field--variant-outlined .v-field__outline) {
  --v-field-border-opacity: 0.5 !important;
}

:deep(.v-field--variant-outlined.v-field--focused .v-field__outline) {
  --v-field-border-opacity: 1 !important;
}
</style>
