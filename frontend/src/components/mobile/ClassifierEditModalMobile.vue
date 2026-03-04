<script setup lang="ts">
import { 
  NModal, NCard, NForm, NFormItem, NInput, NSelect, NButton, NSpace, NDivider, NIcon
} from 'naive-ui'
import { SaveOutlined as SaveIcon } from '@vicons/material'
import { useClassifierEdit } from '../../composables/modals/useClassifierEdit'

const props = defineProps<{
  show: boolean
  ruleData: any
  isNew: boolean
}>()

const emit = defineEmits(['update:show', 'save'])

const { 
  formModel, 
  handleSave,
  genreLoading,
  companyLoading,
  keywordLoading,
  languageLoading,
  countryLoading,
  genreOptions,
  companyOptions,
  keywordOptions,
  languageOptions,
  countryOptions,
  handleGenreSearch,
  handleCompanySearch,
  handleKeywordSearch,
  handleLanguageSearch,
  handleCountrySearch,
  handleGenreSelect,
  handleCompanySelect,
  handleKeywordSelect,
  handleLanguageSelect,
  handleCountrySelect,
  handleGenreDropdownOpen,
  handleCompanyDropdownOpen,
  handleKeywordDropdownOpen,
  handleLanguageDropdownOpen,
  handleCountryDropdownOpen,
  getSelectedGenreIds,
  getSelectedCompanyIds,
  getSelectedKeywordIds,
  getSelectedLanguageCodes,
  getSelectedCountryCodes
} = useClassifierEdit(props, emit)
</script>

<template>
  <n-modal :show="props.show" @update:show="val => emit('update:show', val)" preset="card" style="width: 100%; height: 100vh; margin: 0;" content-style="padding: 16px; overflow-y: auto;" :title="props.isNew ? '添加分类规则' : '编辑分类规则'">
    <n-form label-placement="top">
      <n-divider dashed title-placement="left">基础设置</n-divider>
      <n-form-item label="分类名称" path="name">
        <n-input v-model:value="formModel.name" placeholder="对应的二级文件夹名称" />
      </n-form-item>
      <n-form-item label="适用对象">
        <n-select v-model:value="formModel.target" :options="[{label:'全部',value:'all'},{label:'仅电影',value:'movie'},{label:'仅剧集',value:'tv'}]" />
      </n-form-item>

      <n-divider dashed title-placement="left">匹配条件 (AND)</n-divider>
      <n-form-item label="流派">
        <n-select
          :value="getSelectedGenreIds()"
          :options="genreOptions"
          :loading="genreLoading"
          multiple
          filterable
          clearable
          placeholder="下拉选择或搜索流派"
          remote
          max-tag-count="responsive"
          @search="handleGenreSearch"
          @update:value="handleGenreSelect"
          @update:show="handleGenreDropdownOpen"
        />
      </n-form-item>
      <n-form-item label="原始国家">
        <n-select
          :value="getSelectedCountryCodes()"
          :options="countryOptions"
          :loading="countryLoading"
          multiple
          filterable
          tag
          clearable
          placeholder="下拉选择或输入国家代码"
          max-tag-count="responsive"
          @search="handleCountrySearch"
          @update:value="handleCountrySelect"
          @update:show="handleCountryDropdownOpen"
        />
      </n-form-item>
      <n-form-item label="原始语言">
        <n-select
          :value="getSelectedLanguageCodes()"
          :options="languageOptions"
          :loading="languageLoading"
          multiple
          filterable
          tag
          clearable
          placeholder="下拉选择或输入语言代码"
          max-tag-count="responsive"
          @search="handleLanguageSearch"
          @update:value="handleLanguageSelect"
          @update:show="handleLanguageDropdownOpen"
        />
      </n-form-item>
      <n-form-item label="制作公司">
        <n-select
          :value="getSelectedCompanyIds()"
          :options="companyOptions"
          :loading="companyLoading"
          multiple
          filterable
          clearable
          placeholder="下拉选择或搜索公司"
          remote
          max-tag-count="responsive"
          @search="handleCompanySearch"
          @update:value="handleCompanySelect"
          @update:show="handleCompanyDropdownOpen"
        />
      </n-form-item>
      <n-form-item label="关键词">
        <n-select
          :value="getSelectedKeywordIds()"
          :options="keywordOptions"
          :loading="keywordLoading"
          multiple
          filterable
          clearable
          placeholder="下拉选择或搜索关键词"
          remote
          max-tag-count="responsive"
          @search="handleKeywordSearch"
          @update:value="handleKeywordSelect"
          @update:show="handleKeywordDropdownOpen"
        />
      </n-form-item>
      <n-form-item label="年份/范围">
        <n-input v-model:value="formModel.criteria.year" placeholder="2024 或 2020-2025" />
      </n-form-item>
      <n-form-item label="名称匹配">
        <n-input v-model:value="formModel.criteria.title" placeholder="匹配标题关键词，多个用逗号分隔" />
      </n-form-item>
    </n-form>

    <template #footer>
      <n-space justify="end">
        <n-button @click="emit('update:show', false)">取消</n-button>
        <n-button type="primary" @click="handleSave">保存</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
