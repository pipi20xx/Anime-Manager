<script setup lang="ts">
import { 
  NSpace, NButton, NIcon, NPopconfirm, NEmpty, 
  NSwitch, NGrid, NGi, NText
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  DeleteOutlined as DeleteIcon,
  DragIndicatorOutlined as DragIcon,
  CloudDownloadOutlined as ExportIcon,
  CloudUploadOutlined as ImportIcon
} from '@vicons/material'
import ClassifierEditModal from '../../components/ClassifierEditModal.vue'
import { useSecondaryRule } from '../../composables/views/useSecondaryRule'
import { getButtonStyle } from '../../composables/useButtonStyles'

const {
  rules,
  showRuleModal,
  editingRule,
  isNewRule,
  editingIndex,
  importLoading,
  fileInput,
  draggedIndex,
  handleSaveRule,
  saveRulesToBackend,
  deleteRule,
  handleExport,
  triggerImport,
  handleFileChange,
  onDragStart,
  onDragOver,
  onDrop,
  translateIds
} = useSecondaryRule()
</script>

<template>
  <div class="secondary-rule-view">
    <input type="file" ref="fileInput" style="display:none" accept=".json" @change="handleFileChange" />
    <n-space vertical size="large">
      <div class="toolbar-row">
        <n-text depth="3">
          根据元数据标签（流派、国家、标题关键词）自动决定文件整理后的二级目录。
        </n-text>
        <n-space>
          <n-button v-bind="getButtonStyle('secondary')" size="small" @click="triggerImport" :loading="importLoading">
            导入
          </n-button>
          <n-button v-bind="getButtonStyle('secondary')" size="small" @click="handleExport">
            导出
          </n-button>
          <n-button v-bind="getButtonStyle('primary')" size="small" @click="editingRule = null; isNewRule = true; showRuleModal = true">
            添加新分类规则
          </n-button>
        </n-space>
      </div>

      <div class="classifier-container">
        <n-empty v-if="rules.length === 0" description="尚未配置二级分类规则" style="padding: 100px 0" />
        <n-grid :cols="3" :x-gap="16" :y-gap="16" v-else>
          <n-gi v-for="(rule, index) in rules" :key="rule.id || index">
            <div 
              class="rect-rule-card" 
              :class="{ 'is-dragging': draggedIndex === index, 'is-disabled': !rule.enabled }"
              draggable="true"
              @dragstart="onDragStart(index)"
              @dragover="onDragOver"
              @drop="onDrop(index)"
              @click="editingRule = rule; isNewRule = false; editingIndex = index; showRuleModal = true"
            >
              <div class="card-header">
                <div class="header-left">
                  <n-icon class="drag-handle" size="18"><DragIcon /></n-icon>
                  <span class="index-badge">#{{ index + 1 }}</span>
                  <span class="rule-name">{{ rule.name }}</span>
                </div>
                <n-switch v-model:value="rule.enabled" size="small" @click.stop="saveRulesToBackend" />
              </div>

              <div class="card-body">
                <div class="criteria-list">
                  <div class="c-item"><span>标题匹配:</span><span class="c-val">{{ rule.criteria.title || '任意' }}</span></div>
                  <div class="c-item"><span>流派:</span><span class="c-val">{{ translateIds(rule.criteria.genre_ids, 'genres') || '任意' }}</span></div>
                  <div class="c-item"><span>制作公司:</span><span class="c-val">{{ translateIds(rule.criteria.company_ids, 'companies') || '任意' }}</span></div>
                  <div class="c-item"><span>关键词:</span><span class="c-val">{{ translateIds(rule.criteria.keyword_ids, 'keywords') || '任意' }}</span></div>
                  <div class="c-item"><span>原始国家:</span><span class="c-val">{{ translateIds(rule.criteria.origin_country, 'countries') || '任意' }}</span></div>
                  <div class="c-item"><span>原始语言:</span><span class="c-val">{{ translateIds(rule.criteria.original_language, 'languages') || '任意' }}</span></div>
                  <div class="c-item"><span>年份范围:</span><span class="c-val">{{ rule.criteria.year || '任意' }}</span></div>
                  <div class="c-item"><span>适用对象:</span><span class="c-val">{{ rule.target === 'movie' ? '仅电影' : (rule.target === 'tv' ? '仅剧集' : '全部') }}</span></div>
                </div>
              </div>

              <div class="card-footer">
                <n-popconfirm @positive-click.stop="deleteRule(index)" positive-text="确定" negative-text="取消">
                  <template #trigger>
                    <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click.stop>
                      <template #icon><n-icon><DeleteIcon /></n-icon></template>
                    </n-button>
                  </template>
                  确定删除该规则吗？
                </n-popconfirm>
                <n-text depth="3" style="font-size: 10px">按住左上角可排序</n-text>
              </div>
            </div>
          </n-gi>
        </n-grid>
      </div>
    </n-space>

    <ClassifierEditModal v-model:show="showRuleModal" :rule-data="editingRule" :is-new="isNewRule" @save="handleSaveRule" />
  </div>
</template>

<style scoped>
.toolbar-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }

/* 卡片核心样式 - 增强对比度 */
.rect-rule-card { 
  background-color: var(--bg-surface); 
  border: 1px solid rgba(255, 255, 255, 0.2); 
  padding: 16px; 
  border-radius: 8px; 
  cursor: pointer; 
  transition: all 0.2s ease; 
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  height: auto; 
}
.rect-rule-card:hover { 
  border-color: var(--n-primary-color); 
  background-color: var(--bg-surface-hover); 
  transform: translateY(-2px); 
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); 
}

.is-dragging { opacity: 0.4; border: 2px dashed var(--n-primary-color); }
.is-disabled { opacity: 0.5; filter: grayscale(0.8); }

.card-header { display: flex; justify-content: space-between; align-items: center; font-weight: bold; margin-bottom: 10px; }
.header-left { display: flex; align-items: center; gap: 8px; }
.drag-handle { color: var(--n-text-color-3); cursor: grab; }
.index-badge { font-family: monospace; font-size: 10px; background: var(--n-action-color); padding: 1px 4px; border-radius: 4px; color: var(--n-primary-color); }
.rule-name { font-size: 15px; color: var(--n-text-color-1); }

.criteria-list { font-size: 11px; color: var(--n-text-color-3); display: grid; gap: 4px; margin-bottom: 12px; }
.c-val { color: var(--n-info-color); margin-left: 4px; font-weight: 500; }

.card-footer { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  border-top: 1px solid var(--n-divider-color); 
  padding-top: 12px; 
}
</style>
