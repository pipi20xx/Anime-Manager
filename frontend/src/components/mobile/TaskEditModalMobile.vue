<script setup lang="ts">
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
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
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
        
        <n-tab-pane name="automation" tab="自动化与过滤">
          <n-space vertical size="large" class="m-mt-md">
            <div class="m-config-row">
              <span class="m-config-row__label">实时监控</span>
              <n-switch v-model:value="form.incremental_enabled" />
              <AppSelectField 
                v-model:value="form.incremental_mode" 
                label="模式"
                style="width: 140px"
                :options="[{label: '实时', value: 'realtime'}, {label: '轮询', value: 'polling'}]" 
              />
            </div>
            
            <div class="m-config-row">
              <span class="m-config-row__label">定时扫描</span>
              <n-switch v-model:value="form.scheduler_enabled" />
            </div>

            <n-form-item v-if="form.incremental_mode === 'polling'">
              <AppTextField v-model:value="form.monitor_interval" label="轮询间隔" type="number" :min="1">
                <template #suffix>秒</template>
              </AppTextField>
            </n-form-item>
            <n-form-item v-else>
              <AppTextField :value="'实时监听文件系统事件 (Inotify)'" label="监控状态" readonly />
            </n-form-item>
            
            <n-form-item>
              <AppTextField v-model:value="form.scheduler_interval" label="扫描间隔" type="number" :min="60">
                <template #suffix>秒</template>
              </AppTextField>
            </n-form-item>

            <n-form-item>
              <AppTextField v-model:value="form.process_interval" label="限流间隔" type="number" :min="0">
                <template #suffix>秒</template>
              </AppTextField>
            </n-form-item>
            <n-form-item label="跳过限流">
              <n-space vertical :size="8">
                <n-switch v-model:value="form.skip_rate_limit" />
                <n-checkbox-group v-if="form.skip_rate_limit" v-model:value="form.skip_rate_limit_types">
                  <n-space vertical>
                    <n-checkbox value="history">历史记录跳过</n-checkbox>
                    <n-checkbox value="recognition_failed">识别失败跳过</n-checkbox>
                    <n-checkbox value="emby_exists">Emby已存在跳过</n-checkbox>
                    <n-checkbox value="regex_match">正则匹配跳过</n-checkbox>
                  </n-space>
                </n-checkbox-group>
              </n-space>
            </n-form-item>
            <n-form-item label="忽略文件正则"><n-dynamic-tags v-model:value="form.ignore_file_regex" /></n-form-item>
            <n-form-item label="忽略目录正则"><n-dynamic-tags v-model:value="form.ignore_dir_regex" /></n-form-item>
            
            <n-space vertical size="medium" class="m-mt-md">
              <n-checkbox v-model:checked="form.anime_priority">动漫优先</n-checkbox>
              <n-checkbox v-model:checked="form.overwrite_mode">覆盖模式</n-checkbox>
              <n-checkbox v-model:checked="form.trigger_strm">联动 STRM</n-checkbox>
              <n-checkbox v-model:checked="form.clean_empty_dir">清理空目录</n-checkbox>
              <n-checkbox v-model:checked="form.ignore_history">忽略历史</n-checkbox>
            </n-space>
            
            <n-form-item label="Emby 检查" class="m-mt-md">
              <n-space align="center">
                <n-switch v-model:value="form.check_emby_exists" />
                <span style="font-size: var(--m-text-xs); color: var(--text-muted);">检测 Emby 库是否存在，存在则跳过处理</span>
              </n-space>
            </n-form-item>
            <n-form-item label="哈希计算" class="m-mt-sm">
              <n-space vertical size="small">
                <n-space align="center">
                  <n-switch v-model:value="form.calculate_hash" />
                  <span style="font-size: var(--m-text-xs); color: var(--text-muted);">整理时计算 SHA1 和 ED2K 哈希值并记录</span>
                </n-space>
                <div style="font-size: var(--m-text-xs); color: var(--color-error); padding: var(--m-spacing-xs) var(--m-spacing-sm); background: var(--color-error-bg); border-radius: var(--m-radius-sm);">
                  ⚠️ 警告：需要读取整个文件，云盘环境不建议开启
                </div>
              </n-space>
            </n-form-item>
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
  </n-modal>
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
}
</style>
