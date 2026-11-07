<script setup lang="ts">
/**
 * WorkbenchTab — 番剧分季「分组工作台」子 Tab
 */
import { useSeasonSplitStore } from '@/stores'

defineOptions({ name: 'WorkbenchTab' })

const store = useSeasonSplitStore()
</script>

<template>
  <div>
    <div class="d-flex ga-2 mb-4 flex-wrap align-center">
      <v-text-field
        v-model="store.tmdbId"
        label="TMDB ID"
        density="compact"
        variant="outlined"
        prepend-inner-icon="mdi-movie-open-outline"
        hide-details
        style="max-width: 160px"
        @keyup.enter="store.runPreview"
      />
      <v-btn color="primary" variant="tonal" prepend-icon="mdi-auto-fix" :loading="store.loading" @click="store.runPreview">
        生成方案
      </v-btn>
      <v-spacer />
      <template v-if="store.preview">
        <v-chip size="small" variant="tonal">{{ store.preview.title }}</v-chip>
        <v-chip v-if="store.preview.need_split" size="small" color="info" variant="tonal">需要拆分</v-chip>
        <v-chip v-else size="small" variant="tonal">结构一致</v-chip>
        <v-chip v-if="store.preview.volatile" size="small" color="warning" variant="tonal">连载中</v-chip>
        <v-chip v-if="store.preview.stale" size="small" color="error" variant="tonal">方案已过期</v-chip>
        <v-chip
          v-for="(ref, key) in store.preview.references"
          :key="key"
          size="small"
          variant="tonal"
          :color="ref.split ? 'info' : undefined"
          :title="ref.split ? '该参照源与 TMDB 结构不一致，需要拆分' : '该参照源与 TMDB 结构一致'"
        >
          {{ String(key).toUpperCase() }} {{ store.refSummary(ref) }}
        </v-chip>
      </template>
    </div>

    <div class="text-caption text-medium-emphasis mb-3 px-1">
      「生成方案」会同时拉取 TVDB 与 Bangumi（启用规则表时再加一份），右侧「自动生成」里逐个切换比较；
      <b>参照优先级 / 规则表 / 强制参照</b> 统一在「高级 → 默认参数」里设置。
      候选卡片右侧的数字是该依据会切成的集数（如 <code>12 + 14</code>）。
    </div>

    <v-card v-if="!store.preview" class="glass-card">
      <div class="empty-state pa-8 text-center">
        <v-icon size="40" color="primary" class="mb-2">mdi-call-split</v-icon>
        <div class="text-body-2 text-medium-emphasis">
          输入 TMDB ID 后点「生成方案」：会读取 TMDB 季结构，按参照源 / 播出间隔 / 年份 / 结局标记给出候选分组。
        </div>
      </div>
    </v-card>

    <v-row v-else>
      <!-- 原始季 -->
      <v-col cols="12" md="4">
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
          <span class="section-title">TMDB 原始季</span>
          <v-chip size="x-small" variant="tonal">{{ store.preview.episodes.length }} 集</v-chip>
          <v-spacer />
          <span class="text-caption text-medium-emphasis">{{ store.rawSeasons.length }} 季</span>
        </div>

        <div class="season-stack">
          <v-card v-for="season in store.rawSeasons" :key="season.number" class="glass-card season-card">
            <div class="season-card__head">
              <span class="season-card__title">第 {{ season.number }} 季</span>
              <v-chip size="x-small" variant="tonal">{{ season.episodes.length }} 集</v-chip>
              <v-spacer />
              <span class="season-card__range font-mono">{{ season.range }}</span>
            </div>

            <div class="ep-list">
              <template v-for="ep in season.episodes" :key="ep.episode_number">
                <div class="ep-row text-caption">
                  <span class="font-mono">E{{ store.pad2(ep.episode_number) }}</span>
                  <span class="text-medium-emphasis">{{ ep.air_date || '—' }}</span>
                  <span class="ep-name text-truncate">{{ ep.name }}</span>
                  <v-icon v-if="ep.episode_type === 'finale'" size="x-small" color="warning">mdi-flag-checkered</v-icon>
                </div>
                <div v-if="store.gapSet.has(`${ep.season_number}-${ep.episode_number}`)" class="gap-line text-caption">
                  <v-icon size="x-small">mdi-arrow-down-thin</v-icon>
                  播出间隔 &gt; {{ store.preview.gap_mark_days }} 天
                </div>
              </template>
            </div>
          </v-card>
        </div>
      </v-col>

      <!-- 分组编辑器 -->
      <v-col cols="12" md="5">
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
          <span class="section-title">分组定义</span>
          <v-chip size="x-small" variant="tonal">{{ store.labelOf(store.reference) }}</v-chip>
          <v-chip size="x-small" variant="tonal" color="primary">
            {{ store.groups.length }} 组 / {{ store.coveredEpisodes }} 集
          </v-chip>
          <v-spacer />
          <v-btn size="small" variant="tonal" prepend-icon="mdi-plus" @click="store.addGroup">加一季</v-btn>
        </div>

        <div class="season-stack">
          <v-card v-for="(g, i) in store.groups" :key="i" class="glass-card season-card">
            <div class="season-card__head">
              <span class="season-card__title">第 {{ g.order }} 季</span>
              <v-chip size="x-small" variant="tonal">{{ store.countOf(g) || '—' }} 集</v-chip>
              <v-spacer />
              <span class="season-card__range font-mono">{{ store.rangeLabel(g) }}</span>
              <v-btn
                size="small"
                variant="text"
                color="error"
                icon="mdi-delete-outline"
                title="删除这一季"
                @click="store.removeGroup(i)"
              />
            </div>

            <v-text-field
              v-model="g.name"
              label="季名"
              density="compact"
              variant="outlined"
              hide-details
            />

            <div class="season-row">
              <span class="season-label">起始</span>
              <span class="se-prefix">S</span>
              <v-text-field
                v-model.number="g.start.s"
                type="number"
                density="compact"
                variant="outlined"
                hide-details
                class="se-input"
              />
              <span class="se-prefix">E</span>
              <v-text-field
                v-model.number="g.start.e"
                type="number"
                density="compact"
                variant="outlined"
                hide-details
                class="se-input"
              />
            </div>

            <div class="season-row">
              <span class="season-label">结束</span>
              <span class="se-prefix">S</span>
              <v-text-field
                v-model.number="g.end.s"
                type="number"
                density="compact"
                variant="outlined"
                hide-details
                class="se-input"
              />
              <span class="se-prefix">E</span>
              <v-text-field
                v-model.number="g.end.e"
                type="number"
                density="compact"
                variant="outlined"
                hide-details
                class="se-input"
              />
            </div>
          </v-card>

          <v-card v-if="!store.groups.length" class="glass-card season-card season-card--empty">
            <div class="text-caption text-medium-emphasis">
              还没有分组：点右上「加一季」，或从右侧「自动生成」里选一个依据
            </div>
          </v-card>

          <v-card class="glass-card season-card season-card--add" @click="store.addGroup">
            <v-icon size="28">mdi-plus</v-icon>
            <span class="text-caption">加一季</span>
          </v-card>
        </div>

        <div class="text-caption text-medium-emphasis mt-2 px-1">
          组内按「播出顺序」连续编号（第 1 组 = 第 1 季 E1 起）；下面的排除集不参与重排、保持原编号。
        </div>

        <div class="d-flex flex-wrap align-center ga-2 mt-3">
          <v-text-field
            v-model="store.excludeInput"
            label="排除集（季-集，回车添加）"
            density="compact"
            variant="outlined"
            hide-details
            style="max-width: 220px"
            @keyup.enter="store.addExclude"
          />
          <v-chip
            v-for="(ex, i) in store.excluded"
            :key="`${ex.s}-${ex.e}`"
            size="small"
            closable
            variant="tonal"
            @click:close="store.excluded.splice(i, 1); store.scheduleCompile()"
          >
            S{{ ex.s }}E{{ ex.e }}
          </v-chip>
          <span v-if="!store.excluded.length" class="text-caption text-medium-emphasis">
            排除的集保持原编号（总集篇 / 特别篇）
          </span>
        </div>

        <v-alert
          v-for="(w, i) in store.compileResult?.warnings || []"
          :key="i"
          type="warning"
          variant="tonal"
          density="compact"
          class="mt-2"
        >
          {{ w }}
        </v-alert>
      </v-col>

      <!-- 自动生成 -->
      <v-col cols="12" md="3">
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
          <span class="section-title">自动生成</span>
          <v-spacer />
          <v-chip size="x-small" variant="tonal">{{ store.candidateList.length }} 种依据</v-chip>
        </div>

        <div class="season-stack">
          <v-card
            v-for="c in store.recommendedCandidates"
            :key="c.key"
            class="glass-card option-card"
            :class="{ 'option-card--active': store.reference === c.key }"
            @click="store.pickBasis(c.key)"
          >
            <v-icon size="18" class="option-card__icon">mdi-layers-triple-outline</v-icon>
            <span class="option-card__label">{{ store.labelOf(c.key) }}</span>
            <v-icon v-if="c.warn" size="14" color="warning" title="该依据会漏掉部分集数">mdi-alert-outline</v-icon>
            <v-spacer />
            <span class="option-card__value">{{ c.noSplit ? '不拆' : c.sizeText }}</span>
          </v-card>

          <div class="section-title text-medium-emphasis mt-1">按固定集数</div>

          <v-card
            v-for="c in store.manualCandidates"
            :key="c.key"
            class="glass-card option-card"
            :class="{ 'option-card--active': store.reference === c.key }"
            @click="store.pickBasis(c.key)"
          >
            <v-icon size="18" class="option-card__icon">mdi-grid</v-icon>
            <span class="option-card__label">{{ store.labelOf(c.key) }}</span>
            <v-icon v-if="c.warn" size="14" color="warning" title="该依据会漏掉部分集数">mdi-alert-outline</v-icon>
            <v-spacer />
            <span class="option-card__value">{{ c.noSplit ? '不拆' : c.sizeText }}</span>
          </v-card>

          <v-alert type="info" variant="tonal" density="compact" class="mt-1">
            右侧数字是「点下去会切成几集」（<code>12 + 14</code>）；<code>不拆</code> 表示整季一季。
            「播出间隔」按首播日期算，间隔 &gt; 阈值（默认 45 天，可在高级改）就切一刀；
            「季结局标记」依赖 TMDB 的 finale 标记；「固定集数」是最后的手工兜底。
          </v-alert>
        </div>
      </v-col>
    </v-row>

    <!-- 输出 -->
    <v-card v-if="store.preview" class="glass-card mt-4">
      <div class="d-flex align-center flex-wrap ga-2 pa-3">
        <v-tabs v-model="store.outputTab" density="compact" color="primary">
          <v-tab value="map">逐集映射</v-tab>
          <v-tab value="words">渲染词</v-tab>
          <v-tab value="json">剧集组 JSON</v-tab>
        </v-tabs>
        <v-spacer />
        <v-chip size="small" variant="tonal">覆盖 {{ store.compileResult?.episode_total || 0 }} 集</v-chip>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-content-copy" @click="store.copy(store.renderWordsText, '渲染词已复制')">
          复制渲染词
        </v-btn>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-file-code-outline" @click="store.copy(store.groupJsonText, '剧集组 JSON 已复制')">
          复制剧集组
        </v-btn>
        <v-btn size="small" color="success" variant="tonal" prepend-icon="mdi-check" @click="store.applySave('active')">
          保存并启用
        </v-btn>
        <v-btn
          size="small"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-cloud-upload-outline"
          :disabled="!store.preview.existing_rule"
          @click="store.pushGroup(store.preview.existing_rule)"
        >
          写 SYTMDB
        </v-btn>
      </div>
      <v-divider />
      <div class="pa-2">
        <v-window v-model="store.outputTab">
          <v-window-item value="map">
            <div class="text-caption text-medium-emphasis px-2 pb-2">
              虚拟季/集 = 改写后的编号（整理时用它命名、Emby 用它显示）；原始季/集 = TMDB 的编号。
            </div>
            <div v-if="store.mappingBySeason.length" class="card-grid">
              <v-card v-for="grp in store.mappingBySeason" :key="grp.season" class="glass-card manage-card">
                <div class="manage-card__header">
                  <div class="manage-card__title">第 {{ grp.season }} 季</div>
                  <v-chip class="manage-card__badge" size="x-small" variant="tonal">{{ grp.rows.length }} 集</v-chip>
                </div>

                <div class="manage-card__body map-body">
                  <div v-for="row in grp.rows" :key="row.episode" class="map-line">
                    <span class="map-line__virt">E{{ store.pad2(row.episode) }}</span>
                    <span class="map-line__org">← S{{ row.org_season }}E{{ store.pad2(row.org_episode) }}</span>
                    <span class="map-line__title" :title="row.name">{{ row.name || '—' }}</span>
                  </div>
                </div>
              </v-card>
            </div>

            <div v-else class="text-caption text-medium-emphasis pa-3">
              当前分组是恒等映射（季集号不需要改），所以没有逐集改写记录。
            </div>
          </v-window-item>
          <v-window-item value="words">
            <div class="text-caption text-medium-emphasis px-2 pb-2">
              由识别引擎在最后一步执行，比你自己的「自定义渲染词」晚一步；命中后季集号会直接写进识别结果。
            </div>
            <div v-if="store.manualRenderWords" class="d-flex align-center ga-2 px-2 pb-2">
              <v-chip size="small" color="warning" variant="tonal">
                已手动修改（保存时按此文本入库）
              </v-chip>
              <v-spacer />
              <v-btn
                size="small"
                variant="text"
                prepend-icon="mdi-refresh"
                @click="store.regenerateRenderWords"
              >
                从分组重新生成
              </v-btn>
            </div>
            <div v-if="store.compileResult?.absolute_rules?.length" class="d-flex align-center ga-2 px-2 pb-2">
              <v-chip size="small" color="secondary" variant="tonal" prepend-icon="mdi-numeric">
                已附带 {{ store.compileResult.absolute_rules.length }} 条连番号折算规则（不写 SYTMDB）
              </v-chip>
            </div>
            <v-textarea
              :model-value="store.renderWordsText"
              @update:model-value="store.onRenderWordsInput"
              class="render-words-editor"
              variant="outlined"
              density="compact"
              rows="12"
              hide-details
              spellcheck="false"
              placeholder="（分组为恒等映射，无需生成规则）"
            />
          </v-window-item>
          <v-window-item value="json">
            <div class="text-caption text-medium-emphasis px-2 pb-2">
              点右上「写 SYTMDB」推送后，Emby 会按这些剧集组显示成多季；文件本身仍需按分季后编号命名。
            </div>
            <pre class="code-block">{{ store.groupJsonText }}</pre>
          </v-window-item>
        </v-window>
      </div>
    </v-card>
  </div>
