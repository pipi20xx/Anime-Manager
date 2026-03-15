<template>
  <div class="tab-wrapper">
    <n-space vertical size="large" style="margin-top: 16px;">
      <n-grid :cols="2" :x-gap="24" :y-gap="24" item-responsive>
        <n-gi span="2 m:1">
          <n-card title="凭据管理" size="small">
            <template #header-extra>
              <n-icon size="20" color="var(--n-primary-color)"><KeyIcon /></n-icon>
            </template>
            <n-form label-placement="top">
              <n-form-item label="当前密码">
                <n-input v-model:value="pwdForm.old_password" type="password" show-password-on="mousedown" placeholder="验证当前密码" />
              </n-form-item>
              <n-form-item label="新密码">
                <n-input v-model:value="pwdForm.new_password" type="password" show-password-on="mousedown" placeholder="设置新密码" />
              </n-form-item>
              <n-form-item label="确认新密码">
                <n-input v-model:value="confirmPassword" type="password" show-password-on="mousedown" placeholder="再次输入新密码" />
              </n-form-item>
              <n-button type="primary" block secondary :loading="savingPwd" @click="handleUpdatePasswordDirectly">立即更新密码</n-button>
            </n-form>
          </n-card>
        </n-gi>

        <n-gi span="2 m:1">
          <n-card title="多重身份验证 (2FA)" size="small">
            <template #header-extra>
              <n-icon size="20" class="shield-icon"><ShieldIcon /></n-icon>
            </template>
            <n-space vertical size="large">
              <div class="setting-item">
                <n-thing title="TOTP 动态验证码" :description="isOtpEnabled ? '状态：已保护 (推荐)' : '状态：未保护 (高风险)'" />
                <n-switch :value="isOtpEnabled" @update:value="handleOtpSwitch" />
              </div>
              <n-alert v-if="!isOtpEnabled" type="warning" title="安全风险提示">未开启 2FA 时，建议立即开启以防密码泄露。</n-alert>
              <n-alert v-else type="success" title="系统已受保护">每次登录时，系统都会要求您提供 6 位动态码。</n-alert>
            </n-space>
          </n-card>
        </n-gi>
      </n-grid>

      <n-card title="会话管理" size="medium" embedded>
        <template #header-extra>
          <n-button size="small" type="error" ghost :loading="revokingAll" @click="handleRevokeAll" :disabled="sessions.length <= 1">
            踢出所有其他设备
          </n-button>
        </template>
        <n-space vertical size="medium">
          <div class="setting-item">
            <n-thing title="JWT 令牌永不过期" description="开启后登录令牌将不会自动过期（10年），关闭后为24小时自动过期" />
            <n-switch :value="jwtNeverExpire" @update:value="handleJwtNeverExpireChange" :loading="savingJwtConfig" />
          </div>
          <n-alert v-if="jwtNeverExpire" type="warning" title="安全提示">
            永不过期会降低安全性，建议仅在可信环境中使用。
          </n-alert>
        </n-space>
        <n-divider />
        <n-spin :show="loadingSessions">
          <n-list v-if="sessions.length > 0" hoverable clickable>
            <n-list-item v-for="session in sessions" :key="session.id">
              <template #prefix>
                <n-icon size="24" :color="session.is_current ? 'var(--n-primary-color)' : '#999'">
                  <DeviceIcon />
                </n-icon>
              </template>
              <n-thing>
                <template #header>
                  <n-space align="center">
                    <span style="font-weight: 600">{{ session.browser_name }} / {{ session.os_name }}</span>
                    <n-tag v-if="session.is_current" type="success" size="small" round>当前会话</n-tag>
                  </n-space>
                </template>
                <template #description>
                  <n-space vertical size="small">
                    <n-text depth="3">IP: {{ session.ip_address }}</n-text>
                    <n-text depth="3">登录时间: {{ formatTime(session.created_at) }}</n-text>
                    <n-text depth="3">过期时间: {{ formatTime(session.expires_at) }} ({{ formatExpiresIn(session.expires_in) }})</n-text>
                  </n-space>
                </template>
              </n-thing>
              <template #suffix>
                <n-button 
                  v-if="!session.is_current" 
                  size="small" 
                  type="error" 
                  ghost 
                  :loading="revokingSessionId === session.id"
                  @click="handleRevokeSession(session.id)"
                >
                  踢出
                </n-button>
              </template>
            </n-list-item>
          </n-list>
          <n-empty v-else description="暂无登录会话" />
        </n-spin>
      </n-card>

      <n-card size="medium" embedded v-if="username">
        <div class="setting-item">
          <n-thing :title="'当前登录：' + username" :description="'最近登录时间：' + (lastLogin || '暂无')" />
          <n-button type="error" ghost @click="logout">退出登录</n-button>
        </div>
      </n-card>
    </n-space>

    <n-modal v-model:show="showOtpSetup" preset="card" title="设置双重身份验证" style="width: 400px">
      <n-space vertical align="center" size="large">
        <n-text align="center">请使用验证器应用扫描下方二维码</n-text>
        <div class="qr-container"><img :src="otpSetupData.qr_code" alt="QR Code" v-if="otpSetupData.qr_code" /></div>
        <n-alert type="warning" :show-icon="false" style="width: 100%">密钥: {{ otpSetupData.secret }}</n-alert>
        <n-input-group>
          <n-input v-model:value="otpConfirmCode" placeholder="输入 6 位验证码确认" maxlength="6" />
          <n-button type="primary" @click="confirmEnableOtp">确认开启</n-button>
        </n-input-group>
      </n-space>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { 
  useMessage, NSpace, NCard, NIcon, NForm, NGrid, NInput, NButton, NGi, 
  NThing, NSwitch, NFormItem, NAlert, NModal, NInputGroup, NText, NList,
  NListItem, NSpin, NTag, NEmpty, NDivider
} from 'naive-ui'
import { 
  KeyOutlined as KeyIcon,
  VerifiedUserOutlined as ShieldIcon,
  DevicesOutlined as DeviceIcon
} from '@vicons/material'
import axios from 'axios'
import { logout } from '../../store/navigationStore'

