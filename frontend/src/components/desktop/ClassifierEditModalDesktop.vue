<script setup lang="ts">
import { 
  NModal, NCard, NForm, NFormItem, NInput, NSelect, NButton, NSpace, NGrid, NGi, NDivider, NIcon
} from 'naive-ui'
import { SaveOutlined as SaveIcon } from '@vicons/material'
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
  <n-modal :show="props.show" @update:show="val => emit('update:show', val)">
    <n-card
      style="width: 800px"
      :title="props.isNew ? '添加二级分类规则' : '编辑分类规则'"
      bordered
      size="huge"
      role="dialog"
      aria-modal="true"
    >
      <n-form label-placement="left" label-width="100">
        <n-divider title-placement="left">基础设置</n-divider>
        <n-grid :cols="2" :x-gap="12">
          <n-gi :span="2">
            <n-form-item label="分类名称" path="name">
              <n-input v-model:value="formModel.name" placeholder="对应的二级文件夹名称" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="适用对象">
              <n-select v-model:value="formModel.target" :options="[{label:'全部',value:'all'},{label:'仅电影',value:'movie'},{label:'仅剧集',value:'tv'}]" />
            </n-form-item>
          </n-gi>
        </n-grid>

        <n-divider title-placement="left">匹配条件 (AND 逻辑)</n-divider>
        <n-grid :cols="2" :x-gap="12">
          <n-gi>
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
          </n-gi>
          <n-gi>
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
          </n-gi>
          <n-gi>
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
          </n-gi>
          <n-gi>
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
          </n-gi>
          <n-gi>
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
          </n-gi>
          <n-gi>
            <n-form-item label="年份/范围">
              <n-input v-model:value="formModel.criteria.year" placeholder="2024 或 2020-2025" />
            </n-form-item>
          </n-gi>
          <n-gi :span="2">
            <n-form-item label="名称匹配">
              <n-input v-model:value="formModel.criteria.title" placeholder="匹配标题关键词，多个用逗号分隔" />
            </n-form-item>
          </n-gi>
        </n-grid>
      </n-form>

      <template #action>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="emit('update:show', false)">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="handleSave">
            确认并保存
          </n-button>
        </n-space>
      </template>
    </n-card>
  </n-modal>
</template>

<style scoped>
:deep(.n-divider .n-divider__title) {
  font-size: 13px;
  font-weight: 800;
  color: var(--n-primary-color);
  letter-spacing: 1px;
}

:deep(.n-form-item-label) {
  font-weight: 600;
  color: var(--n-text-color-3);
}
</style>
