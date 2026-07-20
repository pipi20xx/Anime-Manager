<script setup lang="ts">
import { h, watch } from 'vue'
import { dataTableThemeOverrides } from '../../store/appearanceStore'
import AppGlassModal from '../AppGlassModal.vue'
import { 
  NDataTable, NButton, NSpace, NIcon, NForm, NFormItem, 
  NSelect, NSwitch, NGrid, NGi,
  NDivider, useDialog
} from 'naive-ui'
import {
  PlusIcon as AddIcon,
  StarIcon,
  PencilSquareIcon as EditIcon,
  TrashIcon as DeleteIcon
} from '@heroicons/vue/24/outline'
import {
  StarIcon as StarFilledIcon
} from '@heroicons/vue/24/solid'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import { useSubscriptionTemplates } from '../../composables/components/useSubscriptionTemplates'
import { getButtonStyle } from '../../composables/useButtonStyles'
import { useBackClose } from '../../composables/useBackClose'

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

// 编辑视图也接入 history 后退：侧滑/侧键后退时先从编辑视图返回列表，再关闭弹框
useBackClose(showEdit)

// 弹框关闭时重置编辑视图
watch(() => props.show, (val) => {
  if (!val) showEdit.value = false
})

const dialog = useDialog()

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
    title: '操作', key: 'actions', width: 100,
    render(row: any) {
      return h(NSpace, { size: 4 }, {
        default: () => [
          h(NButton, { ...getButtonStyle('icon'), size: 'small', onClick: () => openEdit(row) }, { 
            icon: () => h(NIcon, null, { default: () => h(EditIcon) }) 
          }),
          h(NButton, { 
            ...getButtonStyle('iconDanger'), 
            size: 'small',
            onClick: () => {
              dialog.warning({
                title: '确认删除',
                content: `确定删除模板「${row.name}」吗？`,
                positiveText: '确定删除',
                negativeText: '取消',
                onPositiveClick: () => deleteTemplate(row.id)
              })
            }
          }, { 
            icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) 
          })
        ]
      })
    }
  }
]
</script>

<template>
  <AppGlassModal 
    appearance-key="subscription-template-modal"
    :show="show" 
    @update:show="close"
    style="width: 750px;"
    :title="showEdit ? (editModel.id ? '编辑订阅预设' : '新增订阅预设') : '订阅预设模板管理'"
  >
    <div v-if="!showEdit">
      <div style="display: flex; justify-content: space-between; margin-bottom: 16px;">
          <div style="color: var(--text-tertiary); font-size: 13px;">点击星标可将模板设为一键订阅时的默认配置</div>
          <n-button type="primary" size="small" @click="openAdd">
            创建新预设
          </n-button>
      </div>
      <n-data-table :theme-overrides="dataTableThemeOverrides" :columns="columns" :data="templates" :loading="loading" max-height="55vh" />
    </div>

    <div v-else class="edit-form">
      <n-form label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="12">
          <n-gi :span="2"><n-form-item><AppTextField v-model:value="editModel.name" label="预设名称" placeholder="例如: 默认动漫预设" /></n-form-item></n-gi>
          
          <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_res" label="分辨率" placeholder="如: 1080P, 4K" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_team" label="制作组" placeholder="如: LoliHouse, VCB-Studio" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_source" label="介质来源" placeholder="如: Blu-ray, WEB-DL" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_codec" label="视频编码" placeholder="如: H.265, H.264" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_audio" label="音频编码" placeholder="如: FLAC, AAC" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_sub" label="字幕语言" placeholder="如: 简体内封, 繁日内嵌" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_effect" label="视频特效" placeholder="如: HDR10, Dolby Vision" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="editModel.filter_platform" label="发布平台" placeholder="如: Baha, Netflix" /></n-form-item></n-gi>
          
          <n-gi :span="2"><n-divider style="margin: 8px 0" /></n-gi>

          <n-gi :span="2"><n-form-item><AppTextField v-model:value="editModel.include_keywords" label="必须包含" placeholder="包含这些关键词才下载" /></n-form-item></n-gi>
          <n-gi :span="2"><n-form-item><AppTextField v-model:value="editModel.exclude_keywords" label="排除关键词" placeholder="包含这些关键词则跳过" /></n-form-item></n-gi>
          
          <n-gi :span="2"><n-divider style="margin: 8px 0" /></n-gi>

          <n-gi :span="2"><n-form-item><AppTextField v-model:value="editModel.save_path" label="下载目录" placeholder="留空则使用客户端默认路径" /></n-form-item></n-gi>
          <n-gi><n-form-item>
            <AppSelectField v-model:value="editModel.target_client_id" label="下载客户端" :options="clients.map(c => ({label: c.name, value: c.id}))" placeholder="选择目标客户端" clearable />
          </n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="editModel.category" label="分类/标签" placeholder="例如: Anime" /></n-form-item></n-gi>
          
          <n-gi :span="2">
            <n-form-item>
              <AppSelectField 
                v-model:value="editModel.target_feeds" 
                label="监控订阅源"
                multiple
                placeholder="留空则监控所有"
                :options="feeds.map(f => ({label: f.title || f.url, value: String(f.id)}))"
              />
            </n-form-item>
          </n-gi>

          <n-gi :span="2">
            <n-form-item>
              <div class="switch-row">
                <n-switch v-model:value="editModel.auto_fill" />
                <span class="switch-row__label">定时补全</span>
              </div>
            </n-form-item>
          </n-gi>
        </n-grid>
      </n-form>
    </div>

    <template #action>
      <n-space justify="end">
        <n-button v-if="showEdit" v-bind="getButtonStyle('dialogCancel')" @click="showEdit = false">返回列表</n-button>
        <n-button v-if="!showEdit" v-bind="getButtonStyle('dialogCancel')" @click="close">关闭</n-button>
        <n-button v-if="showEdit" v-bind="getButtonStyle('primary')" @click="saveTemplate">保存该预设</n-button>
      </n-space>
    </template>
  </AppGlassModal>
</template>

<style scoped>
.switch-row { display: flex; align-items: center; gap: 8px; }
.switch-row__label { font-weight: 500; color: var(--text-primary); white-space: nowrap; }
.switch-row__desc { font-size: 12px; color: var(--text-tertiary); }
.edit-form { padding-right: 12px; }
</style>