const message = useMessage()
const savingPwd = ref(false)
const confirmPassword = ref('')
const isOtpEnabled = ref(false)
const username = ref('')
const lastLogin = ref('')
const pwdForm = reactive({ old_password: '', new_password: '' })
const showOtpSetup = ref(false)
const otpConfirmCode = ref('')
const otpSetupData = reactive({ secret: '', qr_code: '' })

const sessions = ref<any[]>([])
const loadingSessions = ref(false)
const revokingSessionId = ref<number | null>(null)
const revokingAll = ref(false)
const jwtNeverExpire = ref(false)
const savingJwtConfig = ref(false)

const fetchAccountInfo = async () => {
  try {
    const meRes = await axios.get('/api/auth/me').catch(() => ({ data: {} }))
    if (meRes.data.username) {
        username.value = meRes.data.username
        isOtpEnabled.value = meRes.data.is_otp_enabled
        lastLogin.value = meRes.data.last_login
    }
  } catch (e) { console.error(e) }
}

const fetchConfig = async () => {
  try {
    const res = await axios.get('/api/config')
    jwtNeverExpire.value = res.data.jwt_never_expire || false
  } catch (e) {
    console.error('获取配置失败', e)
  }
}

const handleJwtNeverExpireChange = async (value: boolean) => {
  savingJwtConfig.value = true
  try {
    const res = await axios.get('/api/config')
    const config = res.data
    config.jwt_never_expire = value
    await axios.post('/api/config', config)
    jwtNeverExpire.value = value
    message.success('配置已更新')
  } catch (err: any) {
    message.error(err.response?.data?.detail || '保存失败')
  } finally {
    savingJwtConfig.value = false
  }
}

const fetchSessions = async () => {
  loadingSessions.value = true
  try {
    const res = await axios.get('/api/auth/sessions')
    sessions.value = res.data.sessions || []
  } catch (e) {
    console.error('获取会话失败', e)
    sessions.value = []
  } finally {
    loadingSessions.value = false
  }
}

const formatTime = (isoString: string) => {
  if (!isoString) return '未知'
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const formatExpiresIn = (seconds: number) => {
  if (seconds <= 0) return '已过期'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) {
    return `${hours}小时${minutes}分钟后过期`
  }
  return `${minutes}分钟后过期`
}

const handleRevokeSession = async (sessionId: number) => {
  revokingSessionId.value = sessionId
  try {
    await axios.delete(`/api/auth/sessions/${sessionId}`)
    message.success('会话已踢出')
    await fetchSessions()
  } catch (err: any) {
    message.error(err.response?.data?.detail || '踢出失败')
  } finally {
    revokingSessionId.value = null
  }
}

const handleRevokeAll = async () => {
  revokingAll.value = true
  try {
    await axios.delete('/api/auth/sessions')
    message.success('已踢出所有其他设备')
    await fetchSessions()
  } catch (err: any) {
    message.error(err.response?.data?.detail || '操作失败')
  } finally {
    revokingAll.value = false
  }
}

const handleUpdatePasswordDirectly = async () => {
  if (!pwdForm.old_password || !pwdForm.new_password) return message.warning('请填写完整')
  if (pwdForm.new_password !== confirmPassword.value) return message.error('密码不一致')
  savingPwd.value = true
  try {
    await axios.post('/api/auth/password', pwdForm)
    message.success('密码已更新')
    pwdForm.old_password = ''; pwdForm.new_password = ''; confirmPassword.value = ''
  } catch (err: any) { message.error(err.response?.data?.detail || '修改失败') }
  finally { savingPwd.value = false }
}

const handleOtpSwitch = async (val: boolean) => {
  if (val) {
    try {
      const res = await axios.get('/api/auth/2fa/setup')
      otpSetupData.secret = res.data.secret; otpSetupData.qr_code = res.data.qr_code; showOtpSetup.value = true
    } catch (e) { message.error('2FA初始化失败') }
  } else {
    try { await axios.post('/api/auth/2fa/disable'); isOtpEnabled.value = false; message.success('2FA已禁用') }
    catch (e) { message.error('操作失败') }
  }
}

const confirmEnableOtp = async () => {
  try {
    await axios.post(`/api/auth/2fa/enable?code=${otpConfirmCode.value}`)
    isOtpEnabled.value = true; showOtpSetup.value = false; otpConfirmCode.value = ''; message.success('2FA已开启')
  } catch (err: any) { message.error(err.response?.data?.detail || '验证码无效') }
}

onMounted(() => {
  fetchAccountInfo()
  fetchSessions()
  fetchConfig()
})
</script>

<style scoped>
.setting-item { display: flex; justify-content: space-between; align-items: center; }
.qr-container { background-color: var(--bg-primary); padding: 10px; border-radius: 8px; display: flex; justify-content: center; }
.qr-container img { width: 200px; height: 200px; }
.shield-icon { color: var(--n-primary-color); }
</style>
