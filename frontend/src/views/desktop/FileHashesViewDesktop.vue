<script setup lang="ts">
import { ref, computed, h } from 'vue'
import {
  NCard, NSpace, NButton, NIcon, NTag, NGrid, NGi,
  NTooltip, NPagination, NEmpty, NSpin, NCollapse, NCollapseItem, NDropdown,
  NTabs, NTabPane
} from 'naive-ui'
import {
  DocumentDuplicateIcon as HashIcon,
  ClipboardDocumentIcon as CopyIcon,
  Cog6ToothIcon as SettingsIcon,
  ArrowPathIcon as ResetIcon,
  ArrowDownTrayIcon as ExportIcon,
  DocumentTextIcon as FullInfoIcon
} from '@heroicons/vue/24/outline'
import AppSelectField from '../../components/AppSelectField.vue'
import AppTextField from '../../components/AppTextField.vue'
import AppSearchField from '../../components/AppSearchField.vue'
import AppGlassModal from '../../components/AppGlassModal.vue'
import { getButtonStyle } from '../../composables/useButtonStyles'
import { useFileHashes, type FileHashRecord } from '../../composables/views/useFileHashes'

const {
  loading,
  data,
  filters,
  pagination,
  showDetail,
  selectedRecord,
  fetchData,
  openDetail,
  copyToClipboard,
  formatFileSize,
  formatTime,
  truncateHash,
  // ED2K 模板渲染（剧集 / 电影双模板）
  ed2kTemplates,
  showTemplateSettings,
  defaultEd2kTemplates,
  saveEd2kTemplates,
  isMovieRecord,
  renderEd2kFilename,
  renderEd2kLink,
  copyEd2kWithTemplate,
  ed2kVariableGroups,
  ed2kTemplatePresets,
  // 批量导出 / 复制全部
  exporting,
  exportEd2kLinks,
  copyAllEd2kLinks,
  exportFullInfo,
} = useFileHashes()

const mediaTypeOptions = [
  { label: '全部', value: null },
  { label: '剧集', value: '剧集' },
  { label: '电影', value: '电影' },
]

/** 媒体类型信息（用于模板渲染标签） */
const getMediaTypeInfo = (mediaType: string | null) => {
  if (!mediaType) return null
  const raw = mediaType.toLowerCase()
  const isTv = raw === 'tv' || raw === '剧集'
  return { label: isTv ? '剧集' : '电影', type: isTv ? 'info' : 'warning' }
}

/** 格式化季/集 */
const formatSeasonEpisode = (season: number | null, episode: string | null): string => {
  const s = season !== null && season !== undefined ? `S${String(season).padStart(2, '0')}` : ''
  const e = episode ? `E${episode}` : ''
  return [s, e].filter(Boolean).join(' ')
}

/** 分页处理 */
const handlePageChange = (p: number) => {
  pagination.page = p
  fetchData()
}
const handlePageSizeChange = (s: number) => {
  pagination.pageSize = s
  pagination.page = 1
  fetchData()
}

// ========== 高级设置弹框（剧集 / 电影双模板） ==========
/** 当前编辑的 tab：tv / movie */
const activeTemplateTab = ref<'tv' | 'movie'>('tv')

/** 模板编辑草稿（弹框中编辑，保存时才写入持久化） */
const templateDraft = ref({
  tv: ed2kTemplates.value.tv,
  movie: ed2kTemplates.value.movie,
})

/** 打开设置弹框时同步草稿 */
const openTemplateSettings = () => {
  templateDraft.value = {
    tv: ed2kTemplates.value.tv,
    movie: ed2kTemplates.value.movie,
  }
  showTemplateSettings.value = true
}

/** 保存模板 */
const handleSaveTemplate = () => {
  saveEd2kTemplates({
    tv: templateDraft.value.tv.trim() || defaultEd2kTemplates.tv,
    movie: templateDraft.value.movie.trim() || defaultEd2kTemplates.movie,
  })
  showTemplateSettings.value = false
}

/** 重置当前 tab 的模板为默认 */
const handleResetTemplate = () => {
  templateDraft.value[activeTemplateTab.value] = defaultEd2kTemplates[activeTemplateTab.value]
}

/** 应用预设方案到当前 tab */
const applyPreset = (template: string) => {
  templateDraft.value[activeTemplateTab.value] = template
}

