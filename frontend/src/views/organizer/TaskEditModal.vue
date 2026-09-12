<script setup lang="ts">
/**
 * TaskEditModal — 任务编辑弹窗
 *
 * 分 Tab 表单: 核心配置 / 自动化 / 过滤规则 / 高级选项
 */
import { ref, computed, watch } from 'vue'
import FolderBrowserModal from './FolderBrowserModal.vue'

defineOptions({ name: 'TaskEditModal' })

const props = defineProps<{
  modelValue: boolean
  isNew: boolean
  taskForm: any
  rules: any[]
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  save: []
}>()

const taskEditTab = ref('basic')

const actionTypeOptions = computed(() => {
  const options = [
    { title: '物理移动', value: 'move' },
    { title: '完整复制', value: 'copy' },
    { title: '建立硬链', value: 'link' },
    { title: 'CD2 移动', value: 'cd2_move' },
    { title: 'CD2 复制', value: 'cd2_copy' },
    { title: '仅记录哈希', value: 'hash_only' },
  ]
  // 任一端选择了 CD2 云盘：仅支持云操作模式
  if (props.taskForm.source_via === 'cd2' || props.taskForm.target_via === 'cd2') {
    return options.filter((o) => ['cd2_move', 'cd2_copy'].includes(o.value))
  }
  return options
})

// 切换源/目标类型后，若当前操作类型不再可选则自动纠正
watch(
  () => [props.taskForm.source_via, props.taskForm.target_via],
  () => {
    const valid = actionTypeOptions.value.some((o) => o.value === props.taskForm.action_type)
    if (!valid) {
      props.taskForm.action_type = 'cd2_move'
    }
  }
)

// ---------- 目录浏览选择 ----------
const showFolderBrowser = ref(false)
const browsingField = ref<'source_dir' | 'target_dir'>('source_dir')
const browsingVia = computed(() =>
  browsingField.value === 'source_dir' ? props.taskForm.source_via : props.taskForm.target_via
)

const openFolderBrowser = (field: 'source_dir' | 'target_dir') => {
  browsingField.value = field
  showFolderBrowser.value = true
}

const onFolderSelected = (path: string) => {
  props.taskForm[browsingField.value] = path
}
</script>

<template>
  <v-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" max-width="720" scrollable>
    <v-card class="glass-card">
