<script setup lang="ts">
/**
 * RuleLibraryTab — 番剧分季「规则库」子 Tab
 */
import { useSeasonSplitStore } from '@/stores'
import { DialogTitle } from '@/components/common'

defineOptions({ name: 'RuleLibraryTab' })

const store = useSeasonSplitStore()
</script>

<template>
  <div>
    <div class="d-flex ga-2 mb-4 flex-wrap align-center">
      <v-text-field
        v-model="store.ruleSearch"
        label="搜索番名或 TMDB ID"
        density="compact"
        variant="outlined"
        prepend-inner-icon="mdi-magnify"
        clearable
        hide-details
        class="flex-grow-1"
        style="min-width: 220px"
        @keyup.enter="store.loadRules"
        @click:clear="store.ruleSearch = ''; store.loadRules()"
      />
      <v-select
        v-model="store.ruleStatus"
        :items="[
          { title: '全部状态', value: '' },
          { title: '草稿', value: 'draft' },
          { title: '生效', value: 'active' },
          { title: '停用', value: 'disabled' },
        ]"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width: 150px"
        @update:model-value="store.loadRules"
      />
      <v-select
        v-model="store.ruleOrigin"
        :items="[
          { title: '全部来源', value: '' },
          { title: '手动生成', value: 'manual' },
          { title: 'SYTMDB 导入', value: 'sytmdb' },
          { title: '自动生成', value: 'auto' },
          { title: '历史未知', value: 'legacy' },
        ]"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width: 150px"
        @update:model-value="store.loadRules"
      />
      <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="store.loading" @click="store.loadRules">刷新</v-btn>
      <v-btn variant="tonal" prepend-icon="mdi-cloud-download-outline" @click="store.openSytmdbImport">
        导入 SYTMDB
      </v-btn>
      <v-btn color="primary" variant="tonal" prepend-icon="mdi-plus" @click="store.activeTab = 'workbench'">
        新建分季
      </v-btn>
    </div>

    <div class="text-caption text-medium-emphasis mb-3 px-1">
      共 {{ store.rules.length }} 条。只有状态为 <b>生效</b> 的规则会被注入识别；草稿/停用只是保存着不动。
      卡片上的小标签就是「这条规则怎么来的」：<b>手动</b> = 工作台生成、<b>SYTMDB</b> = 一键导入、
      <b>自动</b> = 识别时自动生成、<b>历史</b> = 升级前保存（当时没记来源，无法区分）。
    </div>

    <v-skeleton-loader v-if="store.loading && !store.rules.length" type="card@3" />

    <div v-else-if="store.rules.length" class="card-grid">
      <v-card v-for="rule in store.rules" :key="rule.tmdb_id" class="glass-card manage-card">
        <div class="manage-card__header">
          <div class="manage-card__title" :title="rule.title">{{ rule.title }}</div>
          <div class="d-flex align-center ga-1 flex-shrink-0">
            <v-tooltip :text="store.originOf(rule).hint" location="top">
              <template #activator="{ props }">
                <v-chip
                  v-bind="props"
                  class="manage-card__badge"
                  size="x-small"
                  :color="store.originOf(rule).color"
                  :prepend-icon="store.originOf(rule).icon"
                  variant="tonal"
                  label
                >
                  {{ store.originOf(rule).short }}
                </v-chip>
              </template>
            </v-tooltip>
            <v-chip class="manage-card__badge" size="x-small" :color="store.statusOf(rule).color" variant="tonal" label>
              {{ store.statusOf(rule).label }}
            </v-chip>
          </div>
        </div>

        <div class="manage-card__body">
          <div class="manage-card__info">
            <span class="manage-card__info-label">TMDB</span>
            <span class="manage-card__info-value font-mono">{{ rule.tmdb_id }}</span>
          </div>
          <div class="manage-card__info">
            <span class="manage-card__info-label">依据</span>
            <span class="manage-card__info-value">{{ store.labelOf(rule.reference) }}</span>
          </div>
          <div class="manage-card__info">
            <span class="manage-card__info-label">分组</span>
            <span class="manage-card__info-value">
              {{ (rule.groups || []).length }} 组 · 覆盖 {{ rule.episode_total }} 集
            </span>
          </div>
          <div class="manage-card__info">
            <span class="manage-card__info-label">更新</span>
            <span class="manage-card__info-value">{{ rule.updated_at || '—' }}</span>
          </div>
        </div>

        <v-card-actions class="manage-card__actions">
          <v-spacer />
          <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-pencil" @click="store.editRule(rule)">
            编辑
          </v-btn>
          <v-btn size="small" variant="tonal" prepend-icon="mdi-power" @click="store.toggleRule(rule)">
            {{ rule.status === 'active' ? '停用' : '启用' }}
          </v-btn>
          <v-btn size="small" variant="tonal" prepend-icon="mdi-cloud-upload-outline" @click="store.pushGroup(rule)">
            剧集组
          </v-btn>
          <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="store.removeRule(rule)">
            删除
          </v-btn>
        </v-card-actions>
      </v-card>
    </div>

    <v-card v-else class="glass-card">
      <div class="empty-state pa-8 text-center">
        <v-icon size="40" color="primary" class="mb-2">mdi-format-list-bulleted</v-icon>
        <div class="text-body-2 text-medium-emphasis">还没有分季规则，去「分组工作台」新建一条</div>
      </div>
    </v-card>

    <!-- SYTMDB 剧集组一键导入 -->
    <v-dialog v-model="store.sytmdbOpen" max-width="920" scrollable>
      <v-card class="glass-card">
        <DialogTitle icon="mdi-cloud-download-outline" icon-color="primary" title="从 SYTMDB 导入剧集组"
          @close="store.closeSytmdbImport()" />
        <v-divider />

        <v-card-text class="pa-4">
          <v-alert density="compact" variant="tonal" color="info" class="mb-3" icon="mdi-information-outline">
            <div class="text-caption">
              <div>
                直接把 SYTMDB 上已经画好的<b>剧集组</b>搬进规则库：不拿 TMDB ID 重新生成，
                季号 / 集号 / 组名都按那边的数据来；<b>S0 特别篇也照搬</b>（放进哪组就落到哪季），
                只有重复集会被去重。渲染词由剧集组反推，并逐集回放自检。
              </div>
              <div class="mt-1">
                导入后仍可用「剧集组」按钮把结果写回 SYTMDB——两边内容一致，不会互相打架。
              </div>
            </div>
          </v-alert>

          <div class="d-flex flex-wrap ga-3 align-center mb-2">
            <v-select v-model="store.sytmdbStatus" :items="[
              { title: '导入后立即生效', value: 'active' },
              { title: '先存草稿', value: 'draft' },
            ]" density="compact" variant="outlined" hide-details style="max-width: 170px" />
            <v-checkbox v-model="store.sytmdbOverwrite" label="覆盖已有规则" density="compact" hide-details />
            <v-spacer />
            <v-btn size="small" variant="text" prepend-icon="mdi-refresh" :loading="store.sytmdbLoading"
              @click="store.loadSytmdbCandidates()">
              重新扫描
            </v-btn>
          </div>

          <div class="text-caption text-medium-emphasis mb-3">
            数据源 <span class="font-mono">{{ store.sytmdbSource || '—' }}</span>
            · 扫描 {{ store.sytmdbScanned }} 条
            · 带剧集组 {{ store.sytmdbItems.length }} 条
            · 可导入 {{ store.sytmdbImportable }} 条
            · 已有规则 {{ store.sytmdbExisting }} 条
          </div>

          <v-alert v-if="store.sytmdbError" density="compact" variant="tonal" color="error" class="mb-3">
            {{ store.sytmdbError }}
          </v-alert>

          <v-progress-linear v-if="store.sytmdbLoading" indeterminate color="primary" class="mb-3" />

          <v-table v-else density="compact" fixed-header height="320" class="sytmdb-table">
            <thead>
              <tr>
                <th style="width: 44px">
                  <v-checkbox :model-value="store.sytmdbSelected.length > 0 &&
                    store.sytmdbSelected.length === store.sytmdbSelectable.length"
                    :indeterminate="store.sytmdbSelected.length > 0 &&
                      store.sytmdbSelected.length < store.sytmdbSelectable.length" density="compact"
                    hide-details @update:model-value="store.toggleSytmdbAll(!!$event)" />
                </th>
                <th>番名</th>
                <th style="width: 100px">TMDB</th>
                <th style="width: 150px">剧集组 / 改动</th>
                <th style="width: 130px">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in store.sytmdbItems" :key="row.tmdb_id">
                <td>
                  <v-checkbox :model-value="store.sytmdbSelected.includes(row.tmdb_id)"
                    :disabled="!row.will_change || (row.existing && !store.sytmdbOverwrite)" density="compact"
                    hide-details @update:model-value="store.toggleSytmdbItem(row.tmdb_id, !!$event)" />
                </td>
                <td>
                  <div class="text-body-2">{{ row.title }}</div>
                  <div class="text-caption text-medium-emphasis">
                    {{ row.year || '—' }}
                    <span v-if="row.specials"> · 含 {{ row.specials }} 集 S0 特别篇</span>
                    <span v-if="row.duplicates"> · {{ row.duplicates }} 处重复集</span>
                  </div>
                </td>
                <td class="font-mono text-caption">{{ row.tmdb_id }}</td>
                <td class="text-caption">
                  <template v-if="row.group_count">
                    {{ row.group_count }} 组 / {{ row.episode_total }} 集
                    <span class="text-medium-emphasis">· 改 {{ row.changed_episodes }} 集</span>
                  </template>
                  <template v-else>无分组</template>
                </td>
                <td>
                  <v-chip v-if="!row.group_count" size="x-small" variant="tonal" color="grey" label>
                    空分组
                  </v-chip>
                  <v-chip v-else-if="!row.will_change" size="x-small" variant="tonal" color="grey" label>
                    无改动
                  </v-chip>
                  <v-chip v-else-if="row.existing" size="x-small" variant="tonal" color="warning" label
                    :title="`已有规则：${row.existing_status || '已存在'}`">
                    已有 · {{ store.originMetaOf(row.existing_origin).short }}
                  </v-chip>
                  <v-chip v-else size="x-small" variant="tonal" color="success" label>可导入</v-chip>
                </td>
              </tr>
              <tr v-if="!store.sytmdbItems.length">
                <td colspan="5" class="text-center text-medium-emphasis text-body-2 pa-6">
                  SYTMDB 上还没有任何剧集组
                </td>
              </tr>
            </tbody>
          </v-table>

          <v-alert v-if="store.sytmdbResult" density="compact" variant="tonal" class="mt-3"
            :color="store.sytmdbResult.failed.length ? 'warning' : 'success'">
            <div class="text-caption">
              导入 {{ store.sytmdbResult.imported }} 条
              <span v-if="store.sytmdbResult.skipped.length">· 跳过 {{ store.sytmdbResult.skipped.length }} 条</span>
              <span v-if="store.sytmdbResult.failed.length">· 失败 {{ store.sytmdbResult.failed.length }} 条</span>
            </div>
            <div v-if="store.sytmdbResult.failed.length" class="text-caption mt-1">
              <div v-for="fail in store.sytmdbResult.failed" :key="fail.tmdb_id">
                TMDB {{ fail.tmdb_id }}：{{ fail.error }}
              </div>
            </div>
            <div v-if="store.sytmdbResult.items.some((i) => i.warnings.length)" class="text-caption mt-1">
              <div v-for="item in store.sytmdbResult.items.filter((i) => i.warnings.length)" :key="item.tmdb_id">
                {{ item.title }}：{{ item.warnings.join('；') }}
              </div>
            </div>
          </v-alert>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <div class="text-caption text-medium-emphasis">
            已选 {{ store.sytmdbSelected.length }} 项
            <span v-if="store.sytmdbSelected.length === store.sytmdbSelectable.length && store.sytmdbSelectable.length">
              （全部）
            </span>
          </div>
          <v-spacer />
          <v-btn variant="text" @click="store.closeSytmdbImport()">关闭</v-btn>
          <v-btn color="primary" :loading="store.sytmdbImporting" :disabled="!store.sytmdbSelected.length"
            prepend-icon="mdi-download" @click="store.runSytmdbImport()">
            开始导入
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>
