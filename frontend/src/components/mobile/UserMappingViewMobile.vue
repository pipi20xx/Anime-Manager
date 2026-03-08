<script setup lang="ts">
import { ref, h, watch } from 'vue'
import { 
  NCard, NTabs, NTabPane, NDataTable, NButton, NSpace, NInput, NIcon, NModal, NForm, NFormItem, NTag, NEmpty, NStatistic, NPopconfirm, NSpin
} from 'naive-ui'
import { 
  AddOutlined as AddIcon, 
  EditOutlined as EditIcon, 
  DeleteOutlined as DeleteIcon,
  DownloadOutlined as ImportIcon,
  UploadOutlined as ExportIcon,
  SearchOutlined as SearchIcon
} from '@vicons/material'
import { useUserMapping, type MappingItem } from '../../composables/views/useUserMapping'

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

const handleImport = async () => {
  await importFromRef(activeType.value)
}

const genreColumns = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '中文', key: 'name_zh' },
  { title: '英文', key: 'name_en' },
  { title: '操作', key: 'actions', width: 100, render(row: MappingItem) {
    return h(NSpace, { size: 2 }, {
      default: () => [
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEditModal(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
        h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => handleDelete(row.id) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
      ]
    })
  }}
]

const companyColumns = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '名称', key: 'name' },
  { title: '国家', key: 'country', width: 60 },
  { title: '操作', key: 'actions', width: 100, render(row: MappingItem) {
    return h(NSpace, { size: 2 }, {
      default: () => [
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEditModal(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
        h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => handleDelete(row.id) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
      ]
    })
  }}
]

const keywordColumns = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '中文', key: 'name_zh' },
  { title: '英文', key: 'name_en' },
  { title: '操作', key: 'actions', width: 100, render(row: MappingItem) {
    return h(NSpace, { size: 2 }, {
      default: () => [
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEditModal(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
        h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => handleDelete(row.id) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
      ]
    })
  }}
]

const languageColumns = [
  { title: '代码', key: 'code', width: 80 },
  { title: '中文', key: 'name_zh' },
  { title: '英文', key: 'name_en' },
  { title: '操作', key: 'actions', width: 100, render(row: MappingItem) {
    return h(NSpace, { size: 2 }, {
      default: () => [
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEditModal(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
        h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => handleDelete(row.code || row.id) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
      ]
    })
  }}
]

const countryColumns = [
  { title: '代码', key: 'code', width: 80 },
  { title: '中文', key: 'name_zh' },
  { title: '英文', key: 'name_en' },
  { title: '操作', key: 'actions', width: 100, render(row: MappingItem) {
    return h(NSpace, { size: 2 }, {
      default: () => [
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEditModal(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
        h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => handleDelete(row.code || row.id) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
      ]
    })
  }}
]
</script>

<template>
  <div class="mapping-view-mobile">
    <n-space vertical size="small" style="margin-bottom: 12px;">
      <n-card size="small" bordered>
        <n-space justify="space-between" align="center">
          <n-statistic :value="`${refCounts.user.genres + refCounts.user.companies + refCounts.user.keywords + refCounts.user.languages + refCounts.user.countries}`">
            <template #label>已定义映射</template>
          </n-statistic>
        </n-space>
      </n-card>
    </n-space>

    <n-card bordered size="small">
      <template #header>
        <n-space justify="space-between" align="center" style="width: 100%">
          <span>ID 映射管理</span>
          <n-space>
            <n-button size="tiny" @click="exportMappings">
              <template #icon><n-icon><ExportIcon /></n-icon></template>
            </n-button>
            <n-button size="tiny" @click="triggerImport" :loading="fileImportLoading">
              <template #icon><n-icon><ImportIcon /></n-icon></template>
            </n-button>
            <n-button size="tiny" @click="handleImport" :loading="importLoading" v-if="['genre', 'company', 'keyword'].includes(activeType)">
              <template #icon><n-icon><ImportIcon /></n-icon></template>
              导入
            </n-button>
            <n-button type="primary" size="tiny" @click="openAddModal">
              <template #icon><n-icon><AddIcon /></n-icon></template>
              添加
            </n-button>
          </n-space>
        </n-space>
      </template>
      
      <n-tabs type="line" v-model:value="activeType" size="small">
        <n-tab-pane name="genre" tab="流派">
          <n-input 
            v-model:value="genreSearch" 
            placeholder="搜索 ID 或名称..." 
            size="small" 
            clearable
            style="margin-bottom: 8px"
          >
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <n-data-table :columns="genreColumns" :data="genreMappings" :loading="loading" size="small" />
        </n-tab-pane>
        
        <n-tab-pane name="company" tab="公司">
          <n-input 
            v-model:value="companySearch" 
            placeholder="搜索 ID、名称或国家..." 
            size="small" 
            clearable
            style="margin-bottom: 8px"
          >
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <div class="scroll-table-wrap" @scroll="handleCompanyScroll">
            <n-data-table :columns="companyColumns" :data="companyMappings" :loading="companyLoading && companyMappings.length === 0" size="small" />
            <div class="loading-more" v-if="companyLoading && companyMappings.length > 0">
              <n-spin size="small" />
              <span>加载中...</span>
            </div>
            <div class="no-more" v-if="!companyLoading && companyMappings.length >= companyTotal && companyTotal > 0">
              已加载全部 {{ companyTotal }} 条
            </div>
          </div>
        </n-tab-pane>
        
        <n-tab-pane name="keyword" tab="关键词">
          <n-input 
            v-model:value="keywordSearch" 
            placeholder="搜索 ID 或名称..." 
            size="small" 
            clearable
            style="margin-bottom: 8px"
          >
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <div class="scroll-table-wrap" @scroll="handleKeywordScroll">
            <n-data-table :columns="keywordColumns" :data="keywordMappings" :loading="keywordLoading && keywordMappings.length === 0" size="small" />
            <div class="loading-more" v-if="keywordLoading && keywordMappings.length > 0">
              <n-spin size="small" />
              <span>加载中...</span>
            </div>
            <div class="no-more" v-if="!keywordLoading && keywordMappings.length >= keywordTotal && keywordTotal > 0">
              已加载全部 {{ keywordTotal }} 条
            </div>
          </div>
        </n-tab-pane>

        <n-tab-pane name="language" tab="语言">
          <n-input 
            v-model:value="languageSearch" 
            placeholder="搜索代码或名称..." 
            size="small" 
            clearable
            style="margin-bottom: 8px"
          >
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <n-data-table :columns="languageColumns" :data="languageMappings" :loading="loading" size="small" />
        </n-tab-pane>

        <n-tab-pane name="country" tab="国家">
          <n-input 
            v-model:value="countrySearch" 
            placeholder="搜索代码或名称..." 
            size="small" 
            clearable
            style="margin-bottom: 8px"
          >
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <n-data-table :columns="countryColumns" :data="countryMappings" :loading="loading" size="small" />
        </n-tab-pane>
      </n-tabs>
    </n-card>

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
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" @click="handleSave">保存</n-button>
        </n-space>
      </template>
    </n-modal>

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
  padding: 8px;
}
.scroll-table-wrap {
  max-height: 300px;
  overflow-y: auto;
}
.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  color: #666;
}
.no-more {
  text-align: center;
  padding: 12px;
  color: #999;
  font-size: 12px;
}
</style>
