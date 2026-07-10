<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import { h } from 'vue'
import { dataTableThemeOverrides } from '../../store/appearanceStore'
import { 
  NCard, NSpace, NButton, NDataTable, NForm, NFormItem, 
  NSwitch, NPopconfirm, NTag, NIcon
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  EditOutlined as EditIcon,
  DeleteOutlined as DeleteIcon,
  PlayArrowOutlined as PlayIcon
} from '@vicons/material'
import AppTextField from '../AppTextField.vue'
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
      const colorMap: Record<string, string> = {
        success: '#2e7d32',
        error: '#c62828',
        default: '#616161'
      }
      return h(NTag, { 
        size: 'small', 
        round: true,
        bordered: false,
        style: { 
          color: '#fff', 
          backgroundColor: colorMap[info.type] || '#616161', 
          borderColor: 'transparent' 
        }
      }, { default: () => info.text })
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
      return h(NSpace, { size: 4 }, {
        default: () => [
          h(NButton, { ...getButtonStyle('iconPrimary'), size: 'small', onClick: () => startCheck(row.id!) }, { 
            icon: () => h(NIcon, null, { default: () => h(PlayIcon) })
          }),
          h(NButton, { ...getButtonStyle('icon'), size: 'small', onClick: () => openEdit(row) }, { 
            icon: () => h(NIcon, null, { default: () => h(EditIcon) })
          }),
          h(NPopconfirm, { 
            onPositiveClick: () => deleteConfig(row.id!),
            positiveText: '确定',
            negativeText: '取消'
          }, {
            trigger: () => h(NButton, { ...getButtonStyle('iconDanger'), size: 'small' }, { 
              icon: () => h(NIcon, null, { default: () => h(DeleteIcon) })
            }),
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
        <div class="switch-row">
          <n-switch v-model:value="config.health_check_enabled" />
          <span class="switch-row__label">自动巡检</span>
        </div>
        <n-form-item label-placement="left" :show-feedback="false">
          <AppTextField v-model:value="config.health_check_interval" label="巡检频率 (分)" type="number" :min="1" />
        </n-form-item>
        <n-button v-bind="getButtonStyle('primary')" size="small" @click="saveAll">保存设置</n-button>
      </n-space>

      <n-data-table 
        :columns="columns" 
        :data="configs" 
        :theme-overrides="dataTableThemeOverrides"
        :loading="loading"
        size="small"
      />
    </n-card>

    <!-- Modal 共享 -->
    <AppGlassModal appearance-key="health-check-manager-modal" v-model:show="showModal" title="健康检查配置" style="width: 600px">
      <n-form :model="editingConfig" label-placement="left" label-width="100">
        <n-form-item>
          <AppTextField v-model:value="editingConfig.name" label="配置名称" placeholder="例如: 阿里云盘掉盘检测" />
        </n-form-item>
        <n-form-item>
          <AppTextField v-model:value="editingConfig.file_path" label="文件路径" placeholder="容器内的文件路径，例如: /mnt/aliyun/check.txt" />
        </n-form-item>
        <n-form-item>
          <AppTextField v-model:value="editingConfig.file_url" label="远程 URL" placeholder="文件的直链 URL (包含 Cookie 或 Token)" />
        </n-form-item>
        <n-form-item>
          <div class="switch-row">
            <n-switch v-model:value="editingConfig.enabled" />
            <span class="switch-row__label">启用检测</span>
          </div>
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="showModal = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="saveConfig">提交保存</n-button>
        </n-space>
      </template>
    </AppGlassModal>
  </div>
</template>

<style scoped>
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
</style>