// ========== 导出 / 复制全部 ==========
/** 下拉菜单选项 */
const exportOptions = [
  { label: '导出 ED2K 链接 (txt)', key: 'export_ed2k', icon: () => h(NIcon, null, { default: () => h(ExportIcon) }) },
  { label: '复制全部 ED2K 链接', key: 'copy_all_ed2k', icon: () => h(NIcon, null, { default: () => h(CopyIcon) }) },
  { type: 'divider', key: 'd1' },
  { label: '导出完整信息 (txt)', key: 'export_full', icon: () => h(NIcon, null, { default: () => h(FullInfoIcon) }) },
]

/** 下拉菜单选择处理 */
const handleExportSelect = (key: string) => {
  if (key === 'export_ed2k') exportEd2kLinks()
  else if (key === 'copy_all_ed2k') copyAllEd2kLinks()
  else if (key === 'export_full') exportFullInfo()
}

/** 预览用的记录：取当前 tab 对应类型的首条数据，没有则用选中记录 */
const previewRecord = computed<FileHashRecord | null>(() => {
  const wantMovie = activeTemplateTab.value === 'movie'
  const matched = data.value.find(r => isMovieRecord(r) === wantMovie && r.ed2k_link)
  return matched || selectedRecord.value || data.value[0] || null
})

/** 模板预览：渲染后的文件名（用当前 tab 的草稿模板） */
const previewFilename = computed(() => {
  if (!previewRecord.value) return '（暂无数据可预览）'
  return renderEd2kFilename(previewRecord.value, templateDraft.value[activeTemplateTab.value])
})

/** 模板预览：完整 ED2K 链接 */
const previewEd2kLink = computed(() => {
  if (!previewRecord.value || !previewRecord.value.ed2k_link) return '（暂无数据可预览）'
  const fn = renderEd2kFilename(previewRecord.value, templateDraft.value[activeTemplateTab.value])
  const parts = previewRecord.value.ed2k_link.split('|')
  if (parts.length >= 5 && parts[0] === 'ed2k://' && parts[1] === 'file') {
    parts[2] = fn
    return parts.join('|')
  }
  return previewRecord.value.ed2k_link
})

// 详情弹框的字段分组定义
const detailSections = computed(() => {
  const r = selectedRecord.value
  if (!r) return []
  return [
    {
      title: '基础信息',
      items: [
        { label: '原始文件名', value: r.original_filename, mono: true, full: true },
        { label: '文件大小', value: formatFileSize(r.file_size) },
        { label: 'TMDB ID', value: r.tmdb_id || '-' },
        { label: '媒体类型', value: (() => { const m = (r.media_type || '').toLowerCase(); if (m === 'tv' || m === '剧集') return '剧集'; if (m === 'movie' || m === '电影') return '电影'; return r.media_type || '-' })() },
        { label: '记录 ID', value: String(r.id) },
        { label: '计算时间', value: formatTime(r.calculated_at), full: true },
      ],
    },
    {
      title: '识别信息',
      items: [
        { label: '标题', value: r.title || '-' },
        { label: '季号', value: r.season !== null && r.season !== undefined ? String(r.season) : '-' },
        { label: '集数', value: r.episode || '-' },
        { label: '年份', value: r.year || '-' },
        { label: '分辨率', value: r.resolution || '-' },
        { label: '制作组', value: r.team || '-' },
        { label: '视频编码', value: r.video_encode || '-' },
        { label: '音频编码', value: r.audio_encode || '-' },
        { label: '视频特效', value: r.video_effect || '-' },
        { label: '介质来源', value: r.source || '-' },
        { label: '字幕', value: r.subtitle || '-' },
        { label: '发布平台', value: r.platform || '-' },
        { label: '二级分类', value: r.secondary_category || '-' },
        { label: '原产地', value: r.origin_country || '-' },
        { label: '发布日期', value: r.release_date || '-', full: true },
      ],
    },
    {
      title: '哈希与路径',
      items: [
        { label: 'SHA1', value: r.sha1, mono: true, full: true },
        { label: 'ED2K', value: r.ed2k, mono: true, full: true },
        { label: 'ED2K 链接', value: r.ed2k_link, mono: true, full: true },
        { label: '源路径', value: r.source_path, mono: true, full: true },
        { label: '目标路径', value: r.target_path || '-', mono: true, full: true },
      ],
    },
  ]
})
</script>

