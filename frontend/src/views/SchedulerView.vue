<script setup lang="ts">
/**
 * SchedulerView — 任务计划
 *
 * 所有定时任务（自定义 + 系统内置）统一以卡片网格展示：
 * - 调度统一使用 cron 表达式；编辑弹窗提供图形化构建（间隔/每天/每周/每月），
 *   也可直接手写 cron，实时预览未来触发时间
 * - 自定义任务：添加 / 编辑 / 删除 / 启停 / 立即运行
 * - 系统内置任务：以 cron 覆盖配置修改周期，不允许删除
 * - 单击卡片进入编辑；WebSocket 实时推送 + 30s 轮询兜底
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  schedulerApi,
  type SchedulerJob,
  type SchedulerAction,
  type CustomScheduledJob,
  type CronPreview,
  type BuiltinExtraParam,
} from '@/api'
import { useNotification, useConfirm, useWebSocket } from '@/composables'
import { getStatusTag } from '@/utils/taskStatus'

defineOptions({ name: 'SchedulerView' })

const router = useRouter()
const { success, error: showError } = useNotification()
const { confirm } = useConfirm()

// --- 数据 ---
const builtinJobs = ref<SchedulerJob[]>([])
const customJobs = ref<CustomScheduledJob[]>([])
const actions = ref<SchedulerAction[]>([])
const loading = ref(false)

// 操作中的任务（防抖），key: `custom_${id}` / `builtin_${job_id}`
const runningIds = ref<Set<string>>(new Set())
const busyIds = ref<Set<string>>(new Set())

function customScheduleDesc(job: CustomScheduledJob): string {
  return job.schedule_desc || '-'
}

// 卡片统一视图：自定义任务在前，内置任务在后
const cards = computed(() => [
  ...customJobs.value.map(j => ({
    key: `custom_${j.id}`,
    kind: 'custom' as const,
    name: j.name,
    module: j.module || j.action_name,
    description: j.action_name,
    scheduleDesc: customScheduleDesc(j),
    enabled: j.enabled,
    locked: false,
    canRun: true,
    canEdit: true,
    canDelete: true,
    nextRun: j.next_run,
    lastRun: j.last_run,
    raw: j,
  })),
  ...builtinJobs.value.map(j => ({
    key: `builtin_${j.job_id}`,
    kind: 'builtin' as const,
    name: j.name,
    module: j.module,
    description: j.description,
    scheduleDesc: j.schedule_desc,
    enabled: j.enabled ?? true,
    locked: j.locked,
    canRun: j.can_run,
    canEdit: j.editable,
    canDelete: false,
    nextRun: j.next_run,
    lastRun: j.last_run,
    raw: j,
  })),
])

const actionMap = computed(() => {
  const map: Record<string, SchedulerAction> = {}
  for (const a of actions.value) map[a.action] = a
  return map
})

// --- 编辑弹窗 ---
const showDialog = ref(false)
const saving = ref(false)
// editTarget: null=新建自定义；{kind:'custom', job}；{kind:'builtin', job}
const editTarget = ref<{ kind: 'custom' | 'builtin'; job: any } | null>(null)

// --- cron 图形化构建 ---
type BuildMode = 'interval' | 'daily' | 'weekly' | 'monthly' | 'custom'
const buildMode = ref<BuildMode>('interval')
const intervalValue = ref(15)
const intervalUnit = ref<number>(1) // 1=分钟 60=小时 1440=天
const runTime = ref('09:00')
const weeklyDow = ref(1) // 0=周日 1-6=周一~周六
const monthlyDom = ref(1)
const cronText = ref('*/15 * * * *')
const formEnabled = ref(true)
const formName = ref('')
const formAction = ref('')

// 内置任务的附加参数（如死种清理的超时阈值）
const extraDefs = ref<BuiltinExtraParam[]>([])
const extraValues = ref<Record<string, any>>({})

