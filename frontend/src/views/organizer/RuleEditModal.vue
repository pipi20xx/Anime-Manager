<script setup lang="ts">
/**
 * RuleEditModal — 重命名规则编辑弹窗
 *
 * 完整表单 + 变量手册折叠面板
 */
defineOptions({ name: 'RuleEditModal' })

const props = defineProps<{
  modelValue: boolean
  isNew: boolean
  ruleForm: any
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  save: []
}>()

// 变量手册
const variableGroups = [
  {
    title: '最终决策结果',
    vars: {
      '{title}': '最终识别出的标题',
      '{year}': '上映年份',
      '{category}': '资源类别',
      '{season}': '季号',
      '{season_02}': '季号补零',
      '{episode}': '集号',
      '{episode_02}': '集号补零',
      '{resolution}': '分辨率',
      '{team}': '制作组',
      '{source}': '介质来源',
      '{video_encode}': '视频编码',
      '{audio_encode}': '音频编码',
      '{subtitle}': '字幕语言',
      '{video_effect}': '视频特效',
      '{platform}': '发布平台',
      '{release_date}': '发布日期',
      '{tmdb_id}': 'TMDB ID',
      '{secondary_category}': '二级分类全路径',
      '{main_category}': '主二级分类',
      '{origin_country}': '原产地国家',
      '{filename}': '清洗后原名',
      '{processed_name}': '渲染后原名',
      '{original_filename}': '原始文件名',
      '{path}': '原始路径',
    },
  },
  {
    title: '本地解析元数据',
    vars: {
      '{raw_cn_name}': '解析到的中文名',
      '{raw_en_name}': '解析到的英文名',
      '{raw_season}': '原始解析季号',
      '{raw_episode}': '原始解析集号',
      '{raw_resource_team}': '原始解析制作组',
      '{raw_filename}': '完全原始文件名 (不含后缀)',
    },
  },
  {
    title: 'TMDB 原始信息',
    vars: {
      '{tmdb_title}': 'TMDB 官方中文标题',
      '{tmdb_original_title}': 'TMDB 官方原名',
      '{tmdb_year}': 'TMDB 年份',
      '{tmdb_date}': 'TMDB 完整日期',
      '{tmdb_overview}': '内容简介',
    },
  },
]
</script>

<template>
  <v-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" max-width="800" scrollable>
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start>mdi-form-textbox</v-icon>
        {{ isNew ? '创建新规则' : '编辑重命名规则' }}
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <v-text-field
          v-model="ruleForm.name"
          label="规则名称"
          placeholder="起个名字方便辨认"
          variant="outlined"
          density="compact"
          class="mb-3"
        />

        <v-textarea
          v-model="ruleForm.movie_pattern"
          label="电影命名模板"
          placeholder="{title} ({year})/{title} ({year})"
          variant="outlined"
          density="compact"
          rows="2"
          auto-grow
          class="mb-3"
        />

        <v-textarea
          v-model="ruleForm.tv_pattern"
          label="剧集命名模板"
          placeholder="{title} ({year})/Season {season}/S{season_02}E{episode_02} - {title}"
          variant="outlined"
          density="compact"
          rows="2"
          auto-grow
          class="mb-2"
        />

        <!-- 变量手册折叠面板 -->
        <v-expansion-panels class="mt-4">
          <v-expansion-panel>
            <v-expansion-panel-title>
              <div class="d-flex align-center ga-2">
                <v-icon size="18">mdi-code-braces</v-icon>
                <span class="font-weight-medium">可用变量手册</span>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div class="variable-manual">
                <div v-for="group in variableGroups" :key="group.title" class="variable-section">
                  <div class="variable-section-title">{{ group.title }}</div>
                  <v-row dense>
                    <v-col v-for="(desc, variable) in group.vars" :key="variable" cols="12" sm="6">
                      <div class="variable-item">
                        <code>{{ variable }}</code>
                        <span>{{ desc }}</span>
                      </div>
                    </v-col>
                  </v-row>
                </div>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="emit('update:modelValue', false)">取消</v-btn>
        <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="emit('save')">保存规则配置</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
