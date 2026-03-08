<script setup lang="ts">
import { 
  NModal, NButton, NSpace, NIcon, NForm, NFormItem, 
  NInput, NSelect, NSwitch, NPopconfirm,
  NScrollbar, NDivider, NList, NListItem, NTag, NText
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  StarOutlined as StarIcon,
  StarFilled as StarFilledIcon,
  DeleteOutlined as DeleteIcon,
  ArrowBackOutlined as BackIcon
} from '@vicons/material'
import { useSubscriptionTemplates } from '../../composables/components/useSubscriptionTemplates'

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
  <n-modal 
    :show="show" 
    @update:show="close"
    preset="card"
    class="mobile-fullscreen-modal"
  >
    <template #header>
      <div class="mobile-modal-header">
        <n-button quaternary circle @click="showEdit ? showEdit = false : close()">
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
                        :color="row.is_default ? '#fbb308' : '#ccc'" 
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
                    <n-button quaternary circle type="error" size="small"><template #icon><n-icon><DeleteIcon/></n-icon></template></n-button>
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
            <n-form-item label="预设名称"><n-input v-model:value="editModel.name" placeholder="例如: 默认预设" /></n-form-item>
            
            <n-divider>匹配过滤</n-divider>
            <n-form-item label="分辨率"><n-input v-model:value="editModel.filter_res" placeholder="1080p, 4k" /></n-form-item>
            <n-form-item label="制作组"><n-input v-model:value="editModel.filter_team" placeholder="LoliHouse" /></n-form-item>
            <n-form-item label="来源"><n-input v-model:value="editModel.filter_source" placeholder="Web-DL" /></n-form-item>
            <n-form-item label="视频编码"><n-input v-model:value="editModel.filter_codec" placeholder="HEVC" /></n-form-item>
            <n-form-item label="音频编码"><n-input v-model:value="editModel.filter_audio" placeholder="FLAC" /></n-form-item>
            <n-form-item label="字幕语言"><n-input v-model:value="editModel.filter_sub" placeholder="CHS" /></n-form-item>
            <n-form-item label="视频特效"><n-input v-model:value="editModel.filter_effect" placeholder="HDR10" /></n-form-item>
            <n-form-item label="发布平台"><n-input v-model:value="editModel.filter_platform" placeholder="Baha" /></n-form-item>
            
            <n-divider>关键词过滤</n-divider>
            <n-form-item label="必须包含"><n-input v-model:value="editModel.include_keywords" placeholder="关键词" /></n-form-item>
            <n-form-item label="排除关键词"><n-input v-model:value="editModel.exclude_keywords" placeholder="排除词" /></n-form-item>
            
            <n-divider>下载设置</n-divider>
            <n-form-item label="下载目录"><n-input v-model:value="editModel.save_path" placeholder="留空默认" /></n-form-item>
            <n-form-item label="下载客户端">
              <n-select v-model:value="editModel.target_client_id" :options="clients.map(c => ({label: c.name, value: c.id}))" />
            </n-form-item>
            <n-form-item label="分类/标签"><n-input v-model:value="editModel.category" placeholder="Anime" /></n-form-item>
            <n-form-item label="监控订阅源">
              <n-select 
                v-model:value="editModel.target_feeds" 
                multiple
                placeholder="留空则监控所有"
                :options="feeds.map(f => ({label: f.title || f.url, value: String(f.id)}))"
              />
            </n-form-item>

            <n-divider>其他选项</n-divider>
            <n-space justify="space-between" align="center" style="margin-bottom: 12px;">
              <span>定时补全</span>
              <n-switch v-model:value="editModel.auto_fill" />
            </n-space>
            <n-space justify="space-between" align="center" style="margin-bottom: 24px;">
              <span>设为默认预设</span>
              <n-switch v-model:value="editModel.is_default" />
            </n-space>
          </n-form>
        </n-scrollbar>
        <div class="footer-btn">
          <n-button block type="primary" @click="saveTemplate">保存预设</n-button>
        </div>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
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
  background: var(--app-surface-card);
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
.preview-text { font-size: 11px; color: var(--n-text-color-3); }

.full-edit { display: flex; flex-direction: column; height: 100%; }
.footer-btn { margin-top: auto; padding-top: 16px; }
</style>
