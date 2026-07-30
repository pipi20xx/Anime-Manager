<script setup lang="ts">
/**
 * PriorityRuleModal — 洗版规则管理弹窗
 *
 * 对标旧前端 PriorityRuleModalDesktop:
 * - 基础规则 (FilterRule) CRUD
 * - 洗版策略 (QualityProfile) CRUD + 拖拽排序 + 分值设置
 */
import { ref, computed, watch } from 'vue'
import { api } from '@/api/client'
import { useNotification, useConfirm } from '@/composables'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void }>()

const { success, error: showError, warning } = useNotification()
const { confirm } = useConfirm()

const activeTab = ref('profiles')
const rules = ref<any[]>([])
const profiles = ref<any[]>([])
const loading = ref(false)

// 编辑状态
const showRuleEdit = ref(false)
const currentRule = ref<any>({ name: '', conditions: {} })
const showProfileEdit = ref(false)
const currentProfile = ref<any>({ name: '', rules_config: [], upgrade_allowed: false, cutoff_score: 0 })

const conditionLabels: Record<string, string> = {
  resolution: '分辨率', source: '介质来源', video_encode: '视频编码',
  video_effect: '视频特效', audio_encode: '音频编码', subtitle: '字幕语言',
  platform: '发布平台', team: '制作组',
  must_contain: '必须包含', must_not_contain: '不能包含',
}

const defaultCondition = {
  resolution: null, source: null, video_encode: null,
  audio_encode: null, video_effect: null, subtitle: null,
  platform: null, team: null, must_contain: '', must_not_contain: '',
}

watch(() => props.show, (val) => { if (val) init() })

async function init() {
  loading.value = true
  try {
    const [r, p] = await Promise.all([
      api.get<any[]>('/api/priority/rules'),
      api.get<any[]>('/api/priority/profiles'),
    ])
    rules.value = r || []
    profiles.value = p || []
  } catch { showError('加载数据失败') }
  finally { loading.value = false }
}

// --- Rule CRUD ---
function openAddRule() {
  currentRule.value = { name: '', conditions: { ...defaultCondition } }
  showRuleEdit.value = true
}

function openEditRule(rule: any) {
  currentRule.value = JSON.parse(JSON.stringify(rule))
  if (!currentRule.value.conditions) currentRule.value.conditions = { ...defaultCondition }
  showRuleEdit.value = true
}

async function saveRule() {
  if (!currentRule.value.name) { warning('规则名称不能为空'); return }
  try {
    await api.post('/api/priority/rules', currentRule.value)
    success('规则保存成功')
    showRuleEdit.value = false
    init()
  } catch (e: any) { showError(e?.response?.data?.detail || e?.message || '保存失败') }
}

async function deleteRule(rule: any) {
  const ok = await confirm({ title: '确认删除', content: `确定删除规则「${rule.name}」吗？`, confirmColor: 'error' })
  if (!ok) return
  try {
    await api.delete(`/api/priority/rules/${rule.id}`)
    success('已删除')
    init()
  } catch (e: any) { showError(e?.response?.data?.detail || e?.message || '删除失败') }
}

// --- Profile CRUD ---
const availableRules = computed(() => {
  if (!currentProfile.value.rules_config) return rules.value
  const usedIds = currentProfile.value.rules_config.map((x: any) => x.rule_id)
  return rules.value.filter((r: any) => !usedIds.includes(r.id))
})

function openAddProfile() {
  currentProfile.value = { name: '', rules_config: [], upgrade_allowed: false, cutoff_score: 0 }
  showProfileEdit.value = true
}

function openEditProfile(profile: any) {
  currentProfile.value = JSON.parse(JSON.stringify(profile))
  if (!currentProfile.value.rules_config) currentProfile.value.rules_config = []
  showProfileEdit.value = true
}

function addRuleToProfile(ruleId: number) {
  const rule = rules.value.find((r: any) => r.id === ruleId)
  if (!rule) return
  let defaultScore = 1000
  if (currentProfile.value.rules_config.length > 0) {
    const minScore = Math.min(...currentProfile.value.rules_config.map((r: any) => r.score || 0))
    defaultScore = Math.max(0, minScore - 100)
  }
  currentProfile.value.rules_config.push({ rule_id: rule.id, name: rule.name, score: defaultScore })
}

function removeRuleFromProfile(index: number) {
  currentProfile.value.rules_config.splice(index, 1)
}

function moveRuleUp(index: number) {
  if (index <= 0) return
  const arr = currentProfile.value.rules_config
  ;[arr[index], arr[index - 1]] = [arr[index - 1], arr[index]]
}

function moveRuleDown(index: number) {
  const arr = currentProfile.value.rules_config
  if (index >= arr.length - 1) return
  ;[arr[index], arr[index + 1]] = [arr[index + 1], arr[index]]
}

