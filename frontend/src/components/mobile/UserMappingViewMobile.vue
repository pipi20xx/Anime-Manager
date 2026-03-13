<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  NCard, NTabs, NTabPane, NButton, NSpace, NInput, NIcon, NModal, NForm, NFormItem, NEmpty, NSpin, NDrawer, NDrawerContent, NTag
} from 'naive-ui'
import {
  AddOutlined as AddIcon,
  EditOutlined as EditIcon,
  DeleteOutlined as DeleteIcon,
  DownloadOutlined as ImportIcon,
  UploadOutlined as ExportIcon,
  SearchOutlined as SearchIcon,
  MoreVertOutlined as MoreIcon,
  CloudDownloadOutlined as CloudImportIcon,
  CleaningServicesOutlined as ClearIcon
} from '@vicons/material'
import { useUserMapping, type MappingItem } from '../../composables/views/useUserMapping'
import { getButtonStyle } from '../../composables/useButtonStyles'
import { useBackClose } from '../../composables/useBackClose'

const {
  loading,
  importLoading,
  activeType,
  genreMappings,
  companyMappings,
  keywordMappings,
  languageMappings,
  countryMappings,
  refCounts,
  companyTotal,
  keywordTotal,
  companyPage,
  keywordPage,
  companyLoading,
  keywordLoading,
  genreSearch,
  companySearch,
  keywordSearch,
  languageSearch,
  countrySearch,
  importFromRef,
  fetchMappings,
  fetchCompanies,
  fetchKeywords,
  loadMoreCompanies,
  loadMoreKeywords,
  saveGenreMapping,
  deleteGenreMapping,
  saveCompanyMapping,
  deleteCompanyMapping,
  saveKeywordMapping,
  deleteKeywordMapping,
  saveLanguageMapping,
  deleteLanguageMapping,
  saveCountryMapping,
  deleteCountryMapping,
  exportMappings,
  fileInput,
  fileImportLoading,
  triggerImport,
  handleFileImport
} = useUserMapping()

watch(activeType, (newType) => {
  if (newType === 'company' && companyMappings.value.length === 0) {
    fetchCompanies()
  } else if (newType === 'keyword' && keywordMappings.value.length === 0) {
    fetchKeywords()
  }
})

const handleCompanyScroll = (e: Event) => {
  const target = e.target as HTMLElement
  const { scrollTop, scrollHeight, clientHeight } = target
  if (scrollHeight - scrollTop - clientHeight < 50 && !companyLoading.value && companyMappings.value.length < companyTotal.value) {
    loadMoreCompanies()
  }
}

const handleKeywordScroll = (e: Event) => {
  const target = e.target as HTMLElement
  const { scrollTop, scrollHeight, clientHeight } = target
  if (scrollHeight - scrollTop - clientHeight < 50 && !keywordLoading.value && keywordMappings.value.length < keywordTotal.value) {
    loadMoreKeywords()
  }
}

const showModal = ref(false)
const isNewItem = ref(false)

const formModel = ref<MappingItem>({
  id: 0,
  name_zh: '',
  name_en: '',
  name: '',
  country: '',
  code: ''
})

const openAddModal = () => {
  isNewItem.value = true
  formModel.value = { id: 0, name_zh: '', name_en: '', name: '', country: '', code: '' }
  showModal.value = true
}

const openEditModal = (item: MappingItem) => {
  isNewItem.value = false
  formModel.value = { ...item, id: item.id || 0, code: item.code || String(item.id) }
  showModal.value = true
}

const handleSave = async () => {
  let success = false
  if (activeType.value === 'genre') {
    success = await saveGenreMapping(formModel.value)
  } else if (activeType.value === 'company') {
    success = await saveCompanyMapping(formModel.value)
  } else if (activeType.value === 'keyword') {
    success = await saveKeywordMapping(formModel.value)
  } else if (activeType.value === 'language') {
    success = await saveLanguageMapping(formModel.value)
  } else {
    success = await saveCountryMapping(formModel.value)
  }
  if (success) showModal.value = false
}

const handleDelete = async (id: number | string) => {
  if (activeType.value === 'genre') {
    await deleteGenreMapping(Number(id))
  } else if (activeType.value === 'company') {
    await deleteCompanyMapping(Number(id))
  } else if (activeType.value === 'keyword') {
    await deleteKeywordMapping(Number(id))
  } else if (activeType.value === 'language') {
    await deleteLanguageMapping(String(id))
  } else {
    await deleteCountryMapping(String(id))
  }
}

// 操作抽屉状态
const showActionDrawer = ref(false)
const currentItem = ref<MappingItem | null>(null)
useBackClose(showActionDrawer)

// 全局操作抽屉
const showGlobalActionDrawer = ref(false)
useBackClose(showGlobalActionDrawer)