// 自定义任务的动作参数（如 TMDB 全量刷新的筛选条件）
const actionParamValues = ref<Record<string, any>>({})
const selectedActionParams = computed(() => actionMap.value[formAction.value]?.params_schema || [])

const generatedCron = computed(() => {
  const time = runTime.value || '09:00'
  const [h, m] = time.split(':').map((v) => parseInt(v, 10) || 0)
  switch (buildMode.value) {
    case 'interval': {
      const v = Math.max(1, Math.round(intervalValue.value || 1))
      if (intervalUnit.value === 1440) return `0 0 */${v} * *`
      return intervalUnit.value === 1 ? `*/${v} * * * *` : `0 */${v} * * *`
    }
    case 'daily':
      return `${m} ${h} * * *`
    case 'weekly':
      return `${m} ${h} * * ${weeklyDow.value}`
    case 'monthly':
      return `${m} ${h} ${Math.min(31, Math.max(1, monthlyDom.value))} * *`
    default:
      return cronText.value
  }
})

// 图形化输入变化时同步 cron 文本
watch([buildMode, intervalValue, intervalUnit, runTime, weeklyDow, monthlyDom], () => {
  if (buildMode.value !== 'custom') {
    cronText.value = generatedCron.value
  }
})

// 手动改 cron 文本时切到自定义模式
watch(cronText, (val) => {
  if (buildMode.value !== 'custom' && val !== generatedCron.value) {
    buildMode.value = 'custom'
  }
})

// 间隔不均匀提示（cron 分钟步进会在每小时重置）
const unevenIntervalHint = computed(() => {
  if (buildMode.value !== 'interval') return ''
  if (intervalUnit.value === 1) {
    const v = Math.round(intervalValue.value || 0)
    if (v > 60 || 60 % v !== 0) return '注意：分钟步进会在每小时重置，实际触发间隔可能不均匀'
  } else if (intervalUnit.value === 60) {
    const v = Math.round(intervalValue.value || 0)
    if (v > 24 || 24 % v !== 0) return '注意：小时步进会在每天零点重置，实际触发间隔可能不均匀'
  }
  return ''
})

// cron 预览
const cronPreview = ref<CronPreview | null>(null)
const cronError = ref('')
let previewTimer: ReturnType<typeof setTimeout> | null = null

watch(cronText, () => {
  if (!showDialog.value) return
  if (previewTimer) clearTimeout(previewTimer)
  cronPreview.value = null
  cronError.value = ''
  previewTimer = setTimeout(async () => {
    const cron = cronText.value.trim()
    if (!cron) return
    try {
      cronPreview.value = await schedulerApi.cronPreview(cron)
    } catch (e: any) {
      cronError.value = e?.message || '无效的 cron 表达式'
    }
  }, 400)
})

function parseCronToForm(cron: string) {
  const fields = (cron || '').trim().split(/\s+/)
  if (fields.length !== 5) {
    buildMode.value = 'custom'
    return
  }
  const [minute, hour, dom, month, dow] = fields
  const setTime = (h: number, m: number) => {
    runTime.value = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
  }
  try {
    if (hour === '*' && minute.startsWith('*/')) {
      buildMode.value = 'interval'
      intervalUnit.value = 1
      intervalValue.value = parseInt(minute.slice(2), 10) || 15
      return
    }
    if (minute === '0' && hour.startsWith('*/')) {
      buildMode.value = 'interval'
      intervalUnit.value = 60
      intervalValue.value = parseInt(hour.slice(2), 10) || 2
      return
    }
    if (minute === '0' && hour === '0' && dom.startsWith('*/')) {
      buildMode.value = 'interval'
      intervalUnit.value = 1440
      intervalValue.value = parseInt(dom.slice(2), 10) || 7
      return
    }
    if (dom === '*' && month === '*' && dow === '*') {
      buildMode.value = 'daily'
      setTime(parseInt(hour, 10), parseInt(minute, 10))
      return
    }
    if (dom === '*' && month === '*' && dow !== '*') {
      buildMode.value = 'weekly'
      weeklyDow.value = parseInt(dow, 10) % 7
      setTime(parseInt(hour, 10), parseInt(minute, 10))
      return
    }
    if (month === '*' && dow === '*' && dom !== '*') {
      buildMode.value = 'monthly'
      monthlyDom.value = parseInt(dom, 10) || 1
      setTime(parseInt(hour, 10), parseInt(minute, 10))
      return
    }
  } catch (e) {
    // fallthrough
  }
  buildMode.value = 'custom'
}

