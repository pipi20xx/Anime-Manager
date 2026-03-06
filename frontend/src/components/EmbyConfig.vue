<script setup lang="ts">
import { ref } from 'vue'
import { NCard, NIcon, NForm, NFormItem, NInput, NSwitch, NSpace, NButton, useMessage } from 'naive-ui'
import { MovieOutlined as EmbyIcon } from '@vicons/material'

interface Props {
  embyUrl: string
  embyApiKey: string
  embyUsername: string
  embyPassword: string
  embyUserId: string
}

const props = defineProps<Props>()
const emit = defineEmits(['update:embyUrl', 'update:embyApiKey', 'update:embyUsername', 'update:embyPassword', 'update:embyUserId'])

const message = useMessage()
const loading = ref(false)
const testLoading = ref(false)

const testConnection = async () => {
  if (!props.embyUrl || !props.embyApiKey) {
    message.warning('请先填写服务地址和 API Key')
    return
  }
  
  testLoading.value = true
  try {
    const url = props.embyUrl.replace(/\/$/, '')
    const response = await fetch(`${url}/System/Info?api_key=${props.embyApiKey}`)
    if (response.ok) {
      message.success('连接成功！')
    } else {
      message.error('连接失败，请检查配置')
    }
  } catch (error: any) {
    message.error('连接失败：' + (error?.message || error))
  } finally {
    testLoading.value = false
  }
}

const fetchToken = async () => {
  if (!props.embyUrl || !props.embyUsername || !props.embyPassword) {
    message.warning('请先填写服务地址、用户名和密码')
    return
  }
  
  loading.value = true
  try {
    const url = props.embyUrl.replace(/\/$/, '')
    const response = await fetch(`${url}/Users/authenticatebyname`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Emby-Authorization': `MediaBrowser Client="AnimeManager", Device="Web", DeviceId="web-${Date.now()}", Version="1.0.0"`
      },
      body: JSON.stringify({
        Username: props.embyUsername,
        Pw: props.embyPassword
      })
    })
    
    if (response.ok) {
      const data = await response.json()
      if (data.AccessToken) {
        emit('update:embyApiKey', data.AccessToken)
        if (data.User?.Id) {
          emit('update:embyUserId', data.User.Id)
        }
        message.success('Token 获取成功！')
      }
    } else {
      message.error('登录失败，请检查用户名和密码')
    }
  } catch (error: any) {
    message.error('获取 Token 失败：' + (error?.message || error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <n-card bordered>
    <template #header>
      <div class="card-title-box">
        <n-icon size="20" style="color: var(--n-primary-color)"><EmbyIcon /></n-icon>
        <span class="card-title-text">Emby/Jellyfin 设置</span>
      </div>
    </template>
    
    <n-form label-placement="left" label-width="100">
      <n-form-item label="服务地址">
        <n-space vertical :size="2" style="width: 100%">
          <n-input 
            :value="embyUrl" 
            placeholder="http://localhost:8096" 
            @update:value="(val: string) => emit('update:embyUrl', val)"
          />
          <span style="font-size: 12px; color: #666;">Emby/Jellyfin 服务器地址，包含端口号</span>
        </n-space>
      </n-form-item>

      <n-form-item label="API Key">
        <n-space vertical :size="2" style="width: 100%">
          <n-input 
            :value="embyApiKey" 
            type="password" 
            show-password-on="click" 
            placeholder="输入 API Key"
            @update:value="(val: string) => emit('update:embyApiKey', val)"
          />
          <span style="font-size: 12px; color: #666;">在 Emby/Jellyfin 设置中生成 API Key，或使用下方按钮自动获取</span>
        </n-space>
      </n-form-item>

      <n-form-item label="用户名">
        <n-input 
          :value="embyUsername" 
          placeholder="管理员用户名"
          @update:value="(val: string) => emit('update:embyUsername', val)"
        />
      </n-form-item>

      <n-form-item label="密码">
        <n-input 
          :value="embyPassword" 
          type="password" 
          show-password-on="click" 
          placeholder="管理员密码"
          @update:value="(val: string) => emit('update:embyPassword', val)"
        />
      </n-form-item>

      <n-form-item label="用户 ID">
        <n-space vertical :size="2" style="width: 100%">
          <n-input 
            :value="embyUserId" 
            placeholder="自动获取或手动输入"
            @update:value="(val: string) => emit('update:embyUserId', val)"
          />
          <span style="font-size: 12px; color: #666;">用于特定操作的用户标识，通常可自动获取</span>
        </n-space>
      </n-form-item>

      <n-form-item label="操作">
        <n-space>
          <n-button type="primary" :loading="loading" @click="fetchToken">
            自动获取 Token
          </n-button>
          <n-button secondary :loading="testLoading" @click="testConnection">
            测试连接
          </n-button>
        </n-space>
      </n-form-item>
    </n-form>
  </n-card>
</template>

<style scoped>
.card-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title-text {
  font-size: 15px;
  font-weight: 600;
  color: #eee;
}
</style>
