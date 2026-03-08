<script setup lang="ts">
import { 
  NCard, NSpace, NInput, NButton, NRadio, NRadioGroup, 
  NForm, NFormItem, NGrid, NGi, NIcon, NAlert, NDivider, NTag, NInputNumber
} from 'naive-ui'
import {
  CableOutlined as ConnectIcon,
  SaveOutlined as SaveIcon
} from '@vicons/material'
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
      <n-form-item label="主机地址">
        <n-input v-model:value="dbConfig.host" placeholder="localhost" />
      </n-form-item>
      
      <n-form-item label="端口">
        <n-input-number v-model:value="dbConfig.port" :show-button="false" style="width: 100%" />
      </n-form-item>

      <n-form-item label="用户名">
        <n-input v-model:value="dbConfig.user" placeholder="postgres" />
      </n-form-item>
      
      <n-form-item label="密码">
        <n-input v-model:value="dbConfig.password" type="password" show-password-on="mousedown" placeholder="数据库密码" />
      </n-form-item>

      <n-form-item label="数据库名">
        <n-input v-model:value="dbConfig.database" placeholder="anime_pro_matcher" />
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
