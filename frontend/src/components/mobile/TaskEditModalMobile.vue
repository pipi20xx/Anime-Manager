<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import { 
  NModal, NForm, NFormItem, NTabs, NTabPane, NSpace, NSelect, 
  NCheckbox, NCheckboxGroup, NButton, NIcon, NGrid, NGi, NDynamicTags,
  NRadioGroup, NRadioButton, NSwitch, NCard
} from 'naive-ui'
import {
  FolderOpenOutlined as FolderIcon
} from '@vicons/material'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import FilePickerModal from '../FilePickerModal.vue'
import { useTaskEdit } from '../../composables/modals/useTaskEdit'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  taskData: any
  isNew: boolean
  availableRules: any[]
  apiBase: string
}>()

const emit = defineEmits(['update:show', 'save'])

const {
  form,
  showPicker,
  pickerTarget,
  openPicker,
  handlePickerConfirm,
  handleSave,
  actionOptions
} = useTaskEdit(props, emit)
</script>

<template>
  <AppGlassModal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    style="width: 100%; height: 100vh; margin: 0;"
    content-style="padding: 0; display: flex; flex-direction: column;"
    :title="isNew ? '创建新整理任务' : '编辑任务配置'"
  >
    <n-form label-placement="top" label-width="100" size="small" style="flex: 1; overflow-y: auto; padding: var(--m-spacing-lg);">
      <n-tabs type="line" animated>
        <n-tab-pane name="basic" tab="核心配置">
          <n-space vertical size="large" class="m-mt-md">
            <n-form-item><AppTextField v-model:value="form.name" label="任务名称" placeholder="起个名字" /></n-form-item>
            <n-form-item>
              <AppSelectField v-model:value="form.rule_id" label="重命名规则" :options="availableRules.map(r=>({label:r.name, value:r.id}))" placeholder="选择规则" clearable />
            </n-form-item>
            <n-form-item>
              <AppTextField v-model:value="form.source_dir" label="源目录" placeholder="待整理的文件夹">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openPicker('source')"><template #icon><n-icon><FolderIcon /></n-icon></template></n-button>
                </template>
              </AppTextField>
            </n-form-item>
            <n-form-item>
              <AppTextField v-model:value="form.target_dir" label="目标目录" placeholder="整理后的根目录">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openPicker('target')"><template #icon><n-icon><FolderIcon /></n-icon></template></n-button>
                </template>
              </AppTextField>
            </n-form-item>
            
            <!-- Mobile Optimization: Use Select instead of Radio Group -->
            <n-form-item>
              <AppSelectField v-model:value="form.action_type" label="操作类型" :options="actionOptions" placeholder="选择操作类型" />
            </n-form-item>
          </n-space>
        </n-tab-pane>
        
        <n-tab-pane name="automation" tab="自动化">
          <n-space vertical size="large" class="m-mt-md">
            <div class="m-config-row">
              <n-switch v-model:value="form.incremental_enabled" />
              <span class="m-config-row__label">实时监控</span>
              <AppSelectField 
                v-model:value="form.incremental_mode" 
                label="模式"
                style="width: 160px"
                :options="[{label: '实时', value: 'realtime'}, {label: '轮询', value: 'polling'}]" 
              />
            </div>
            <n-form-item v-if="form.incremental_mode === 'polling'">
              <AppTextField v-model:value="form.monitor_interval" label="轮询间隔" type="number" :min="1">
                <template #suffix>秒</template>
              </AppTextField>
            </n-form-item>
            <n-form-item v-else>
              <AppTextField :value="'实时监听文件系统事件 (Inotify)'" label="监控状态" readonly />
            </n-form-item>
            
            <div class="m-config-row">
              <n-switch v-model:value="form.scheduler_enabled" />
              <span class="m-config-row__label">定时扫描</span>
              <AppTextField v-model:value="form.scheduler_interval" label="扫描间隔" type="number" :min="60" style="width: 160px">
                <template #suffix>秒</template>
              </AppTextField>
            </div>

            <div class="m-config-row">
              <n-switch v-model:value="form.skip_rate_limit" />
              <span class="m-config-row__label">跳过限流</span>
              <n-space vertical :size="8" style="flex: 1;">
                <AppTextField v-model:value="form.process_interval" label="限流间隔" type="number" :min="0" style="width: 160px">
                  <template #suffix>秒</template>
                </AppTextField>
                <n-checkbox-group v-if="form.skip_rate_limit" v-model:value="form.skip_rate_limit_types">
                  <n-space vertical>
                    <n-checkbox value="history">历史记录跳过</n-checkbox>
                    <n-checkbox value="recognition_failed">识别失败跳过</n-checkbox>
                    <n-checkbox value="emby_exists">Emby已存在跳过</n-checkbox>
                    <n-checkbox value="regex_match">正则匹配跳过</n-checkbox>
                  </n-space>
                </n-checkbox-group>
              </n-space>
            </div>
          </n-space>
        </n-tab-pane>

        <n-tab-pane name="filters" tab="过滤规则">
          <n-space vertical size="large" class="m-mt-md">
            <n-form-item label="忽略文件正则"><n-dynamic-tags v-model:value="form.ignore_file_regex" /></n-form-item>
            <n-form-item label="忽略目录正则"><n-dynamic-tags v-model:value="form.ignore_dir_regex" /></n-form-item>
          </n-space>
        </n-tab-pane>

        <n-tab-pane name="advanced" tab="高级选项">
          <n-space vertical size="medium" class="m-mt-md">
            <div class="switch-row">
              <n-switch v-model:value="form.anime_priority" />
              <span class="switch-row__label">动漫优先</span>
              <span class="switch-row__desc">优先使用动漫专用识别策略，提高动漫识别准确率</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.overwrite_mode" :disabled="form.action_type === 'hash_only'" />
              <span class="switch-row__label">覆盖模式</span>
              <span class="switch-row__desc">目标路径已存在文件时允许覆盖<span v-if="form.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.trigger_strm" :disabled="form.action_type === 'hash_only'" />
              <span class="switch-row__label">联动 STRM</span>
              <span class="switch-row__desc">整理完成后自动生成/更新 STRM 文件<span v-if="form.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.clean_empty_dir" :disabled="form.action_type === 'hash_only'" />
              <span class="switch-row__label">清理空目录</span>
              <span class="switch-row__desc">整理后删除源目录中的空文件夹<span v-if="form.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.ignore_history" />
              <span class="switch-row__label">忽略历史</span>
              <span class="switch-row__desc">跳过已成功整理或已跳过的历史记录，不重新处理</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.retry_failed" />
              <span class="switch-row__label">重试失败项</span>
              <span class="switch-row__desc">重新尝试之前识别失败的文件（TMDB 数据可能已更新）</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.check_emby_exists" :disabled="form.action_type === 'hash_only'" />
              <span class="switch-row__label">Emby 检查</span>
              <span class="switch-row__desc">检测 Emby 库是否存在，存在则跳过处理<span v-if="form.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下无效）</span></span>
            </div>
            <div class="switch-row" style="align-items: flex-start;">
              <n-switch v-model:value="form.calculate_hash" :disabled="form.action_type === 'hash_only'" />
              <n-space vertical :size="4">
                <div class="switch-row">
                  <span class="switch-row__label">哈希计算</span>
                  <span class="switch-row__desc">整理时计算 SHA1 和 ED2K 哈希值并记录<span v-if="form.action_type === 'hash_only'" class="inactive-hint">（仅记录哈希模式下强制启用）</span></span>
                </div>
                <div v-if="form.action_type !== 'hash_only'" style="font-size: var(--m-text-xs); color: var(--color-error); padding: var(--m-spacing-xs) var(--m-spacing-sm); background: var(--color-error-bg); border-radius: var(--m-radius-sm);">
                  ⚠️ 警告：需要读取整个文件，云盘环境不建议开启
                </div>
              </n-space>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.series_fingerprint" />
              <span class="switch-row__label">智能记忆</span>
              <span class="switch-row__desc">自动记住系列特征，后续文件实现秒级识别</span>
            </div>
          </n-space>
        </n-tab-pane>
      </n-tabs>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="handleSave">保存</n-button>
      </n-space>
    </template>

    <FilePickerModal 
      v-model:show="showPicker"
      :initial-path="pickerTarget === 'source' ? form.source_dir : form.target_dir"
      :api-base="apiBase"
      @confirm="handlePickerConfirm"
    />
  </AppGlassModal>
</template>

<style scoped>
.m-mt-sm { margin-top: var(--m-spacing-sm); }
.m-mt-md { margin-top: var(--m-spacing-md); }

.m-config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 56px;
  flex-wrap: wrap;
}

.m-config-row__label {
  font-size: var(--m-text-sm);
  color: var(--text-primary);
  white-space: nowrap;
  line-height: 1;
  width: 84px;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.switch-row__label {
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}
.switch-row__desc {
  font-size: var(--m-text-xs);
  color: var(--text-tertiary);
}
.inactive-hint {
  color: var(--text-disabled);
  font-style: italic;
}
</style>
