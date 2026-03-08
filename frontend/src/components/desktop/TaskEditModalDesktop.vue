<script setup lang="ts">
import { 
  NModal, NForm, NFormItem, NTabs, NTabPane, NSpace, NInput, NSelect, 
  NInputNumber, NCheckbox, NButton, NIcon, NGrid, NGi, NDynamicTags,
  NRadioGroup, NRadioButton, NSwitch
} from 'naive-ui'
import {
  FolderOpenOutlined as FolderIcon
} from '@vicons/material'
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
  handleSave
} = useTaskEdit(props, emit)
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 700px" 
    :title="isNew ? '创建新整理任务' : '编辑任务配置'"
  >
    <n-form label-placement="left" label-width="100" size="small">
      <n-tabs type="line" animated>
        <n-tab-pane name="basic" tab="核心配置">
          <n-space vertical size="large" class="mt-4">
            <n-form-item label="任务名称"><n-input v-model:value="form.name" placeholder="起个名字" /></n-form-item>
            <n-form-item label="重命名规则">
              <n-select v-model:value="form.rule_id" :options="availableRules.map(r=>({label:r.name, value:r.id}))" placeholder="选择规则" />
            </n-form-item>
            <n-form-item label="源目录">
              <n-input v-model:value="form.source_dir" placeholder="待整理的文件夹">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openPicker('source')"><template #icon><n-icon><FolderIcon /></n-icon></template></n-button>
                </template>
              </n-input>
            </n-form-item>
            <n-form-item label="目标目录">
              <n-input v-model:value="form.target_dir" placeholder="整理后的根目录">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openPicker('target')"><template #icon><n-icon><FolderIcon /></n-icon></template></n-button>
                </template>
              </n-input>
            </n-form-item>
            <n-form-item label="操作类型">
              <n-radio-group v-model:value="form.action_type">
                <n-radio-button value="move">物理移动</n-radio-button>
                <n-radio-button value="copy">完整复制</n-radio-button>
                <n-radio-button value="link">建立硬链</n-radio-button>
                <n-radio-button value="cd2_move">CD2 移动</n-radio-button>
                <n-radio-button value="cd2_copy">CD2 复制</n-radio-button>
              </n-radio-group>
            </n-form-item>
          </n-space>
        </n-tab-pane>
        
        <n-tab-pane name="automation" tab="自动化与过滤">
          <n-space vertical size="large" class="mt-4">
            <n-grid :cols="2" :x-gap="12">
              <n-gi>
                <n-form-item label="实时监控">
                  <n-space align="center">
                    <n-switch v-model:value="form.incremental_enabled" />
                    <n-radio-group v-if="form.incremental_enabled" v-model:value="form.incremental_mode" size="small">
                      <n-radio-button value="realtime">实时</n-radio-button>
                      <n-radio-button value="polling">轮询</n-radio-button>
                    </n-radio-group>
                  </n-space>
                </n-form-item>
              </n-gi>
              <n-gi>
                <n-form-item label="定时扫描">
                  <n-switch v-model:value="form.scheduler_enabled" />
                </n-form-item>
              </n-gi>
            </n-grid>

            <n-grid :cols="2" :x-gap="12">
              <n-gi>
                <n-form-item label="轮询间隔" v-if="form.incremental_enabled && form.incremental_mode === 'polling'">
                  <n-input-number v-model:value="form.monitor_interval" :min="1" style="width: 100%">
                    <template #suffix>秒</template>
                  </n-input-number>
                </n-form-item>
                <n-form-item label="监控状态" v-else-if="form.incremental_enabled">
                  <div style="color: #666">实时监听文件系统事件 (Inotify)</div>
                </n-form-item>
              </n-gi>
              <n-gi>
                <n-form-item label="扫描间隔" v-if="form.scheduler_enabled">
                  <n-input-number v-model:value="form.scheduler_interval" :min="60" style="width: 100%">
                    <template #suffix>秒</template>
                  </n-input-number>
                </n-form-item>
              </n-gi>
            </n-grid>

            <n-form-item label="限流间隔">
              <n-input-number v-model:value="form.process_interval" :min="0" style="width: 100%">
                <template #suffix>秒</template>
              </n-input-number>
            </n-form-item>
            <n-form-item label="忽略文件正则"><n-dynamic-tags v-model:value="form.ignore_file_regex" /></n-form-item>
            <n-form-item label="忽略目录正则"><n-dynamic-tags v-model:value="form.ignore_dir_regex" /></n-form-item>
            <n-space justify="space-around" class="mt-2">
              <n-checkbox v-model:checked="form.anime_priority">动漫优先</n-checkbox>
              <n-checkbox v-model:checked="form.overwrite_mode">覆盖模式</n-checkbox>
              <n-checkbox v-model:checked="form.trigger_strm">联动 STRM</n-checkbox>
              <n-checkbox v-model:checked="form.clean_empty_dir">清理空目录</n-checkbox>
              <n-checkbox v-model:checked="form.ignore_history">忽略历史</n-checkbox>
            </n-space>
            <n-form-item label="Emby 检查" class="mt-4">
              <n-space align="center">
                <n-switch v-model:value="form.check_emby_exists" />
                <span style="font-size: 12px; color: #666;">检测 Emby 库是否存在，存在则跳过处理</span>
              </n-space>
            </n-form-item>
            <n-form-item label="哈希计算" class="mt-2">
              <n-space vertical :size="8">
                <n-space align="center">
                  <n-switch v-model:value="form.calculate_hash" />
                  <span style="font-size: 12px; color: #666;">整理时计算 SHA1 和 ED2K 哈希值并记录</span>
                </n-space>
                <div style="font-size: 11px; color: #e57373; padding: 4px 8px; background: #ffebee; border-radius: 4px;">
                  ⚠️ 警告：需要读取整个文件，云盘环境不建议开启
                </div>
              </n-space>
            </n-form-item>
          </n-space>
        </n-tab-pane>
      </n-tabs>
    </n-form>
    <template #action>
      <n-space justify="end">
        <n-button v-bind="getButtonStyle('ghost')" @click="emit('update:show', false)">取消</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="handleSave">保存任务配置</n-button>
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
.mt-2 { margin-top: 8px; }
.mt-4 { margin-top: 16px; }
</style>