const openItemActions = (item: MappingItem, e: Event) => {
  e.stopPropagation()
  currentItem.value = item
  showActionDrawer.value = true
}

const handleItemAction = async (key: string) => {
  showActionDrawer.value = false
  setTimeout(async () => {
    if (key === 'edit' && currentItem.value) {
      openEditModal(currentItem.value)
    } else if (key === 'delete' && currentItem.value) {
      await handleDelete(currentItem.value.code || currentItem.value.id)
    }
  }, 300)
}

const handleGlobalAction = async (key: string) => {
  showGlobalActionDrawer.value = false
  setTimeout(async () => {
    if (key === 'export') {
      await exportMappings()
    } else if (key === 'import') {
      await triggerImport()
    } else if (key === 'ref') {
      await importFromRef(activeType.value)
    }
  }, 300)
}

const totalCount = computed(() => {
  return refCounts.value.user.genres + refCounts.value.user.companies + refCounts.value.user.keywords + refCounts.value.user.languages + refCounts.value.user.countries
})

const tabCounts = computed(() => ({
  genre: genreMappings.value.length,
  company: companyMappings.value.length,
  keyword: keywordMappings.value.length,
  language: languageMappings.value.length,
  country: countryMappings.value.length
}))
</script>

<template>
  <div class="mapping-view-mobile">
    <!-- 统计卡片 -->
    <div class="stats-card">
      <div class="stats-content">
        <div class="stats-item">
          <span class="stats-value">{{ totalCount }}</span>
          <span class="stats-label">已定义映射</span>
        </div>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <n-button type="primary" dashed size="small" @click="openAddModal">
        <template #icon><n-icon><AddIcon /></n-icon></template>
        添加映射
      </n-button>
      <n-button v-bind="getButtonStyle('icon')" size="small" @click="showGlobalActionDrawer = true">
        <template #icon><n-icon><MoreIcon /></n-icon></template>
      </n-button>
    </div>

    <!-- 映射列表 -->
    <div class="mapping-container">
      <n-tabs type="segment" v-model:value="activeType" size="small" class="mapping-tabs">
        <n-tab-pane name="genre" tab="流派">
          <div class="search-box">
            <n-input
              v-model:value="genreSearch"
              placeholder="搜索 ID 或名称..."
              size="small"
              clearable
            >
              <template #prefix><n-icon><SearchIcon /></n-icon></template>
            </n-input>
          </div>
          <div class="mapping-list">
            <div v-for="item in genreMappings" :key="item.id" class="mapping-card" @click="openEditModal(item)">
              <div class="card-content">
                <div class="card-header">
                  <n-tag size="small" type="info">{{ item.id }}</n-tag>
                  <span class="name-zh">{{ item.name_zh }}</span>
                </div>
                <div class="name-en">{{ item.name_en }}</div>
              </div>
              <div class="card-actions" @click.stop="openItemActions(item, $event)">
                <n-icon size="20"><MoreIcon /></n-icon>
              </div>
            </div>
            <n-empty v-if="genreMappings.length === 0 && !loading" description="暂无数据" />
          </div>
        </n-tab-pane>

        <n-tab-pane name="company" tab="公司">
          <div class="search-box">
            <n-input
              v-model:value="companySearch"
              placeholder="搜索 ID、名称或国家..."
              size="small"
              clearable
            >
              <template #prefix><n-icon><SearchIcon /></n-icon></template>
            </n-input>
          </div>
          <div class="mapping-list scrollable" @scroll="handleCompanyScroll">
            <div v-for="item in companyMappings" :key="item.id" class="mapping-card" @click="openEditModal(item)">
              <div class="card-content">
                <div class="card-header">
                  <n-tag size="small" type="info">{{ item.id }}</n-tag>
                  <span class="name-zh">{{ item.name }}</span>
                  <n-tag v-if="item.country" size="small" type="success">{{ item.country }}</n-tag>
                </div>
              </div>
              <div class="card-actions" @click.stop="openItemActions(item, $event)">
                <n-icon size="20"><MoreIcon /></n-icon>
              </div>
            </div>
            <div v-if="companyLoading && companyMappings.length > 0" class="loading-more">
              <n-spin size="small" />
              <span>加载中...</span>
            </div>
            <div v-if="!companyLoading && companyMappings.length >= companyTotal && companyTotal > 0" class="no-more">
              已加载全部 {{ companyTotal }} 条
            </div>
            <n-empty v-if="companyMappings.length === 0 && !companyLoading" description="暂无数据" />
          </div>
        </n-tab-pane>

        <n-tab-pane name="keyword" tab="关键词">
          <div class="search-box">
            <n-input
              v-model:value="keywordSearch"
              placeholder="搜索 ID 或名称..."
              size="small"
              clearable
            >
              <template #prefix><n-icon><SearchIcon /></n-icon></template>
            </n-input>
          </div>
          <div class="mapping-list scrollable" @scroll="handleKeywordScroll">
            <div v-for="item in keywordMappings" :key="item.id" class="mapping-card" @click="openEditModal(item)">
              <div class="card-content">
                <div class="card-header">
                  <n-tag size="small" type="info">{{ item.id }}</n-tag>
                  <span class="name-zh">{{ item.name_zh }}</span>
                </div>
                <div class="name-en">{{ item.name_en }}</div>
              </div>
              <div class="card-actions" @click.stop="openItemActions(item, $event)">
                <n-icon size="20"><MoreIcon /></n-icon>
              </div>
            </div>
            <div v-if="keywordLoading && keywordMappings.length > 0" class="loading-more">
              <n-spin size="small" />
              <span>加载中...</span>
            </div>
            <div v-if="!keywordLoading && keywordMappings.length >= keywordTotal && keywordTotal > 0" class="no-more">
              已加载全部 {{ keywordTotal }} 条
            </div>
            <n-empty v-if="keywordMappings.length === 0 && !keywordLoading" description="暂无数据" />
          </div>
        </n-tab-pane>

        <n-tab-pane name="language" tab="语言">
          <div class="search-box">
            <n-input
              v-model:value="languageSearch"
              placeholder="搜索代码或名称..."
              size="small"
              clearable
            >
              <template #prefix><n-icon><SearchIcon /></n-icon></template>
            </n-input>
          </div>
          <div class="mapping-list">
            <div v-for="item in languageMappings" :key="item.code" class="mapping-card" @click="openEditModal(item)">
              <div class="card-content">
                <div class="card-header">
                  <n-tag size="small" type="info">{{ item.code }}</n-tag>
                  <span class="name-zh">{{ item.name_zh }}</span>
                </div>
                <div class="name-en">{{ item.name_en }}</div>
              </div>
              <div class="card-actions" @click.stop="openItemActions(item, $event)">
                <n-icon size="20"><MoreIcon /></n-icon>
              </div>
            </div>
            <n-empty v-if="languageMappings.length === 0 && !loading" description="暂无数据" />
          </div>
        </n-tab-pane>

        <n-tab-pane name="country" tab="国家">
          <div class="search-box">
            <n-input
              v-model:value="countrySearch"
              placeholder="搜索代码或名称..."
              size="small"
              clearable
            >
              <template #prefix><n-icon><SearchIcon /></n-icon></template>
            </n-input>
          </div>
          <div class="mapping-list">
            <div v-for="item in countryMappings" :key="item.code" class="mapping-card" @click="openEditModal(item)">
              <div class="card-content">
                <div class="card-header">
                  <n-tag size="small" type="info">{{ item.code }}</n-tag>
                  <span class="name-zh">{{ item.name_zh }}</span>
                </div>
                <div class="name-en">{{ item.name_en }}</div>
              </div>
              <div class="card-actions" @click.stop="openItemActions(item, $event)">
                <n-icon size="20"><MoreIcon /></n-icon>
              </div>
            </div>
            <n-empty v-if="countryMappings.length === 0 && !loading" description="暂无数据" />
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>

    <!-- 编辑弹窗 -->
    <n-modal :show="showModal" @update:show="val => showModal = val" preset="card" style="width: 90%; max-width: 400px" :title="isNewItem ? '添加映射' : '编辑映射'">
      <n-form label-placement="top">
        <template v-if="activeType === 'genre'">
          <n-form-item label="ID"><n-input v-model:value="formModel.id" :disabled="!isNewItem" placeholder="TMDB ID" type="number" /></n-form-item>
          <n-form-item label="中文名"><n-input v-model:value="formModel.name_zh" /></n-form-item>
          <n-form-item label="英文名"><n-input v-model:value="formModel.name_en" /></n-form-item>
        </template>
        <template v-else-if="activeType === 'company'">
          <n-form-item label="ID"><n-input v-model:value="formModel.id" :disabled="!isNewItem" placeholder="TMDB ID" type="number" /></n-form-item>
          <n-form-item label="名称"><n-input v-model:value="formModel.name" /></n-form-item>
          <n-form-item label="国家"><n-input v-model:value="formModel.country" /></n-form-item>
        </template>
        <template v-else-if="activeType === 'keyword'">
          <n-form-item label="ID"><n-input v-model:value="formModel.id" :disabled="!isNewItem" placeholder="TMDB ID" type="number" /></n-form-item>
          <n-form-item label="中文名"><n-input v-model:value="formModel.name_zh" /></n-form-item>
          <n-form-item label="英文名"><n-input v-model:value="formModel.name_en" /></n-form-item>
        </template>
        <template v-else-if="activeType === 'language'">
          <n-form-item label="代码"><n-input v-model:value="formModel.code" :disabled="!isNewItem" placeholder="如: ja, zh" /></n-form-item>
          <n-form-item label="中文名"><n-input v-model:value="formModel.name_zh" /></n-form-item>
          <n-form-item label="英文名"><n-input v-model:value="formModel.name_en" /></n-form-item>
        </template>
        <template v-else>
          <n-form-item label="代码"><n-input v-model:value="formModel.code" :disabled="!isNewItem" placeholder="如: JP, CN" /></n-form-item>
          <n-form-item label="中文名"><n-input v-model:value="formModel.name_zh" /></n-form-item>
          <n-form-item label="英文名"><n-input v-model:value="formModel.name_en" /></n-form-item>
        </template>
      </n-form>

      <template #footer>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('ghost')" @click="showModal = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="handleSave">保存</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 项目操作抽屉 -->
    <n-drawer v-model:show="showActionDrawer" placement="bottom" :height="200" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content :title="currentItem?.name_zh || currentItem?.name || '映射操作'" closable>
        <div class="action-list">
          <div class="action-item" @click="handleItemAction('edit')">
            <div class="action-icon">
              <n-icon size="22"><EditIcon /></n-icon>
            </div>
            <span class="action-label">编辑</span>
          </div>
          <div class="action-item danger" @click="handleItemAction('delete')">
            <div class="action-icon">
              <n-icon size="22"><DeleteIcon /></n-icon>
            </div>
            <span class="action-label">删除</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>

    <!-- 全局操作抽屉 -->
    <n-drawer v-model:show="showGlobalActionDrawer" placement="bottom" :height="280" style="border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;">
      <n-drawer-content title="更多操作" closable>
        <div class="action-list">
          <div class="action-item" @click="handleGlobalAction('export')">
            <div class="action-icon">
              <n-icon size="22"><ExportIcon /></n-icon>
            </div>
            <span class="action-label">导出映射</span>
          </div>
          <div class="action-item" @click="handleGlobalAction('import')">
            <div class="action-icon">
              <n-icon size="22"><ImportIcon /></n-icon>
            </div>
            <span class="action-label">导入映射</span>
          </div>
          <div v-if="['genre', 'company', 'keyword'].includes(activeType)" class="action-item" @click="handleGlobalAction('ref')">
            <div class="action-icon">
              <n-icon size="22"><CloudImportIcon /></n-icon>
            </div>
            <span class="action-label">从参考库导入</span>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>

    <input
      type="file"
      ref="fileInput"
      accept=".json"
      style="display: none"
      @change="handleFileImport"
    />
  </div>
