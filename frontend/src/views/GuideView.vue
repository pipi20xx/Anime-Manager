<script setup lang="ts">
/**
 * GuideView — 使用指南
 *
 * 功能:
 * - 全链路识别流水线说明
 * - 自定义识别词 / 特权规则 / 渲染词
 * - RSS 下载规则 / 追剧订阅
 * - STRM 虚拟库 / 数据中心
 * - 设置说明
 */
import { ref } from 'vue'

defineOptions({ name: 'GuideView' })

const activeTab = ref('pipeline')

// 识别流水线阶段
const pipelineStages = [
  {
    icon: 'mdi-file-document-outline',
    title: '1. 输入文件名',
    desc: '系统接收文件名或完整路径作为输入',
    detail: '支持番剧文件名、路径、合集名等多种格式。系统会自动提取文件名中的关键信息。',
  },
  {
    icon: 'mdi-filter-outline',
    title: '2. 预处理 — 识别词过滤',
    desc: '使用自定义识别词规则清洗文件名',
    detail: '识别词（Noise）用于从文件名中移除干扰信息，如发布站名、广告词等。支持正则表达式。',
  },
  {
    icon: 'mdi-crown-outline',
    title: '3. 特权提取',
    desc: '优先使用特权规则提取关键信息',
    detail: '特权规则（Privileged）可以优先从文件名中提取制作组、分辨率等关键信息，避免被普通解析覆盖。',
  },
  {
    icon: 'mdi-brain',
    title: '4. 智能解析',
    desc: 'AI 引擎解析文件名中的番剧名、季号、集号等',
    detail: '系统使用内置规则 + TMDB/Bangumi 数据库进行智能匹配，提取番剧名、季号、集号、分辨率、编码等信息。',
  },
  {
    icon: 'mdi-palette-outline',
    title: '5. 后处理 — 渲染词',
    desc: '使用渲染词规则美化输出结果',
    detail: '渲染词（Render）用于将解析结果转换为标准格式，如将 1080p 转为 FHD，将 4K 转为 UHD 等。',
  },
  {
    icon: 'mdi-check-circle-outline',
    title: '6. 最终结果',
    desc: '输出完整的识别结果，包含 TMDB/Bangumi 映射',
    detail: '最终结果包含番剧名、季号、集号、分辨率、制作组、TMDB ID、Bangumi ID 等完整信息。',
  },
]

// 识别词示例
const noiseExamples = [
  { pattern: '\\[某某字幕组\\]', desc: '屏蔽特定字幕组名', type: '正则' },
  { pattern: '\\[1080P\\]', desc: '屏蔽分辨率标记', type: '正则' },
  { pattern: 'www.example.com', desc: '屏蔽广告网址', type: '正则' },
]

// 特权规则示例
const privilegeExamples = [
  { pattern: '(\\d{4})', field: 'year', desc: '提取年份', example: '[2024] → year: 2024' },
  { pattern: '(1080[pi]|4K|720P)', field: 'resolution', desc: '提取分辨率', example: '1080P → resolution: 1080P' },
  { pattern: '\\[(\\w+)\\]', field: 'team', desc: '提取制作组', example: '[SubGroup] → team: SubGroup' },
]

// 渲染词示例
const renderExamples = [
  { from: '1080p', to: 'FHD', desc: '统一高清格式标记' },
  { from: '2160p', to: 'UHD', desc: '统一 4K 格式标记' },
  { from: '720p', to: 'HD', desc: '统一标清格式标记' },
]

// RSS 规则说明
const rssRuleFields = [
  { field: 'name', desc: '规则名称', required: true },
  { field: 'pattern', desc: '匹配模式（正则表达式）', required: true },
  { field: 'priority', desc: '优先级（数字越小越优先）', required: false },
  { field: 'target_path', desc: '下载目标路径', required: true },
  { field: 'client_id', desc: '下载客户端 ID', required: true },
  { field: 'enabled', desc: '是否启用', required: false },
]

