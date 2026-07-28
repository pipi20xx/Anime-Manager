<script setup lang="ts">
/**
 * HealthCheckTab — 掉盘与 CK 失效检测
 *
 * 功能: 配置健康检查项、触发检测、查看状态
 */
import { ref, reactive, onMounted } from 'vue'
import { healthApi, configApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

defineOptions({ name: 'HealthCheckTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const configs = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const showModal = ref(false)
const isEditing = ref(false)

const config = reactive<any>({
  health_check_enabled: false,
  health_check_interval: 30,
})

const editingConfig = reactive({
  id: null as number | null,
  name: '',
  file_path: '',
  file_url: '',
  enabled: true,
})

async function fetchConfig() {
  try {
    const data = await configApi.getConfig()
    config.health_check_enabled = data.health_check_enabled || false
    config.health_check_interval = data.health_check_interval || 30
  } catch (e) {
    console.error(e)
  }
}

async function fetchConfigs() {
  loading.value = true
  try {
    configs.value = await healthApi.getConfigs()
  } catch (e) {
    showError('获取健康检查配置失败')
  } finally {
    loading.value = false
  }
}

async function saveAll() {
  saving.value = true
  try {
    const data = await configApi.getConfig()
    data.health_check_enabled = config.health_check_enabled
    data.health_check_interval = config.health_check_interval
    await configApi.saveConfig(data)
    success('设置已保存')
  } catch (e: any) {
    showError(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function openAdd() {
  isEditing.value = false
  Object.assign(editingConfig, {
    id: null,
    name: '',
    file_path: '',
    file_url: '',
    enabled: true,
  })
  showModal.value = true
}

function openEdit(item: any) {
  isEditing.value = true
  Object.assign(editingConfig, {
    id: item.id,
    name: item.name,
    file_path: item.file_path,
    file_url: item.file_url,
    enabled: item.enabled,
  })
  showModal.value = true
}

async function deleteConfig(id: number) {
  const ok = await confirm('确定要删除此检测配置吗？')
  if (!ok) return
  try {
    await healthApi.deleteConfig(id)
    success('已删除')
    await fetchConfigs()
  } catch (e: any) {
    showError(e?.message || '删除失败')
  }
}

async function startCheck(id: number) {
  try {
    await healthApi.triggerCheck(id)
    success('检测已触发')
    // 延迟刷新
    setTimeout(() => fetchConfigs(), 2000)
  } catch (e: any) {
    showError(e?.message || '触发失败')
  }
}

async function checkAll() {
  try {
    await healthApi.triggerCheckAll()
    success('全部检测已触发')
    setTimeout(() => fetchConfigs(), 2000)
  } catch (e: any) {
    showError(e?.message || '触发失败')
  }
}

async function saveConfig() {
  try {
    if (isEditing.value && editingConfig.id) {
      await healthApi.updateConfig(editingConfig.id!, { ...editingConfig })
    } else {
      await healthApi.createConfig({ ...editingConfig })
    }
    success('配置已保存')
    showModal.value = false
    await fetchConfigs()
  } catch (e: any) {
    showError(e?.message || '保存失败')
  }
}

function getStatusInfo(status: string): { text: string; color: string } {
  if (status === 'OK') return { text: '正常', color: 'success' }
  if (status && status.startsWith('Failed')) return { text: '异常', color: 'error' }
  if (status) return { text: status, color: 'warning' }
  return { text: '未检测', color: 'grey' }
}

function formatDate(dateStr: string) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  fetchConfig()
  fetchConfigs()
})
</script>

<template>
  <div>
    <!-- 全局设置 -->
    <v-card class="glass-card mb-4">
      <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
        <div class="d-flex align-center ga-2">
          <v-icon color="primary" size="20">mdi-harddisk-remove</v-icon>
          <span class="text-subtitle-1 font-weight-bold">掉盘与 CK 失效检测</span>
        </div>
        <div class="d-flex ga-2">
          <v-btn color="info" variant="tonal" size="small" prepend-icon="mdi-play" @click="checkAll">
            立即检测全部
          </v-btn>
          <v-btn color="primary" variant="tonal" size="small" prepend-icon="mdi-plus" @click="openAdd">
            添加配置
          </v-btn>
        </div>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <div class="text-body-2 text-medium-emphasis mb-4">
          通过定时下载指定文件并与本地路径进行比对，用于监测硬盘是否掉线或下载源的 Cookie 是否失效。
        </div>

        <div class="d-flex align-center ga-4 flex-wrap pa-3 rounded-lg mb-4" style="background: rgba(128,128,128,0.06)">
          <div class="d-flex align-center ga-3">
            <v-switch v-model="config.health_check_enabled" density="compact" hide-details color="primary" />
            <span class="text-body-2 font-weight-medium">自动巡检</span>
          </div>
          <v-text-field
            v-model="config.health_check_interval"
            label="巡检频率 (分)"
            type="number"
            variant="outlined"
            density="compact"
            hide-details
            min="1"
            style="max-width: 160px"
          />
          <v-btn color="primary" variant="flat" size="small" :loading="saving" @click="saveAll">保存设置</v-btn>
        </div>

        <!-- 配置列表 -->
        <div v-if="loading" class="d-flex justify-center pa-4">
          <v-progress-circular indeterminate color="primary" size="24" />
        </div>
        <v-table v-else-if="configs.length > 0" density="compact" class="bg-transparent">
          <thead>
            <tr>
              <th>名称</th>
              <th>文件路径</th>
              <th>远程 URL</th>
              <th>状态</th>
              <th>最后检查</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in configs" :key="item.id">
              <td class="text-body-2 font-weight-medium">{{ item.name }}</td>
              <td class="text-caption font-monospace">{{ item.file_path }}</td>
              <td class="text-caption font-monospace">{{ item.file_url || '-' }}</td>
              <td>
                <v-chip size="x-small" :color="getStatusInfo(item.last_status).color" variant="tonal">
                  {{ getStatusInfo(item.last_status).text }}
                </v-chip>
              </td>
              <td class="text-caption">{{ formatDate(item.last_check) }}</td>
              <td>
                <div class="d-flex ga-1">
                  <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-play" @click="startCheck(item.id)">执行</v-btn>
                  <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-pencil" @click="openEdit(item)">编辑</v-btn>
                  <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteConfig(item.id)">删除</v-btn>
                </div>
              </td>
            </tr>
          </tbody>
        </v-table>
        <div v-else class="text-center text-medium-emphasis pa-8">
          暂无检测配置，请点击右上角添加
        </div>
      </v-card-text>
    </v-card>

    <!-- 编辑/添加弹窗 -->
    <v-dialog v-model="showModal" max-width="500">
      <v-card>
        <v-card-title class="pa-4 d-flex align-center ga-2">
          <v-icon color="primary" size="20">mdi-harddisk-remove</v-icon>
          <span>健康检查配置</span>
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-text-field
            v-model="editingConfig.name"
            label="配置名称"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="例如: 阿里云盘掉盘检测"
          />
          <v-text-field
            v-model="editingConfig.file_path"
            label="文件路径"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="容器内的文件路径，例如: /mnt/aliyun/check.txt"
          />
          <v-text-field
            v-model="editingConfig.file_url"
            label="远程 URL"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="文件的直链 URL (包含 Cookie 或 Token)"
          />
          <div class="d-flex align-center ga-3">
            <v-switch v-model="editingConfig.enabled" density="compact" hide-details color="primary" />
            <span class="text-body-2 font-weight-medium">启用检测</span>
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showModal = false">取消</v-btn>
          <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveConfig">提交保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>