</template>

<style scoped>
.mapping-view-mobile {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--m-spacing-md);
  gap: var(--m-spacing-md);
}

/* 统计卡片 */
.stats-card {
  background: var(--app-surface-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-spacing-lg);
  border: 1px solid var(--app-border-light);
}
.stats-content {
  display: flex;
  justify-content: center;
}
.stats-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-spacing-xs);
}
.stats-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-primary);
  line-height: 1;
}
.stats-label {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
}

/* 工具栏 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 映射容器 */
.mapping-container {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.mapping-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.mapping-tabs :deep(.n-tabs-nav) {
  margin-bottom: var(--m-spacing-md);
}
.mapping-tabs :deep(.n-tab-pane) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 搜索框 */
.search-box {
  margin-bottom: var(--m-spacing-md);
}

/* 映射列表 */
.mapping-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-sm);
}
.mapping-list.scrollable {
  max-height: calc(100vh - 280px);
}

/* 映射卡片 */
.mapping-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-spacing-md);
  background: var(--app-surface-card);
  border: 1px solid var(--app-border-light);
  border-radius: var(--m-radius-md);
  cursor: pointer;
  transition: all 0.15s ease;
  -webkit-tap-highlight-color: transparent;
}
.mapping-card:active {
  background: var(--bg-surface-hover);
  transform: scale(0.995);
}
.card-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--m-spacing-xs);
}
.card-header {
  display: flex;
  align-items: center;
  gap: var(--m-spacing-sm);
  flex-wrap: wrap;
}
.name-zh {
  font-size: var(--m-text-md);
  font-weight: 600;
  color: var(--text-primary);
}
.name-en {
  font-size: var(--m-text-sm);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-actions {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  border-radius: var(--m-radius-md);
  transition: all 0.15s ease;
}
.card-actions:active {
  background: var(--app-surface-inner);
  color: var(--text-primary);
}

/* 加载更多 */
.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  color: var(--text-muted);
}
.no-more {
  text-align: center;
  padding: 12px;
  color: var(--text-tertiary);
  font-size: 12px;
}

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
.action-item.danger {
  color: var(--color-error);
}
.action-item.danger .action-icon {
  color: var(--color-error);
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
.action-item.danger .action-icon {
  background: var(--color-error-bg);
}
.action-label {
  font-size: var(--m-text-md);
  font-weight: 500;
}
</style>
