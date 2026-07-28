<script setup lang="ts">
/**
 * ClientManageTab — 下载器管理
 *
 * 功能: 添加、编辑、删除、测试下载客户端
 */
import { ref, reactive, onMounted } from 'vue'
import { clientsApi } from '@/api'
import { useNotification, useConfirm } from '@/composables'

defineOptions({ name: 'ClientManageTab' })

const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

const clients = ref<any[]>([])
const loading = ref(false)
const showModal = ref(false)
const isNewClient = ref(false)
const testLoading = ref(false)
const testResult = ref<{ success: boolean; message: string } | null>(null)

const form = reactive({
  id: '',
  name: '',
  type: 'qbittorrent',
  url: '',
  username: '',
  password: '',
  api_token: '',
  default_save_path: '',
  mount_path: '',
  monitor_enabled: false,
  monitor_interval: 5,
  is_default: false,
  version: '',
  last_test_time: '',
})

const typeOptions = [
  { title: 'qBittorrent', value: 'qbittorrent' },
  { title: 'CloudDrive2', value: 'cd2' },
]

function hasCd2Client(): boolean {
  return clients.value.some((c: any) => c.type === 'cd2' && c.id !== form.id)
}

async function fetchClients() {
  loading.value = true
  try {
    clients.value = await clientsApi.getClients()
  } catch (e) {
    showError('获取客户端列表失败')
  } finally {
    loading.value = false
  }
}

function openAddClient() {
  isNewClient.value = true
  testResult.value = null
  Object.assign(form, {
    id: '',
    name: '新客户端',
    type: 'qbittorrent',
    url: 'http://127.0.0.1:8080',
    username: 'admin',
    password: 'adminadmin',
    api_token: '',
    default_save_path: '',
    mount_path: '',
    monitor_enabled: true,
    monitor_interval: 5,
    is_default: false,
    version: '',
    last_test_time: '',
  })
  showModal.value = true
}

function openEditClient(client: any) {
  isNewClient.value = false
  testResult.value = null
  Object.assign(form, JSON.parse(JSON.stringify(client)))
  if (!form.version) form.version = ''
  if (!form.last_test_time) form.last_test_time = ''
  showModal.value = true
}

async function handleDeleteClient(client: any) {
  const ok = await confirm(`确定要删除下载客户端「${client.name}」吗？`)
  if (!ok) return
  try {
    await clientsApi.deleteClient(client.id)
    success('客户端已删除')
    await fetchClients()
  } catch (e: any) {
    showError(e?.message || '删除失败')
  }
}

async function handleTest() {
  testLoading.value = true
  testResult.value = null
  try {
    const data = await clientsApi.testClient({ ...form })
    testResult.value = data
    if (data.success) {
      success('连接测试成功')
      if (data.version) form.version = data.version
      form.last_test_time = new Date().toLocaleString('zh-CN')
    } else {
      showError('连接测试失败')
    }
  } catch (e: any) {
    testResult.value = { success: false, message: e?.message || '请求失败' }
    showError('请求失败')
  } finally {
    testLoading.value = false
  }
}

async function handleSave() {
  try {
    let updatedClients: any[]
    if (isNewClient.value) {
      updatedClients = [...clients.value, { ...form }]
    } else {
      updatedClients = clients.value.map((c: any) => c.id === form.id ? { ...form } : c)
    }
    await clientsApi.saveClients(updatedClients)
    success('客户端已保存')
    showModal.value = false
    await fetchClients()
  } catch (e: any) {
    showError(e?.message || '保存失败')
  }
}

onMounted(() => {
  fetchClients()
})
</script>