<template>
  <div class="file-hashes-view">
    <div class="page-header">
      <div>
        <h1>文件哈希记录</h1>
        <div class="subtitle">ED2K 哈希与识别信息缓存（只读）</div>
      </div>
      <n-space>
        <n-tag size="small" round :bordered="false" type="primary">
          共 {{ pagination.itemCount }} 条
        </n-tag>
        <n-dropdown trigger="click" :options="exportOptions" @select="handleExportSelect">
          <n-button
            v-bind="getButtonStyle('secondary')"
            :loading="exporting"
            title="导出 / 复制全部"
          >
            导出
          </n-button>
        </n-dropdown>
        <n-button
          v-bind="getButtonStyle('secondary')"
          @click="openTemplateSettings"
          title="ED2K 链接命名模板设置"
        >
          高级设置
        </n-button>
      </n-space>
    </div>

    <n-card bordered class="mt-4" data-app-instance="file-hashes-card">
      <template #header>
        <div class="d-flex align-center gap-2">
          <n-icon style="color: var(--n-primary-color)"><HashIcon /></n-icon>
          <span>哈希记录列表</span>
        </div>
      </template>

      <n-space vertical :size="12">
        <!-- 筛选栏 -->
        <n-grid :cols="24" :x-gap="12" :y-gap="8" responsive="screen" item-responsive>
          <n-gi span="24 m:10">
            <AppSearchField
              v-model:value="filters.q"
              placeholder="搜索文件名、标题、ED2K、SHA1、路径..."
              :loading="loading"
              @search="() => { pagination.page = 1; fetchData() }"
            />
          </n-gi>
          <n-gi span="12 m:4">
            <AppSelectField
              v-model:value="filters.media_type"
              label="类型"
              placeholder="全部类型"
              clearable
              :options="mediaTypeOptions"
            />
          </n-gi>
          <n-gi span="24 m:3">
            <AppSelectField
              v-model:value="filters.tmdb_id"
              label="TMDB ID"
              placeholder="按 TMDB ID 筛选"
              clearable
              filterable
              tag
              :options="[]"
            />
          </n-gi>
          <n-gi span="12 m:3">
            <AppTextField
              :value="filters.season"
              @update:value="(val: any) => filters.season = val === '' || val === null ? null : Number(val)"
              label="季号"
              placeholder="如 1"
              type="number"
              :min="0"
              :max="99"
            />
          </n-gi>
          <n-gi span="12 m:3">
            <AppTextField
              v-model:value="filters.team"
              label="制作组"
              placeholder="如 ANi、Lilith-Raws"
            />
          </n-gi>
        </n-grid>

        <!-- 卡片列表 -->
        <n-spin :show="loading">
          <div v-if="data.length > 0" class="cards-list">
            <div
              v-for="item in data"
              :key="item.id"
              class="hash-card"
              @click="openDetail(item)"
            >
              <!-- 顶部行：标题（年份）+ 季集 + 类型 | 右侧 ID/大小/TMDB -->
              <div class="card-top">
                <div class="card-title-group">
                  <span class="card-title-main">{{ item.title || item.original_filename }}</span>
                  <span v-if="item.year" class="card-year">({{ item.year }})</span>
                  <span
                    v-if="formatSeasonEpisode(item.season, item.episode)"
                    class="hash-tag tag-episode"
                  >
                    {{ formatSeasonEpisode(item.season, item.episode) }}
                  </span>
                  <span
                    v-if="getMediaTypeInfo(item.media_type)"
                    class="hash-tag tag-type"
                  >
                    {{ getMediaTypeInfo(item.media_type)!.label }}
                  </span>
                </div>
                <div class="card-meta-right">
                  <span v-if="item.tmdb_id" class="hash-tag tag-tmdb">TMDB: {{ item.tmdb_id }}</span>
                  <span class="hash-tag tag-size">{{ formatFileSize(item.file_size) }}</span>
                  <span class="hash-tag tag-id">#{{ item.id }}</span>
                </div>
              </div>

              <!-- 原始文件名（副标题） -->
              <div class="card-filename" :title="item.original_filename">{{ item.original_filename }}</div>

              <!-- 属性标签：分辨率 / 编码 / 制作组 / 来源 等 -->
              <div
                v-if="item.resolution || item.video_encode || item.audio_encode || item.team || item.source || item.platform"
                class="card-attrs"
              >
                <span v-if="item.resolution" class="hash-tag tag-res">{{ item.resolution }}</span>
                <span v-if="item.video_encode" class="hash-tag tag-encode">{{ item.video_encode }}</span>
                <span v-if="item.audio_encode" class="hash-tag tag-encode">{{ item.audio_encode }}</span>
                <span v-if="item.team" class="hash-tag tag-team">{{ item.team }}</span>
                <span v-if="item.source" class="hash-tag tag-source">{{ item.source }}</span>
                <span v-if="item.platform" class="hash-tag tag-platform">{{ item.platform }}</span>
              </div>

              <!-- ED2K 链接 -->
              <div v-if="item.ed2k_link" class="card-ed2k" @click.stop>
                <n-tooltip placement="top">
                  <template #trigger>
                    <span class="ed2k-text">{{ truncateHash(renderEd2kLink(item) || item.ed2k_link, 60, 30) }}</span>
                  </template>
                  <div class="ed2k-tooltip">
                    <div class="ed2k-tooltip-label">渲染后：</div>
                    <div class="ed2k-tooltip-content">{{ renderEd2kLink(item) }}</div>
                  </div>
                </n-tooltip>
                <n-button
                  v-bind="getButtonStyle('icon')"
                  size="tiny"
                  title="复制 ED2K 链接（按模板渲染）"
                  @click.stop="copyEd2kWithTemplate(item)"
                >
                  <template #icon><n-icon :size="14"><CopyIcon /></n-icon></template>
                </n-button>
              </div>
            </div>
          </div>
          <div v-else-if="!loading" class="empty-state">
            <n-empty description="暂无数据" />
          </div>
        </n-spin>

        <!-- 分页 -->
        <div v-if="pagination.itemCount > 0" class="pagination-wrapper">
          <n-pagination
            :page="pagination.page"
            :page-size="pagination.pageSize"
            :item-count="pagination.itemCount"
            :show-size-picker="pagination.showSizePicker"
            :page-sizes="pagination.pageSizes"
            @update:page="handlePageChange"
            @update:page-size="handlePageSizeChange"
          />
        </div>
      </n-space>
    </n-card>

    <!-- 详情弹框（只读，表单式布局，对齐新建订阅风格） -->
    <AppGlassModal
      appearance-key="file-hashes-modal"
      v-model:show="showDetail"
      style="width: 700px; max-width: 96vw;"
      title="文件哈希详情"
      bordered
      size="huge"
    >
      <template #header-extra>
        <n-tag v-if="selectedRecord" size="small" round :bordered="false" type="primary">
          ID #{{ selectedRecord.id }}
        </n-tag>
      </template>

      <div v-if="selectedRecord" class="detail-content">
        <div v-for="(section, sIdx) in detailSections" :key="section.title" class="detail-section">
          <div class="section-title">{{ section.title }}</div>
          <div class="kv-grid">
            <div
              v-for="item in section.items"
              :key="item.label"
              class="kv-item"
              :class="{ 'is-full': item.full }"
            >
              <div class="kv-label">{{ item.label }}</div>
              <div class="kv-value" :class="{ 'is-mono': item.mono }">
                <span class="value-text">{{ item.value }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <n-empty v-else description="暂无数据" />

      <template #action>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('dialogConfirm')" @click="showDetail = false">
            关闭
          </n-button>
        </n-space>
      </template>
    </AppGlassModal>

    <!-- 高级设置弹框：ED2K 链接命名模板 -->
    <AppGlassModal
      appearance-key="file-hashes-template-settings"
      v-model:show="showTemplateSettings"
      style="width: 700px; max-width: 96vw;"
      title="ED2K 链接命名模板"
      bordered
      size="huge"
    >
      <n-space vertical :size="16">
        <!-- 说明 -->
        <div class="template-hint">
          复制 ED2K 链接时，会根据记录的媒体类型自动选择对应模板组合识别信息生成新的文件名，替换链接中的文件名段。
          变量用 <code>{}</code> 包裹，好比重命名规则。不含 <code>{'{' + 'ext}'}</code> 时自动补后缀。
        </div>

        <!-- 剧集 / 电影 双模板切换 -->
        <n-tabs v-model:value="activeTemplateTab" type="line" animated>
          <!-- 剧集模板 -->
          <n-tab-pane name="tv" tab="剧集模板">
            <n-space vertical :size="12">
              <!-- 快捷预设 -->
              <div class="preset-section">
                <div class="preset-title">快捷预设</div>
                <div class="preset-buttons">
                  <button
                    v-for="preset in ed2kTemplatePresets.tv"
                    :key="preset.template"
                    class="preset-btn"
                    :class="{ 'is-active': templateDraft.tv === preset.template }"
                    :title="preset.template"
                    @click="applyPreset(preset.template)"
                  >
                    <span class="preset-btn-label">{{ preset.label }}</span>
                    <span class="preset-btn-desc">{{ preset.desc }}</span>
                  </button>
                </div>
              </div>

              <!-- 模板输入 -->
              <AppTextField
                v-model:value="templateDraft.tv"
                label="剧集命名模板"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 4 }"
                placeholder="{title} ({year}) - S{season_02}E{episode_02} - {team}"
                style="font-family: var(--code-font);"
              />
            </n-space>
          </n-tab-pane>

          <!-- 电影模板 -->
          <n-tab-pane name="movie" tab="电影模板">
            <n-space vertical :size="12">
              <!-- 快捷预设 -->
              <div class="preset-section">
                <div class="preset-title">快捷预设</div>
                <div class="preset-buttons">
                  <button
                    v-for="preset in ed2kTemplatePresets.movie"
                    :key="preset.template"
                    class="preset-btn"
                    :class="{ 'is-active': templateDraft.movie === preset.template }"
                    :title="preset.template"
                    @click="applyPreset(preset.template)"
                  >
                    <span class="preset-btn-label">{{ preset.label }}</span>
                    <span class="preset-btn-desc">{{ preset.desc }}</span>
                  </button>
                </div>
              </div>

              <!-- 模板输入 -->
              <AppTextField
                v-model:value="templateDraft.movie"
                label="电影命名模板"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 4 }"
                placeholder="{title} ({year}) - {team}"
                style="font-family: var(--code-font);"
              />
            </n-space>
          </n-tab-pane>
        </n-tabs>

        <!-- 按钮组 -->
        <n-space>
          <n-button v-bind="getButtonStyle('ghost')" size="small" @click="handleResetTemplate">
            <template #icon><n-icon><ResetIcon /></n-icon></template>
            恢复当前类型默认
          </n-button>
        </n-space>

        <!-- 实时预览（随当前 tab 切换） -->
        <div class="template-preview">
          <div class="preview-title">
            实时预览
            <span class="preview-type-tag">{{ activeTemplateTab === 'tv' ? '剧集' : '电影' }}</span>
          </div>
          <div class="preview-row">
            <span class="preview-label">渲染文件名：</span>
            <code class="preview-value">{{ previewFilename }}</code>
          </div>
          <div class="preview-row">
            <span class="preview-label">完整 ED2K：</span>
            <code class="preview-value preview-ed2k">{{ previewEd2kLink }}</code>
          </div>
        </div>

        <!-- 变量手册 -->
        <n-collapse>
          <n-collapse-item title="可用变量手册" name="vars">
            <div class="v-manual">
              <div v-for="g in ed2kVariableGroups" :key="g.title" class="v-section">
                <div class="v-section-title">{{ g.title }}</div>
                <n-grid :cols="2" :x-gap="12" :y-gap="8">
                  <n-gi v-for="(desc, v) in g.vars" :key="v">
                    <div class="v-item"><code>{{ v }}</code><span>{{ desc }}</span></div>
                  </n-gi>
                </n-grid>
              </div>
            </div>
          </n-collapse-item>
        </n-collapse>
      </n-space>

      <template #action>
        <n-space justify="end">
          <n-button v-bind="getButtonStyle('dialogCancel')" @click="showTemplateSettings = false">
            取消
          </n-button>
          <n-button v-bind="getButtonStyle('dialogConfirm')" @click="handleSaveTemplate">
            保存模板
          </n-button>
        </n-space>
      </template>
    </AppGlassModal>
  </div>