// 变量手册
const variableManual = [
  { var: '{title}', desc: '番剧标题', example: '葬送的芙莉莲' },
  { var: '{season}', desc: '季号（补零）', example: '01' },
  { var: '{episode}', desc: '集号（补零）', example: '05' },
  { var: '{resolution}', desc: '分辨率', example: '1080p' },
  { var: '{team}', desc: '制作组', example: 'SubGroup' },
  { var: '{year}', desc: '年份', example: '2024' },
  { var: '{video_encode}', desc: '视频编码', example: 'x264' },
  { var: '{audio_encode}', desc: '音频编码', example: 'AAC' },
  { var: '{tmdb_id}', desc: 'TMDB ID', example: '226711' },
  { var: '{bangumi_id}', desc: 'Bangumi ID', example: '384858' },
]
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6">
      <h1 class="text-h5 font-weight-bold">使用指南</h1>
      <div class="text-body-2 text-medium-emphasis mt-1">规则与正则指南</div>
    </div>

    <v-tabs v-model="activeTab" color="primary" class="mb-4">
      <v-tab value="pipeline">识别流水线</v-tab>
      <v-tab value="noise">识别词</v-tab>
      <v-tab value="privilege">特权规则</v-tab>
      <v-tab value="render">渲染词</v-tab>
      <v-tab value="rss">RSS 规则</v-tab>
      <v-tab value="variables">变量手册</v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <!-- 识别流水线 -->
      <v-window-item value="pipeline">
        <v-row>
          <v-col v-for="(stage, index) in pipelineStages" :key="index" cols="12" sm="6" md="4">
            <v-card class="glass-card guide-card">
              <v-card-text class="pa-4">
                <div class="d-flex align-center ga-3 mb-3">
                  <v-avatar color="primary" variant="tonal" size="40">
                    <v-icon :icon="stage.icon" />
                  </v-avatar>
                  <div class="text-subtitle-2 font-weight-bold">{{ stage.title }}</div>
                </div>
                <div class="text-body-2 mb-2">{{ stage.desc }}</div>
                <div class="text-caption text-medium-emphasis">{{ stage.detail }}</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>

      <!-- 识别词 -->
      <v-window-item value="noise">
        <v-card class="glass-card">
          <v-card-title class="pa-4 pb-2">
            <v-icon start color="primary">mdi-filter-outline</v-icon>
            自定义识别词 (预处理)
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <div class="text-body-2 mb-4">
              识别词（Noise）用于在识别前从文件名中移除干扰信息。每行一条规则，支持正则表达式。
              当文件名中包含干扰信息（如字幕组名、广告词、标记等）时，识别词可以在解析前将其清除，提高识别准确率。
            </div>

            <div class="text-subtitle-2 font-weight-medium mb-2">示例</div>
            <v-table density="compact" class="bg-transparent">
              <thead>
                <tr>
                  <th>模式</th>
                  <th>说明</th>
                  <th>类型</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in noiseExamples" :key="index">
                  <td><code>{{ item.pattern }}</code></td>
                  <td>{{ item.desc }}</td>
                  <td><v-chip size="x-small" variant="tonal">{{ item.type }}</v-chip></td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- 特权规则 -->
      <v-window-item value="privilege">
        <v-card class="glass-card">
          <v-card-title class="pa-4 pb-2">
            <v-icon start color="info">mdi-crown-outline</v-icon>
            自定义特权规则 (优先提取)
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <div class="text-body-2 mb-4">
              特权规则（Privileged）可以优先从文件名中提取特定字段信息。
              当文件名包含多个可能匹配时，特权规则的结果会被优先采用。
            </div>

            <div class="text-subtitle-2 font-weight-medium mb-2">示例</div>
            <v-table density="compact" class="bg-transparent">
              <thead>
                <tr>
                  <th>模式</th>
                  <th>提取字段</th>
                  <th>说明</th>
                  <th>效果</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in privilegeExamples" :key="index">
                  <td><code>{{ item.pattern }}</code></td>
                  <td><v-chip size="small" variant="tonal" color="primary">{{ item.field }}</v-chip></td>
                  <td>{{ item.desc }}</td>
                  <td class="text-caption">{{ item.example }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- 渲染词 -->
      <v-window-item value="render">
        <v-card class="glass-card">
          <v-card-title class="pa-4 pb-2">
            <v-icon start color="accent">mdi-palette-outline</v-icon>
            自定义渲染词 (后处理)
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <div class="text-body-2 mb-4">
              渲染词（Render）用于在识别完成后，将结果中的特定值替换为标准化格式。
              例如将各种分辨率的写法统一为标准格式。
            </div>

            <div class="text-subtitle-2 font-weight-medium mb-2">示例</div>
            <v-table density="compact" class="bg-transparent">
              <thead>
                <tr>
                  <th>原始值</th>
                  <th>渲染为</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in renderExamples" :key="index">
                  <td><code>{{ item.from }}</code></td>
                  <td><v-chip size="small" variant="flat" color="primary">{{ item.to }}</v-chip></td>
                  <td>{{ item.desc }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- RSS 规则 -->
      <v-window-item value="rss">
        <v-card class="glass-card">
          <v-card-title class="pa-4 pb-2">
            <v-icon start color="info">mdi-rss</v-icon>
            RSS 下载规则配置
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <div class="text-body-2 mb-4">
              RSS 下载规则用于自动监控 RSS 源并根据匹配条件自动下载番剧资源。
              当新的 RSS 条目匹配规则时，系统会自动将下载任务发送到指定的下载客户端。
            </div>

            <div class="text-subtitle-2 font-weight-medium mb-2">字段说明</div>
            <v-table density="compact" class="bg-transparent">
              <thead>
                <tr>
                  <th>字段</th>
                  <th>说明</th>
                  <th>必填</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in rssRuleFields" :key="index">
                  <td><code>{{ item.field }}</code></td>
                  <td>{{ item.desc }}</td>
                  <td>
                    <v-icon v-if="item.required" size="16" color="info">mdi-check-circle</v-icon>
                    <v-icon v-else size="16" color="grey">mdi-minus-circle-outline</v-icon>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- 变量手册 -->
      <v-window-item value="variables">
        <v-card class="glass-card">
          <v-card-title class="pa-4 pb-2">
            <v-icon start color="info">mdi-code-tags</v-icon>
            变量手册
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <div class="text-body-2 mb-4">
              以下变量可在重命名规则、路径模板等处使用，系统会自动替换为对应的值。
            </div>

            <v-table density="compact" class="bg-transparent">
              <thead>
                <tr>
                  <th>变量</th>
                  <th>说明</th>
                  <th>示例值</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in variableManual" :key="index">
                  <td><code>{{ item.var }}</code></td>
                  <td>{{ item.desc }}</td>
                  <td class="text-caption text-medium-emphasis">{{ item.example }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
  </v-container>
</template>


