<script setup lang="ts">
import { 
  NModal, NForm, NFormItem, NTabs, NTabPane, NSpace, NInput, NGrid, NGi, 
  NDivider, NCheckbox, NInputNumber, NSelect, NDynamicTags, NAlert, 
  NSpin, NCode, NEmpty, NIcon, NButton, NScrollbar, NRadioButton, NRadioGroup,
  NSwitch
} from 'naive-ui'
import {
  FolderOpenOutlined as FolderIcon
} from '@vicons/material'
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
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 950px" 
    :title="isNew ? '新建 STRM 任务' : '编辑 STRM 任务配置'"
  >
    <n-form label-placement="left" label-width="100" size="small">
      <n-tabs type="line" animated>
        <!-- 1. 基础设置 -->
        <n-tab-pane name="basic" tab="核心设置">
          <n-space vertical size="large" class="mt-4">
            <n-form-item label="任务名称"><n-input v-model:value="form.name" placeholder="例如: 百度网盘电影库" /></n-form-item>
            
            <n-form-item label="同步模式">
              <n-space>
                <n-radio-group v-model:value="form.sync_mode">
                  <n-radio-button value="local">本地文件扫描</n-radio-button>
                  <n-radio-button value="tree_file">目录树文件</n-radio-button>
                </n-radio-group>
              </n-space>
            </n-form-item>

            <n-alert v-if="form.sync_mode === 'tree_file'" type="warning" size="small" class="mb-4">
              目录树模式将解析您提供的文本文件内容来同步 STRM。
            </n-alert>

            <n-form-item label="目录树文件" v-if="form.sync_mode === 'tree_file'">
              <n-input v-model:value="form.tree_file_path" placeholder="例如: /root/tree.txt">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openPicker('tree')"><template #icon><n-icon><FolderIcon /></n-icon></template></n-button>
                </template>
              </n-input>
            </n-form-item>

            <n-form-item label="源目录">
              <n-input v-model:value="form.source_path" placeholder="待扫描的本地媒体文件夹">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openPicker('source')"><template #icon><n-icon><FolderIcon /></n-icon></template></n-button>
                </template>
              </n-input>
            </n-form-item>
            <n-form-item label="目标目录">
              <n-input v-model:value="form.target_path" placeholder="STRM 文件存放位置">
                <template #suffix>
                  <n-button v-bind="getButtonStyle('icon')" size="small" @click="openPicker('target')"><template #icon><n-icon><FolderIcon /></n-icon></template></n-button>
                </template>
              </n-input>
            </n-form-item>
            <n-form-item label="链接前缀">
              <n-input v-model:value="form.content_prefix" placeholder="http://ip:port/..." />
            </n-form-item>
          </n-space>
        </n-tab-pane>

        <!-- 2. 过滤与策略 -->
        <n-tab-pane name="filters" tab="过滤与策略">
          <n-space vertical size="large" class="mt-4">
            <n-form-item label="视频扩展名"><n-dynamic-tags v-model:value="form.target_extensions" /></n-form-item>
            <n-form-item label="元数据扩展名"><n-dynamic-tags v-model:value="form.meta_extensions" /></n-form-item>
            <n-divider dashed title-placement="left">生成与限流选项</n-divider>
            <n-grid :cols="2">
              <n-gi><n-space vertical><n-checkbox v-model:checked="form.copy_meta">同步元数据文件</n-checkbox><n-checkbox v-model:checked="form.clean_target">生成前清理目标</n-checkbox></n-space></n-gi>
              <n-gi><n-space vertical><n-checkbox v-model:checked="form.overwrite_strm">覆盖已有 STRM</n-checkbox><n-checkbox v-model:checked="form.overwrite_meta">覆盖已有元数据</n-checkbox><n-checkbox v-model:checked="form.clean_empty_dirs">生成后清理空目录</n-checkbox></n-space></n-gi>
            </n-grid>
            <n-form-item label="限流间隔" class="mt-4">
              <n-input-number v-model:value="form.process_interval" :min="0" :step="0.1" style="width: 350px">
                <template #suffix>秒/文件 (建议: 0.5 - 1.0)</template>
              </n-input-number>
            </n-form-item>
          </n-space>
        </n-tab-pane>

        <!-- 3. 自动化与预览 -->
        <n-tab-pane name="automation" tab="自动化与预览">
          <n-form label-placement="top" size="small">
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
                </n-gi>
                <n-gi>
                  <n-form-item label="扫描间隔" v-if="form.scheduler_enabled">
                    <n-input-number v-model:value="form.scheduler_interval" :min="60" style="width: 100%">
                      <template #suffix>秒</template>
                    </n-input-number>
                  </n-form-item>
                </n-gi>
              </n-grid>

              <n-form-item label="实时联动策略">
                <n-checkbox v-model:checked="form.webhook_enabled">
                  <span style="font-size: 13px">响应 CD2 Webhook 推送并自动同步 (建议开启以获得实时入库体验)</span>
                </n-checkbox>
              </n-form-item>

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
      :initial-path="pickerTarget === 'source' ? form.source_path : (pickerTarget === 'target' ? form.target_path : form.tree_file_path)"
      :api-base="apiBase"
      :allow-files="pickerTarget === 'tree'"
      @confirm="handlePickerConfirm"
    />
  </n-modal>
</template>

<style scoped>
.mt-4 { margin-top: 16px; }
.preview-mini-box { 
  background: var(--app-surface-inner); 
  border: 1px solid var(--app-border-light); 
  padding: 12px; 
  border-radius: var(--button-border-radius, 4px); 
  min-height: 80px; 
}
.p-wrap { word-break: break-all; }
.p-line { color: var(--n-info-color); font-family: monospace; font-size: 13px; margin-bottom: 8px; }
.p-sub { color: var(--text-muted); font-size: 11px; }
</style>