</template>

<style scoped>
.file-hashes-view {
  width: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.page-header h1 {
  margin: 0;
  font-size: var(--text-3xl);
}

.subtitle {
  font-size: var(--text-sm);
  color: var(--n-primary-color);
  letter-spacing: var(--tracking-widest);
  font-weight: bold;
}

.page-header :deep(.n-space) {
  align-items: center;
}

.mt-4 {
  margin-top: var(--space-4);
}

.d-flex {
  display: flex;
}

.align-center {
  align-items: center;
}

.gap-2 {
  gap: var(--space-2);
}

/* === 卡片列表 === */
.cards-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hash-card {
  padding: 14px 16px;
  border-radius: var(--card-border-radius, 12px);
  background: var(--app-surface-card-mixed);
  border: var(--app-card-border-width, 1px) var(--app-card-border-style, solid) var(--app-card-border-color, var(--app-border-light));
  transition: all 0.2s ease;
  cursor: pointer;
}

.hash-card:hover {
  border-color: var(--n-primary-color);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
}

/* 顶部行 */
.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.card-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  flex: 1;
  min-width: 0;
}

.card-title-main {
  font-size: var(--text-lg);
  font-weight: bold;
  color: var(--text-primary);
  /* 单行截断，不提前换行 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-shrink: 1;
  min-width: 0;
}

.card-year {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.card-meta-right {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

/* === 元数据标签（对齐整理历史色系） === */
.hash-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 500;
  background: transparent;
  border-radius: 11px;
  font-family: var(--code-font);
  border: 1px solid;
  white-space: nowrap;
}

