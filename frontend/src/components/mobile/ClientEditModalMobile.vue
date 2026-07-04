<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import { 
  NSpace, NFormItem, NSelect, 
  NButton, NIcon, NAlert, NSwitch, NForm
} from 'naive-ui'
import {
  SaveOutlined as SaveIcon,
  CloudUploadOutlined as TestIcon,
} from '@vicons/material'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
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
  <AppGlassModal
    appearance-key="client-edit-modal"
    :show="show"
    @update:show="val => emit('update:show', val)"
    style="width: 100%; height: 100vh; margin: 0;"
    content-style="padding: 16px; overflow-y: auto;"
    :title="isNew ? '添加下载器' : '编辑下载器'"
  >
    <n-form label-placement="top">
      <n-space vertical size="large">
        <n-form-item>
          <AppSelectField v-model:value="form.type" label="类型" :options="typeOptions" />
        </n-form-item>
        
        <n-form-item>
          <AppTextField v-model:value="form.name" label="名称" placeholder="起个名字" />
        </n-form-item>
        
        <n-form-item>
          <AppTextField v-model:value="form.url" label="地址 (URL)" placeholder="http://192.168.1.x:8080" />
        </n-form-item>
        
        <n-form-item>
          <AppTextField v-model:value="form.username" label="用户名" placeholder="admin" type="password" />
        </n-form-item>
        
        <n-form-item>
          <AppTextField v-model:value="form.password" label="密码" placeholder="password" type="password" />
        </n-form-item>

        <n-form-item v-if="form.type === 'cd2'">
          <AppTextField v-model:value="form.api_token" label="API Token (选填)" placeholder="直接使用 API Token" type="password" />
        </n-form-item>

        <n-form-item>
          <AppTextField v-model:value="form.default_save_path" label="默认下载路径 (选填)" placeholder="留空默认" />
        </n-form-item>

        <n-form-item v-if="form.type === 'cd2'">
          <AppTextField v-model:value="form.mount_path" label="CD2 本地挂载点" placeholder="例如: /NVME/..." />
        </n-form-item>

        <n-form-item v-if="form.type === 'cd2'">
             <n-switch v-model:value="form.monitor_enabled">
                <template #checked>已开启后台传输监控</template>
                <template #unchecked>开启后台传输监控</template>
            </n-switch>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px">轮询云端任务触发STRM联动</div>
        </n-form-item>

        <n-form-item v-if="form.type === 'cd2' && form.monitor_enabled">
          <AppTextField v-model:value="form.monitor_interval" label="监控间隔 (秒)" type="number" :min="1" :max="60" placeholder="5" hint="默认 5 秒，gRPC 开销小可适当降低" />
        </n-form-item>

        <n-form-item label="选项">
          <n-space>
              <n-switch v-model:value="form.is_default">
                  <template #checked>设为默认客户端</template>
                  <template #unchecked>非默认</template>
              </n-switch>
          </n-space>
        </n-form-item>

        <n-alert v-if="testResult" :type="testResult.success ? 'success' : 'error'" title="测试结果">
          {{ testResult.message }}
        </n-alert>

      </n-space>
    </n-form>
    
    <template #footer>
      <n-space justify="space-between">
        <n-button v-bind="getButtonStyle('primary')" :loading="testLoading" @click="handleTest">
          测试连接
        </n-button>
        <n-space>
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="handleSave" size="small">
            保存
          </n-button>
        </n-space>
      </n-space>
    </template>
  </AppGlassModal>
</template>
