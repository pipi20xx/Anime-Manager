<template>
  <div class="tab-wrapper">
    <n-space vertical size="large" style="margin-top: 16px;">
      <!-- 全局验证开关 -->
      <n-card size="medium" embedded>
        <div class="setting-item">
          <n-thing title="启用登录验证" description="开启后，访问本系统界面需进行账号密码及 2FA 校验。关闭后，内网环境可直接访问。" />
          <n-switch v-model:value="uiAuthEnabled" @update:value="handleToggleAuth" />
        </div>
      </n-card>

      <n-grid :cols="2" :x-gap="24" :y-gap="24" item-responsive>
        <!-- 修改密码 -->
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

        <!-- 2FA -->
        <n-gi span="2 m:1">
          <n-card title="多重身份验证 (2FA)" size="small">
            <template #header-extra>
              <n-icon size="20" color="#03dac6"><ShieldIcon /></n-icon>
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

      <n-card size="medium" embedded v-if="username">
        <div class="setting-item">
          <n-thing :title="'当前登录：' + username" :description="'最近登录时间：' + (lastLogin || '暂无')" />
          <n-button type="error" ghost @click="logout">退出登录</n-button>
        </div>
      </n-card>
    </n-space>

    <!-- 2FA Setup Modal -->
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
  NThing, NSwitch, NFormItem, NAlert, NModal, NInputGroup, NText
} from 'naive-ui'
import { 
  KeyOutlined as KeyIcon,
  VerifiedUserOutlined as ShieldIcon
} from '@vicons/material'
import axios from 'axios'
import { uiAuthEnabled as uiAuthStore, logout } from '../../store/navigationStore'

const message = useMessage()
const savingPwd = ref(false)
const confirmPassword = ref('')
const isOtpEnabled = ref(false)
const uiAuthEnabled = ref(uiAuthStore.value)
const username = ref('')
const lastLogin = ref('')
const pwdForm = reactive({ old_password: '', new_password: '' })
const showOtpSetup = ref(false)
const otpConfirmCode = ref('')
const otpSetupData = reactive({ secret: '', qr_code: '' })

const fetchAccountInfo = async () => {
  try {
    const [meRes, statusRes] = await Promise.all([
      axios.get('/api/auth/me').catch(() => ({ data: {} })),
      axios.get('/api/auth/status')
    ])
    if (meRes.data.username) {
        username.value = meRes.data.username
        isOtpEnabled.value = meRes.data.is_otp_enabled
        lastLogin.value = meRes.data.last_login
    }
    uiAuthEnabled.value = statusRes.data.ui_auth_enabled
  } catch (e) { console.error(e) }
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

const handleToggleAuth = async (val: boolean) => {
  try {
    await axios.post('/api/config', {
      ui_auth_enabled: val
    })
    uiAuthStore.value = val
    localStorage.setItem('apm_ui_auth_enabled', String(val))
    message.success(val ? '登录验证已开启' : '登录验证已关闭')
  } catch (e) {
    message.error('操作失败')
    uiAuthEnabled.value = !val // 恢复原状
  }
}

const save = async () => {
  // 这里通常是全局配置保存的一部分，可以保持为空或者同步 uiAuthEnabled 到后端
  // 暂时通过 get_auth_status 逻辑处理，如果需要修改后端 config，需要加一个 endpoint
  uiAuthStore.value = uiAuthEnabled.value
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

defineExpose({ save })
onMounted(fetchAccountInfo)
</script>

<style scoped>
.setting-item { display: flex; justify-content: space-between; align-items: center; }
.qr-container { background-color: #fff; padding: 10px; border-radius: 8px; display: flex; justify-content: center; }
.qr-container img { width: 200px; height: 200px; }
</style>
