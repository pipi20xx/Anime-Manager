<script setup lang="ts">
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import AppGlassModal from '../AppGlassModal.vue'
import AppGlassCard from '../AppGlassCard.vue'
import { 
  NTabs, NTabPane, NButton, NSpace, NSelect, NSwitch, 
  NIcon, NGrid, NGi, NEmpty, NDivider,
  NForm, NFormItem, NInputNumber
} from 'naive-ui'
import { useBackDialog } from '../../composables/useBackDialog'
import {
  PlusIcon as AddIcon,
  TrashIcon as DeleteIcon,
  Bars2Icon as DragIcon
} from '@heroicons/vue/24/outline'
import draggable from 'vuedraggable'
import { usePriorityRules } from '../../composables/components/usePriorityRules'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits(['update:show'])

const dialog = useBackDialog()

const handleDeleteProfileWithConfirm = (profile: any) => {
  dialog.warning({
    title: '确认删除',
    content: `确定删除策略「${profile.name}」吗？`,
    positiveText: '确定删除',
    negativeText: '取消',
    onPositiveClick: () => deleteProfile(profile.id)
  })
}

const handleDeleteRuleWithConfirm = (rule: any) => {
  dialog.warning({
    title: '确认删除',
    content: `确定删除规则「${rule.name}」吗？`,
    positiveText: '确定删除',
    negativeText: '取消',
    onPositiveClick: () => deleteRule(rule.id)
  })
}

const {
  activeTab, rules, profiles,
  showRuleEdit, currentRule, showProfileEdit, currentProfile,
  availableRules,
  openAddRule, openEditRule, saveRule, deleteRule,
  openAddProfile, openEditProfile, saveProfile, deleteProfile,
  addRuleToProfile, removeRuleFromProfile,
  close
} = usePriorityRules(props, emit)

const conditionLabels: Record<string, string> = {
  resolution: '分辨率',
  source: '介质来源',
  video_encode: '视频编码',
  video_effect: '视频特效',
  audio_encode: '音频编码',
  subtitle: '字幕语言',
  platform: '发布平台',
  team: '制作组',
  must_contain: '必须包含',
  must_not_contain: '不能包含'
}

function getConditions(rule: any) {
  const conds = rule.conditions || {}
  return Object.keys(conditionLabels)
    .map(k => ({ key: k, label: conditionLabels[k], value: conds[k] || '不限制', empty: !conds[k] }))
}

</script>

