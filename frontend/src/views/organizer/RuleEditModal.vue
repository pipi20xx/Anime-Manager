<script setup lang="ts">
/**
 * RuleEditModal — 重命名规则编辑弹窗
 *
 * 完整表单 + 模板实时渲染预览 + 变量手册折叠面板
 * 预览逻辑与后端 Renamer.format_path 保持一致
 */
import { computed } from 'vue'

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
      '{raw_processed_name}': '原始处理后名',
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
  {
    title: '其他内置变量',
    vars: {
      '{ext}': '文件后缀名 (不含点)',
      '{name}': '原始文件名 (不含后缀)',
      '{group}': '{team} 的别名',
      '{date}': '{release_date} 的别名',
    },
  },
]

// --- 预览示例数据 ---
const MOVIE_SAMPLE: any = {
  original_filename: 'Your.Name.2016.BluRay.1080p.x264-NAGOMI.mkv',
  final: {
    title: '你的名字',
    year: '2016',
    category: '电影',
    season: '',
    episode: '',
    resolution: '1080p',
    team: 'NAGOMI',
    source: 'BDMV',
    video_encode: 'x264',
    audio_encode: 'AAC',
    subtitle: 'CHS',
    video_effect: '',
    platform: '',
    release_date: '2016-08-26',
    tmdb_id: '376867',
    secondary_category: '电影/日本动画',
    origin_country: 'JP',
    filename: 'Your.Name.2016.BluRay.1080p.x264-NAGOMI',
    processed_name: '你的名字.2016.1080p.BDMV',
    path: '/downloads/Your.Name.2016.BluRay.1080p.x264-NAGOMI.mkv',
  },
  raw: {
    cn_name: '你的名字',
    en_name: 'Your Name',
    season: '',
    episode: '',
    resource_team: 'NAGOMI',
    filename: 'Your.Name.2016.BluRay.1080p.x264-NAGOMI',
    processed_name: 'Your.Name.2016.BluRay.1080p.x264-NAGOMI',
  },
  tmdb: {
    title: '你的名字',
    original_title: '君の名は。',
    year: '2016',
    date: '2016-08-26',
    overview: '在深山小镇生活的高中生三叶与东京少年泷互换身体的故事……',
  },
}

const TV_SAMPLE: any = {
  original_filename: '[ANi] 葬送的芙莉莲 - 08 [1080P][Baha][WEB-DL][AAC AVC][CHT].mkv',
  final: {
    title: '葬送的芙莉莲',
    year: '2023',
    category: '剧集',
    season: '1',
    episode: '8',
    resolution: '1080p',
    team: 'ANi',
    source: 'WebRip',
    video_encode: 'H.264',
    audio_encode: 'AAC',
    subtitle: 'CHT',
    video_effect: '',
    platform: 'Baha',
    release_date: '2023-09-29',
    tmdb_id: '209867',
    secondary_category: '剧集/日本动画',
    origin_country: 'JP',
    filename: '[ANi] 葬送的芙莉莲 - 08 [1080P][Baha][WEB-DL][AAC AVC][CHT]',
    processed_name: '葬送的芙莉莲 S01E08',
    path: '/downloads/[ANi] 葬送的芙莉莲 - 08 [1080P][Baha][WEB-DL][AAC AVC][CHT].mkv',
  },
  raw: {
    cn_name: '葬送的芙莉莲',
    en_name: 'Sousou no Frieren',
    season: '1',
    episode: '8',
    resource_team: 'ANi',
    filename: '[ANi] 葬送的芙莉莲 - 08 [1080P][Baha][WEB-DL][AAC AVC][CHT]',
    processed_name: '葬送的芙莉莲 - 08 [1080P]',
  },
  tmdb: {
    title: '葬送的芙莉莲',
    original_title: '葬送のフリーレン',
    year: '2023',
    date: '2023-09-29',
    overview: '打倒了魔王的勇者一行人中的芙莉莲，踏上新的旅途……',
  },
}

// --- 预览渲染（与后端 Renamer.format_path 逻辑对齐） ---
function pad2(v: string): string {
  const n = parseInt(v, 10)
  return Number.isNaN(n) ? v : String(n).padStart(2, '0')
}