<template>
  <div>
    <div v-if="loading" class="d-flex justify-center pa-8">
      <v-progress-circular indeterminate color="primary" size="32" />
    </div>

    <template v-else>
      <!-- 客户端列表 -->
      <v-card class="glass-card mb-4">
        <v-card-title class="pa-4 pb-2 d-flex align-center justify-space-between">
          <div class="d-flex align-center ga-2">
            <v-icon color="primary" size="20">mdi-download-circle-outline</v-icon>
            <span class="text-subtitle-1 font-weight-bold">下载客户端配置</span>
          </div>
          <v-btn color="primary" variant="tonal" size="small" prepend-icon="mdi-plus" @click="openAddClient">
            添加客户端
          </v-btn>
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-row v-if="clients.length > 0">
            <v-col v-for="client in clients" :key="client.id" cols="12" sm="6" md="4">
              <v-card
                class="glass-card manage-card hover-lift cursor-pointer"
                @click="openEditClient(client)"
              >
                <!-- 标题行 -->
                <div class="manage-card__header">
                  <div class="d-flex align-center ga-1 manage-card__title">
                    <v-icon v-if="client.is_default" size="14" color="info">mdi-star</v-icon>
                    <span class="text-truncate">{{ client.name }}</span>
                  </div>
                  <v-chip size="x-small" variant="tonal" color="primary" class="manage-card__badge">{{ client.type }}</v-chip>
                </div>

                <!-- 信息区 -->
                <div class="manage-card__body">
                  <div class="manage-card__info">
                    <span class="manage-card__info-label">地址</span>
                    <span class="manage-card__info-value" :title="client.url">{{ client.url }}</span>
                  </div>
                  <div v-if="client.version" class="manage-card__tags">
                    <v-chip size="x-small" color="info" variant="tonal">{{ client.version }}</v-chip>
                    <span v-if="client.last_test_time" class="text-caption text-medium-emphasis">{{ client.last_test_time }}</span>
                  </div>
                </div>

                <v-divider />
                <v-card-actions class="manage-card__actions">
                  <v-spacer />
                  <v-btn
                    size="small"
                    variant="tonal"
                    color="error"
                    prepend-icon="mdi-delete-outline"
                    @click.stop="handleDeleteClient(client)"
                  >删除</v-btn>
                </v-card-actions>
              </v-card>
            </v-col>
          </v-row>
          <div v-else class="text-center pa-8 text-medium-emphasis">
            暂无下载器，请点击右上角添加
          </div>
        </v-card-text>
      </v-card>
    </template>

    <!-- 编辑/添加客户端弹窗 -->
    <v-dialog v-model="showModal" max-width="600" scrollable>
      <v-card>
        <v-card-title class="pa-4 d-flex align-center ga-2">
          <v-icon color="primary" size="20">mdi-download-circle-outline</v-icon>
          <span>{{ isNewClient ? '添加下载器' : '编辑下载器' }}</span>
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-select
            v-model="form.type"
            label="类型"
            :items="typeOptions.filter(o => o.value !== 'cd2' || !hasCd2Client())"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
          />

          <v-text-field
            v-model="form.name"
            label="名称"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="给它起个名字"
          />

          <v-text-field
            v-model="form.url"
            label="地址 (URL)"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="http://192.168.1.x:8080"
          />

          <v-text-field
            v-model="form.username"
            label="用户名"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="admin"
          />

          <v-text-field
            v-model="form.password"
            label="密码"
            type="password"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
          />

          <v-text-field
            v-if="form.type === 'cd2'"
            v-model="form.api_token"
            label="API Token (选填)"
            type="password"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="直接使用 API Token，无需用户名密码"
          />

          <v-text-field
            v-model="form.default_save_path"
            label="默认下载路径 (选填)"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="留空则使用下载器全局设置"
          />

          <v-text-field
            v-if="form.type === 'cd2'"
            v-model="form.mount_path"
            label="CD2 本地挂载点 (选填)"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            placeholder="例如: /NVME/docker2/clouddrive2-19798/medata/CloudDrive"
          />

          <div v-if="form.type === 'cd2'" class="d-flex align-center ga-3 mb-3">
            <v-switch v-model="form.monitor_enabled" density="compact" hide-details color="primary" />
            <div>
              <div class="text-body-2 font-weight-medium">后台传输监控</div>
              <div class="text-caption text-medium-emphasis">开启后监控 CD2 传输任务完成状态，自动触发 STRM 文件生成</div>
            </div>
          </div>

          <v-text-field
            v-if="form.type === 'cd2' && form.monitor_enabled"
            v-model="form.monitor_interval"
            label="监控间隔 (秒)"
            type="number"
            variant="outlined"
            density="compact"
            class="mb-3"
            hide-details
            min="1"
            max="60"
          />

          <div class="d-flex align-center ga-3 mb-3">
            <v-switch v-model="form.is_default" density="compact" hide-details color="primary" />
            <div>
              <div class="text-body-2 font-weight-medium">设为默认客户端</div>
              <div class="text-caption text-medium-emphasis">开启后作为新增下载任务的默认下载器</div>
            </div>
          </div>

          <!-- 测试结果 -->
          <v-alert v-if="testResult" :type="testResult.success ? 'success' : 'error'" variant="tonal" density="compact" class="mb-3">
            {{ testResult.message }}
          </v-alert>

          <v-alert v-if="!testResult && form.version" type="info" variant="tonal" density="compact">
            <div>版本: {{ form.version }}</div>
            <div v-if="form.last_test_time">测试时间: {{ form.last_test_time }}</div>
          </v-alert>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-btn variant="tonal" color="primary" :loading="testLoading" prepend-icon="mdi-connection" @click="handleTest">
            测试连接
          </v-btn>
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showModal = false">取消</v-btn>
          <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="handleSave">保存配置</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<!-- scoped 样式已迁移至 global.css .hover-lift -->
