<script setup lang="ts">
import { reactive, watch } from 'vue'
import { 
  NModal, NSpace, NFormItem, NInput, NCollapse, NCollapseItem, 
  NIcon, NGrid, NGi, NButton
} from 'naive-ui'
import {
  CodeOutlined as VariableIcon
} from '@vicons/material'
import { getButtonStyle } from '../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
  ruleData: any
  isNew: boolean
}>()

const emit = defineEmits(['update:show', 'save'])

const form = reactive({
  id: '',
  name: '',
  movie_pattern: '',
  tv_pattern: ''
})

watch(() => props.show, (newVal) => {
  if (newVal) {
    Object.assign(form, JSON.parse(JSON.stringify(props.ruleData)))
  }
})

const variableGroups = [
  {
    title: "🧠 最终决策结果",
    vars: {
      "{title}": "最终识别出的标题",
      "{year}": "上映年份",
      "{category}": "资源类别",
      "{season}": "季号",
      "{season_02}": "季号补零",
      "{episode}": "集号",
      "{episode_02}": "集号补零",
      "{resolution}": "分辨率",
      "{team}": "制作组",
      "{source}": "来源",
      "{video_encode}": "视频编码",
      "{audio_encode}": "音频编码",
      "{subtitle}": "字幕语言",
      "{video_effect}": "视频特效",
      "{platform}": "发布平台",
      "{release_date}": "发布日期",
      "{tmdb_id}": "TMDB ID",
      "{secondary_category}": "二级分类全路径 (如: 日漫/热血)",
      "{main_category}": "主二级分类 (仅取第一项, 如: 日漫)",
      "{origin_country}": "原产地国家 (如: 日本, 中国)",
      "{filename}": "清洗后原名",
      "{processed_name}": "渲染后原名",
      "{original_filename}": "原始文件名",
      "{path}": "原始路径"
    }
  },
  {
    title: "🔍 本地解析元数据",
    vars: {
      "{raw_cn_name}": "解析到的中文名",
      "{raw_en_name}": "解析到的英文名",
      "{raw_season}": "原始解析季号",
      "{raw_episode}": "原始解析集号",
      "{raw_resource_team}": "原始解析制作组",
      "{raw_filename}": "完全原始文件名 (不含后缀)"
    }
  },
  {
    title: "🎬 TMDB 原始信息",
    vars: {
      "{tmdb_title}": "TMDB 官方中文标题",
      "{tmdb_original_title}": "TMDB 官方原名",
      "{tmdb_year}": "TMDB 年份",
      "{tmdb_date}": "TMDB 完整日期",
      "{tmdb_id}": "TMDB 数字 ID",
      "{tmdb_overview}": "内容简介"
    }
  }
]

const handleSave = () => {
  emit('save', { ...form })
}
</script>

<template>
  <n-modal 
    :show="show" 
    @update:show="val => emit('update:show', val)" 
    preset="card" 
    style="width: 800px" 
    :title="isNew ? '创建新规则' : '编辑重命名规则'"
  >
    <n-space vertical size="large">
      <n-form-item label="规则名称">
        <n-input v-model:value="form.name" placeholder="起个名字方便辨认" />
      </n-form-item>
      
      <n-form-item label="电影命名模板">
        <n-input 
          v-model:value="form.movie_pattern" 
          type="textarea" 
          :autosize="{minRows:2}" 
          placeholder="{title} ({year})/{title} ({year})"
          style="font-family: var(--code-font);"
        />
      </n-form-item>
      
      <n-form-item label="剧集命名模板">
        <n-input 
          v-model:value="form.tv_pattern" 
          type="textarea" 
          :autosize="{minRows:2}" 
          placeholder="{title} ({year})/Season {season}/S{season_02}E{episode_02} - {title}"
          style="font-family: var(--code-font);"
        />
      </n-form-item>
      
      <n-collapse class="mt-4">
        <n-collapse-item title="可用变量手册" name="1">
          <template #header-extra><n-icon><VariableIcon /></n-icon></template>
          <div class="v-manual">
            <div v-for="g in variableGroups" :key="g.title" class="v-s">
              <div class="v-st">{{ g.title }}</div>
              <n-grid :cols="2" :x-gap="12" :y-gap="8">
                <n-gi v-for="(desc, v) in g.vars" :key="v">
                  <div class="v-c"><code>{{ v }}</code><span>{{ desc }}</span></div>
                </n-gi>
              </n-grid>
            </div>
          </div>
        </n-collapse-item>
      </n-collapse>
    </n-space>
    <template #action>
      <n-space justify="end">
        <n-button v-bind="getButtonStyle('ghost')" @click="emit('update:show', false)">取消</n-button>
        <n-button v-bind="getButtonStyle('primary')" @click="handleSave">保存规则配置</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.v-manual { 
  padding: 12px; 
  background: var(--app-surface-inner); 
  border-radius: var(--card-border-radius, 8px); 
  border: 1px solid var(--app-border-light);
}
.v-s { margin-bottom: 20px; }
.v-st { 
  font-size: 12px; 
  font-weight: bold; 
  color: var(--n-primary-color); 
  margin-bottom: 8px; 
  border-bottom: 1px solid var(--app-border-light); 
}
.v-c { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.v-c code { 
  color: var(--n-warning-color); 
  font-family: var(--code-font); 
  background: var(--app-surface-card); 
  padding: 2px 4px; 
  border-radius: 4px; 
  border: 1px solid var(--app-border-light);
}
.mt-4 { margin-top: 16px; }
</style>