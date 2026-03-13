<script setup lang="ts">
import { ref, h } from 'vue'
import {
  NSpace, NButton, NIcon, NPopconfirm, NEmpty,
  NSwitch, NList, NListItem, NThing, NDrawer, NDrawerContent
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  DeleteOutlined as DeleteIcon,
  CloudDownloadOutlined as ExportIcon,
  CloudUploadOutlined as ImportIcon,
  MoreVertOutlined as MoreIcon,
  EditOutlined as EditIcon
} from '@vicons/material'
import ClassifierEditModal from '../../components/ClassifierEditModal.vue'
import { useSecondaryRule } from '../../composables/views/useSecondaryRule'
import { useBackClose } from '../../composables/useBackClose'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  rules,
  showRuleModal,
  editingRule,
  isNewRule,
  editingIndex,
  importLoading,
  fileInput,
  handleSaveRule,
  saveRulesToBackend,
  deleteRule,
  handleExport,
  triggerImport,
  handleFileChange,
  translateIds
} = useSecondaryRule()

useBackClose(showRuleModal)

// 操作抽屉状态
const showActionDrawer = ref(false)
useBackClose(showActionDrawer)

const actionItems = [
  { key: 'import', label: '导入规则', icon: ImportIcon },
  { key: 'export', label: '导出规则', icon: ExportIcon },
]

const handleAction = (key: string) => {
  showActionDrawer.value = false
  setTimeout(() => {
    if (key === 'import') triggerImport()
    else if (key === 'export') handleExport()
  }, 300)
}
</script>

<template>
  <div class="secondary-rule-view-mobile">
    <input type="file" ref="fileInput" style="display:none" accept=".json" @change="handleFileChange" />
    
    <div class="mobile-toolbar">
      <n-button type="primary" dashed size="small" @click="editingRule = null; isNewRule = true; showRuleModal = true">
        <template #icon><n-icon><AddIcon /></n-icon></template>
        添加新分类规则
      </n-button>

      <n-button v-bind="getButtonStyle('icon')" size="small" style="margin-left: 8px;" @click="showActionDrawer = true">
        <template #icon><n-icon><MoreIcon /></n-icon></template>
      </n-button>
    </div>

    <div class="rules-list">
      <n-empty v-if="rules.length === 0" description="暂无规则" style="padding: 60px 0" />
      <div v-else class="rules-grid">
        <div 
          v-for="(rule, index) in rules" 
          :key="rule.id || index" 
          class="rule-card"
          @click="editingRule = rule; isNewRule = false; editingIndex = index; showRuleModal = true"
        >
          <div class="card-top">
            <span class="rule-name">{{ rule.name }}</span>
            <n-switch v-model:value="rule.enabled" size="small" @click.stop @update:value="saveRulesToBackend" />
          </div>
          <div class="criteria-mini">
            <div v-if="rule.target !== 'all'" class="c-tag target">{{ rule.target === 'movie' ? '电影' : (rule.target === 'tv' ? '剧集' : rule.target) }}</div>
            <div v-if="translateIds(rule.criteria.genre_ids, 'genres')" class="c-tag">{{ translateIds(rule.criteria.genre_ids, 'genres') }}</div>
            <div v-if="translateIds(rule.criteria.company_ids, 'companies')" class="c-tag">{{ translateIds(rule.criteria.company_ids, 'companies') }}</div>
            <div v-if="translateIds(rule.criteria.keyword_ids, 'keywords')" class="c-tag">{{ translateIds(rule.criteria.keyword_ids, 'keywords') }}</div>
            <div v-if="translateIds(rule.criteria.origin_country, 'countries')" class="c-tag">{{ translateIds(rule.criteria.origin_country, 'countries') }}</div>
            <div v-if="translateIds(rule.criteria.original_language, 'languages')" class="c-tag">{{ translateIds(rule.criteria.original_language, 'languages') }}</div>
            <div v-if="rule.criteria.title" class="c-tag">{{ rule.criteria.title }}</div>
            <div v-if="rule.criteria.year" class="c-tag">{{ rule.criteria.year }}</div>
          </div>
          <div class="card-footer" @click.stop>
            <n-space justify="end">
              <n-popconfirm @positive-click="deleteRule(index)">
                <template #trigger>
                  <n-button v-bind="getButtonStyle('iconDanger')" size="small">
                    <template #icon><n-icon><DeleteIcon /></n-icon></template>
                  </n-button>
                </template>
                确定删除?
              </n-popconfirm>
            </n-space>
          </div>
        </div>
      </div>
    </div>

    <ClassifierEditModal v-model:show="showRuleModal" :rule-data="editingRule" :is-new="isNewRule" @save="handleSaveRule" />

    <!-- 操作抽屉 -->
    <n-drawer v-model:show="showActionDrawer" placement="bottom" :height="actionItems.length * 100 + 60" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content title="更多操作" closable :native-scrollbar="false">
        <div class="action-list">
          <div
            v-for="item in actionItems"
            :key="item.key"
            class="action-item"
            @click="handleAction(item.key)"
          >
            <div class="action-icon">
              <n-icon size="22"><component :is="item.icon" /></n-icon>
            </div>
            <span class="action-label">{{ item.label }}</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.secondary-rule-view-mobile { display: flex; flex-direction: column; height: 100%; }
.mobile-toolbar { display: flex; align-items: center; padding: 12px; border-bottom: 1px solid var(--app-border-light); }
.rules-list { flex: 1; overflow-y: auto; }

.rules-list { flex: 1; overflow-y: auto; padding: 12px; box-sizing: border-box; }
.rules-grid { display: flex; flex-direction: column; gap: 12px; }
.rule-card {
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--card-border-radius, 8px);
  padding: 12px;
}
.card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.rule-name { font-weight: bold; font-size: 15px; color: var(--text-primary); }
.criteria-mini { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
.c-tag { font-size: 10px; background: var(--app-surface-inner); padding: 2px 6px; border-radius: 4px; color: var(--text-tertiary); border: 1px solid var(--app-border-light); }
.c-tag.target { color: var(--color-success); border-color: var(--success-medium); }
.card-footer { border-top: 1px solid var(--app-border-light); padding-top: 10px; }

/* 操作列表样式 */
.action-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-xs);
}
.action-item {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-md);
  padding: var(--m-spacing-md);
  border-radius: var(--m-radius-md);
  cursor: pointer;
  transition: background 0.15s ease;
  -webkit-tap-highlight-color: transparent;
}
.action-item:active {
  background: var(--bg-surface-hover);
}
.action-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-surface-inner);
  border-radius: var(--m-radius-md);
  color: var(--text-secondary);
}
.action-label {
  font-size: var(--m-text-md);
  font-weight: 500;
}
</style>