/* 季集标签 (S01E12) - 电光蓝 */
.hash-tag.tag-episode {
  background: #3B82F6;
  color: #fff;
  border-color: #3B82F6;
}

/* 类型标签 (剧集/电影) - 深蓝 */
.hash-tag.tag-type {
  background: #1565c0;
  color: #fff;
  border-color: #1565c0;
}

/* 分辨率标签 (1080P) - 深橙 */
.hash-tag.tag-res {
  background: #e65100;
  color: #fff;
  border-color: #e65100;
}

/* 编码标签 (H.265/AAC) - 深橙 */
.hash-tag.tag-encode {
  background: #e65100;
  color: #fff;
  border-color: #e65100;
}

/* 制作组标签 - 深蓝 */
.hash-tag.tag-team {
  background: #1565c0;
  color: #fff;
  border-color: #1565c0;
}

/* 介质来源标签 - 红色 */
.hash-tag.tag-source {
  background: #c62828;
  color: #fff;
  border-color: #c62828;
}

/* 发布平台标签 - 青色 */
.hash-tag.tag-platform {
  background: #00838f;
  color: #fff;
  border-color: #00838f;
}

/* TMDB 标签 - 深绿 */
.hash-tag.tag-tmdb {
  background: #2e7d32;
  color: #fff;
  border-color: #2e7d32;
}

