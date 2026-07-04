<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import { 
  NForm, NFormItem, NTabs, NTabPane, NSpace, 
  NDivider, NCheckbox, NSelect, NDynamicTags, NAlert, 
  NSpin, NCode, NEmpty, NIcon, NButton, NScrollbar,
  NSwitch
} from 'naive-ui'
import {
  FolderOpenOutlined as FolderIcon
} from '@vicons/material'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import FilePickerModal from '../FilePickerModal.vue'
import { useStrmTask } from '../../composables/modals/useStrmTask'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  taskData: any
  isNew: boolean
  apiBase: string
}>()

const emit = defineEmits(['update:show', 'save'])

const {
  form,
  previewLoading,
  previewData,
  showPicker,
  pickerTarget,
  openPicker,
  handlePickerConfirm,
  handleSave
} = useStrmTask(props, emit)
</script>

<template>
  <AppGlassModal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    style="width: 950px" 
    :title="isNew ? '新建 STRM 任务' : '编辑 STRM 任务配置'"
  >
    <n-form label-placement="left" label-width="100" size="small">
      <n-tabs type="line" animated>
        <!-- 1. 基础设置 -->
        <n-tab-pane name="basic" tab="核心设置">
          <n-space vertical size="large" class="mt-4">
            <n-form-item><AppTextField v-model:value="form.name" label="任务名称" placeholder="例如: 百度网盘电影库" /></n-form-item>
            
            <n-form-item>
              <AppSelectField v-model:value="form.sync_mode" label="同步模式" :options="[
                {label:'本地文件扫描', value:'local'},
                {label:'目录树文件', value:'tree_file'}
              ]" />
            </n-form-item>

            <n-alert v-if="form.sync_mode === 'tree_file'" type="warning" size="small" class="mb-4">
              目录树模式将解析您提供的文本文件内容来同步 STRM。
            </n-alert>

            <n-form-item v-if="form.sync_mode === 'tree_file'">
              <AppTextField v-model:value="form.tree_file_path" label="目录树文件" placeholder="例如: /root/tree.txt">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openPicker('tree')"><template #icon><n-icon><FolderIcon /></n-icon></template></n-button>
                </template>
              </AppTextField>
            </n-form-item>

            <n-form-item>
              <AppTextField v-model:value="form.source_path" label="源目录" placeholder="待扫描的本地媒体文件夹">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openPicker('source')"><template #icon><n-icon><FolderIcon /></n-icon></template></n-button>
                </template>
              </AppTextField>
            </n-form-item>
            <n-form-item>
              <AppTextField v-model:value="form.target_path" label="目标目录" placeholder="STRM 文件存放位置">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openPicker('target')"><template #icon><n-icon><FolderIcon /></n-icon></template></n-button>
                </template>
              </AppTextField>
            </n-form-item>
            <n-form-item>
              <AppTextField v-model:value="form.content_prefix" label="链接前缀" placeholder="http://ip:port/..." />
            </n-form-item>
            <n-form-item>
              <AppTextField v-model:value="form.process_interval" label="限流间隔" type="number" :min="0" :step="0.1" style="width: 350px">
                <template #suffix>秒/文件 (建议: 0.5 - 1.0)</template>
              </AppTextField>
            </n-form-item>
          </n-space>
        </n-tab-pane>

        <!-- 2. 自动化与预览 -->
        <n-tab-pane name="automation" tab="自动化与预览">
          <n-form label-placement="top" size="small">
            <n-space vertical size="large" class="mt-4">
              <div class="config-row">
                <n-switch v-model:value="form.incremental_enabled" />
                <span class="config-row__label">实时监控</span>
                <AppSelectField v-model:value="form.incremental_mode" label="模式" :options="[{label:'实时', value:'realtime'}, {label:'轮询', value:'polling'}]" style="width: 160px" />
                <AppTextField v-if="form.incremental_mode === 'polling'" v-model:value="form.monitor_interval" label="轮询间隔" type="number" :min="1" style="width: 160px">
                  <template #suffix>秒</template>
                </AppTextField>
                <span v-else class="config-row__hint">实时监听文件系统事件 (Inotify)</span>
              </div>

              <div class="config-row">
                <n-switch v-model:value="form.scheduler_enabled" />
                <span class="config-row__label">定时扫描</span>
                <AppTextField v-model:value="form.scheduler_interval" label="扫描间隔" type="number" :min="60" style="width: 160px">
                  <template #suffix>秒</template>
                </AppTextField>
              </div>

              <n-divider dashed />
            
              <n-space align="center" justify="space-between">
                <b style="font-size: 14px">实时 URL 预览</b>
                <n-checkbox v-model:checked="form.url_encode">路径 URL 编码</n-checkbox>
              </n-space>
            
              <div class="preview-mini-box">
                <n-spin :show="previewLoading">
                  <div v-if="previewData" class="p-wrap">
                    <div class="p-line"><code>{{ previewData.preview_content }}</code></div>
                    <div class="p-sub">基于文件: {{ previewData.sample_file }}</div>
                  </div>
                  <n-empty v-else size="small" description="配置源目录以查看预览" />
                </n-spin>
              </div>
            </n-space>
          </n-form>
        </n-tab-pane>

        <!-- 3. 过滤规则 -->
        <n-tab-pane name="filters" tab="过滤规则">
          <n-space vertical size="large" class="mt-4">
            <n-form-item label="视频扩展名"><n-dynamic-tags v-model:value="form.target_extensions" /></n-form-item>
            <n-form-item label="元数据扩展名"><n-dynamic-tags v-model:value="form.meta_extensions" /></n-form-item>
          </n-space>
        </n-tab-pane>

        <!-- 4. 高级设置 -->
        <n-tab-pane name="advanced" tab="高级设置">
          <n-space vertical size="large" class="mt-4">
            <div class="switch-row">
              <n-switch v-model:value="form.copy_meta" />
              <span class="switch-row__label">同步元数据文件</span>
              <span class="switch-row__desc">将 nfo、海报等元数据文件一起同步到目标目录</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.clean_target" />
              <span class="switch-row__label">生成前清理目标</span>
              <span class="switch-row__desc">生成 STRM 前清空目标目录已有内容</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.overwrite_strm" />
              <span class="switch-row__label">覆盖已有 STRM</span>
              <span class="switch-row__desc">目标目录存在同名 STRM 时覆盖</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.overwrite_meta" />
              <span class="switch-row__label">覆盖已有元数据</span>
              <span class="switch-row__desc">目标目录存在同名元数据时覆盖</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.clean_empty_dirs" />
              <span class="switch-row__label">生成后清理空目录</span>
              <span class="switch-row__desc">同步完成后删除目标目录中的空文件夹</span>
            </div>
            <div class="switch-row">
              <n-switch v-model:value="form.webhook_enabled" />
              <span class="switch-row__label">实时联动策略</span>
              <span class="switch-row__desc">响应 CD2 Webhook 推送并自动同步（建议开启以获得实时入库体验）</span>
            </div>
          </n-space>
        </n-tab-pane>
      </n-tabs>
    </n-form>
    <template #action>
      <n-space justify="end">
        <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="handleSave">保存任务配置</n-button>
      </n-space>
    </template>

    <FilePickerModal 
      v-model:show="showPicker"
      :initial-path="pickerTarget === 'source' ? form.source_path : (pickerTarget === 'target' ? form.target_path : form.tree_file_path)"
      :api-base="apiBase"
      :allow-files="pickerTarget === 'tree'"
      @confirm="handlePickerConfirm"
    />
  </AppGlassModal>
</template>

<style scoped>
.switch-row { display: flex; align-items: center; gap: 8px; }
.switch-row__label { font-weight: 500; color: var(--text-primary); white-space: nowrap; }
.switch-row__desc { font-size: 12px; color: var(--text-tertiary); }

.config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 56px;
}
.config-row__label {
  font-size: 14px;
  color: var(--text-primary);
  white-space: nowrap;
  line-height: 1;
  width: 84px;
}
.config-row__hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.mt-4 { margin-top: 16px; }
.preview-mini-box { 
  background: var(--app-surface-card-mixed); 
  border: 1px solid var(--app-border-light); 
  padding: 12px; 
  border-radius: var(--card-border-radius, var(--button-border-radius, 4px)); 
  min-height: 80px; 
}
.p-wrap { word-break: break-all; }
.p-line { color: var(--n-info-color); font-family: monospace; font-size: 13px; margin-bottom: 8px; }
.p-sub { color: var(--text-muted); font-size: 11px; }
</style>