function sanitize(s: string): string {
  return s.replace(/[\\/:*?"<>|]/g, ' ').replace(/\s+/g, ' ').trim()
}

function renderPattern(pattern: string, sample: any): string {
  if (!pattern || !pattern.trim()) return ''

  const dot = sample.original_filename.lastIndexOf('.')
  const ext = dot > 0 ? sample.original_filename.slice(dot + 1) : ''
  const base = dot > 0 ? sample.original_filename.slice(0, dot) : sample.original_filename

  const map: Record<string, string> = {}
  for (const [k, v] of Object.entries(sample.final)) {
    map[`{${k}}`] = String(v ?? '')
  }
  map['{season_02}'] = pad2(String(sample.final.season ?? ''))
  map['{episode_02}'] = pad2(String(sample.final.episode ?? ''))

  for (const [k, v] of Object.entries(sample.raw)) {
    map[`{raw_${k}}`] = String(v ?? '')
  }
  for (const [k, v] of Object.entries(sample.tmdb)) {
    map[`{tmdb_${k}}`] = String(v ?? '')
  }

  map['{ext}'] = ext
  map['{original_filename}'] = sanitize(base)
  map['{name}'] = sanitize(base)
  map['{path}'] = sanitize(String(sample.final.path ?? ''))

  const secCat = map['{secondary_category}'] ?? ''
  map['{main_category}'] = secCat ? secCat.split('/')[0] : ''
  map['{group}'] = map['{team}'] ?? ''
  map['{date}'] = map['{release_date}'] ?? ''

  let result = pattern
  for (const [k, v] of Object.entries(map)) {
    result = result.split(k).join(v)
  }

  // 路径清洗，与后端一致
  result = result.split('()').join('').split('[]').join('')
  result = result.replace(/\s+-\s+-/g, ' - ')
  result = result.replace(/\[\s+\]/g, '')
  result = result.replace(/\(\s+\)/g, '')
  result = result.replace(/\s+/g, ' ').trim()

  const segments = result.split('/').map((p) => sanitize(p)).filter(Boolean)
  return segments.join('/')
}

const moviePreview = computed(() => renderPattern(props.ruleForm.movie_pattern, MOVIE_SAMPLE))
const tvPreview = computed(() => renderPattern(props.ruleForm.tv_pattern, TV_SAMPLE))
</script>

<template>
  <v-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" max-width="800" scrollable>
    <v-card class="glass-card">
<v-card-title class="pa-4 d-flex align-center">
<v-icon start>mdi-form-textbox</v-icon>
{{ isNew ? '创建新规则' : '编辑重命名规则' }}
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="emit('update:modelValue', false)" />
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
          class="mb-1"
        />
        <div v-if="moviePreview" class="kv-value--mono mb-3">{{ moviePreview }}</div>

        <v-textarea
          v-model="ruleForm.tv_pattern"
          label="剧集命名模板"
          placeholder="{title} ({year})/Season {season}/S{season_02}E{episode_02} - {title}"
          variant="outlined"
          density="compact"
          rows="2"
          auto-grow
          class="mb-1"
        />
        <div v-if="tvPreview" class="kv-value--mono mb-2">{{ tvPreview }}</div>

        <!-- 变量手册折叠面板 -->
        <v-expansion-panels class="mt-4">
          <v-expansion-panel>
            <v-expansion-panel-title>
              <div class="d-flex align-center ga-2">
                <v-icon size="18">mdi-code-block-braces</v-icon>
                <span class="font-weight-medium">可用变量手册</span>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div class="variable-manual">
                <div v-for="group in variableGroups" :key="group.title" class="variable-section">
                  <div class="variable-section-title">{{ group.title }}</div>
                  <v-row density="compact">
                    <v-col v-for="(desc, variable) in group.vars" :key="variable" cols="12" sm="6">
                      <div class="variable-item">
                        <span>{{ variable }}</span>
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
        <v-btn variant="tonal" color="primary" prepend-icon="mdi-content-save-outline" @click="emit('save')">保存规则配置</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
