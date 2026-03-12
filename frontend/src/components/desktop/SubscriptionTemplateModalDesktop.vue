<script setup lang="ts">
import { h } from 'vue'
import { 
  NModal, NDataTable, NButton, NSpace, NIcon, NForm, NFormItem, 
  NInput, NSelect, NSwitch, NGrid, NGi, NPopconfirm,
  NScrollbar, NDivider
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  StarOutlined as StarIcon,
  StarFilled as StarFilledIcon,
  EditOutlined as EditIcon,
  DeleteOutlined as DeleteIcon
} from '@vicons/material'
import { useSubscriptionTemplates } from '../../composables/components/useSubscriptionTemplates'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  clients: any[]
}>()

const emit = defineEmits(['update:show'])

const {
  templates, loading, showEdit, feeds, editModel,
  openAdd, openEdit, saveTemplate, deleteTemplate, setDefault,
  close
} = useSubscriptionTemplates(props, emit)

const columns = [
  { 
    title: '默认', key: 'is_default', width: 60, align: 'center',
    render(row: any) {
      return row.is_default 
        ? h(NIcon, { color: 'var(--n-warning-color)', size: 20 }, { default: () => h(StarFilledIcon) })
        : h(NButton, { quaternary: true, circle: true, onClick: () => setDefault(row) }, { 
            icon: () => h(NIcon, { color: 'var(--text-muted)' }, { default: () => h(StarIcon) }) 
          })
    }
  },
  { title: '模板名称', key: 'name', width: 180 },
  { title: '分类', key: 'category', width: 100 },
  { title: '包含关键词', key: 'include_keywords', ellipsis: { tooltip: true } },
  { 
    title: '操作', key: 'actions', width: 120,
    render(row: any) {
      return h(NSpace, { size: 4 }, {
        default: () => [
          h(NButton, { size: 'tiny', secondary: true, onClick: () => openEdit(row) }, { 
            icon: () => h(NIcon, null, { default: () => h(EditIcon) }) 
          }),
          h(NPopconfirm, { positiveText: '确定', negativeText: '取消', onPositiveClick: () => deleteTemplate(row.id) }, {
            trigger: () => h(NButton, { size: 'tiny', secondary: true, type: 'error' }, { 
              icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) 
            }),
            default: () => '确定删除此模板吗？'
          })
        ]
      })
    }
  }
]
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="close"
    preset="card"
    style="width: 750px; max-width: 95vw;"
    :title="showEdit ? (editModel.id ? '编辑订阅预设' : '新增订阅预设') : '订阅预设模板管理'"
  >
    <div v-if="!showEdit">
      <div style="display: flex; justify-content: space-between; margin-bottom: 16px;">
          <div style="color: var(--text-tertiary); font-size: 13px;">点击星标可将模板设为一键订阅时的默认配置</div>
          <n-button type="primary" size="small" @click="openAdd">
            创建新预设
          </n-button>
      </div>
      <n-data-table :columns="columns" :data="templates" :loading="loading" max-height="55vh" />
    </div>

    <n-scrollbar v-else style="max-height: 65vh; padding-right: 12px;">
      <n-form label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="12">
          <n-gi :span="2"><n-form-item label="预设名称"><n-input v-model:value="editModel.name" placeholder="例如: 默认动漫预设" /></n-form-item></n-gi>
          
          <n-gi><n-form-item label="分辨率"><n-input v-model:value="editModel.filter_res" placeholder="如: 1080p, 4k" /></n-form-item></n-gi>
          <n-gi><n-form-item label="制作组"><n-input v-model:value="editModel.filter_team" placeholder="如: LoliHouse, VCB-Studio" /></n-form-item></n-gi>
          <n-gi><n-form-item label="来源"><n-input v-model:value="editModel.filter_source" placeholder="如: Blu-ray, Web-DL" /></n-form-item></n-gi>
          <n-gi><n-form-item label="视频编码"><n-input v-model:value="editModel.filter_codec" placeholder="如: HEVC, AVC" /></n-form-item></n-gi>
          <n-gi><n-form-item label="音频编码"><n-input v-model:value="editModel.filter_audio" placeholder="如: FLAC, AAC" /></n-form-item></n-gi>
          <n-gi><n-form-item label="字幕语言"><n-input v-model:value="editModel.filter_sub" placeholder="如: CHS, CHT" /></n-form-item></n-gi>
          <n-gi><n-form-item label="视频特效"><n-input v-model:value="editModel.filter_effect" placeholder="如: HDR10, DV" /></n-form-item></n-gi>
          <n-gi><n-form-item label="发布平台"><n-input v-model:value="editModel.filter_platform" placeholder="如: Baha, Netflix" /></n-form-item></n-gi>
          
          <n-gi :span="2"><n-divider style="margin: 8px 0" /></n-gi>

          <n-gi :span="2"><n-form-item label="必须包含"><n-input v-model:value="editModel.include_keywords" placeholder="包含这些关键词才下载" /></n-form-item></n-gi>
          <n-gi :span="2"><n-form-item label="排除关键词"><n-input v-model:value="editModel.exclude_keywords" placeholder="包含这些关键词则跳过" /></n-form-item></n-gi>
          
          <n-gi :span="2"><n-divider style="margin: 8px 0" /></n-gi>

          <n-gi :span="2"><n-form-item label="下载目录"><n-input v-model:value="editModel.save_path" placeholder="留空则使用客户端默认路径" /></n-form-item></n-gi>
          <n-gi><n-form-item label="下载客户端">
            <n-select v-model:value="editModel.target_client_id" :options="clients.map(c => ({label: c.name, value: c.id}))" placeholder="选择目标客户端" />
          </n-form-item></n-gi>
          <n-gi><n-form-item label="分类/标签"><n-input v-model:value="editModel.category" placeholder="例如: Anime" /></n-form-item></n-gi>
          
          <n-gi :span="2">
            <n-form-item label="监控订阅源">
              <n-select 
                v-model:value="editModel.target_feeds" 
                multiple
                placeholder="留空则监控所有"
                :options="feeds.map(f => ({label: f.title || f.url, value: String(f.id)}))"
              />
            </n-form-item>
          </n-gi>

          <n-gi>
            <n-form-item label="定时补全">
              <n-switch v-model:value="editModel.auto_fill" />
            </n-form-item>
          </n-gi>
        </n-grid>
      </n-form>
    </n-scrollbar>

    <template #action>
      <n-space justify="end">
        <n-button v-if="showEdit" v-bind="getButtonStyle('ghost')" @click="showEdit = false">返回列表</n-button>
        <n-button v-if="!showEdit" v-bind="getButtonStyle('ghost')" @click="close">关闭</n-button>
        <n-button v-if="showEdit" v-bind="getButtonStyle('primary')" @click="saveTemplate">保存该预设</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
