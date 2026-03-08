<script setup lang="ts">
import { 
  NCard, NSpace, NButton, NModal, NForm, NFormItem, 
  NInput, NInputNumber, NSwitch, NPopconfirm, NTag, NIcon,
  NList, NListItem, NThing, NButtonGroup
} from 'naive-ui'
import {
  CheckCircleOutlined as OkIcon,
  ErrorOutlineOutlined as ErrorIcon,
  HelpOutlineOutlined as UnknownIcon,
  RefreshOutlined as RefreshIcon,
  AddOutlined as AddIcon,
  DeleteOutlined as DeleteIcon,
  EditOutlined as EditIcon,
  PlayArrowOutlined as PlayIcon
} from '@vicons/material'
import { useHealthCheck } from '../../composables/useHealthCheck'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  config, saveAll, loading, configs, showModal, editingConfig,
  fetchConfigs, openAdd, openEdit, saveConfig, deleteConfig, 
  startCheck, checkAll, formatDate, getStatusInfo
} = useHealthCheck()
</script>

<template>
  <div class="health-check-mobile">
    <n-space vertical size="large">
      <!-- 全局设置卡片 -->
      <n-card title="巡检设置" size="small">
        <n-form label-placement="left" :show-feedback="false">
          <n-space vertical>
            <n-space justify="space-between" align="center" style="width: 100%">
              <span>自动巡检开关</span>
              <n-switch v-model:value="config.health_check_enabled" />
            </n-space>
            <n-space justify="space-between" align="center" style="width: 100%">
              <span>频率 (分钟)</span>
              <n-input-number v-model:value="config.health_check_interval" :min="1" size="small" style="width: 100px" />
            </n-space>
            <n-button v-bind="getButtonStyle('primary')" block @click="saveAll" style="margin-top: 8px">保存全局设置</n-button>
          </n-space>
        </n-form>
      </n-card>

      <!-- 任务列表卡片 -->
      <n-card title="监测项目" size="small">
        <template #header-extra>
          <n-button v-bind="getButtonStyle('primary')" size="tiny" @click="openAdd">
            新增
          </n-button>
        </template>

        <n-list v-if="configs.length > 0">
          <n-list-item v-for="item in configs" :key="item.id">
            <n-thing :title="item.name">
              <template #description>
                <div class="path-text">{{ item.file_path }}</div>
              </template>
              <template #header-extra>
                <n-tag :type="getStatusInfo(item.last_status).type" size="small" bordered="false">
                  {{ getStatusInfo(item.last_status).text }}
                </n-tag>
              </template>
              <div style="font-size: 12px; color: #888; margin-top: 4px;">
                最后检查: {{ formatDate(item.last_check) }}
              </div>
            </n-thing>
            
            <template #suffix>
              <n-space vertical size="small">
                <n-button circle size="small" @click="startCheck(item.id!)">
                  <template #icon><n-icon><PlayIcon /></n-icon></template>
                </n-button>
                <n-button circle size="small" @click="openEdit(item)">
                  <template #icon><n-icon><EditIcon /></n-icon></template>
                </n-button>
                <n-popconfirm @positive-click="deleteConfig(item.id!)" positive-text="确定" negative-text="取消">
                  <template #trigger>
                    <n-button v-bind="getButtonStyle('iconDanger')" size="small">
                      <template #icon><n-icon><DeleteIcon /></n-icon></template>
                    </n-button>
                  </template>
                  确定删除吗？
                </n-popconfirm>
              </n-space>
            </template>
          </n-list-item>
        </n-list>
        
        <div v-else style="padding: 20px; text-align: center; color: #666;">
          暂无监测项目
        </div>

        <template #action>
          <n-button v-bind="getButtonStyle('secondary')" block @click="checkAll" :loading="loading">
            立即运行全量检测
          </n-button>
        </template>
      </n-card>
    </n-space>

    <!-- 移动端 Modal -->
    <n-modal v-model:show="showModal" preset="card" title="编辑项目" style="width: 90%; max-width: 400px;">
      <n-form :model="editingConfig" label-placement="top">
        <n-form-item label="名称">
          <n-input v-model:value="editingConfig.name" />
        </n-form-item>
        <n-form-item label="路径">
          <n-input v-model:value="editingConfig.file_path" type="textarea" :autosize="{ minRows: 2 }" />
        </n-form-item>
        <n-form-item label="URL (可选)">
          <n-input v-model:value="editingConfig.file_url" type="textarea" :autosize="{ minRows: 2 }" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="editingConfig.enabled" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-button v-bind="getButtonStyle('primary')" block @click="saveConfig">保存配置</n-button>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.path-text {
  font-size: 12px;
  color: #666;
  word-break: break-all;
  max-width: 200px;
}
</style>