/* 大小标签 - 紫色 */
.hash-tag.tag-size {
  background: #7b1fa2;
  color: #fff;
  border-color: #7b1fa2;
}

/* ID 标签 - 灰色 */
.hash-tag.tag-id {
  background: #616161;
  color: #fff;
  border-color: #616161;
}

/* 原始文件名（副标题） */
.card-filename {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  line-height: 1.4;
  word-break: break-all;
  margin-bottom: 8px;
  font-family: var(--code-font, monospace);
}

/* 属性标签 */
.card-attrs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

/* ED2K 链接行 */
.card-ed2k {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--app-border-light);
}

.ed2k-text {
  flex: 1;
  min-width: 0;
  font-family: var(--code-font, monospace);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 空状态 */
.empty-state {
  padding: 60px 0;
  display: flex;
  justify-content: center;
}

/* 分页 */
.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding-top: 4px;
}

/* === ED2K tooltip === */
.ed2k-tooltip {
  max-width: 500px;
  word-break: break-all;
}
.ed2k-tooltip-label {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-bottom: 2px;
}
.ed2k-tooltip-content {
  font-family: var(--code-font, monospace);
  font-size: 11px;
}

/* === 高级设置弹框 === */
.template-hint {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
  padding: 10px 12px;
  background: var(--app-surface-list-mixed);
  border-radius: 8px;
  border: 1px solid var(--app-border-light);
}
.template-hint code {
  font-family: var(--code-font);
  color: var(--n-warning-color);
  background: var(--app-surface-card-mixed);
  padding: 1px 4px;
  border-radius: 3px;
}

