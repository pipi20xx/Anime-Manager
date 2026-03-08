<script setup lang="ts">
import { ref, computed, h, watch, nextTick } from 'vue'
import { 
  NCard, NTabs, NTabPane, NDataTable, NButton, NSpace, NInput, NIcon, NModal, NForm, NFormItem, NTag, NEmpty, NStatistic, NGrid, NGi, NPopconfirm, NSpin
} from 'naive-ui'
import { 
  AddOutlined as AddIcon, 
  EditOutlined as EditIcon, 
  DeleteOutlined as DeleteIcon,
  DownloadOutlined as ImportIcon,
  UploadOutlined as ExportIcon,
  LabelOutlined as LabelIcon,
  BusinessOutlined as CompanyIcon,
  TagOutlined as KeywordIcon,
  LanguageOutlined as LanguageIcon,
  PublicOutlined as CountryIcon,
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
  if (scrollHeight - scrollTop - clientHeight < 100 && !companyLoading.value && companyMappings.value.length < companyTotal.value) {
    loadMoreCompanies()
  }
}

const handleKeywordScroll = (e: Event) => {
  const target = e.target as HTMLElement
  const { scrollTop, scrollHeight, clientHeight } = target
  if (scrollHeight - scrollTop - clientHeight < 100 && !keywordLoading.value && keywordMappings.value.length < keywordTotal.value) {
    loadMoreKeywords()
  }
}