<template>
  <AppGlassModal
    appearance-key="priority-rule-modal"
    :show="show"
    @update:show="close"
    style="width: 900px;"
    title="洗版规则管理"
    bordered
    size="huge"
  >
    <div class="main-container">
      <n-tabs v-model:value="activeTab" type="line" animated>
        
        <!-- Tab 1: Profiles -->
        <n-tab-pane name="profiles" tab="洗版策略 (Profiles)">
          <div class="tab-header">
            <div class="desc">
              策略决定了洗版的优先顺序。您可以将多个"基础规则"组合，越靠上的规则洗版优先级越高。
            </div>
            <n-button v-bind="getButtonStyle('primary')" @click="openAddProfile">
              新建策略
            </n-button>
          </div>
          
          <div class="profile-list">
            <AppGlassCard
              v-for="profile in profiles"
              :key="profile.id"
              appearance-key="priority-profile-card"
              bordered
              embedded
              class="profile-card clickable-card"
              @click="openEditProfile(profile)"
            >
              <div class="card-header mb-2">
                <span class="card-name">{{ profile.name }}</span>
              </div>
              <div class="p-disp">
                <div class="p-row">
                  <span class="p-label">洗版状态</span>
                  <div class="v" :class="{ 'v-active': profile.upgrade_allowed }">{{ profile.upgrade_allowed ? '是' : '否' }}</div>
                </div>
                <div class="p-row">
                  <span class="p-label">截止分值</span>
                  <div class="v">{{ profile.cutoff_score ?? 0 }}</div>
                </div>
                <div class="p-row">
                  <span class="p-label">规则数量</span>
                  <div class="v">{{ profile.rules_config?.length || 0 }} 条</div>
                </div>
              </div>
              <div class="rule-preview" v-if="profile.rules_config?.length">
                <div v-for="(r, idx) in profile.rules_config.slice(0, 3)" :key="idx" class="rule-preview-item">
                  <span class="rule-idx">{{ idx + 1 }}</span>
                  <span class="rule-name" :title="r.name">{{ r.name }}</span>
                  <span class="rule-score">{{ r.score }}</span>
                </div>
                <div v-if="profile.rules_config.length > 3" class="rule-more">
                  ...以及其他 {{ profile.rules_config.length - 3 }} 条规则
                </div>
              </div>
              <div v-else class="rule-preview-empty">暂无规则</div>
              <template #action>
                <n-space justify="end" @click.stop>
                  <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="handleDeleteProfileWithConfirm(profile)">
                    <template #icon><n-icon><DeleteIcon/></n-icon></template>
                  </n-button>
                </n-space>
              </template>
            </AppGlassCard>
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

          <div class="rule-list">
            <AppGlassCard
              v-for="rule in rules"
              :key="rule.id"
              appearance-key="priority-rule-card"
              bordered
              embedded
              class="rule-card clickable-card"
              @click="openEditRule(rule)"
            >
              <div class="card-header mb-2">
                <span class="card-name">{{ rule.name }}</span>
              </div>
              <div class="r-disp">
                <div class="r-row" v-for="cond in getConditions(rule)" :key="cond.key">
                  <span class="r-label">{{ cond.label }}</span>
                  <div class="r-v" :class="{ 'r-v-empty': cond.empty }" :title="cond.value">{{ cond.value }}</div>
                </div>
              </div>
              <template #action>
                <n-space justify="end" @click.stop>
                  <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="handleDeleteRuleWithConfirm(rule)">
                    <template #icon><n-icon><DeleteIcon/></n-icon></template>
                  </n-button>
                </n-space>
              </template>
            </AppGlassCard>
            <n-empty v-if="rules.length === 0" description="暂无规则，请先点击右上角新建" class="mt-4" />
          </div>
        </n-tab-pane>

      </n-tabs>
    </div>

    <!-- Rule Editor Modal -->
    <AppGlassModal appearance-key="priority-rule-modal" v-model:show="showRuleEdit" title="编辑基础规则" style="width: 700px;" bordered size="huge">
      <n-form label-placement="left" label-width="100">
        <n-form-item><AppTextField v-model:value="currentRule.name" label="规则名称" placeholder="例如: 4K HDR 优先" /></n-form-item>
        <n-divider title-placement="left">匹配条件 (留空表示不限制)</n-divider>
        <n-grid :cols="2" :x-gap="12">
          <n-gi><n-form-item><AppTextField v-model:value="currentRule.conditions.resolution" label="分辨率" placeholder="如: 4K, 1080P" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="currentRule.conditions.team" label="制作组" placeholder="如: LoliHouse" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="currentRule.conditions.source" label="介质来源" placeholder="如: Blu-ray" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="currentRule.conditions.video_encode" label="视频编码" placeholder="如: H.265" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="currentRule.conditions.audio_encode" label="音频编码" placeholder="如: FLAC" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="currentRule.conditions.subtitle" label="字幕语言" placeholder="如: 简体内封" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="currentRule.conditions.video_effect" label="视频特效" placeholder="如: HDR" /></n-form-item></n-gi>
          <n-gi><n-form-item><AppTextField v-model:value="currentRule.conditions.platform" label="发布平台" placeholder="如: Baha" /></n-form-item></n-gi>
          <n-gi :span="2">
            <n-form-item><AppTextField v-model:value="currentRule.conditions.must_contain" label="必须包含" placeholder="包含这些关键词" /></n-form-item>
          </n-gi>
          <n-gi :span="2">
            <n-form-item><AppTextField v-model:value="currentRule.conditions.must_not_contain" label="不能包含" placeholder="包含这些关键词则排除" /></n-form-item>
          </n-gi>
        </n-grid>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="showRuleEdit = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="saveRule">保存规则</n-button>
        </n-space>
      </template>
    </AppGlassModal>

    <!-- Profile Editor Modal -->
    <AppGlassModal appearance-key="priority-rule-modal" v-model:show="showProfileEdit" title="编辑洗版策略" style="width: 700px;" bordered size="huge">
      <n-form label-placement="left" label-width="100">
        <n-form-item><AppTextField v-model:value="currentProfile.name" label="策略名称" placeholder="例如: 4K优先策略" /></n-form-item>
        <n-grid :cols="2" :x-gap="12">
          <n-gi :span="2">
            <n-form-item>
              <div class="switch-row">
                <n-switch v-model:value="currentProfile.upgrade_allowed" />
                <span class="switch-row__label">允许洗版</span>
                <span class="switch-row__desc">开启后达到截止分值前持续洗版</span>
              </div>
            </n-form-item>
          </n-gi>
          <n-gi :span="2">
            <n-form-item>
              <AppTextField 
                v-model:value="currentProfile.cutoff_score" 
                label="截止分值"
                type="number"
                :disabled="!currentProfile.upgrade_allowed"
                placeholder="达到此分值后停止洗版"
              />
            </n-form-item>
          </n-gi>
        </n-grid>
      </n-form>
      <n-divider title-placement="left">洗版排序 (拖拽调整，上方优先)</n-divider>
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
          <AppSelectField :options="availableRules.map(r=>({label:r.name, value:r.id}))" label="添加规则" @update:value="addRuleToProfile" placeholder="选择要添加的规则..." />
      </div>
      <template #footer>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="showProfileEdit = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="saveProfile">保存策略</n-button>
        </n-space>
      </template>
    </AppGlassModal>
  </AppGlassModal>
