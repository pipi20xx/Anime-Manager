<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import { 
  NButton, NSpace, NIcon, NForm, NFormItem, 
  NSelect, NSwitch, NPopconfirm,
  NScrollbar, NDivider, NList, NListItem, NTag, NText
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  StarOutlined as StarIcon,
  StarFilled as StarFilledIcon,
  DeleteOutlined as DeleteIcon,
  ArrowBackOutlined as BackIcon
} from '@vicons/material'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
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

</script>

<template>
  <AppGlassModal 
    appearance-key="subscription-template-modal"
    :show="show" 
    @update:show="close"
    class="mobile-fullscreen-modal"
  >
    <template #header>
      <div class="mobile-modal-header">
        <n-button v-bind="getButtonStyle('iconPrimary')" @click="showEdit ? showEdit = false : close()">
          <template #icon><n-icon><BackIcon/></n-icon></template>
        </n-button>
        <span class="title">{{ showEdit ? '编辑预设' : '订阅预设管理' }}</span>
      </div>
    </template>

    <div class="mobile-template-container">
      <!-- List View -->
      <div v-if="!showEdit" class="tab-content">
        <n-button block type="primary" @click="openAdd" style="margin-bottom: 16px;">
          <template #icon><n-icon><AddIcon /></n-icon></template>
          创建新预设
        </n-button>

        <div v-if="templates.length > 0" class="mobile-list">
          <div v-for="row in templates" :key="row.id" class="mobile-card" @click="openEdit(row)">
             <div class="card-body">
                <div class="card-title-row">
                   <div class="title-box">
                      <n-icon 
                        :color="row.is_default ? 'var(--n-warning-color)' : 'var(--text-muted)'" 
                        size="20"
                        @click.stop="setDefault(row)"
                      >
                        <component :is="row.is_default ? StarFilledIcon : StarIcon" />
                      </n-icon>
                      <span class="name">{{ row.name }}</span>
                   </div>
                   <n-tag size="tiny" round quaternary>{{ row.category }}</n-tag>
                </div>
                <div class="preview-text">
                  组: {{ row.filter_team || '不限' }} | 质量: {{ row.filter_res || '不限' }}
                </div>
             </div>
             <div class="card-actions" @click.stop>
                <n-popconfirm positive-text="确定" negative-text="取消" @positive-click="deleteTemplate(row.id)">
                  <template #trigger>
                    <n-button v-bind="getButtonStyle('iconDanger')" size="small"><template #icon><n-icon><DeleteIcon/></n-icon></template></n-button>
                  </template>
                  删除？
                </n-popconfirm>
             </div>
          </div>
        </div>
        <n-empty v-else description="暂无预设模板" />
      </div>

      <!-- Edit View -->
      <div v-else class="tab-content full-edit">
        <n-scrollbar style="max-height: calc(100vh - 180px)">
          <n-form label-placement="top">
            <n-form-item><AppTextField v-model:value="editModel.name" label="预设名称" placeholder="例如: 默认预设" /></n-form-item>
            
            <n-divider>匹配过滤</n-divider>
            <n-form-item><AppTextField v-model:value="editModel.filter_res" label="分辨率" placeholder="1080P, 4K" /></n-form-item>
            <n-form-item><AppTextField v-model:value="editModel.filter_team" label="制作组" placeholder="LoliHouse" /></n-form-item>
            <n-form-item><AppTextField v-model:value="editModel.filter_source" label="介质来源" placeholder="WEB-DL" /></n-form-item>
            <n-form-item><AppTextField v-model:value="editModel.filter_codec" label="视频编码" placeholder="H.265" /></n-form-item>
            <n-form-item><AppTextField v-model:value="editModel.filter_audio" label="音频编码" placeholder="FLAC" /></n-form-item>
            <n-form-item><AppTextField v-model:value="editModel.filter_sub" label="字幕语言" placeholder="简体内封" /></n-form-item>
            <n-form-item><AppTextField v-model:value="editModel.filter_effect" label="视频特效" placeholder="HDR10" /></n-form-item>
            <n-form-item><AppTextField v-model:value="editModel.filter_platform" label="发布平台" placeholder="Baha" /></n-form-item>
            
            <n-divider>关键词过滤</n-divider>
            <n-form-item><AppTextField v-model:value="editModel.include_keywords" label="必须包含" placeholder="关键词" /></n-form-item>
            <n-form-item><AppTextField v-model:value="editModel.exclude_keywords" label="排除关键词" placeholder="排除词" /></n-form-item>
            
            <n-divider>下载设置</n-divider>
            <n-form-item><AppTextField v-model:value="editModel.save_path" label="下载目录" placeholder="留空默认" /></n-form-item>
            <n-form-item>
              <AppSelectField v-model:value="editModel.target_client_id" label="下载客户端" :options="clients.map(c => ({label: c.name, value: c.id}))" clearable />
            </n-form-item>
            <n-form-item><AppTextField v-model:value="editModel.category" label="分类/标签" placeholder="Anime" /></n-form-item>
            <n-form-item>
              <AppSelectField 
                v-model:value="editModel.target_feeds" 
                label="监控订阅源"
                multiple
                placeholder="留空则监控所有"
                :options="feeds.map(f => ({label: f.title || f.url, value: String(f.id)}))"
              />
            </n-form-item>

            <n-divider>其他选项</n-divider>
            <div class="switch-row" style="margin-bottom: 12px;">
              <n-switch v-model:value="editModel.auto_fill" />
              <span class="switch-row__label">定时补全</span>
            </div>
            <div class="switch-row" style="margin-bottom: 24px;">
              <n-switch v-model:value="editModel.is_default" />
              <span class="switch-row__label">设为默认预设</span>
            </div>
          </n-form>
        </n-scrollbar>
        <div class="footer-btn">
          <n-button block v-bind="getButtonStyle('primary')" @click="saveTemplate">保存预设</n-button>
        </div>
      </div>
    </div>
  </AppGlassModal>
</template>

<style scoped>
.switch-row { display: flex; align-items: center; gap: 8px; }
.switch-row__label { font-weight: 500; color: var(--text-primary); white-space: nowrap; }
.switch-row__desc { font-size: 12px; color: var(--text-tertiary); }

.mobile-fullscreen-modal {
  width: 100vw !important;
  height: 100vh !important;
  margin: 0 !important;
  max-height: 100vh !important;
}
.mobile-modal-header { display: flex; align-items: center; gap: 8px; }
.mobile-modal-header .title { font-weight: bold; font-size: 16px; }

.mobile-template-container { height: calc(100vh - 120px); }
.tab-content { padding: 12px; }

.mobile-list { display: flex; flex-direction: column; gap: 12px; }
.mobile-card {
  background: var(--app-surface-card-mixed);
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  align-items: center;
}
.card-body { flex: 1; overflow: hidden; }
.card-title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.title-box { display: flex; align-items: center; gap: 8px; }
.title-box .name { font-weight: bold; font-size: 14px; }
.preview-text { font-size: 11px; color: var(--text-tertiary); }

.full-edit { display: flex; flex-direction: column; height: 100%; }
.footer-btn { margin-top: auto; padding-top: 16px; }
</style>
