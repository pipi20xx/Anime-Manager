<script setup lang="ts">
/**
 * RulesTab — 重命名规则
 *
 * 卡片网格展示重命名规则列表
 * 操作: 添加 / 编辑 / 复制 / 删除
 */
import { ref, reactive } from 'vue'
import { useNotification, useConfirm, useDragSort } from '@/composables'
import RuleEditModal from './RuleEditModal.vue'

defineOptions({ name: 'RulesTab' })

const { success, error: showError, warning } = useNotification()
const { confirm } = useConfirm()

const props = defineProps<{
  rules: any[]
  loading: boolean
}>()

const emit = defineEmits<{
  'update:rules': [rules: any[]]
  save: []
}>()

// 拖拽排序（不可变模式：通过 getter 获取列表，回调返回新数组）
const { dragIndex, dragOverIndex, onDragStart, onDragOver, onDragEnd } = useDragSort(
  () => props.rules,
  {
    onSort: (newList) => {
      emit('update:rules', newList!)
      emit('save')
    },
  },
)

// --- 规则编辑弹窗 ---
const showRuleModal = ref(false)
const isNewRule = ref(false)
const editingRuleIndex = ref(-1)

const ruleForm = reactive({
  id: '',
  name: '',
  movie_pattern: '',
  tv_pattern: '',
})

function resetRuleForm() {
  ruleForm.id = ''
  ruleForm.name = ''
  ruleForm.movie_pattern = ''
  ruleForm.tv_pattern = ''
}

function openAddRule() {
  resetRuleForm()
  ruleForm.id = 'rule_' + Date.now()
  isNewRule.value = true
  editingRuleIndex.value = -1
  showRuleModal.value = true
}

function openEditRule(index: number) {
  resetRuleForm()
  isNewRule.value = false
  editingRuleIndex.value = index
  Object.assign(ruleForm, JSON.parse(JSON.stringify(props.rules[index])))
  showRuleModal.value = true
}

async function handleSaveRule() {
  if (!ruleForm.name) {
    warning('请输入规则名称')
    return
  }
  const payload = { ...ruleForm }
  const newRules = [...props.rules]

  if (isNewRule.value) {
    newRules.push(payload)
  } else {
    newRules[editingRuleIndex.value] = payload
  }
  emit('update:rules', newRules)
  showRuleModal.value = false
  emit('save')
}

// --- 规则快捷操作 ---
async function deleteRule(index: number) {
  const ok = await confirm({ title: '确认删除规则', content: '确定要删除这条规则吗？', confirmColor: 'error' })
  if (!ok) return
  const newRules = [...props.rules]
  newRules.splice(index, 1)
  emit('update:rules', newRules)
  emit('save')
}

async function duplicateRule(index: number) {
  const newRule = { ...props.rules[index] }
  newRule.id = 'rule_' + Date.now()
  newRule.name = newRule.name + ' (副本)'
  const newRules = [...props.rules]
  newRules.splice(index + 1, 0, newRule)
  emit('update:rules', newRules)
  emit('save')
  success('规则已复制')
}
</script>

<template>
  <div>
    <div class="d-flex justify-end mb-4">
      <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openAddRule">添加规则</v-btn>
    </div>

    <v-row v-if="loading">
      <v-col v-for="i in 3" :key="i" cols="12" sm="6" md="4">
        <v-skeleton-loader type="card" />
      </v-col>
    </v-row>

    <v-row v-else-if="rules.length > 0">
      <v-col
        v-for="(rule, index) in rules"
        :key="rule.id"
        cols="12" sm="6" md="4"
        draggable="true"
        :class="{ 'drag-sorting': dragIndex === index, 'drag-over': dragOverIndex === index }"
        @dragstart="onDragStart(index, $event)"
        @dragover="onDragOver(index, $event)"
        @dragend="onDragEnd"
      >
        <v-card class="glass-card manage-card cursor-pointer" :class="{ 'hover-lift': dragIndex === -1 }" @click="dragIndex === -1 && openEditRule(index)">
          <!-- 标题行 -->
          <div class="manage-card__header">
            <div class="manage-card__title">{{ rule.name }}</div>
          </div>

          <!-- 信息区 -->
          <div class="manage-card__body">
            <div v-if="rule.movie_pattern" class="manage-card__info">
              <span class="manage-card__info-label">电影</span>
              <span class="manage-card__info-value" :title="rule.movie_pattern">{{ rule.movie_pattern }}</span>
            </div>
            <div v-if="rule.tv_pattern" class="manage-card__info">
              <span class="manage-card__info-label">剧集</span>
              <span class="manage-card__info-value" :title="rule.tv_pattern">{{ rule.tv_pattern }}</span>
            </div>
            <div v-if="!rule.movie_pattern && !rule.tv_pattern" class="manage-card__desc">
              未配置模板
            </div>
          </div>

          <v-divider />
          <v-card-actions class="manage-card__actions">
            <v-spacer />
            <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-content-copy" @click.stop="duplicateRule(index)">复制</v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click.stop="deleteRule(index)">删除</v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <div v-else class="text-center pa-8">
      <v-icon size="64" color="primary" class="mb-4">mdi-form-textbox</v-icon>
      <div class="text-h6 font-weight-medium">暂无重命名规则</div>
    </div>

    <!-- 规则编辑弹窗 -->
    <RuleEditModal
      v-model="showRuleModal"
      :is-new="isNewRule"
      :rule-form="ruleForm"
      @save="handleSaveRule"
    />
  </div>
</template>