async function saveProfile() {
  if (!currentProfile.value.name) { warning('策略名称不能为空'); return }
  try {
    await api.post('/api/priority/profiles', currentProfile.value)
    success('策略保存成功')
    showProfileEdit.value = false
    init()
  } catch (e: any) { showError(e?.response?.data?.detail || e?.message || '保存失败') }
}

async function deleteProfile(profile: any) {
  const ok = await confirm({ title: '确认删除', content: `确定删除策略「${profile.name}」吗？`, confirmColor: 'error' })
  if (!ok) return
  try {
    await api.delete(`/api/priority/profiles/${profile.id}`)
    success('已删除')
    init()
  } catch (e: any) { showError(e?.response?.data?.detail || e?.message || '删除失败') }
}

function getConditions(rule: any) {
  const conds = rule.conditions || {}
  return Object.keys(conditionLabels)
    .map(k => ({ key: k, label: conditionLabels[k], value: conds[k] || '不限制', empty: !conds[k] }))
}
</script>

<template>
  <v-dialog :model-value="show" max-width="900" scrollable @update:model-value="$emit('update:show', $event)">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-arrow-up-bold-circle-outline</v-icon>
        洗版规则管理
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <v-tabs v-model="activeTab" color="primary" class="mb-4">
          <v-tab value="profiles">洗版策略</v-tab>
          <v-tab value="rules">基础规则</v-tab>
        </v-tabs>

        <v-window v-model="activeTab">
          <!-- ===== Profiles Tab ===== -->
          <v-window-item value="profiles">
            <div class="d-flex justify-space-between align-center mb-4">
              <div class="text-body-2 text-medium-emphasis">策略决定了洗版的优先顺序，越靠上的规则洗版优先级越高。</div>
              <v-btn color="primary" variant="flat" size="small" prepend-icon="mdi-plus" @click="openAddProfile">新建策略</v-btn>
            </div>

            <v-skeleton-loader v-if="loading" type="card@3" />

            <v-row v-else-if="profiles.length > 0">
              <v-col v-for="profile in profiles" :key="profile.id" cols="12" sm="6">
                <v-card class="glass-card manage-card hover-lift cursor-pointer" @click="openEditProfile(profile)">
                  <!-- 标题行 -->
                  <div class="manage-card__header">
                    <div class="manage-card__title">{{ profile.name }}</div>
                  </div>

                  <!-- 信息区 -->
                  <div class="manage-card__body">
                    <div class="manage-card__info">
                      <span class="manage-card__info-label">洗版</span>
                      <span :class="profile.upgrade_allowed ? 'text-success' : 'text-medium-emphasis'" class="font-weight-bold manage-card__info-value">{{ profile.upgrade_allowed ? '开启' : '关闭' }}</span>
                    </div>
                    <div class="manage-card__info">
                      <span class="manage-card__info-label">截止分值</span>
                      <span class="font-weight-bold manage-card__info-value">{{ profile.cutoff_score ?? 0 }}</span>
                    </div>
                    <div class="manage-card__info">
                      <span class="manage-card__info-label">规则</span>
                      <span class="font-weight-bold manage-card__info-value">{{ profile.rules_config?.length || 0 }} 条</span>
                    </div>
                    <div v-if="profile.rules_config?.length" class="manage-card__tags">
                      <v-chip v-for="(r, idx) in profile.rules_config.slice(0, 3)" :key="idx" size="x-small" variant="tonal" color="primary">
                        {{ r.name }}
                      </v-chip>
                      <span v-if="profile.rules_config.length > 3" class="text-caption text-medium-emphasis">+{{ profile.rules_config.length - 3 }}</span>
                    </div>
                  </div>

                  <!-- 操作区 -->
                  <div class="manage-card__actions">
                    <v-spacer />
                    <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click.stop="deleteProfile(profile)">删除</v-btn>
                  </div>
                </v-card>
              </v-col>
            </v-row>
            <div v-else class="text-center pa-6 text-medium-emphasis">暂无策略，请先点击右上角新建</div>
          </v-window-item>

          <!-- ===== Rules Tab ===== -->
          <v-window-item value="rules">
            <div class="d-flex justify-space-between align-center mb-4">
              <div class="text-body-2 text-medium-emphasis">"基础规则"是最小的规则单位，可以在策略中组合使用。</div>
              <v-btn color="primary" variant="flat" size="small" prepend-icon="mdi-plus" @click="openAddRule">新建规则</v-btn>
            </div>

            <v-skeleton-loader v-if="loading" type="card@3" />

            <v-row v-else-if="rules.length > 0">
              <v-col v-for="rule in rules" :key="rule.id" cols="12" sm="6">
                <v-card class="glass-card manage-card hover-lift cursor-pointer" @click="openEditRule(rule)">
                  <!-- 标题行 -->
                  <div class="manage-card__header">
                    <div class="manage-card__title">{{ rule.name }}</div>
                  </div>

                  <!-- 信息区 -->
                  <div class="manage-card__body">
                    <div v-for="cond in getConditions(rule)" :key="cond.key" class="manage-card__info">
                      <span class="manage-card__info-label">{{ cond.label }}</span>
                      <span class="manage-card__info-value" :class="{ 'text-medium-emphasis font-italic': cond.empty }">{{ cond.value }}</span>
                    </div>
                  </div>

                  <!-- 操作区 -->
                  <div class="manage-card__actions">
                    <v-spacer />
                    <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click.stop="deleteRule(rule)">删除</v-btn>
                  </div>
                </v-card>
              </v-col>
            </v-row>
            <div v-else class="text-center pa-6 text-medium-emphasis">暂无规则，请先点击右上角新建</div>
          </v-window-item>
        </v-window>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="$emit('update:show', false)">关闭</v-btn>
      </v-card-actions>
    </v-card>

    <!-- Rule Editor -->
    <v-dialog v-model="showRuleEdit" max-width="700" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4">编辑基础规则</v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-text-field v-model="currentRule.name" label="规则名称" placeholder="例如: 4K HDR 优先" variant="outlined" density="compact" class="mb-3" />
          <div class="text-subtitle-2 font-weight-medium mb-2">匹配条件 (留空表示不限制)</div>
          <v-row dense>
            <v-col cols="6"><v-text-field v-model="currentRule.conditions.resolution" label="分辨率" placeholder="如: 4K, 1080P" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="currentRule.conditions.team" label="制作组" placeholder="如: LoliHouse" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="currentRule.conditions.source" label="介质来源" placeholder="如: Blu-ray" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="currentRule.conditions.video_encode" label="视频编码" placeholder="如: H.265" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="currentRule.conditions.audio_encode" label="音频编码" placeholder="如: FLAC" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="currentRule.conditions.subtitle" label="字幕语言" placeholder="如: 简体内封" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="currentRule.conditions.video_effect" label="视频特效" placeholder="如: HDR" variant="outlined" density="compact" /></v-col>
            <v-col cols="6"><v-text-field v-model="currentRule.conditions.platform" label="发布平台" placeholder="如: Baha" variant="outlined" density="compact" /></v-col>
            <v-col cols="12"><v-text-field v-model="currentRule.conditions.must_contain" label="必须包含" placeholder="包含这些关键词" variant="outlined" density="compact" /></v-col>
            <v-col cols="12"><v-text-field v-model="currentRule.conditions.must_not_contain" label="不能包含" placeholder="包含这些关键词则排除" variant="outlined" density="compact" /></v-col>
          </v-row>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showRuleEdit = false">取消</v-btn>
          <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveRule">保存规则</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Profile Editor -->
    <v-dialog v-model="showProfileEdit" max-width="700" scrollable>
      <v-card class="glass-card">
        <v-card-title class="pa-4">编辑洗版策略</v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-text-field v-model="currentProfile.name" label="策略名称" placeholder="例如: 4K优先策略" variant="outlined" density="compact" class="mb-3" />
          <v-row dense>
            <v-col cols="6">
              <v-switch v-model="currentProfile.upgrade_allowed" color="primary" density="compact" hide-details label="允许洗版" />
            </v-col>
            <v-col cols="6">
              <v-text-field v-model="currentProfile.cutoff_score" label="截止分值" type="number" :disabled="!currentProfile.upgrade_allowed" variant="outlined" density="compact" hint="达到此分值后停止洗版" persistent-hint />
            </v-col>
          </v-row>

          <div class="text-subtitle-2 font-weight-medium mt-4 mb-2">洗版排序 (上方优先)</div>
          <div class="pa-3 rounded-lg" style="background: rgba(var(--v-theme-on-surface), 0.04);">
            <div v-for="(r, idx) in currentProfile.rules_config" :key="idx" class="d-flex align-center ga-2 pa-2 mb-2 rounded" style="background: rgba(var(--v-theme-on-surface), 0.06);">
              <v-btn icon="mdi-chevron-up" size="x-small" variant="text" :disabled="idx === 0" @click="moveRuleUp(idx as number)" />
              <v-btn icon="mdi-chevron-down" size="x-small" variant="text" :disabled="idx === currentProfile.rules_config.length - 1" @click="moveRuleDown(idx as number)" />
              <span class="text-primary font-weight-bold text-caption" style="min-width:20px">{{ (idx as number) + 1 }}</span>
              <span class="text-body-2 flex-grow-1">{{ r.name }}</span>
              <v-text-field v-model="r.score" label="分值" type="number" variant="outlined" density="compact" hide-details style="max-width:80px" />
              <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-close" @click="removeRuleFromProfile(idx as number)">移除</v-btn>
            </div>
            <v-select
              label="添加规则"
              :items="availableRules.map((r: any) => ({ title: r.name, value: r.id }))"
              placeholder="选择要添加的规则..."
              clearable variant="outlined" density="compact" hide-details
              @update:model-value="addRuleToProfile"
            />
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="showProfileEdit = false">取消</v-btn>
          <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveProfile">保存策略</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>