const showModal = ref(false)
const editingItem = ref<MappingItem | null>(null)
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
  editingItem.value = item
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
  if (success) {
    showModal.value = false
  }
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
  { title: 'ID', key: 'id', width: 100 },
  { title: '中文名称', key: 'name_zh' },
  { title: '英文名称', key: 'name_en' },
  { title: '操作', key: 'actions', width: 120, render(row: MappingItem) {
    return h(NSpace, {}, {
      default: () => [
        h(NButton, { size: 'small', quaternary: true, onClick: () => openEditModal(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
        h(NButton, { size: 'small', quaternary: true, type: 'error', onClick: () => handleDelete(row.id) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
      ]
    })
  }}
]

const companyColumns = [
  { title: 'ID', key: 'id', width: 100 },
  { title: '名称', key: 'name' },
  { title: '国家', key: 'country', width: 100 },
  { title: '操作', key: 'actions', width: 120, render(row: MappingItem) {
    return h(NSpace, {}, {
      default: () => [
        h(NButton, { size: 'small', quaternary: true, onClick: () => openEditModal(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
        h(NButton, { size: 'small', quaternary: true, type: 'error', onClick: () => handleDelete(row.id) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
      ]
    })
  }}
]

const keywordColumns = [
  { title: 'ID', key: 'id', width: 100 },
  { title: '中文名称', key: 'name_zh' },
  { title: '英文名称', key: 'name_en' },
  { title: '操作', key: 'actions', width: 120, render(row: MappingItem) {
    return h(NSpace, {}, {
      default: () => [
        h(NButton, { size: 'small', quaternary: true, onClick: () => openEditModal(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
        h(NButton, { size: 'small', quaternary: true, type: 'error', onClick: () => handleDelete(row.id) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
      ]
    })
  }}
]

const languageColumns = [
  { title: '代码', key: 'code', width: 100 },
  { title: '中文名称', key: 'name_zh' },
  { title: '英文名称', key: 'name_en' },
  { title: '操作', key: 'actions', width: 120, render(row: MappingItem) {
    return h(NSpace, {}, {
      default: () => [
        h(NButton, { size: 'small', quaternary: true, onClick: () => openEditModal(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
        h(NButton, { size: 'small', quaternary: true, type: 'error', onClick: () => handleDelete(row.code || row.id) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
      ]
    })
  }}
]

const countryColumns = [
  { title: '代码', key: 'code', width: 100 },
  { title: '中文名称', key: 'name_zh' },
  { title: '英文名称', key: 'name_en' },
  { title: '操作', key: 'actions', width: 120, render(row: MappingItem) {
    return h(NSpace, {}, {
      default: () => [
        h(NButton, { size: 'small', quaternary: true, onClick: () => openEditModal(row) }, { icon: () => h(NIcon, null, { default: () => h(EditIcon) }) }),
        h(NButton, { size: 'small', quaternary: true, type: 'error', onClick: () => handleDelete(row.code || row.id) }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) })
      ]
    })
  }}
]
</script>

<template>
  <div class="mapping-view">
    <n-grid :cols="5" :x-gap="16" style="margin-bottom: 16px;">
      <n-gi>
        <n-card size="small" bordered>
          <n-statistic label="流派 (TMDB / 已导入)" :value="`${refCounts.ref.genres} / ${refCounts.user.genres}`">
            <template #prefix><n-icon><LabelIcon /></n-icon></template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" bordered>
          <n-statistic label="制作公司 (TMDB / 已导入)" :value="`${refCounts.ref.companies} / ${refCounts.user.companies}`">
            <template #prefix><n-icon><CompanyIcon /></n-icon></template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" bordered>
          <n-statistic label="关键词 (TMDB / 已导入)" :value="`${refCounts.ref.keywords} / ${refCounts.user.keywords}`">
            <template #prefix><n-icon><KeywordIcon /></n-icon></template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" bordered>
          <n-statistic label="语言 (已定义)" :value="refCounts.user.languages">
            <template #prefix><n-icon><LanguageIcon /></n-icon></template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" bordered>
          <n-statistic label="国家 (已定义)" :value="refCounts.user.countries">
            <template #prefix><n-icon><CountryIcon /></n-icon></template>
          </n-statistic>
        </n-card>
      </n-gi>
    </n-grid>

    <n-card bordered size="small">
      <template #header>
        <n-space justify="space-between" align="center">
          <span class="card-title">ID 映射管理</span>
          <n-space>
            <n-button size="small" @click="exportMappings">
              <template #icon><n-icon><ExportIcon /></n-icon></template>
              导出备份
            </n-button>
            <n-button size="small" @click="triggerImport" :loading="fileImportLoading">
              <template #icon><n-icon><ImportIcon /></n-icon></template>
              导入备份
            </n-button>
            <n-button size="small" @click="handleImport" :loading="importLoading" v-if="['genre', 'company', 'keyword'].includes(activeType)">
              <template #icon><n-icon><ImportIcon /></n-icon></template>
              导入当前分类
            </n-button>
            <n-button type="primary" size="small" @click="openAddModal">
              <template #icon><n-icon><AddIcon /></n-icon></template>
              添加映射
            </n-button>
          </n-space>
        </n-space>
      </template>
      <template #header-extra>
        <n-tag type="info" size="small">自定义中文名称，优先于 TMDB 官方数据</n-tag>
      </template>
      
      <n-tabs type="line" v-model:value="activeType">
        <n-tab-pane name="genre" tab="流派">
          <template #tab>流派</template>
          <n-input 
            v-model:value="genreSearch" 
            placeholder="搜索 ID 或名称..." 
            size="small" 
            clearable
            style="margin-bottom: 12px"
          >
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <n-data-table 
            :columns="genreColumns" 
            :data="genreMappings" 
            :loading="loading"
            :max-height="400"
            size="small"
          />
          <n-empty v-if="!loading && genreMappings.length === 0" description="暂无流派映射，点击「导入当前分类」从 TMDB 导入" style="padding: 40px 0" />
        </n-tab-pane>
        
        <n-tab-pane name="company" tab="制作公司">
          <template #tab>制作公司</template>
          <n-input 
            v-model:value="companySearch" 
            placeholder="搜索 ID、名称或国家..." 
            size="small" 
            clearable
            style="margin-bottom: 12px"
          >
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <div class="scroll-table-wrap" @scroll="handleCompanyScroll">
            <n-data-table 
              :columns="companyColumns" 
              :data="companyMappings" 
              :loading="companyLoading && companyMappings.length === 0"
              size="small"
            />
            <div class="loading-more" v-if="companyLoading && companyMappings.length > 0">
              <n-spin size="small" />
              <span>加载中...</span>
            </div>
            <div class="no-more" v-if="!companyLoading && companyMappings.length >= companyTotal && companyTotal > 0">
              已加载全部 {{ companyTotal }} 条
            </div>
          </div>
          <n-empty v-if="!companyLoading && companyMappings.length === 0" description="暂无制作公司映射，点击「导入当前分类」从 TMDB 导入" style="padding: 40px 0" />
        </n-tab-pane>
        
        <n-tab-pane name="keyword" tab="关键词">
          <template #tab>关键词</template>
          <n-input 
            v-model:value="keywordSearch" 
            placeholder="搜索 ID 或名称..." 
            size="small" 
            clearable
            style="margin-bottom: 12px"
          >
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <div class="scroll-table-wrap" @scroll="handleKeywordScroll">
            <n-data-table 
              :columns="keywordColumns" 
              :data="keywordMappings" 
              :loading="keywordLoading && keywordMappings.length === 0"
              size="small"
            />
            <div class="loading-more" v-if="keywordLoading && keywordMappings.length > 0">
              <n-spin size="small" />
              <span>加载中...</span>
            </div>
            <div class="no-more" v-if="!keywordLoading && keywordMappings.length >= keywordTotal && keywordTotal > 0">
              已加载全部 {{ keywordTotal }} 条
            </div>
          </div>
          <n-empty v-if="!keywordLoading && keywordMappings.length === 0" description="暂无关键词映射，点击「导入当前分类」从 TMDB 导入" style="padding: 40px 0" />
        </n-tab-pane>

        <n-tab-pane name="language" tab="原始语言">
          <template #tab>原始语言</template>
          <n-input 
            v-model:value="languageSearch" 
            placeholder="搜索代码或名称..." 
            size="small" 
            clearable
            style="margin-bottom: 12px"
          >
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <n-data-table 
            :columns="languageColumns" 
            :data="languageMappings" 
            :loading="loading"
            :max-height="400"
            size="small"
          />
          <n-empty v-if="!loading && languageMappings.length === 0" description="暂无语言映射，点击「添加映射」手动添加" style="padding: 40px 0" />
        </n-tab-pane>

        <n-tab-pane name="country" tab="原始国家">
          <template #tab>原始国家</template>
          <n-input 
            v-model:value="countrySearch" 
            placeholder="搜索代码或名称..." 
            size="small" 
            clearable
            style="margin-bottom: 12px"
          >
            <template #prefix><n-icon><SearchIcon /></n-icon></template>
          </n-input>
          <n-data-table 
            :columns="countryColumns" 
            :data="countryMappings" 
            :loading="loading"
            :max-height="400"
            size="small"
          />
          <n-empty v-if="!loading && countryMappings.length === 0" description="暂无国家映射，点击「添加映射」手动添加" style="padding: 40px 0" />
        </n-tab-pane>
      </n-tabs>
    </n-card>

    <n-modal :show="showModal" @update:show="val => showModal = val">
      <n-card
        style="width: 500px"
        :title="isNewItem ? '添加映射' : '编辑映射'"
        bordered
        size="huge"
      >
        <n-form label-placement="left" label-width="80">
          <template v-if="activeType === 'genre'">
            <n-form-item label="ID" required>
              <n-input 
                v-model:value="formModel.id" 
                :disabled="!isNewItem"
                placeholder="输入 TMDB ID"
                type="number"
              />
            </n-form-item>
            <n-form-item label="中文名">
              <n-input v-model:value="formModel.name_zh" placeholder="流派中文名称" />
            </n-form-item>
            <n-form-item label="英文名">
              <n-input v-model:value="formModel.name_en" placeholder="流派英文名称" />
            </n-form-item>
          </template>
          
          <template v-else-if="activeType === 'company'">
            <n-form-item label="ID" required>
              <n-input 
                v-model:value="formModel.id" 
                :disabled="!isNewItem"
                placeholder="输入 TMDB ID"
                type="number"
              />
            </n-form-item>
            <n-form-item label="名称">
              <n-input v-model:value="formModel.name" placeholder="公司名称" />
            </n-form-item>
            <n-form-item label="国家">
              <n-input v-model:value="formModel.country" placeholder="如: JP, CN, US" />
            </n-form-item>
          </template>
          
          <template v-else-if="activeType === 'keyword'">
            <n-form-item label="ID" required>
              <n-input 
                v-model:value="formModel.id" 
                :disabled="!isNewItem"
                placeholder="输入 TMDB ID"
                type="number"
              />
            </n-form-item>
            <n-form-item label="中文名">
              <n-input v-model:value="formModel.name_zh" placeholder="关键词中文名称" />
            </n-form-item>
            <n-form-item label="英文名">
              <n-input v-model:value="formModel.name_en" placeholder="关键词英文名称" />
            </n-form-item>
          </template>

          <template v-else-if="activeType === 'language'">
            <n-form-item label="代码" required>
              <n-input 
                v-model:value="formModel.code" 
                :disabled="!isNewItem"
                placeholder="如: ja, zh, en"
              />
            </n-form-item>
            <n-form-item label="中文名">
              <n-input v-model:value="formModel.name_zh" placeholder="语言中文名称" />
            </n-form-item>
            <n-form-item label="英文名">
              <n-input v-model:value="formModel.name_en" placeholder="语言英文名称" />
            </n-form-item>
          </template>

          <template v-else>
            <n-form-item label="代码" required>
              <n-input 
                v-model:value="formModel.code" 
                :disabled="!isNewItem"
                placeholder="如: JP, CN, US"
              />
            </n-form-item>
            <n-form-item label="中文名">
              <n-input v-model:value="formModel.name_zh" placeholder="国家中文名称" />
            </n-form-item>
            <n-form-item label="英文名">
              <n-input v-model:value="formModel.name_en" placeholder="国家英文名称" />
            </n-form-item>
          </template>
        </n-form>

        <template #action>
          <n-space justify="end">
            <n-button @click="showModal = false">取消</n-button>
            <n-button type="primary" @click="handleSave">保存</n-button>
          </n-space>
        </template>
      </n-card>
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
.mapping-view {
  width: 100%;
}
.card-title {
  font-weight: 600;
  font-size: 15px;
}
.scroll-table-wrap {
  max-height: 400px;
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