</template>

<style scoped>
.ep-row {
  display: grid;
  grid-template-columns: 62px 86px 1fr 18px;
  gap: 6px;
  align-items: center;
  padding: 2px 4px;
  border-radius: 6px;
}

.ep-row:hover {
  background: rgba(var(--v-theme-primary), 0.06);
}

.render-words-editor :deep(textarea) {
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.ep-name {
  color: rgba(var(--v-theme-on-surface), 0.68);
}

.gap-line {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
  color: rgb(var(--v-theme-warning));
  border-top: 1px dashed rgba(var(--v-theme-warning), 0.35);
  border-bottom: 1px dashed rgba(var(--v-theme-warning), 0.35);
}

.map-body {
  max-height: 320px;
  overflow-y: auto;
}

.map-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  line-height: 1.7;
  padding: 1px 0;
}

.map-line:hover {
  background: rgba(var(--v-theme-primary), 0.05);
}

.map-line__virt {
  flex: 0 0 34px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.map-line__org {
  flex: 0 0 76px;
  opacity: 0.5;
  font-variant-numeric: tabular-nums;
}

.map-line__title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: 0.75;
}

.season-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 560px;
  overflow-y: auto;
  padding-right: 2px;
}

.season-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  overflow: visible !important;
}

.season-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.season-card__title {
  font-size: 14px;
  font-weight: 700;
  white-space: nowrap;
}

