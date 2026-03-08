<script setup lang="ts">
import { h } from 'vue'
import { 
  NCard, NSpace, NButton, NDataTable, NModal, NForm, NFormItem, 
  NInput, NInputNumber, NSwitch, NPopconfirm, NTag, NIcon
} from 'naive-ui'
import {
  CheckCircleOutlined as OkIcon,
  ErrorOutlineOutlined as ErrorIcon,
  HelpOutlineOutlined as UnknownIcon,
  RefreshOutlined as RefreshIcon,
  AddOutlined as AddIcon
} from '@vicons/material'
import { useHealthCheck } from '../../composables/useHealthCheck'
import type { HealthCheckConfig } from '../../api/health'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  config, saveAll, loading, configs, showModal, editingConfig,
  fetchConfigs, openAdd, openEdit, saveConfig, deleteConfig, 
  startCheck, checkAll, formatDate, getStatusInfo
} = useHealthCheck()

const columns = [
  { title: '名称', key: 'name' },
  { title: '文件路径', key: 'file_path', ellipsis: { tooltip: true } },
  { title: '远程 URL', key: 'file_url', ellipsis: { tooltip: true } },
  { 
    title: '状态', 
    key: 'last_status',
    render(row: HealthCheckConfig) {
      const info = getStatusInfo(row.last_status)
      const icon = info.isOk ? OkIcon : (info.isFailed ? ErrorIcon : UnknownIcon)
      
      return h(NSpace, { align: 'center', size: 4 }, {
        default: () => [
          h(NIcon, { component: icon, color: info.type === 'success' ? '#18a058' : (info.type === 'error' ? '#d03050' : '#888') }),
          h(NTag, { type: info.type, size: 'small', bordered: false }, { default: () => info.text })
        ]
      })
    }
  },
  { 
    title: '最后检查', 
    key: 'last_check',
    render(row: HealthCheckConfig) {
      return formatDate(row.last_check)
    }
  },
  {
    title: '操作',
    key: 'actions',
    render(row: HealthCheckConfig) {
      return h(NSpace, {}, {
        default: () => [
          h(NButton, { size: 'tiny', onClick: () => startCheck(row.id!) }, { default: () => '检测' }),
          h(NButton, { size: 'tiny', onClick: () => openEdit(row) }, { default: () => '编辑' }),
          h(NPopconfirm, { 
            onPositiveClick: () => deleteConfig(row.id!),
            positiveText: '确定',
            negativeText: '取消'
          }, {
            trigger: () => h(NButton, { size: 'tiny', type: 'error', ghost: true }, { default: () => '删除' }),
            default: () => '确定要删除这条检测配置吗？'
          })
        ]
      })
    }
  }
]
</script>

<template>
  <div class="health-check-desktop">
    <n-card bordered title="掉盘与 CK 失效检测" size="small">
      <template #header-extra>
        <n-space>
          <n-button v-bind="getButtonStyle('icon')" size="small" @click="fetchConfigs">
            <template #icon><n-icon><RefreshIcon /></n-icon></template>
          </n-button>
          <n-button v-bind="getButtonStyle('warning')" size="small" @click="checkAll">
            立即检测全部
          </n-button>
          <n-button v-bind="getButtonStyle('primary')" size="small" @click="openAdd">
            添加配置
          </n-button>
        </n-space>
      </template>

      <div class="description" style="margin-bottom: 16px; font-size: 13px; color: var(--text-tertiary);">
        通过定时下载指定文件并与本地路径进行比对，用于监测硬盘是否掉线或下载源的 Cookie 是否失效。
      </div>

      <n-space align="center" style="background: var(--bg-surface); padding: 12px; border-radius: 8px; margin-bottom: 16px;">
        <n-form-item label="自动巡检" label-placement="left" :show-feedback="false">
          <n-switch v-model:value="config.health_check_enabled" />
        </n-form-item>
        <n-form-item label="巡检频率 (分)" label-placement="left" :show-feedback="false">
          <n-input-number v-model:value="config.health_check_interval" :min="1" size="small" style="width: 120px" />
        </n-form-item>
        <n-button v-bind="getButtonStyle('primary')" size="small" @click="saveAll">保存设置</n-button>
      </n-space>

      <n-data-table 
        :columns="columns" 
        :data="configs" 
        :loading="loading"
        size="small"
      />
    </n-card>

    <!-- Modal 共享 -->
    <n-modal v-model:show="showModal" preset="card" title="健康检查配置" style="width: 600px">
      <n-form :model="editingConfig" label-placement="left" label-width="100">
        <n-form-item label="配置名称">
          <n-input v-model:value="editingConfig.name" placeholder="例如: 阿里云盘掉盘检测" />
        </n-form-item>
        <n-form-item label="文件路径">
          <n-input v-model:value="editingConfig.file_path" placeholder="容器内的文件路径，例如: /mnt/aliyun/check.txt" />
        </n-form-item>
        <n-form-item label="远程 URL">
          <n-input v-model:value="editingConfig.file_url" placeholder="文件的直链 URL (包含 Cookie 或 Token)" />
        </n-form-item>
        <n-form-item label="启用检测">
          <n-switch v-model:value="editingConfig.enabled" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('ghost')" @click="showModal = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="saveConfig">提交保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>
