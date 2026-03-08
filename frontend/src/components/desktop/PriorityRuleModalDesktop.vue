<script setup lang="ts">
import { 
  NModal, NCard, NTabs, NTabPane, NButton, NSpace, NInput, NSelect, NSwitch, 
  NIcon, NGrid, NGi, NTag, NEmpty, NPopconfirm, NDivider,
  NForm, NFormItem, NInputNumber
} from 'naive-ui'
import { 
  AddOutlined as AddIcon,
  DeleteOutlined as DeleteIcon,
  EditOutlined as EditIcon,
  DragHandleOutlined as DragIcon
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
    style="width: 900px; max-width: 95vw; height: 80vh;"
    title="优先级规则管理"
    :bordered="false"
  >
    <div class="main-container">
      <n-tabs v-model:value="activeTab" type="segment" animated>
        
        <!-- Tab 1: Profiles -->
        <n-tab-pane name="profiles" tab="优先级策略 (Profiles)">
          <div class="tab-header">
            <div class="desc">
              策略决定了下载的优先顺序。您可以将多个"基础规则"组合，越靠上的规则优先级越高。
            </div>
            <n-button v-bind="getButtonStyle('primary')" @click="openAddProfile">
              新建策略
            </n-button>
          </div>
          
          <div class="profile-list">
            <n-grid :cols="2" :x-gap="12" :y-gap="12">
              <n-gi v-for="profile in profiles" :key="profile.id">
                <n-card hoverable class="profile-card" @click="openEditProfile(profile)">
                  <template #header>
                    <div class="p-header">
                      <span>{{ profile.name }}</span>
                    </div>
                  </template>
                  <template #header-extra>
                    <n-tag v-if="profile.upgrade_allowed" type="success" size="small" round>可洗版</n-tag>
                    <n-tag v-else type="default" size="small" round>锁定</n-tag>
                  </template>
                  
                  <div class="p-preview">
                    <div v-for="(r, idx) in profile.rules_config.slice(0, 3)" :key="idx" class="p-rule-item">
                      <span class="idx">{{ idx + 1 }}</span>
                      <span class="name">{{ r.name }}</span>
                    </div>
                    <div v-if="profile.rules_config.length > 3" class="more">... 以及更多</div>
                    <div v-if="profile.rules_config.length === 0" class="empty">暂无规则</div>
                  </div>
                  
                  <template #action>
                     <n-space justify="end" :size="4">
                       <n-button size="tiny" secondary @click.stop="openEditProfile(profile)">
                         <template #icon><n-icon><EditIcon/></n-icon></template>
                       </n-button>
                       <n-popconfirm positive-text="确定" negative-text="取消" @positive-click.stop="deleteProfile(profile.id)">
                         <template #trigger>
                           <n-button size="tiny" secondary type="error" @click.stop>
                             <template #icon><n-icon><DeleteIcon/></n-icon></template>
                           </n-button>
                         </template>
                         确定删除此策略吗？
                       </n-popconfirm>
                     </n-space>
                  </template>
                </n-card>
              </n-gi>
            </n-grid>
            <n-empty v-if="profiles.length === 0" description="暂无策略，请先点击右上角新建" class="mt-4" />
          </div>
        </n-tab-pane>

        <!-- Tab 2: Rules -->
        <n-tab-pane name="rules" tab="基础规则 (Rules)">
          <div class="tab-header">
            <div class="desc">
              "基础规则"是最小的规则单位。您可以创建多个规则（如：4K限定、字幕组限定），然后在策略中组合使用。
            </div>
            <n-button v-bind="getButtonStyle('primary')" @click="openAddRule">
              新建规则
            </n-button>
          </div>

          <n-grid :cols="3" :x-gap="12" :y-gap="12">
            <n-gi v-for="rule in rules" :key="rule.id">
              <n-card size="small" hoverable class="rule-card" @click="openEditRule(rule)">
                <template #header>
                  <div class="r-header">
                    {{ rule.name }}
                  </div>
                </template>
                <div class="r-content">
                  <n-tag size="small" v-if="rule.conditions.resolution">{{ rule.conditions.resolution }}</n-tag>
                  <n-tag size="small" v-if="rule.conditions.source">{{ rule.conditions.source }}</n-tag>
                  <n-tag size="small" v-if="rule.conditions.video_encode">{{ rule.conditions.video_encode }}</n-tag>
                  <n-tag size="small" v-if="rule.conditions.video_effect">{{ rule.conditions.video_effect }}</n-tag>
                  <n-tag size="small" v-if="rule.conditions.audio_encode">{{ rule.conditions.audio_encode }}</n-tag>
                  <n-tag size="small" v-if="rule.conditions.subtitle">{{ rule.conditions.subtitle }}</n-tag>
                  <n-tag size="small" v-if="rule.conditions.platform">{{ rule.conditions.platform }}</n-tag>
                  <n-tag size="small" v-if="rule.conditions.team">{{ rule.conditions.team }}</n-tag>
                </div>
                <template #action>
                  <n-space justify="end" :size="4">
                    <n-button size="tiny" secondary @click.stop="openEditRule(rule)">
                      <template #icon><n-icon><EditIcon/></n-icon></template>
                    </n-button>
                    <n-popconfirm positive-text="确定" negative-text="取消" @positive-click="deleteRule(rule.id)">
                      <template #trigger>
                        <n-button size="tiny" secondary type="error" @click.stop>
                          <template #icon><n-icon><DeleteIcon/></n-icon></template>
                        </n-button>
                      </template>
                      确定删除？
                    </n-popconfirm>
                  </n-space>
                </template>
              </n-card>
            </n-gi>
          </n-grid>
        </n-tab-pane>

      </n-tabs>
    </div>

    <!-- Rule Editor Modal -->
    <n-modal v-model:show="showRuleEdit" preset="card" title="编辑基础规则" style="width: 600px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="规则名称"><n-input v-model:value="currentRule.name" placeholder="例如: 4K HDR 优先" /></n-form-item>
        <n-divider title-placement="left">匹配条件 (留空表示不限制)</n-divider>
        <n-grid :cols="2" :x-gap="12">
                      <n-gi><n-form-item label="分辨率"><n-input v-model:value="currentRule.conditions.resolution" placeholder="如: 4K, 1080P" /></n-form-item></n-gi>          <n-gi><n-form-item label="制作组"><n-input v-model:value="currentRule.conditions.team" placeholder="如: LoliHouse" /></n-form-item></n-gi>
          <n-gi><n-form-item label="来源"><n-input v-model:value="currentRule.conditions.source" placeholder="如: Blu-ray" /></n-form-item></n-gi>
          <n-gi><n-form-item label="视频编码"><n-input v-model:value="currentRule.conditions.video_encode" placeholder="如: HEVC" /></n-form-item></n-gi>
          <n-gi><n-form-item label="音频编码"><n-input v-model:value="currentRule.conditions.audio_encode" placeholder="如: FLAC" /></n-form-item></n-gi>
          <n-gi><n-form-item label="字幕语言"><n-input v-model:value="currentRule.conditions.subtitle" placeholder="如: CHS" /></n-form-item></n-gi>
          <n-gi><n-form-item label="视频特效"><n-input v-model:value="currentRule.conditions.video_effect" placeholder="如: HDR" /></n-form-item></n-gi>
          <n-gi><n-form-item label="发布平台"><n-input v-model:value="currentRule.conditions.platform" placeholder="如: Baha" /></n-form-item></n-gi>
          <n-gi :span="2">
            <n-form-item label="必须包含"><n-input v-model:value="currentRule.conditions.must_contain" placeholder="包含这些关键词" /></n-form-item>
          </n-gi>
          <n-gi :span="2">
            <n-form-item label="不能包含"><n-input v-model:value="currentRule.conditions.must_not_contain" placeholder="包含这些关键词则排除" /></n-form-item>
          </n-gi>
        </n-grid>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('ghost')" @click="showRuleEdit = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="saveRule">保存规则</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Profile Editor Modal -->
    <n-modal v-model:show="showProfileEdit" preset="card" title="编辑优先级策略" style="width: 600px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="策略名称"><n-input v-model:value="currentProfile.name" /></n-form-item>
        <n-grid :cols="2" :x-gap="12">
          <n-gi>
            <n-form-item label="允许洗版"><n-switch v-model:value="currentProfile.upgrade_allowed" /></n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="截止分值">
              <n-input-number 
                v-model:value="currentProfile.cutoff_score" 
                :disabled="!currentProfile.upgrade_allowed"
                placeholder="达到此分值后停止洗版"
                style="width: 100%"
              />
            </n-form-item>
          </n-gi>
        </n-grid>
      </n-form>
      <n-divider title-placement="left">优先级排序 (拖拽调整，上方优先)</n-divider>
      <div class="drag-area">
          <draggable v-model="currentProfile.rules_config" item-key="rule_id" handle=".drag-handle">
            <template #item="{ element, index }">
              <div class="drag-item">
                <div class="drag-handle"><n-icon><DragIcon/></n-icon></div>
                <div class="drag-content">
                  <span>{{ element.name }}</span>
                  <div style="display: flex; align-items: center; gap: 8px">
                    <span style="font-size: 12px; color: var(--text-muted)">分值:</span>
                    <n-input-number v-model:value="element.score" size="tiny" :show-button="false" style="width: 60px" />
                  </div>
                </div>
                <n-button v-bind="getButtonStyle('iconDanger')" size="tiny" @click="removeRuleFromProfile(index)">
                   <template #icon><n-icon><DeleteIcon/></n-icon></template>
                </n-button>
              </div>
            </template>
          </draggable>
          <n-select :options="availableRules.map(r=>({label:r.name, value:r.id}))" @update:value="addRuleToProfile" placeholder="添加规则..." />
      </div>
      <template #footer>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('ghost')" @click="showProfileEdit = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="saveProfile">保存策略</n-button>
        </n-space>
      </template>
    </n-modal>
  </n-modal>
</template>

<style scoped>
.main-container { height: 100%; display: flex; flex-direction: column; }
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.desc { color: var(--n-text-color-3); font-size: 13px; max-width: 70%; }
.profile-card { cursor: pointer; border-radius: 8px; }
.p-header { display: flex; align-items: center; gap: 8px; font-weight: bold; }
.p-preview { margin: 12px 0; background: var(--n-action-color); padding: 8px; border-radius: 6px; font-size: 12px; }
.p-rule-item { display: flex; gap: 8px; margin-bottom: 4px; }
.p-rule-item .idx { color: var(--n-primary-color); font-weight: bold; }
.rule-card { border-radius: 8px; }
.r-header { display: flex; align-items: center; gap: 6px; font-weight: bold; }
.r-content { margin: 8px 0; display: flex; flex-wrap: wrap; gap: 4px; }
.drag-area { background: var(--n-action-color); padding: 12px; border-radius: 8px; display: flex; flex-direction: column; gap: 8px; }
.drag-item { background: var(--n-card-color); padding: 8px; border-radius: 6px; display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.drag-handle { cursor: move; opacity: 0.5; }
.drag-content { flex: 1; font-weight: 500; }
.mt-4 { margin-top: 16px; }
</style>
