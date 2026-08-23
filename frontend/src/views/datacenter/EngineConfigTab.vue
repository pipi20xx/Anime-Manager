<script setup lang="ts">
/**
 * EngineConfigTab — 引擎配置
 *
 * 功能: PostgreSQL 连接配置/测试/保存
 */
import { ref, reactive, onMounted } from 'vue'
import { dataCenterApi, configApi } from '@/api'
import { useNotification } from '@/composables'

const { success, error: showError } = useNotification()

const dbConfigLoading = ref(false)
const dbConfigTesting = ref(false)
const dbConfig = reactive({ type: 'sqlite', host: 'localhost', port: 5432, user: 'postgres', password: '', database: 'anime_pro_matcher' })

async function fetchDbConfig() {
  try {
    const data = await configApi.getConfig() as any
    if (data?.database) Object.assign(dbConfig, data.database)
  } catch (e) { /* ignore */ }
}

async function testDbConnection() {
  dbConfigTesting.value = true
  try {
    const data = await dataCenterApi.testDbConnection(dbConfig) as any
    if (data?.status === 'success') success(data.message)
    else showError(data?.message || '连接失败')
  } catch (e: any) { showError(e?.message || '测试连接失败') }
  finally { dbConfigTesting.value = false }
}

async function saveDbConfig() {
  dbConfigLoading.value = true
  try {
    const data = await dataCenterApi.saveDbConnection(dbConfig) as any
    if (data?.status === 'success') { success(data.message); setTimeout(() => window.location.reload(), 1500) }
    else showError(data?.message || '保存失败')
  } catch (e: any) { showError(e?.message || '保存失败') }
  finally { dbConfigLoading.value = false }
}

onMounted(() => {
  fetchDbConfig()
})
</script>

<template>
  <v-card class="glass-card pa-4" max-width="700">
    <div class="d-flex align-center justify-space-between mb-4">
      <div class="text-subtitle-1 font-weight-bold">数据库引擎配置</div>
      <v-chip size="small" :color="dbConfig.type === 'postgresql' ? 'primary' : 'info'" variant="tonal">当前模式: {{ dbConfig.type.toUpperCase() }}</v-chip>
    </div>

    <v-alert type="success" density="compact" variant="tonal" class="mb-4">
      系统已全面升级为 <b>PostgreSQL 高性能架构</b>。单文件 SQLite 模式已被弃用。
    </v-alert>

    <div class="text-subtitle-2 font-weight-bold text-primary mb-3">PostgreSQL 核心引擎配置</div>
    <v-row dense>
      <v-col cols="12" sm="8"><v-text-field v-model="dbConfig.host" label="主机地址" variant="outlined" density="compact" class="mb-3" /></v-col>
      <v-col cols="12" sm="4"><v-text-field v-model="dbConfig.port" label="端口" type="number" variant="outlined" density="compact" class="mb-3" /></v-col>
    </v-row>
    <v-row dense>
      <v-col cols="12" sm="6"><v-text-field v-model="dbConfig.user" label="用户名" variant="outlined" density="compact" class="mb-3" /></v-col>
      <v-col cols="12" sm="6"><v-text-field v-model="dbConfig.password" label="密码" type="password" variant="outlined" density="compact" class="mb-3" /></v-col>
    </v-row>
    <v-text-field v-model="dbConfig.database" label="数据库名" variant="outlined" density="compact" class="mb-3" />

    <v-alert type="warning" density="compact" variant="tonal" class="mb-4">
      系统将自动管理 <code>public</code> 和 <code>metadata</code> Schema。请确保所使用的账户拥有创建 Schema 和扩展（pg_trgm）的权限。
    </v-alert>

    <div class="d-flex justify-end ga-2">
      <v-btn color="info" variant="tonal" prepend-icon="mdi-lan-connect" :loading="dbConfigTesting" @click="testDbConnection">测试连接</v-btn>
      <v-btn variant="tonal" color="primary" prepend-icon="mdi-content-save-outline" :loading="dbConfigLoading" @click="saveDbConfig">保存并应用</v-btn>
    </div>
  </v-card>
</template>
