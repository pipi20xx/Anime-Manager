<script setup lang="ts">
/**
 * HealthCheckTab — 掉盘与 CK 失效检测
 *
 * 功能: 配置健康检查项、触发检测、查看状态
 */
import { ref, reactive, onMounted } from 'vue'
import { healthApi, configApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'
import FolderBrowserModal from '@/views/organizer/FolderBrowserModal.vue'

defineOptions({ name: 'HealthCheckTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

// ---------- 文件路径浏览选择（file 模式） ----------
const showFileBrowser = ref(false)
const openFileBrowser = () => { showFileBrowser.value = true }
const onFileSelected = (path: string) => { editingConfig.file_path = path }

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
  path_via: 'local' as 'local' | 'cd2',
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
    path_via: 'local',
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
    path_via: item.path_via || 'local',
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
  if (status && status !== 'Unknown') return { text: status, color: 'warning' }
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
    <div class="d-flex align-center justify-space-between mb-3">
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
    </div>

    <div class="text-body-2 text-medium-emphasis mb-4">
      通过定时检测指定文件是否存在，用于监测本地硬盘是否掉线、CD2 云端是否可访问，或下载源的 Cookie 是否失效。支持本地路径和 CD2 挂载路径。
    </div>

    <div class="d-flex align-center ga-4 flex-wrap mb-4">
      <div class="switch-row-lg">
        <v-switch v-model="config.health_check_enabled" density="compact" hide-details color="primary" />
        <div>
          <div class="switch-label">自动巡检</div>
          <div class="switch-desc">定时检测硬盘掉线和 Cookie 失效</div>
        </div>
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
      <v-btn variant="tonal" color="primary" size="small" prepend-icon="mdi-content-save-outline" :loading="saving" @click="saveAll">保存设置</v-btn>
    </div>

    <!-- 配置列表 -->
    <div v-if="loading" class="d-flex justify-center pa-4">
      <v-progress-circular indeterminate color="primary" size="24" />
    </div>
    <div v-else-if="configs.length > 0" class="card-grid">
      <v-card
        v-for="item in configs"
        :key="item.id"
        class="glass-card"
        :class="{
          'service-card--running': item.enabled && item.last_status === 'OK',
          'service-card--stopped': item.enabled && item.last_status && item.last_status !== 'OK',
          'service-card--pending': item.enabled && !item.last_status,
          'service-card--disabled': !item.enabled,
        }"
      >
          <v-card-text class="pa-4">
            <div class="d-flex align-center justify-space-between mb-2">
              <div class="d-flex align-center ga-2">
                <span class="text-body-2 font-weight-bold">{{ item.name }}</span>
                <v-chip v-if="!item.enabled" size="x-small" color="grey" variant="tonal">已禁用</v-chip>
              </div>
              <v-chip size="x-small" :color="getStatusInfo(item.last_status).color" variant="tonal">
                {{ getStatusInfo(item.last_status).text }}
              </v-chip>
            </div>
            <div class="d-flex flex-column ga-1 mb-3">
              <div class="kv-row">
                <span class="kv-label">文件路径</span>
                <span class="d-flex align-center ga-1">
                  <v-chip size="x-small" variant="flat" :color="item.path_via === 'cd2' ? 'indigo' : 'brown-grey'" class="mr-1">{{ item.path_via === 'cd2' ? 'CD2' : '本地' }}</v-chip>
                  <span class="kv-value kv-value--mono text-caption">{{ item.file_path }}</span>
                </span>
              </div>
              <div class="kv-row">
                <span class="kv-label">远程 URL</span>
                <span class="kv-value kv-value--mono text-caption">{{ item.file_url || '-' }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-label">最后检查</span>
                <span class="kv-value text-caption">{{ formatDate(item.last_check) }}</span>
              </div>
            </div>
            <div class="d-flex ga-1">
              <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-play" @click="startCheck(item.id)">执行</v-btn>
              <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-pencil" @click="openEdit(item)">编辑</v-btn>
              <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="deleteConfig(item.id)">删除</v-btn>
            </div>
          </v-card-text>
        </v-card>
    </div>
    <div v-else class="text-center text-medium-emphasis pa-8">
      暂无检测配置，请点击右上角添加
    </div>

    <!-- 编辑/添加弹窗 -->
    <v-dialog v-model="showModal" max-width="500">
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center ga-2">
          <v-icon color="primary" size="20">mdi-harddisk-remove</v-icon>
          <span>健康检查配置</span>
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showModal = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <!-- 说明 -->
          <v-alert density="compact" variant="tonal" color="info" class="mb-3" icon="mdi-information-outline">
            <div class="text-caption">
              <div>仅填写<b>文件路径</b>：只检测文件是否存在（本地磁盘 IO 验证 / CD2 gRPC 云端检查）。</div>
              <div>同时填写<b>远程 URL</b>：文件存在后再请求 URL，HTTP 非 200/206 则判定 Cookie 失效。</div>
            </div>
          </v-alert>
          <v-text-field
            v-model="editingConfig.name"
            label="配置名称"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="例如: 阿里云盘掉盘检测"
          />
          <!-- 路径类型切换 -->
          <div class="mb-2">
            <div class="text-caption text-medium-emphasis mb-1">文件路径类型</div>
            <v-btn-toggle v-model="editingConfig.path_via" mandatory density="compact" class="mb-2">
              <v-btn value="local" prepend-icon="mdi-harddisk">本地路径</v-btn>
              <v-btn value="cd2" prepend-icon="mdi-cloud-outline">CD2 云盘</v-btn>
            </v-btn-toggle>
          </div>
          <v-text-field
            v-model="editingConfig.file_path"
            :label="editingConfig.path_via === 'cd2' ? '文件路径 (CD2 路径，如 /115open/check.txt)' : '文件路径'"
            variant="outlined"
            density="compact"
            class="mb-1"
            hide-details
            :placeholder="editingConfig.path_via === 'cd2' ? '/115open/check.txt' : '容器内的文件路径，例如: /mnt/aliyun/check.txt'"
            append-inner-icon="mdi-file-outline"
            @click:append-inner="openFileBrowser"
          />
          <div v-if="editingConfig.file_path" class="text-caption mb-3" :class="editingConfig.path_via === 'cd2' ? 'text-indigo' : 'text-medium-emphasis'">
            <v-icon size="12" class="mr-1">mdi-cloud-outline</v-icon>检测方式: {{ editingConfig.path_via === 'cd2' ? 'CD2 (gRPC 云端文件存在性检查)' : '本地磁盘 (文件存在 + IO 读取验证)' }}
          </div>
          <v-text-field
            v-model="editingConfig.file_url"
            label="远程 URL"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="文件的直链 URL (包含 Cookie 或 Token)"
          />
          <div class="switch-row-lg">
            <v-switch v-model="editingConfig.enabled" density="compact" hide-details color="primary" />
            <span class="switch-label">启用检测</span>
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showModal = false">取消</v-btn>
          <v-btn variant="tonal" color="primary" prepend-icon="mdi-content-save-outline" @click="saveConfig">提交保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 检测文件路径浏览选择（文件模式） -->
    <FolderBrowserModal
      v-model="showFileBrowser"
      :via="editingConfig.path_via"
      mode="file"
      :title="editingConfig.path_via === 'cd2' ? '选择 CD2 云盘检测文件' : '选择本地检测文件'"
      @select="onFileSelected"
    />
  </div>
</template>