.season-card__range {
  font-size: 11px;
  opacity: 0.5;
  white-space: nowrap;
}

.season-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.season-label {
  font-size: 11px;
  opacity: 0.55;
  white-space: nowrap;
  flex: 0 0 28px;
  width: 28px;
}

.se-prefix {
  font-size: 11px;
  opacity: 0.55;
  flex: 0 0 10px;
  width: 10px;
  text-align: center;
}

.se-input {
  flex: 0 0 84px;
  width: 84px;
  max-width: 84px;
}

.se-input :deep(input) {
  text-align: center;
}

.se-input :deep(input[type='number'])::-webkit-outer-spin-button,
.se-input :deep(input[type='number'])::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.se-input :deep(input[type='number']) {
  -moz-appearance: textfield;
  appearance: textfield;
}

.season-card--add {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 84px;
  border-style: dashed !important;
  opacity: 0.75;
  cursor: pointer;
}

.season-card--add:hover {
  opacity: 1;
}

.season-card--empty {
  min-height: 60px;
}

.ep-list {
  max-height: 300px;
  overflow-y: auto;
}

.option-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
}

.option-card--active {
  border-color: rgb(var(--v-theme-primary)) !important;
}

.option-card__icon {
  opacity: 0.6;
}

.option-card__label {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.option-card__value {
  font-size: 11px;
  opacity: 0.6;
  white-space: nowrap;
}
</style>