const dialogTitle = computed(() => {
  if (!editTarget.value) return '添加定时任务'
  return `编辑：${editTarget.value.job.name}`
})
const selectedActionDesc = computed(() => actionMap.value[formAction.value]?.description || '')

// --- WebSocket ---
const { on, onReconnect } = useWebSocket()
let unsubTaskRecord: (() => void) | null = null
let unsubReconnect: (() => void) | null = null
let refreshTimer: ReturnType<typeof setInterval> | null = null

// --- 方法 ---
async function fetchAll() {
  if (loading.value) return
  loading.value = true
  try {
    const [builtinRes, customRes, actionsRes] = await Promise.all([
      schedulerApi.getJobs(),
      schedulerApi.getCustomJobs(),
      schedulerApi.getActions(),
    ])
    builtinJobs.value = builtinRes?.jobs || []
    customJobs.value = customRes?.jobs || []
    actions.value = actionsRes?.actions || []
  } catch (e) {
    showError('获取任务计划失败')
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  editTarget.value = null
  formName.value = ''
  formAction.value = actions.value[0]?.action || ''
  buildMode.value = 'interval'
  intervalValue.value = 15
  intervalUnit.value = 1
  runTime.value = '09:00'
  weeklyDow.value = 1
  monthlyDom.value = 1
  cronText.value = '*/15 * * * *'
  formEnabled.value = true
  cronPreview.value = null
  cronError.value = ''
  extraDefs.value = []
  extraValues.value = {}
  actionParamValues.value = {}
  showDialog.value = true
  triggerPreview()
}

function openEditDialog(card: typeof cards.value[number]) {
  editTarget.value = { kind: card.kind, job: card.raw }
  formName.value = card.name
  formEnabled.value = card.enabled
  cronPreview.value = null
  cronError.value = ''
  if (card.kind === 'custom') {
    const job = card.raw as CustomScheduledJob
    formAction.value = job.action
    parseCronToForm(job.cron)
    extraDefs.value = []
    extraValues.value = {}
    actionParamValues.value = { ...(job.params || {}) }
  } else {
    const job = card.raw as SchedulerJob
    formAction.value = ''
    parseCronToForm(job.cron || '')
    extraDefs.value = job.extra_params || []
    extraValues.value = Object.fromEntries((job.extra_params || []).map(p => [p.key, p.value]))
  }
  showDialog.value = true
  triggerPreview()
}

function triggerPreview() {
  // 打开弹窗后主动触发一次预览
  if (previewTimer) clearTimeout(previewTimer)
  previewTimer = setTimeout(async () => {
    try {
      cronPreview.value = await schedulerApi.cronPreview(cronText.value.trim())
    } catch (e: any) {
      cronError.value = e?.message || '无效的 cron 表达式'
    }
  }, 100)
}

async function saveJob() {
  const cron = cronText.value.trim()
  if (!cron) {
    showError('请填写 cron 表达式')
    return
  }
  saving.value = true
  try {
    // 自定义动作参数（按动作目录的 params_schema 收集）
    let params: Record<string, any> | null = null
    const schema = actionMap.value[formAction.value]?.params_schema
    if (schema?.length) {
      params = {}
      for (const p of schema) {
        const v = actionParamValues.value[p.key]
        if (v !== undefined && v !== null && v !== '') {
          params[p.key] = p.type === 'number' ? Number(v) : v
        }
      }
      if (!Object.keys(params).length) params = null
    }

    if (!editTarget.value) {
      if (!formAction.value) {
        showError('请选择要执行的任务')
        saving.value = false
        return
      }
      await schedulerApi.createCustomJob({
        name: formName.value,
        action: formAction.value,
        cron,
        params,
        enabled: formEnabled.value,
      })
      success('定时任务已创建')
    } else if (editTarget.value.kind === 'custom') {
      const job = editTarget.value.job as CustomScheduledJob
      await schedulerApi.updateCustomJob(job.id, {
        name: formName.value,
        action: job.action,
        cron,
        params,
        enabled: formEnabled.value,
      })
      success('定时任务已更新')
    } else {
      const job = editTarget.value.job as SchedulerJob
      const body: { enabled?: boolean; cron?: string; extra?: Record<string, number> } = {
        enabled: formEnabled.value,
      }
      if (extraDefs.value.length > 0) {
        const extra: Record<string, number> = {}
        for (const p of extraDefs.value) {
          const v = extraValues.value[p.key]
          if (p.type === 'number') {
            extra[p.key] = Number(v) || 0
          }
        }
        body.extra = extra
      }
      body.cron = cron
      await schedulerApi.updateJob(job.job_id, body)
      success('定时任务已更新')
    }
    showDialog.value = false
    fetchAll()
  } catch (e: any) {
    showError(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function deleteJob(card: typeof cards.value[number]) {
  const ok = await confirm({
    title: '确认删除',
    content: `确定要删除定时任务「${card.name}」吗？`,
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await schedulerApi.deleteCustomJob((card.raw as CustomScheduledJob).id)
    success('定时任务已删除')
    fetchAll()
  } catch (e) {
    showError('删除失败')
  }
}

async function toggleEnabled(card: typeof cards.value[number], enabled: boolean) {
  if (busyIds.value.has(card.key)) return
  busyIds.value.add(card.key)
  try {
    if (card.kind === 'custom') {
      await schedulerApi.toggleCustomJob((card.raw as CustomScheduledJob).id, enabled)
    } else {
      await schedulerApi.toggleJob((card.raw as SchedulerJob).job_id, enabled)
    }
    success(enabled ? `已启用「${card.name}」` : `已停用「${card.name}」`)
    fetchAll()
  } catch (e: any) {
    showError(e?.message || '操作失败')
    fetchAll()
  } finally {
    busyIds.value.delete(card.key)
  }
}

async function runJob(card: typeof cards.value[number]) {
  if (runningIds.value.has(card.key)) return
  const ok = await confirm({
    title: '立即运行',
    content: `确定要立即执行「${card.name}」吗？执行日志可在任务中心查看。`,
    confirmColor: 'primary',
  })
  if (!ok) return
  runningIds.value.add(card.key)
  try {
    if (card.kind === 'custom') {
      await schedulerApi.runCustomJob((card.raw as CustomScheduledJob).id)
    } else {
      await schedulerApi.runJob((card.raw as SchedulerJob).job_id)
    }
    success(`「${card.name}」已开始执行`)
    fetchAll()
  } catch (e: any) {
    showError(e?.message || '触发失败')
  } finally {
    runningIds.value.delete(card.key)
  }
}

function viewLogs(module: string) {
  if (module) {
    router.push({ path: '/task-history', query: { module } })
  } else {
    router.push('/task-history')
  }
}

// --- 格式化 ---
function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '-'
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${seconds % 60}秒`
  return `${Math.floor(seconds / 3600)}时${Math.floor((seconds % 3600) / 60)}分`
}

// --- 生命周期 ---
onMounted(() => {
  fetchAll()

  unsubTaskRecord = on('task_record', () => {
    if (!loading.value) fetchAll()
  })
  unsubReconnect = onReconnect(() => fetchAll())
  refreshTimer = setInterval(() => {
    if (!loading.value) fetchAll()
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (unsubTaskRecord) { unsubTaskRecord(); unsubTaskRecord = null }
  if (unsubReconnect) { unsubReconnect(); unsubReconnect = null }
  if (previewTimer) clearTimeout(previewTimer)
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <div class="d-flex align-center mb-4">
      <span class="text-caption">共 {{ cards.length }} 个定时任务</span>
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openCreateDialog">添加定时任务</v-btn>
    </div>

    <!-- 任务卡片网格 -->
    <v-row v-if="loading && cards.length === 0">
      <v-col v-for="i in 6" :key="i" cols="12" sm="6" md="4">
        <v-skeleton-loader type="card" />
      </v-col>
    </v-row>

    <v-row v-else-if="cards.length > 0">
      <v-col v-for="card in cards" :key="card.key" cols="12" sm="6" md="4">
        <v-card
          class="glass-card manage-card"
          :class="{ 'hover-lift': true, 'cursor-pointer': card.canEdit }"
          @click="card.canEdit && openEditDialog(card)"
        >
          <!-- 标题行 -->
          <div class="sc-card__header">
            <div class="sc-card__title text-truncate" :title="card.name">{{ card.name }}</div>
            <v-switch
              v-if="!card.locked"
              :model-value="card.enabled"
              :loading="busyIds.has(card.key)"
              :disabled="busyIds.has(card.key)"
              color="primary"
              hide-details
              density="compact"
              class="sc-card__switch"
              @update:model-value="(val: boolean | null) => toggleEnabled(card, !!val)"
              @click.stop
            />
          </div>

          <!-- 信息区 -->
          <div class="sc-card__body">
            <div class="text-caption text-truncate mb-2" :title="card.description">
              {{ card.description }}
            </div>

            <div class="sc-meta-row">
              <span class="sc-meta-label">
                <v-icon start size="13">mdi-timer-outline</v-icon>周期
              </span>
              <span class="font-weight-medium">{{ card.scheduleDesc }}</span>
            </div>
            <div class="sc-meta-row">
              <span class="sc-meta-label">
                <v-icon start size="13">mdi-clock-check-outline</v-icon>下次执行
              </span>
              <span>{{ card.nextRun ? formatTime(card.nextRun) : '未调度' }}</span>
            </div>
            <div class="sc-meta-row">
              <span class="sc-meta-label">
                <v-icon start size="13">mdi-history</v-icon>上次执行
              </span>
              <span class="d-inline-flex align-center ga-1">
                <template v-if="card.lastRun">
                  <v-chip size="x-small" :color="getStatusTag(card.lastRun.status).color" variant="tonal">
                    {{ getStatusTag(card.lastRun.status).label }}
                  </v-chip>
                  <span>{{ formatTime(card.lastRun.started_at) }}</span>
                  <span v-if="card.lastRun.status === 'completed' && card.lastRun.duration_seconds != null">
                    ({{ formatDuration(card.lastRun.duration_seconds) }})
                  </span>
                </template>
                <span v-else>暂无记录</span>
              </span>
            </div>
            <v-chip
              v-if="card.lastRun?.status === 'running' || runningIds.has(card.key)"
              size="x-small" color="info" variant="tonal" class="mt-2"
            >
              <v-progress-circular indeterminate size="10" width="1" class="mr-1" />
              运行中
            </v-chip>
          </div>

          <v-divider />
          <v-card-actions class="sc-card__actions">
            <v-spacer />
            <v-btn
              v-if="card.canRun"
              size="small" variant="tonal" color="primary" prepend-icon="mdi-play-outline"
              :disabled="runningIds.has(card.key) || card.lastRun?.status === 'running'"
              :loading="runningIds.has(card.key)"
              @click.stop="runJob(card)"
            >
              执行
            </v-btn>
            <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-text-box-outline" @click.stop="viewLogs(card.module)">
              日志
            </v-btn>
            <v-btn
              v-if="card.canDelete"
              size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline"
              @click.stop="deleteJob(card)"
            >
              删除
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-calendar-clock</v-icon>
      <div class="text-h6 font-weight-medium">暂无定时任务</div>
    </div>

    <!-- ===== 新增/编辑弹窗 ===== -->
    <v-dialog v-model="showDialog" max-width="560" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4 d-flex align-center">
          <v-icon start color="primary">mdi-calendar-plus</v-icon>
          {{ dialogTitle }}
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showDialog = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <!-- 基本信息 -->
          <template v-if="!editTarget || editTarget.kind === 'custom'">
            <div class="text-subtitle-2 font-weight-medium mb-2">基本信息</div>
            <v-row density="compact">
              <v-col cols="12" sm="6">
                <v-select
                  v-model="formAction"
                  :items="actions"
                  item-title="name"
                  item-value="action"
                  label="执行任务"
                  variant="outlined"
                  density="compact"
                />
              </v-col>
              <v-col cols="12" sm="6">
                <v-text-field
                  v-model="formName"
                  label="任务名称"
                  variant="outlined"
                  density="compact"
                  placeholder="留空默认使用任务名"
                />
              </v-col>
              <v-col v-if="selectedActionDesc" cols="12" class="pt-0">
                <div class="text-caption">{{ selectedActionDesc }}</div>
              </v-col>
              <!-- 动作参数（如 TMDB 全量刷新的筛选条件） -->
              <template v-if="selectedActionParams.length > 0">
                <v-col v-for="p in selectedActionParams" :key="p.key" cols="12" sm="6">
                  <v-select
                    v-if="p.type === 'select'"
                    v-model="actionParamValues[p.key]"
                    :label="p.label"
                    :items="p.options || []"
                    item-title="title"
                    item-value="value"
                    variant="outlined"
                    density="compact"
                    :hint="p.hint"
                    persistent-hint
                  />
                  <v-text-field
                    v-else
                    v-model="actionParamValues[p.key]"
                    :label="p.label"
                    :type="p.type === 'number' ? 'number' : 'text'"
                    :hint="p.hint"
                    persistent-hint
                    variant="outlined"
                    density="compact"
                  />
                </v-col>
              </template>
            </v-row>
          </template>

          <v-divider class="my-3" />

          <!-- 执行计划 -->
          <div class="text-subtitle-2 font-weight-medium mb-2">执行计划（生成 cron 表达式，也可直接手写）</div>
          <v-row density="compact">
            <v-col cols="12">
              <v-btn-toggle v-model="buildMode" mandatory color="primary" class="w-100 sc-cron-toggle">
                <v-btn value="interval" class="flex-grow-1">间隔</v-btn>
                <v-btn value="daily" class="flex-grow-1">每天</v-btn>
                <v-btn value="weekly" class="flex-grow-1">每周</v-btn>
                <v-btn value="monthly" class="flex-grow-1">每月</v-btn>
                <v-btn value="custom" class="flex-grow-1">自定义</v-btn>
              </v-btn-toggle>
            </v-col>

            <template v-if="buildMode === 'interval'">
              <v-col cols="6" sm="4">
                <v-text-field
                  v-model.number="intervalValue"
                  label="间隔"
                  type="number"
                  min="1"
                  variant="outlined"
                  density="compact"
                  hide-details
                />
              </v-col>
              <v-col cols="6" sm="4">
            <v-select
              v-model="intervalUnit"
              :items="[
                { title: '分钟', value: 1 },
                { title: '小时', value: 60 },
                { title: '天', value: 1440 },
              ]"
              item-title="title"
              item-value="value"
              label="单位"
              variant="outlined"
              density="compact"
              hide-details
            />
              </v-col>
              <v-col v-if="unevenIntervalHint" cols="12" class="pt-0">
                <div class="text-caption">{{ unevenIntervalHint }}</div>
              </v-col>
            </template>

            <template v-else-if="buildMode === 'daily'">
              <v-col cols="12" sm="6">
                <v-text-field
                  v-model="runTime"
                  label="每天执行时间"
                  type="time"
                  variant="outlined"
                  density="compact"
                />
              </v-col>
            </template>

            <template v-else-if="buildMode === 'weekly'">
              <v-col cols="6" sm="4">
                <v-select
                  v-model="weeklyDow"
                  :items="[
                    { title: '周一', value: 1 }, { title: '周二', value: 2 }, { title: '周三', value: 3 },
                    { title: '周四', value: 4 }, { title: '周五', value: 5 }, { title: '周六', value: 6 },
                    { title: '周日', value: 0 },
                  ]"
                  item-title="title"
                  item-value="value"
                  label="星期"
                  variant="outlined"
                  density="compact"
                />
              </v-col>
              <v-col cols="6" sm="4">
                <v-text-field
                  v-model="runTime"
                  label="时间"
                  type="time"
                  variant="outlined"
                  density="compact"
                />
              </v-col>
            </template>

            <template v-else-if="buildMode === 'monthly'">
              <v-col cols="6" sm="4">
                <v-text-field
                  v-model.number="monthlyDom"
                  label="每月几号"
                  type="number"
                  min="1"
                  max="31"
                  variant="outlined"
                  density="compact"
                />
              </v-col>
              <v-col cols="6" sm="4">
                <v-text-field
                  v-model="runTime"
                  label="时间"
                  type="time"
                  variant="outlined"
                  density="compact"
                />
              </v-col>
            </template>

            <v-col cols="12">
              <v-text-field
                v-model="cronText"
                label="Cron 表达式（分 时 日 月 周）"
                variant="outlined"
                density="compact"
                hide-details="auto"
                :error-messages="cronError"
              />
            </v-col>
            <v-col v-if="cronPreview" cols="12" class="pt-0">
              <div class="text-caption">
                {{ cronPreview.desc }}，接下来：
                <span v-for="(t, i) in cronPreview.next_runs" :key="i">
                  {{ formatTime(t) }}<span v-if="i < cronPreview.next_runs.length - 1">、</span>
                </span>
              </div>
            </v-col>
          </v-row>

          <!-- 内置任务的附加参数（如死种清理的超时阈值） -->
          <template v-if="editTarget?.kind === 'builtin' && extraDefs.length > 0">
            <v-divider class="my-3" />
            <div class="text-subtitle-2 font-weight-medium mb-2">任务参数</div>
            <v-row density="compact">
              <v-col v-for="p in extraDefs" :key="p.key" cols="12" sm="6">
                <v-text-field
                  v-model="extraValues[p.key]"
                  :label="p.label"
                  :type="p.type === 'number' ? 'number' : 'text'"
                  :min="p.min"
                  :max="p.max"
                  :hint="p.hint"
                  persistent-hint
                  variant="outlined"
                  density="compact"
                />
              </v-col>
            </v-row>
          </template>

          <v-divider class="my-3" />

          <v-row density="compact">
            <v-col cols="12">
              <div class="d-flex align-center ga-3 py-1">
                <v-switch
                  v-model="formEnabled"
                  label="启用状态"
                  color="primary"
                  density="compact"
                  hide-details
                />
                <span class="text-caption">
                  {{ formEnabled ? '任务将按计划自动执行' : '任务已暂停，不会自动执行' }}
                </span>
              </div>
            </v-col>
          </v-row>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showDialog = false">取消</v-btn>
          <v-btn variant="tonal" color="primary" prepend-icon="mdi-content-save-outline" :loading="saving" @click="saveJob">
            {{ editTarget ? '保存' : '创建任务' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<style scoped>
.sc-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 16px 0 16px;
}

.sc-card__title {
  font-weight: bold;
  font-size: 0.95rem;
  min-width: 0;
}

.sc-card__switch {
  flex-shrink: 0;
  margin-top: -6px;
}

.sc-card__switch :deep(.v-selection-control) {
  min-height: unset;
}

.sc-card__body {
  padding: 8px 16px 10px 16px;
}

.sc-meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.78rem;
  padding: 2px 0;
}

.sc-meta-label {
  min-width: 76px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.sc-card__actions {
  padding: 6px 8px;
}

.sc-cron-toggle .v-btn {
  font-size: 0.8rem;
}
</style>