/* 快捷预设 */
.preset-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.preset-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--n-primary-color);
}
.preset-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.preset-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 12px;
  background: var(--app-surface-card-mixed);
  border: 1px solid var(--app-border-light);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
  min-width: 120px;
}
.preset-btn:hover {
  border-color: var(--n-primary-color);
  background: var(--app-surface-list-mixed);
}
.preset-btn.is-active {
  border-color: var(--n-primary-color);
  background: color-mix(in srgb, var(--n-primary-color) 12%, transparent);
  box-shadow: 0 0 0 1px var(--n-primary-color);
}
.preset-btn-label {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}
.preset-btn.is-active .preset-btn-label {
  color: var(--n-primary-color);
}
.preset-btn-desc {
  font-size: 11px;
  color: var(--text-tertiary);
  line-height: 1.3;
}

.template-preview {
  padding: 12px;
  background: var(--app-surface-list-mixed);
  border-radius: 8px;
  border: 1px solid var(--app-border-light);
}
.preview-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--n-primary-color);
  margin-bottom: 8px;
}
.preview-type-tag {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 9px;
  background: var(--n-primary-color);
  color: #fff;
}
.preview-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
  font-size: var(--text-xs);
}
.preview-row:last-child {
  margin-bottom: 0;
}
.preview-label {
  flex-shrink: 0;
  color: var(--text-tertiary);
  white-space: nowrap;
}
.preview-value {
  font-family: var(--code-font, monospace);
  color: var(--text-primary);
  word-break: break-all;
  line-height: 1.5;
}
.preview-ed2k {
  color: var(--n-success-color);
}

/* 变量手册 */
.v-manual {
  padding: 12px;
  background: var(--app-surface-list-mixed);
  border-radius: 8px;
  border: 1px solid var(--app-border-light);
}
.v-section {
  margin-bottom: 16px;
}
.v-section:last-child {
  margin-bottom: 0;
}
.v-section-title {
  font-size: 12px;
  font-weight: bold;
  color: var(--n-primary-color);
  margin-bottom: 8px;
  border-bottom: 1px solid var(--app-border-light);
  padding-bottom: 4px;
}
.v-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}
.v-item code {
  color: var(--n-warning-color);
  font-family: var(--code-font);
  background: var(--app-surface-card-mixed);
  padding: 2px 4px;
  border-radius: 4px;
  border: 1px solid var(--app-border-light);
  white-space: nowrap;
}

/* === 详情弹框（自然撑开，不设固定高度） === */
.detail-content {
  /* 不设 max-height，让内容自然决定弹框高度 */
}

.detail-section {
  margin-bottom: var(--space-4);
}

.detail-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--n-primary-color);
  margin-bottom: var(--space-2);
  padding-left: var(--space-2);
  border-left: 3px solid var(--n-primary-color);
}

/* 键值对网格 —— gap + 容器背景做分割线
   每行要么 2 个普通项要么 1 个 full 项，无空位故不会露灰底 */
.kv-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1px;
  background: var(--list-border-color, var(--app-border-light));
  border: 1px solid var(--list-border-color, var(--app-border-light));
  border-radius: var(--list-border-radius, var(--radius-md));
  overflow: hidden;
}

.kv-item {
  display: flex;
  align-items: stretch;
  background: var(--app-surface-card-mixed);
  min-height: 32px;
}

.kv-item.is-full {
  grid-column: 1 / -1;
}

.kv-label {
  flex-shrink: 0;
  width: 110px;
  padding: 6px 10px;
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  background: var(--app-surface-list-mixed);
  border-right: var(--list-border-width, 1px) var(--list-border-style, solid) var(--list-border-color, var(--app-border-light));
  display: flex;
  align-items: center;
  white-space: nowrap;
}

.kv-value {
  flex: 1;
  padding: 6px 10px;
  font-size: var(--text-sm);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.kv-value.is-mono .value-text {
  font-family: var(--code-font, monospace);
  font-size: var(--text-xs);
  word-break: break-all;
  line-height: 1.5;
}

.kv-value .value-text {
  flex: 1;
  word-break: break-all;
  line-height: 1.5;
}

/* === 移动端适配 === */
@media (max-width: 767px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
  }

  .page-header h1 {
    font-size: var(--text-2xl);
  }

  /* 卡片标题组独占一行，右侧 meta 换到下方 */
  .card-title-group {
    width: 100%;
  }

  .card-title-main {
    font-size: var(--text-base);
  }

  .card-meta-right {
    width: 100%;
    justify-content: flex-start;
  }

  .kv-grid {
    grid-template-columns: 1fr;
  }

  .kv-label {
    width: 90px;
  }
}
</style>
