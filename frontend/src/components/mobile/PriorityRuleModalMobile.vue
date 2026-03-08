<script setup lang="ts">
import { 
  NModal, NCard, NTabs, NTabPane, NButton, NSpace, NInput, NSelect, NSwitch, 
  NIcon, NTag, NEmpty, NPopconfirm, NDivider, NList, NListItem, NThing,
  NForm, NFormItem, NInputNumber, NScrollbar
} from 'naive-ui'
import { 
  AddOutlined as AddIcon,
  DeleteOutlined as DeleteIcon,
  EditOutlined as EditIcon,
  DragHandleOutlined as DragIcon,
  ArrowBackOutlined as BackIcon
} from '@vicons/material'
import draggable from 'vuedraggable'
import { usePriorityRules } from '../../composables/components/usePriorityRules'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits(['update:show'])

const {
  activeTab, rules, profiles,
  showRuleEdit, currentRule, showProfileEdit, currentProfile,
  availableRules,
  openAddRule, openEditRule, saveRule, deleteRule,
  openAddProfile, openEditProfile, saveProfile, deleteProfile,
  addRuleToProfile, removeRuleFromProfile,
  close
} = usePriorityRules(props, emit)

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
        <n-button quaternary circle @click="close">
          <template #icon><n-icon><BackIcon/></n-icon></template>
        </n-button>
        <span class="title">优先级规则</span>
      </div>
    </template>

    <div class="mobile-container">
      <n-tabs v-model:value="activeTab" type="line" animated justify-content="space-evenly">
        
        <!-- Tab 1: Profiles -->
        <n-tab-pane name="profiles" tab="优先级策略">
          <div class="tab-content">
            <n-button block type="primary" @click="openAddProfile" style="margin-bottom: 16px;">
              <template #icon><n-icon><AddIcon/></n-icon></template>
              新建优先级策略
            </n-button>

            <div v-if="profiles.length > 0" class="mobile-list">
              <div v-for="profile in profiles" :key="profile.id" class="mobile-card" @click="openEditProfile(profile)">
                <div class="card-body">
                  <div class="card-title-row">
                    <div class="title-box">
                      <span class="name">{{ profile.name }}</span>
                    </div>
                    <n-tag v-if="profile.upgrade_allowed" type="success" size="tiny" round>可洗版</n-tag>
                  </div>
                  <div class="rules-preview">
                    {{ profile.rules_config.map(r => r.name).join(' > ') || '暂无规则' }}
                  </div>
                </div>
                <div class="card-actions" @click.stop>
                   <n-button quaternary circle size="small" @click="openEditProfile(profile)">
                     <template #icon><n-icon><EditIcon/></n-icon></template>
                   </n-button>
                   <n-popconfirm positive-text="确定" negative-text="取消" @positive-click="deleteProfile(profile.id)">
                      <template #trigger>
                        <n-button v-bind="getButtonStyle('iconDanger')" size="small"><template #icon><n-icon><DeleteIcon/></n-icon></template></n-button>
                      </template>
                      确定删除？
                   </n-popconfirm>
                </div>
              </div>
            </div>
            <n-empty v-else description="暂无策略" />
          </div>
        </n-tab-pane>

        <!-- Tab 2: Rules -->
        <n-tab-pane name="rules" tab="基础规则">
          <div class="tab-content">
            <n-button block type="primary" dashed @click="openAddRule" style="margin-bottom: 16px;">
              <template #icon><n-icon><AddIcon/></n-icon></template>
              新建规则
            </n-button>

            <div v-if="rules.length > 0" class="mobile-list">
               <div v-for="rule in rules" :key="rule.id" class="mobile-card" @click="openEditRule(rule)">
                  <div class="card-body">
                    <div class="card-title-row">
                      <div class="title-box">
                        <span class="name">{{ rule.name }}</span>
                      </div>
                    </div>
                    <div class="tags-row">
                      <n-tag v-if="rule.conditions.resolution" size="tiny" quaternary>{{ rule.conditions.resolution }}</n-tag>
                      <n-tag v-if="rule.conditions.team" size="tiny" quaternary>{{ rule.conditions.team }}</n-tag>
                      <n-tag v-if="rule.conditions.must_contain" size="tiny" quaternary type="warning">正则</n-tag>
                    </div>
                  </div>
                  <div class="card-actions" @click.stop>
                     <n-button quaternary circle size="small" @click="openEditRule(rule)">
                       <template #icon><n-icon><EditIcon/></n-icon></template>
                     </n-button>
                     <n-popconfirm positive-text="确定" negative-text="取消" @positive-click="deleteRule(rule.id)">
                        <template #trigger>
                          <n-button v-bind="getButtonStyle('iconDanger')" size="small"><template #icon><n-icon><DeleteIcon/></n-icon></template></n-button>
                        </template>
                        确定删除？
                     </n-popconfirm>
                  </div>
               </div>
            </div>
            <n-empty v-else description="暂无规则" />
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>

    <!-- Rule Editor (Mobile Version: Use Modal or Drawer) -->
    <n-modal v-model:show="showRuleEdit" preset="card" class="mobile-fullscreen-modal" title="编辑基础规则">
       <n-scrollbar style="max-height: 80vh">
        <n-form label-placement="top">
          <n-form-item label="规则名称"><n-input v-model:value="currentRule.name" placeholder="例如: 4K HDR 优先" /></n-form-item>
          
          <n-divider>匹配条件 (留空不限)</n-divider>
          <n-form-item label="分辨率"><n-input v-model:value="currentRule.conditions.resolution" placeholder="如: 4K, 1080P" /></n-form-item>
          <n-form-item label="制作组"><n-input v-model:value="currentRule.conditions.team" placeholder="如: LoliHouse" /></n-form-item>
          <n-form-item label="来源"><n-input v-model:value="currentRule.conditions.source" placeholder="如: Blu-ray" /></n-form-item>
          <n-form-item label="视频编码"><n-input v-model:value="currentRule.conditions.video_encode" placeholder="如: HEVC" /></n-form-item>
          <n-form-item label="音频编码"><n-input v-model:value="currentRule.conditions.audio_encode" placeholder="如: FLAC" /></n-form-item>
          <n-form-item label="字幕语言"><n-input v-model:value="currentRule.conditions.subtitle" placeholder="如: CHS" /></n-form-item>
          <n-form-item label="视频特效"><n-input v-model:value="currentRule.conditions.video_effect" placeholder="如: HDR" /></n-form-item>
          <n-form-item label="发布平台"><n-input v-model:value="currentRule.conditions.platform" placeholder="如: Baha" /></n-form-item>
          
          <n-form-item label="必须包含关键词"><n-input v-model:value="currentRule.conditions.must_contain" placeholder="正则或普通词" /></n-form-item>
          <n-form-item label="排除关键词"><n-input v-model:value="currentRule.conditions.must_not_contain" placeholder="正则或普通词" /></n-form-item>
        </n-form>
       </n-scrollbar>
       <template #footer>
          <n-button block v-bind="getButtonStyle('primary')" @click="saveRule">保存规则</n-button>
       </template>
    </n-modal>

    <!-- Profile Editor (Mobile Version) -->
    <n-modal v-model:show="showProfileEdit" preset="card" class="mobile-fullscreen-modal" title="编辑策略">
       <n-scrollbar style="max-height: 80vh">
        <n-form label-placement="top">
          <n-form-item label="策略名称"><n-input v-model:value="currentProfile.name" /></n-form-item>
          <n-form-item label="洗版设置">
            <div style="display:flex; flex-direction: column; gap: 8px; width: 100%">
              <div style="display: flex; justify-content: space-between; align-items: center">
                <span>允许洗版</span> <n-switch v-model:value="currentProfile.upgrade_allowed" />
              </div>
              <div v-if="currentProfile.upgrade_allowed" style="display: flex; justify-content: space-between; align-items: center; gap: 12px">
                <span>截止分值</span>
                <n-input-number v-model:value="currentProfile.cutoff_score" size="small" style="flex: 1" />
              </div>
            </div>
          </n-form-item>
        </n-form>
        <n-divider>规则优先级排序</n-divider>
        <div class="mobile-drag-area">
          <draggable v-model="currentProfile.rules_config" item-key="rule_id" handle=".drag-handle">
            <template #item="{ element, index }">
              <div class="mobile-drag-item">
                <div class="drag-handle"><n-icon size="20"><DragIcon/></n-icon></div>
                <div class="drag-info">
                   <div class="name">{{ element.name }}</div>
                   <div style="display: flex; align-items: center; gap: 4px; margin-top: 4px">
                     <span style="font-size: 11px; color: #888">分值:</span>
                     <n-input-number v-model:value="element.score" size="tiny" :show-button="false" style="width: 50px" />
                   </div>
                </div>
                <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="removeRuleFromProfile(index)">
                   <template #icon><n-icon><DeleteIcon/></n-icon></template>
                </n-button>
              </div>
            </template>
          </draggable>
          <n-select :options="availableRules.map(r=>({label:r.name, value:r.id}))" @update:value="addRuleToProfile" placeholder="点击添加规则..." />
        </div>
       </n-scrollbar>
       <template #footer>
          <n-button block v-bind="getButtonStyle('primary')" @click="saveProfile">保存策略</n-button>
       </template>
    </n-modal>
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

.mobile-container { height: calc(100vh - 120px); display: flex; flex-direction: column; }
.tab-content { padding: 12px; }

.mobile-list { display: flex; flex-direction: column; gap: 12px; }
.mobile-card {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
  padding: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-body { flex: 1; overflow: hidden; }
.card-title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.title-box { display: flex; align-items: center; gap: 6px; }
.title-box .name { font-weight: bold; font-size: 14px; }
.rules-preview { font-size: 11px; color: var(--n-text-color-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tags-row { display: flex; gap: 4px; flex-wrap: wrap; }

.mobile-drag-area { display: flex; flex-direction: column; gap: 10px; padding: 4px; }
.mobile-drag-item {
  background: var(--app-surface-inner);
  border-radius: var(--button-border-radius, 8px);
  padding: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--app-border-light);
}
.drag-info { flex: 1; }
.drag-info .name { font-weight: bold; font-size: 13px; }
.drag-info .score { font-size: 11px; color: var(--n-text-color-3); }
</style>
