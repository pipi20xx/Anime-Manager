<script setup lang="ts">
import { NCard, NIcon, NForm, NFormItem, NInput, NSwitch, NSpace } from 'naive-ui'
import { MovieOutlined as EmbyIcon } from '@vicons/material'

interface Props {
  embyUrl: string
  embyApiKey: string
  embyUsername: string
  embyPassword: string
  embyUserId: string
  embyEnabled: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['update:embyUrl', 'update:embyApiKey', 'update:embyUsername', 'update:embyPassword', 'update:embyUserId', 'update:embyEnabled'])
</script>

<template>
  <n-card bordered size="small">
    <template #header>
      <div class="card-title-box">
        <n-icon size="18" style="color: var(--n-primary-color)"><EmbyIcon /></n-icon>
        <span class="card-title-text">Emby/Jellyfin 设置</span>
      </div>
    </template>
    
    <n-form label-placement="left" label-width="90">
      <n-form-item label="启用服务">
        <n-space align="center">
          <n-switch :value="embyEnabled" @update:value="(val: boolean) => emit('update:embyEnabled', val)">
            <template #checked>已启用</template>
            <template #unchecked>已禁用</template>
          </n-switch>
        </n-space>
      </n-form-item>

      <n-form-item label="服务地址">
        <n-input 
          :value="embyUrl" 
          placeholder="http://localhost:8096" 
          :disabled="!embyEnabled"
          @update:value="(val: string) => emit('update:embyUrl', val)"
        />
      </n-form-item>

      <n-form-item label="API Key">
        <n-input 
          :value="embyApiKey" 
          type="password" 
          show-password-on="click" 
          placeholder="输入 API Key"
          :disabled="!embyEnabled"
          @update:value="(val: string) => emit('update:embyApiKey', val)"
        />
      </n-form-item>

      <n-form-item label="用户名">
        <n-input 
          :value="embyUsername" 
          placeholder="管理员用户名"
          :disabled="!embyEnabled"
          @update:value="(val: string) => emit('update:embyUsername', val)"
        />
      </n-form-item>

      <n-form-item label="密码">
        <n-input 
          :value="embyPassword" 
          type="password" 
          show-password-on="click" 
          placeholder="管理员密码"
          :disabled="!embyEnabled"
          @update:value="(val: string) => emit('update:embyPassword', val)"
        />
      </n-form-item>

      <n-form-item label="用户 ID">
        <n-input 
          :value="embyUserId" 
          placeholder="自动获取或手动输入"
          :disabled="!embyEnabled"
          @update:value="(val: string) => emit('update:embyUserId', val)"
        />
      </n-form-item>
    </n-form>
  </n-card>
</template>

<style scoped>
.card-title-box {
  display: flex;
  align-items: center;
  gap: 6px;
}

.card-title-text {
  font-size: 14px;
  font-weight: 600;
  color: #eee;
}
</style>