</template>

<style scoped>
.main-container { display: flex; flex-direction: column; --tabs-pane-padding: 16px 0 0 0; }
.tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.desc { color: var(--text-tertiary); font-size: 13px; max-width: 70%; }
.profile-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.profile-card { height: 100%; transition: transform var(--transition-fast); border: 1px solid var(--app-border-light); background: var(--app-surface-card-mixed); }
.profile-card:hover { transform: translateY(-4px); border-color: var(--n-primary-color); }
.clickable-card { cursor: pointer; }
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.card-name { font-weight: bold; font-size: var(--text-xl); color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.p-disp { flex-grow: 1; padding: var(--space-2) 0; display: flex; flex-direction: column; gap: var(--space-2); }
.p-disp .p-row { display: flex; align-items: center; gap: 8px; }
.p-disp .p-label { font-size: var(--text-sm); color: var(--text-tertiary); font-weight: 600; min-width: 70px; flex-shrink: 0; }
.p-disp .v { flex: 1; font-size: var(--text-sm); font-family: var(--code-font); background: var(--app-surface-card-mixed); padding: var(--space-1) var(--space-2); border-radius: var(--card-border-radius, var(--button-border-radius, 4px)); color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border: 1px solid var(--app-border-light); }
.rule-preview { margin-top: var(--space-2); display: flex; flex-direction: column; gap: 4px; }
.rule-preview-item { display: flex; align-items: center; gap: 8px; font-size: var(--text-sm); padding: 4px 8px; background: var(--app-surface-card-mixed); border-radius: 4px; border: 1px solid var(--app-border-light); }
.rule-idx { font-weight: bold; color: var(--n-primary-color); min-width: 20px; text-align: center; flex-shrink: 0; }
.rule-name { flex: 1; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rule-score { font-family: var(--code-font); color: var(--text-tertiary); font-size: 12px; flex-shrink: 0; }
.rule-more { font-size: 12px; color: var(--text-tertiary); padding: 4px 8px; font-style: italic; }
.rule-preview-empty { font-size: 12px; color: var(--text-tertiary); font-style: italic; padding: 8px; text-align: center; }
.drag-area { background: var(--app-surface-card-mixed); padding: 12px; border-radius: 8px; display: flex; flex-direction: column; gap: 8px; }
.drag-item { background: var(--app-surface-card-mixed); padding: 8px; border-radius: 6px; display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.rule-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.rule-card { height: 100%; transition: transform var(--transition-fast); border: 1px solid var(--app-border-light); background: var(--app-surface-card-mixed); }
.rule-card:hover { transform: translateY(-4px); border-color: var(--n-primary-color); }
.r-disp { flex-grow: 1; display: flex; flex-direction: column; gap: 4px; }
.r-row { display: flex; align-items: center; gap: 8px; }
.r-label { font-size: var(--text-sm); color: var(--text-tertiary); font-weight: 600; min-width: 70px; flex-shrink: 0; }
.r-v { flex: 1; font-size: var(--text-sm); font-family: var(--code-font); background: var(--app-surface-card-mixed); padding: var(--space-1) var(--space-2); border-radius: var(--card-border-radius, var(--button-border-radius, 4px)); color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border: 1px solid var(--app-border-light); }
.r-v-empty { color: var(--text-tertiary); font-style: italic; }
.drag-handle { cursor: move; opacity: var(--opacity-secondary); }
.drag-content { flex: 1; font-weight: 500; }
.switch-row { display: flex; align-items: center; gap: 8px; }
.switch-row__label { font-weight: 500; color: var(--text-primary); white-space: nowrap; }
.switch-row__desc { font-size: 12px; color: var(--text-tertiary); }
.v-active { color: var(--n-success-color); font-weight: 600; }
.mb-2 { margin-bottom: 8px; }
.mt-4 { margin-top: 16px; }
</style>