<v-card-title class="pa-4 d-flex align-center">
<v-icon start>mdi-folder-sync-outline</v-icon>
{{ isNew ? '创建新整理任务' : '编辑任务配置' }}
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="emit('update:modelValue', false)" />
</v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <v-tabs v-model="taskEditTab" density="compact" color="primary" class="mb-4">
          <v-tab value="basic">核心配置</v-tab>
          <v-tab value="automation">自动化</v-tab>
          <v-tab value="filters">过滤规则</v-tab>
          <v-tab value="advanced">高级选项</v-tab>
        </v-tabs>

        <v-window v-model="taskEditTab">
          <!-- 核心配置 -->
          <v-window-item value="basic">
            <v-text-field
              v-model="taskForm.name"
              label="任务名称"
              placeholder="起个名字"
              variant="outlined"
              density="compact"
              class="mb-3"
            />

            <v-select
              v-model="taskForm.rule_id"
              label="重命名规则"
              :items="rules.map((r: any) => ({ title: r.name, value: r.id }))"
              clearable
              placeholder="选择规则"
              variant="outlined"
              density="compact"
              class="mb-3"
            />

            <div class="mb-2">
              <div class="text-caption text-medium-emphasis mb-1">源目录类型</div>
              <v-btn-toggle v-model="taskForm.source_via" mandatory density="compact" class="mb-2">
                <v-btn value="local" prepend-icon="mdi-harddisk">本地路径</v-btn>
                <v-btn value="cd2" prepend-icon="mdi-cloud-outline">CD2 云盘</v-btn>
              </v-btn-toggle>
            </div>
            <v-text-field
              v-model="taskForm.source_dir"
              :label="taskForm.source_via === 'cd2' ? '源目录 (CD2 路径，如 /115open/downloads)' : '源目录'"
              :placeholder="taskForm.source_via === 'cd2' ? '/115open/downloads' : '待整理的文件夹'"
              variant="outlined"
              density="compact"
              class="mb-1"
              append-inner-icon="mdi-folder-open-outline"
              @click:append-inner="openFolderBrowser('source_dir')"
            />
            <v-alert
              v-if="taskForm.source_via === 'cd2'"
              type="info" variant="tonal" density="compact" class="mb-3"
            >
              将通过 CD2 gRPC 直接扫描云盘目录（无需挂载）。云盘源暂不支持关联字幕识别与哈希计算。
            </v-alert>

            <div class="mb-2 mt-2">
              <div class="text-caption text-medium-emphasis mb-1">目标目录类型</div>
              <v-btn-toggle v-model="taskForm.target_via" mandatory density="compact" class="mb-2">
                <v-btn value="local" prepend-icon="mdi-harddisk">本地路径</v-btn>
                <v-btn value="cd2" prepend-icon="mdi-cloud-outline">CD2 云盘</v-btn>
              </v-btn-toggle>
            </div>
            <v-text-field
              v-model="taskForm.target_dir"
              :label="taskForm.target_via === 'cd2' ? '目标目录 (CD2 路径，如 /115open/media)' : '目标目录'"
              :placeholder="taskForm.target_via === 'cd2' ? '/115open/media' : '整理后的根目录'"
              variant="outlined"
              density="compact"
              class="mb-1"
              append-inner-icon="mdi-folder-open-outline"
              @click:append-inner="openFolderBrowser('target_dir')"
            />
            <v-alert
              v-if="taskForm.target_via === 'cd2'"
              type="info" variant="tonal" density="compact" class="mb-3"
            >
              整理结果将直接写入 CD2 云盘：云→云走服务器端移动/复制；本地→云走 Remote Upload 协议上传。
            </v-alert>
            <v-alert
              v-if="taskForm.source_via === 'cd2' && taskForm.target_via === 'local'"
              type="info" variant="tonal" density="compact" class="mb-3"
            >
              将通过 CD2 下载接口把云端文件直接下载到本地目录（免挂载），完成后可按操作类型删除云端源文件。
            </v-alert>

            <v-select
              v-model="taskForm.action_type"
              label="操作类型"
              :items="actionTypeOptions"
              variant="outlined"
              density="compact"
            />
          </v-window-item>

          <!-- 自动化 -->
          <v-window-item value="automation">
            <div class="org-config-row mb-4">
              <v-switch v-model="taskForm.incremental_enabled" color="primary" density="compact" hide-details />
              <div class="flex-grow-1">
                <div class="font-weight-medium">实时监控</div>
                <div class="text-caption text-medium-emphasis">监听文件系统事件</div>
                <div v-if="taskForm.source_via === 'cd2'" class="text-caption text-warning">
                  云盘源暂不支持实时监控（本地文件系统事件不可用），任务将按计划扫描执行
                </div>
              </div>
            </div>

            <template v-if="taskForm.incremental_enabled">
              <v-select
                v-model="taskForm.incremental_mode"
                label="监控模式"
                :items="[{ title: '实时 (Inotify)', value: 'realtime' }, { title: '轮询', value: 'polling' }]"
                variant="outlined"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-if="taskForm.incremental_mode === 'polling'"
                v-model="taskForm.monitor_interval"
                label="轮询间隔 (秒)"
                type="number"
                variant="outlined"
                density="compact"
                class="mb-3"
              />
            </template>

            <div class="org-config-row mb-4">
              <v-switch v-model="taskForm.scheduler_enabled" color="primary" density="compact" hide-details />
              <div class="flex-grow-1">
                <div class="font-weight-medium">定时扫描</div>
                <div class="text-caption text-medium-emphasis">按固定间隔自动扫描</div>
              </div>
            </div>

            <v-text-field
              v-if="taskForm.scheduler_enabled"
              v-model="taskForm.scheduler_interval"
              label="扫描间隔 (秒)"
              type="number"
              variant="outlined"
              density="compact"
              class="mb-3"
            />

            <div class="org-config-row mb-4">
              <v-switch v-model="taskForm.skip_rate_limit" color="primary" density="compact" hide-details />
              <div class="flex-grow-1">
                <div class="font-weight-medium">跳过限流</div>
                <div class="text-caption text-medium-emphasis">跳过某些类型的限流</div>
              </div>
            </div>

            <v-text-field
              v-model="taskForm.process_interval"
              label="限流间隔 (秒)"
              type="number"
              variant="outlined"
              density="compact"
              class="mb-3"
            />

            <template v-if="taskForm.skip_rate_limit">
              <div class="text-subtitle-2 font-weight-medium mb-2">跳过类型</div>
              <v-checkbox v-model="taskForm.skip_rate_limit_types" value="history" label="历史记录跳过" density="compact" hide-details />
              <v-checkbox v-model="taskForm.skip_rate_limit_types" value="recognition_failed" label="识别失败跳过" density="compact" hide-details />
              <v-checkbox v-model="taskForm.skip_rate_limit_types" value="emby_exists" label="Emby已存在跳过" density="compact" hide-details />
              <v-checkbox v-model="taskForm.skip_rate_limit_types" value="regex_match" label="正则匹配跳过" density="compact" hide-details />
            </template>
          </v-window-item>

          <!-- 过滤规则 -->
          <v-window-item value="filters">
            <div class="text-subtitle-2 font-weight-medium mb-3">忽略文件正则</div>
            <v-combobox
              v-model="taskForm.ignore_file_regex"
              label="添加忽略文件正则"
              multiple
              chips
              clearable
              variant="outlined"
              density="compact"
              class="mb-4"
              placeholder="输入正则后回车添加"
            />

            <div class="text-subtitle-2 font-weight-medium mb-3">忽略目录正则</div>
            <v-combobox
              v-model="taskForm.ignore_dir_regex"
              label="添加忽略目录正则"
              multiple
              chips
              clearable
              variant="outlined"
              density="compact"
              placeholder="输入正则后回车添加"
            />
          </v-window-item>

          <!-- 高级选项 -->
          <v-window-item value="advanced">
            <div class="d-flex flex-column ga-4">
              <div class="switch-row">
                <v-switch v-model="taskForm.anime_priority" density="compact" hide-details color="primary" />
                <div>
                  <div class="switch-label">动漫优先</div>
                  <div class="switch-desc">优先使用动漫识别策略</div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="taskForm.overwrite_mode" :disabled="taskForm.action_type === 'hash_only'" density="compact" hide-details color="primary" />
                <div>
                  <div class="switch-label">覆盖模式</div>
                  <div class="switch-desc">目标已存在时允许覆盖</div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="taskForm.trigger_strm" :disabled="taskForm.action_type === 'hash_only'" density="compact" hide-details color="primary" />
                <div>
                  <div class="switch-label">联动 STRM</div>
                  <div class="switch-desc">整理后自动生成 STRM 文件</div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="taskForm.clean_empty_dir" :disabled="taskForm.action_type === 'hash_only'" density="compact" hide-details color="primary" />
                <div>
                  <div class="switch-label">清理空目录</div>
                  <div class="switch-desc">整理后删除源目录中的空文件夹</div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="taskForm.ignore_history" density="compact" hide-details color="primary" />
                <div>
                  <div class="switch-label">忽略历史</div>
                  <div class="switch-desc">跳过已成功整理的历史记录</div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="taskForm.retry_failed" density="compact" hide-details color="primary" />
                <div>
                  <div class="switch-label">重试失败项</div>
                  <div class="switch-desc">重新尝试之前识别失败的文件</div>
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="taskForm.check_emby_exists" :disabled="taskForm.action_type === 'hash_only'" density="compact" hide-details color="primary" />
                <div>
                  <div class="switch-label">Emby 检查</div>
                  <div class="switch-desc">检测 Emby 库是否存在，存在则跳过</div>
                </div>
              </div>

              <div>
                <div class="switch-row">
                  <v-switch v-model="taskForm.calculate_hash" :disabled="taskForm.action_type === 'hash_only'" density="compact" hide-details color="primary" />
                  <div>
                    <div class="switch-label">哈希计算</div>
                    <div class="switch-desc">整理时计算 SHA1 和 ED2K</div>
                  </div>
                </div>
                <div v-if="taskForm.calculate_hash && taskForm.action_type !== 'hash_only'" class="org-hash-warning">
                  ⚠️ 需要读取整个文件，云盘环境不建议开启
                </div>
              </div>

              <div class="switch-row">
                <v-switch v-model="taskForm.series_fingerprint" density="compact" hide-details color="primary" />
                <div>
                  <div class="switch-label">智能记忆</div>
                  <div class="switch-desc">自动记住系列特征，后续秒级识别</div>
                </div>
              </div>
            </div>
          </v-window-item>
        </v-window>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="emit('update:modelValue', false)">取消</v-btn>
        <v-btn variant="tonal" color="primary" prepend-icon="mdi-content-save-outline" @click="emit('save')">保存任务配置</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 目录浏览选择 -->
  <FolderBrowserModal
    v-model="showFolderBrowser"
    :via="browsingVia"
    :title="browsingField === 'source_dir' ? '选择源目录' : '选择目标目录'"
    @select="onFolderSelected"
  />
</template>
