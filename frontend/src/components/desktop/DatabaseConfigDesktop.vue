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
  <n-card bordered title="数据库引擎配置" size="small">
    <template #header-extra>
      <n-tag :type="dbConfig.type === 'postgresql' ? 'primary' : 'info'" size="small">
        当前模式: {{ dbConfig.type.toUpperCase() }}
      </n-tag>
    </template>

    <n-space vertical size="large">
      <n-alert type="success" show-icon>
        系统已全面升级为 <b>PostgreSQL 高性能架构</b>。
        单文件 SQLite 模式已被弃用，以确保在大规模数据处理下的绝对稳定与极速识别。
      </n-alert>

      <n-form label-placement="left" label-width="100" :disabled="loading">
        <n-divider title-placement="left">PostgreSQL 核心引擎配置</n-divider>
          
        <n-grid :cols="24" :x-gap="12">
            <n-gi :span="18">
              <n-form-item label="主机地址">
                <n-input v-model:value="dbConfig.host" placeholder="localhost" />
              </n-form-item>
            </n-gi>
            <n-gi :span="6">
              <n-form-item label="端口">
                <n-input-number v-model:value="dbConfig.port" :show-button="false" style="width: 100%" />
              </n-form-item>
            </n-gi>
          </n-grid>

          <n-grid :cols="2" :x-gap="12">
            <n-gi>
              <n-form-item label="用户名">
                <n-input v-model:value="dbConfig.user" placeholder="postgres" />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="密码">
                <n-input v-model:value="dbConfig.password" type="password" show-password-on="mousedown" placeholder="数据库密码" />
              </n-form-item>
            </n-gi>
          </n-grid>

          <n-form-item label="数据库名">
            <n-input v-model:value="dbConfig.database" placeholder="anime_pro_matcher" />
          </n-form-item>

          <n-alert type="warning" size="small" class="mt-2">
            系统将自动管理 <code>public</code> 和 <code>metadata</code> Schema。请确保所使用的账户拥有创建 Schema 和扩展（pg_trgm）的权限。
          </n-alert>

        <div class="d-flex justify-end gap-3 mt-4">
          <n-button v-bind="getButtonStyle('secondary')" @click="testConnection" :loading="testing">
            测试连接
          </n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="saveConfig" :loading="loading">
            保存并应用
          </n-button>
        </div>
      </n-form>
    </n-space>
  </n-card>
</template>

<style scoped>
.mt-2 { margin-top: 8px; }
.mt-4 { margin-top: 16px; }
.d-flex { display: flex; }
.justify-end { justify-content: flex-end; }
.gap-3 { gap: 12px; }
</style>
