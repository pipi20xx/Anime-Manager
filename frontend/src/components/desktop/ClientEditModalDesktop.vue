<script setup lang="ts">
import { 
  NModal, NSpace, NFormItem, NInput, NSelect, 
  NButton, NIcon, NAlert, NSwitch, NInputNumber
} from 'naive-ui'
import {
  SaveOutlined as SaveIcon,
  CloudUploadOutlined as TestIcon,
} from '@vicons/material'
import { useClientEdit } from '../../composables/modals/useClientEdit'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  clientData: any
  isNew: boolean
  allClients: any[]
}>()

const emit = defineEmits(['update:show', 'save'])

const {
  form,
  testLoading,
  testResult,
  typeOptions,
  handleTest,
  handleSave
} = useClientEdit(props, emit)
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 600px" 
    :title="isNew ? '添加下载器' : '编辑下载器'"
  >
    <n-space vertical size="large">
      <n-form-item label="类型">
        <n-select v-model:value="form.type" :options="typeOptions" />
      </n-form-item>
      
      <n-form-item label="名称">
        <n-input v-model:value="form.name" placeholder="给它起个名字" />
      </n-form-item>
      
      <n-form-item label="地址 (URL)">
        <n-input v-model:value="form.url" placeholder="http://192.168.1.x:8080" />
      </n-form-item>
      
      <n-form-item label="用户名">
        <n-input v-model:value="form.username" placeholder="admin" type="password" show-password-on="click" />
      </n-form-item>
      
      <n-form-item label="密码">
        <n-input v-model:value="form.password" type="password" show-password-on="click" placeholder="password" />
      </n-form-item>

      <n-form-item v-if="form.type === 'cd2'" label="API Token (选填)">
        <n-input v-model:value="form.api_token" type="password" show-password-on="click" placeholder="直接使用 API Token，无需用户名密码" />
        <template #feedback>
          如果填写了 API Token，将优先使用 Token 认证，忽略用户名和密码
        </template>
      </n-form-item>

      <n-form-item label="默认下载路径 (选填)">
        <n-input v-model:value="form.default_save_path" placeholder="留空则使用下载器全局设置" />
      </n-form-item>

      <n-form-item v-if="form.type === 'cd2'" label="CD2 本地挂载点 (选填)">
        <n-input v-model:value="form.mount_path" placeholder="例如: /NVME/docker2/clouddrive2-19798/medata/CloudDrive" />
        <template #feedback>
          用于将本地绝对路径转换为 CD2 API 内部路径。如果不填写，API 操作可能失败。
        </template>
      </n-form-item>
      
      <n-form-item v-if="form.type === 'cd2'">
         <n-space align="center" :size="12">
            <n-switch v-model:value="form.monitor_enabled" />
            <span class="switch-label">后台传输监控</span>
            <span class="switch-desc">开启后监控 CD2 传输任务完成状态，自动触发 STRM 文件生成</span>
         </n-space>
      </n-form-item>

      <n-form-item v-if="form.type === 'cd2' && form.monitor_enabled" label="监控间隔 (秒)">
        <n-input-number v-model:value="form.monitor_interval" :min="1" :max="60" placeholder="5" style="width: 120px" />
        <template #feedback>
          轮询 CD2 传输任务列表的间隔，默认 5 秒。gRPC 开销很小，可适当降低。
        </template>
      </n-form-item>

      <n-form-item label="选项">
        <n-space align="center" :size="12">
            <n-switch v-model:value="form.is_default" />
            <span class="switch-label">设为默认客户端</span>
            <span class="switch-desc">开启后作为新增下载任务的默认下载器</span>
        </n-space>
      </n-form-item>

      <n-alert v-if="testResult" :type="testResult.success ? 'success' : 'error'" title="连接测试结果">
        {{ testResult.message }}
      </n-alert>

    </n-space>
    
    <template #action>
      <n-space justify="space-between">
        <n-button v-bind="getButtonStyle('primary')" :loading="testLoading" @click="handleTest">
          测试连接
        </n-button>
        <n-space>
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="handleSave">
            保存配置
          </n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.switch-label { font-weight: 500; color: var(--text-primary); white-space: nowrap; }
.switch-desc { font-size: 12px; color: var(--text-tertiary); }
</style>
