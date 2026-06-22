<script setup lang="ts">
import { 
  NCard, NSpace, NButton, NRadio, NRadioGroup, 
  NForm, NFormItem, NGrid, NGi, NIcon, NAlert, NDivider, NTag
} from 'naive-ui'
import {
  CableOutlined as ConnectIcon,
  SaveOutlined as SaveIcon
} from '@vicons/material'
import AppTextField from '../AppTextField.vue'
import { useDatabaseConfig } from '../../composables/components/useDatabaseConfig'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  loading,
  testing,
  dbConfig,
  testConnection,
  saveConfig
} = useDatabaseConfig()
</script>

<template>
  <div class="database-config-mobile">
    <n-alert type="success" :show-icon="false" style="margin-bottom: 16px">
      系统运行于 <b>PostgreSQL</b> 模式
    </n-alert>

    <n-form label-placement="top" :disabled="loading">
      <n-form-item>
        <AppTextField v-model:value="dbConfig.host" label="主机地址" placeholder="localhost" />
      </n-form-item>
      
      <n-form-item>
        <AppTextField v-model:value="dbConfig.port" label="端口" type="number" />
      </n-form-item>

      <n-form-item>
        <AppTextField v-model:value="dbConfig.user" label="用户名" placeholder="postgres" />
      </n-form-item>
      
      <n-form-item>
        <AppTextField v-model:value="dbConfig.password" label="密码" type="password" placeholder="数据库密码" />
      </n-form-item>

      <n-form-item>
        <AppTextField v-model:value="dbConfig.database" label="数据库名" placeholder="anime_pro_matcher" />
      </n-form-item>

      <n-space vertical class="mt-4">
        <n-button v-bind="getButtonStyle('secondary')" block @click="testConnection" :loading="testing">
          测试连接
        </n-button>
        <n-button v-bind="getButtonStyle('primary')" block @click="saveConfig" :loading="loading">
          保存并应用
        </n-button>
      </n-space>
    </n-form>
  </div>
</template>

<style scoped>
.database-config-mobile { padding: 4px; }
.mt-4 { margin-top: 16px; }
</style>
