<script setup lang="ts">
import { 
  NModal, NCard, NForm, NFormItem, NSelect, NButton, NSpace, NDivider, NIcon
} from 'naive-ui'
import { SaveOutlined as SaveIcon } from '@vicons/material'
import AppTextField from '../AppTextField.vue'
import AppSelectField from '../AppSelectField.vue'
import { useClassifierEdit } from '../../composables/modals/useClassifierEdit'
import { getButtonStyle } from '../../composables/useButtonStyles'

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
      <n-form-item path="name">
        <AppTextField v-model:value="formModel.name" label="分类名称" placeholder="对应的二级文件夹名称" />
      </n-form-item>
      <n-form-item>
        <AppSelectField v-model:value="formModel.target" label="适用对象" :options="[{label:'全部',value:'all'},{label:'仅电影',value:'movie'},{label:'仅剧集',value:'tv'}]" />
      </n-form-item>

      <n-divider dashed title-placement="left">匹配条件 (AND)</n-divider>
      <n-form-item>
        <AppSelectField
          label="流派"
          :value="getSelectedGenreIds()"
          :options="genreOptions"
          :loading="genreLoading"
          multiple
          filterable
          clearable
          placeholder="下拉选择或搜索流派"
          remote
          max-tag-count="responsive"
          :fallback-option="(val: string | number) => ({ label: `ID: ${val}`, value: val })"
          :on-search="handleGenreSearch"
          @update:value="handleGenreSelect"
          :on-update-show="handleGenreDropdownOpen"
        />
      </n-form-item>
      <n-form-item>
        <AppSelectField
          label="原始国家"
          :value="getSelectedCountryCodes()"
          :options="countryOptions"
          :loading="countryLoading"
          multiple
          filterable
          tag
          clearable
          placeholder="下拉选择或输入国家代码"
          max-tag-count="responsive"
          :fallback-option="(val: string | number) => ({ label: `${val}`, value: val })"
          :on-search="handleCountrySearch"
          @update:value="handleCountrySelect"
          :on-update-show="handleCountryDropdownOpen"
        />
      </n-form-item>
      <n-form-item>
        <AppSelectField
          label="原始语言"
          :value="getSelectedLanguageCodes()"
          :options="languageOptions"
          :loading="languageLoading"
          multiple
          filterable
          tag
          clearable
          placeholder="下拉选择或输入语言代码"
          max-tag-count="responsive"
          :fallback-option="(val: string | number) => ({ label: `${val}`, value: val })"
          :on-search="handleLanguageSearch"
          @update:value="handleLanguageSelect"
          :on-update-show="handleLanguageDropdownOpen"
        />
      </n-form-item>
      <n-form-item>
        <AppSelectField
          label="制作公司"
          :value="getSelectedCompanyIds()"
          :options="companyOptions"
          :loading="companyLoading"
          multiple
          filterable
          clearable
          placeholder="下拉选择或搜索公司"
          remote
          max-tag-count="responsive"
          :fallback-option="(val: string | number) => ({ label: `ID: ${val}`, value: val })"
          :on-search="handleCompanySearch"
          @update:value="handleCompanySelect"
          :on-update-show="handleCompanyDropdownOpen"
        />
      </n-form-item>
      <n-form-item>
        <AppSelectField
          label="关键词"
          :value="getSelectedKeywordIds()"
          :options="keywordOptions"
          :loading="keywordLoading"
          multiple
          filterable
          clearable
          placeholder="下拉选择或搜索关键词"
          remote
          max-tag-count="responsive"
          :fallback-option="(val: string | number) => ({ label: `ID: ${val}`, value: val })"
          :on-search="handleKeywordSearch"
          @update:value="handleKeywordSelect"
          :on-update-show="handleKeywordDropdownOpen"
        />
      </n-form-item>
      <n-form-item>
        <AppTextField v-model:value="formModel.criteria.year" label="年份/范围" placeholder="2024 或 2020-2025" />
      </n-form-item>
      <n-form-item>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <AppTextField v-model:value="formModel.criteria.title" label="名称匹配" placeholder="匹配标题关键词，多个用逗号分隔" />
          <span style="font-size: 11px; color: var(--text-tertiary); line-height: 1.4;">
            匹配数据库字段: custom_title (用户自定义) → title (TMDB官方) → name (备用)
          </span>
        </div>
      </n-form-item>
    </n-form>

    <template #footer>
      <n-space justify="end">
        <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="handleSave">保存</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
