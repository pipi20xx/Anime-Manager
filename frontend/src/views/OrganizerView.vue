<script setup lang="ts">
/**
 * OrganizerView — 整理管理
 *
 * 全卡片式布局，桌面端网格、移动端自动单列堆叠
 * 拆分为子组件:
 *   - TasksTab: 整理任务
 *   - RulesTab: 重命名规则
 *   - BackgroundTasksTab: 后台任务
 *   - OrganizeHistoryTab: 整理历史
 *   - TaskEditModal: 任务编辑弹窗 (TasksTab 内部引用)
 *   - RuleEditModal: 规则编辑弹窗 (RulesTab 内部引用)
 *   - ExecutionLogModal: 执行日志弹窗 (BackgroundTasksTab 内部引用)
 *   - RulePreviewModal: 规则预览弹窗 (RulesTab 内部引用)
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { organizerApi } from '@/api'
import { useNotification } from '@/composables'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'
import { useSystemStore } from '@/stores'
import TasksTab from './organizer/TasksTab.vue'
import RulesTab from './organizer/RulesTab.vue'
import BackgroundTasksTab from './organizer/BackgroundTasksTab.vue'
import OrganizeHistoryTab from './organizer/OrganizeHistoryTab.vue'
import TaskCenterModal from './organizer/TaskCenterModal.vue'

defineOptions({ name: 'OrganizerView' })

const { success, error: showError } = useNotification()
const systemStore = useSystemStore()

// --- Tab 控制 ---
const activeTab = ref('tasks')

// --- 定时刷新 ---
let refreshTimer: ReturnType<typeof setInterval> | null = null

// --- 数据 ---
const rules = ref<any[]>([])
const tasks = ref<any[]>([])
const backgroundTasks = ref<any[]>([])
const loading = ref(false)

// --- 后台任务 WS 订阅 ---
let wsUnsubscribe: (() => void) | null = null

async function fetchConfig() {
  loading.value = true
  try {
    const data = await organizerApi.getConfig()
    rules.value = data?.rename_rules || []
    tasks.value = data?.organize_tasks || []
  } catch (e) {
    showError('加载配置失败')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  loading.value = true
  try {
    await organizerApi.saveConfig({
      rename_rules: rules.value,
      organize_tasks: tasks.value,
    })
    success('配置已同步')
  } catch (e) {
    showError('保存失败')
  } finally {
    loading.value = false
  }
}

async function fetchBackgroundTasks() {
  try {
    const data = await organizerApi.getBackgroundTasks()
    backgroundTasks.value = data || []
  } catch (e) {
    // 静默
  }
}

// --- 任务中心弹窗 ---
const showTaskCenter = ref(false)

function openTaskCenter() {
  showTaskCenter.value = true
}

// --- 整理历史 Tab 引用 ---
const historyTabRef = ref<InstanceType<typeof OrganizeHistoryTab> | null>(null)

// ============================================================
// 生命周期
// ============================================================
onMounted(() => {
  fetchConfig()
  fetchBackgroundTasks()
  // 每 10 秒刷新后台任务
  refreshTimer = setInterval(() => fetchBackgroundTasks(), 10000)
  wsUnsubscribe = systemStore.$onAction(({ name, after }) => {
    if (name === 'connect') {
      after(() => fetchBackgroundTasks())
    }
  })
})

onUnmounted(() => {
  if (wsUnsubscribe) wsUnsubscribe()
  if (refreshTimer) clearInterval(refreshTimer)
})

// 注册动态顶栏 Tab
const { registerHeaderTab } = useDynamicHeaderTab()
registerHeaderTab({
  items: [
    { title: '整理任务', tab: 'tasks' },
    { title: '重命名规则', tab: 'rules' },
    { title: '后台任务', tab: 'background' },
    { title: '整理历史', tab: 'history' },
  ],
  modelValue: activeTab,
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <v-window v-model="activeTab">
      <!-- ===== 整理任务 ===== -->
      <v-window-item value="tasks">
        <TasksTab
          :rules="rules"
          :tasks="tasks"
          :loading="loading"
          @update:tasks="tasks = $event"
          @save="saveConfig"
        />
      </v-window-item>

      <!-- ===== 重命名规则 ===== -->
      <v-window-item value="rules">
        <RulesTab
          :rules="rules"
          :loading="loading"
          @update:rules="rules = $event"
          @save="saveConfig"
        />
      </v-window-item>

      <!-- ===== 后台任务 ===== -->
      <v-window-item value="background">
        <BackgroundTasksTab
          :background-tasks="backgroundTasks"
          @refresh="fetchBackgroundTasks"
        />
      </v-window-item>

      <!-- ===== 整理历史 ===== -->
      <v-window-item value="history">
        <OrganizeHistoryTab ref="historyTabRef" />
      </v-window-item>
    </v-window>

    <!-- 二级弹窗 — 任务中心 -->
    <TaskCenterModal v-model="showTaskCenter" />
  </v-container>
</template>
