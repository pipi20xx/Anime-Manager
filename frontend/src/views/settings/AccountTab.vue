<script setup lang="ts">
/**
 * AccountTab — 账号与安全
 *
 * 功能: 密码修改、2FA、会话管理、JWT永不过期
 */
import { ref, reactive, onMounted } from 'vue'
import { authApi, configApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import { useSystemStore } from '@/stores'

defineOptions({ name: 'AccountTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()
const systemStore = useSystemStore()

// 密码修改
const pwdForm = reactive({ old_password: '', new_password: '' })
const confirmPassword = ref('')
const savingPwd = ref(false)

// 2FA
const isOtpEnabled = ref(false)
const showOtpSetup = ref(false)
const otpConfirmCode = ref('')
const otpSetupData = reactive({ secret: '', qr_code: '' })

// 会话管理
const sessions = ref<any[]>([])
const loadingSessions = ref(false)
const revokingSessionId = ref<number | null>(null)
const revokingAll = ref(false)
const jwtNeverExpire = ref(false)
const savingJwtConfig = ref(false)

// 用户信息
const username = ref(systemStore.username || '')
const lastLogin = ref('')

async function fetchAccountInfo() {
  try {
    const meRes = await authApi.me()
    if (meRes.username) {
      username.value = meRes.username
      isOtpEnabled.value = meRes.is_otp_enabled
      lastLogin.value = meRes.last_login || ''
    }
  } catch (e) {
    console.error(e)
  }
}

async function fetchConfig() {
  try {
    const res = await configApi.getConfig()
    jwtNeverExpire.value = res.jwt_never_expire || false
  } catch (e) {
    console.error('获取配置失败', e)
  }
}

async function fetchSessions() {
  loadingSessions.value = true
  try {
    const res = await authApi.getSessions()
    sessions.value = res.sessions || []
  } catch (e) {
    console.error('获取会话失败', e)
    sessions.value = []
  } finally {
    loadingSessions.value = false
  }
}

async function handleUpdatePassword() {
  if (!pwdForm.old_password || !pwdForm.new_password) {
    showError('请填写完整信息')
    return
  }
  if (pwdForm.new_password !== confirmPassword.value) {
    showError('两次密码输入不一致')
    return
  }
  savingPwd.value = true
  try {
    await authApi.changePassword(pwdForm)
    success('密码已更新')
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    confirmPassword.value = ''
  } catch (e: any) {
    showError(e?.message || '修改失败')
  } finally {
    savingPwd.value = false
  }
}

async function handleJwtNeverExpireChange(value: boolean | null) {
if (value === null) return
  savingJwtConfig.value = true
  try {
    const res = await configApi.getConfig()
    const configData = { ...res, jwt_never_expire: value }
    await configApi.saveConfig(configData)
    jwtNeverExpire.value = value
    await fetchSessions()
    success(value ? '所有会话已设置为永不过期（10年）' : '所有会话已设置为24小时自动过期')
  } catch (err: any) {
    showError(err?.message || '保存失败')
  } finally {
    savingJwtConfig.value = false
  }
}

async function handleRevokeSession(sessionId: number) {
  revokingSessionId.value = sessionId
  try {
    await authApi.deleteSession(sessionId)
    success('会话已踢出')
    await fetchSessions()
  } catch (err: any) {
    showError(err?.message || '踢出失败')
  } finally {
    revokingSessionId.value = null
  }
}

async function handleRevokeAll() {
  const ok = await confirm('确定要踢出所有其他设备吗？')
  if (!ok) return
  revokingAll.value = true
  try {
    await authApi.deleteAllSessions()
    success('已踢出所有其他设备')
    await fetchSessions()
  } catch (err: any) {
    showError(err?.message || '操作失败')
  } finally {
    revokingAll.value = false
  }
}

async function handleOtpSwitch(val: boolean | null) {
  if (!val) {
    // 关闭 2FA
    try {
      await authApi.disable2fa()
      isOtpEnabled.value = false
      success('2FA已禁用')
    } catch (e) {
      showError('操作失败')
    }
    return
  }
  // 开启 2FA
  try {
    const res = await authApi.setup2fa()
    otpSetupData.secret = res.secret
    otpSetupData.qr_code = res.qr_code
    showOtpSetup.value = true
  } catch (e) {
    showError('2FA初始化失败')
  }
}

async function confirmEnableOtp() {
  try {
    await authApi.enable2fa(otpConfirmCode.value)
    isOtpEnabled.value = true
    showOtpSetup.value = false
    otpConfirmCode.value = ''
    success('2FA已开启')
  } catch (err: any) {
    showError(err?.message || '验证码无效')
  }
}

function formatTime(isoString: string) {
  if (!isoString) return '未知'
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatExpiresIn(seconds: number) {
  if (seconds <= 0) return '已过期'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}小时${minutes}分钟后过期`
  return `${minutes}分钟后过期`
}

function handleLogout() {
  systemStore.logout()
  window.location.href = '/login'
}

onMounted(() => {
  fetchAccountInfo()
  fetchSessions()
  fetchConfig()
})
</script>

<template>
  <div class="account-tab">
    <v-row>
      <!-- 凭据管理 -->
      <v-col cols="12" md="6">
        <v-card class="glass-card">
          <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-key-outline</v-icon>
            <span class="text-subtitle-1 font-weight-bold">凭据管理</span>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <v-text-field
              v-model="pwdForm.old_password"
              label="当前密码"
              type="password"
              variant="outlined"
              density="compact"
              class="mb-3"
              hide-details
            />
            <v-text-field
              v-model="pwdForm.new_password"
              label="新密码"
              type="password"
              variant="outlined"
              density="compact"
              class="mb-3"
              hide-details
            />
            <v-text-field
              v-model="confirmPassword"
              label="确认新密码"
              type="password"
              variant="outlined"
              density="compact"
              class="mb-4"
              hide-details
            />
            <v-btn
              variant="tonal" color="primary"
              block
              prepend-icon="mdi-lock-reset"
              :loading="savingPwd"
              @click="handleUpdatePassword"
            >
              立即更新密码
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- 2FA -->
      <v-col cols="12" md="6">
        <v-card class="glass-card">
          <v-card-title class="pa-4 pb-2 d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-shield-check-outline</v-icon>
            <span class="text-subtitle-1 font-weight-bold">多重身份验证 (2FA)</span>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <div class="switch-row-lg">
              <div>
                <div class="switch-label">TOTP 动态验证码</div>
                <div class="switch-desc">
                  {{ isOtpEnabled ? '状态：已保护 (推荐)' : '状态：未保护 (高风险)' }}
                </div>
              </div>
              <v-switch
                :model-value="isOtpEnabled"
                @update:model-value="handleOtpSwitch"
                density="compact"
                hide-details
                color="primary"
              />
            </div>
            <v-alert v-if="!isOtpEnabled" type="warning" variant="tonal" density="compact">
              未开启 2FA 时，建议立即开启以防密码泄露。
            </v-alert>
            <v-alert v-else type="success" variant="tonal" density="compact">
              每次登录时，系统都会要求您提供 6 位动态码。
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 会话管理 -->
    <v-card class="glass-card mt-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
        <div class="d-flex align-center ga-2">
          <v-icon color="primary" size="20">mdi-devices</v-icon>
          <span class="text-subtitle-1 font-weight-bold">会话管理</span>
        </div>
        <v-btn
          size="small"
          color="error"
          variant="tonal"
          :loading="revokingAll"
          :disabled="sessions.length <= 1"
          @click="handleRevokeAll"
        >
          踢出所有其他设备
        </v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <!-- JWT 永不过期 -->
        <div class="switch-row-lg">
          <div>
            <div class="switch-label">JWT 令牌永不过期</div>
            <div class="switch-desc">开启后登录令牌将不会自动过期（10年），关闭后为24小时自动过期</div>
          </div>
          <v-switch
            :model-value="jwtNeverExpire"
            @update:model-value="handleJwtNeverExpireChange"
            :loading="savingJwtConfig"
            density="compact"
            hide-details
            color="primary"
          />
        </div>
        <v-alert v-if="jwtNeverExpire" type="warning" variant="tonal" density="compact" class="mb-4">
          永不过期会降低安全性，建议仅在可信环境中使用。
        </v-alert>

        <v-divider class="mb-4" />

        <!-- 会话列表 -->
        <div v-if="loadingSessions" class="d-flex justify-center pa-4">
          <v-progress-circular indeterminate color="primary" size="24" />
        </div>
        <template v-else>
          <div v-if="sessions.length > 0">
            <div v-for="session in sessions" :key="session.id" class="d-flex align-center justify-space-between pa-3 rounded-lg mb-2" style="background: rgba(128,128,128,0.06)">
              <div class="d-flex align-center ga-3">
                <v-icon :color="session.is_current ? 'primary' : 'grey'" size="24">mdi-cellphone-link</v-icon>
                <div>
                  <div class="d-flex align-center ga-2">
                    <span class="text-body-2 font-weight-medium">{{ session.browser_name }} / {{ session.os_name }}</span>
                    <v-chip v-if="session.is_current" size="x-small" color="success" variant="tonal">当前会话</v-chip>
                  </div>
                  <div class="text-caption text-medium-emphasis">IP: {{ session.ip_address }}</div>
                  <div class="text-caption text-medium-emphasis">
                    登录时间: {{ formatTime(session.created_at) }} |
                    过期: {{ formatExpiresIn(session.expires_in) }}
                  </div>
                </div>
              </div>
              <v-btn
                v-if="!session.is_current"
                size="small"
                color="error"
                variant="tonal"
                :loading="revokingSessionId === session.id"
                @click="handleRevokeSession(session.id)"
              >
                踢出
              </v-btn>
            </div>
          </div>
          <div v-else class="text-center text-medium-emphasis pa-4">暂无登录会话</div>
        </template>
      </v-card-text>
    </v-card>

    <!-- 退出登录 -->
    <v-card v-if="username" class="glass-card mt-4">
      <v-card-text class="pa-4 d-flex align-center justify-space-between">
        <div>
          <div class="text-body-1 font-weight-medium">当前登录：{{ username }}</div>
          <div class="text-caption text-medium-emphasis">最近登录时间：{{ lastLogin || '暂无' }}</div>
        </div>
        <v-btn color="error" variant="tonal" @click="handleLogout">退出登录</v-btn>
      </v-card-text>
    </v-card>

    <!-- 2FA 设置弹窗 -->
    <v-dialog v-model="showOtpSetup" max-width="400">
      <v-card>
<v-card-title class="pa-4 d-flex align-center ga-2">
<v-icon color="primary" size="20">mdi-shield-check-outline</v-icon>
<span>设置双重身份验证</span>
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="showOtpSetup = false" />
</v-card-title>
        <v-divider />
        <v-card-text class="pa-4 text-center">
          <div class="text-body-2 mb-4">请使用验证器应用扫描下方二维码</div>
          <div v-if="otpSetupData.qr_code" class="d-flex justify-center mb-4">
            <v-img :src="otpSetupData.qr_code" max-width="200" max-height="200" />
          </div>
          <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
            密钥: {{ otpSetupData.secret }}
          </v-alert>
          <v-text-field
            v-model="otpConfirmCode"
            label="验证码"
            placeholder="输入 6 位验证码确认"
            variant="outlined"
            density="compact"
            maxlength="6"
            hide-details
            class="mb-3"
          />
          <v-btn variant="tonal" color="primary" block prepend-icon="mdi-check" @click="confirmEnableOtp">确认开启</v-btn>
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>
