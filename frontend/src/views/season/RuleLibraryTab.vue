<script setup lang="ts">
/**
 * RuleLibraryTab — 番剧分季「规则库」子 Tab
 */
import { useSeasonSplitStore } from '@/stores'

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
      <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="store.loading" @click="store.loadRules">刷新</v-btn>
      <v-btn color="primary" variant="tonal" prepend-icon="mdi-plus" @click="store.activeTab = 'workbench'">
        新建分季
      </v-btn>
    </div>

    <div class="text-caption text-medium-emphasis mb-3 px-1">
      共 {{ store.rules.length }} 条。只有状态为 <b>生效</b> 的规则会被注入识别；草稿/停用只是保存着不动。
      规则是唯一来源——不会自动从别处生成，也不会自动导入规则表。
    </div>

    <v-skeleton-loader v-if="store.loading && !store.rules.length" type="card@3" />

    <div v-else-if="store.rules.length" class="card-grid">
      <v-card v-for="rule in store.rules" :key="rule.tmdb_id" class="glass-card manage-card">
        <div class="manage-card__header">
          <div class="manage-card__title" :title="rule.title">{{ rule.title }}</div>
          <v-chip class="manage-card__badge" size="x-small" :color="store.statusOf(rule).color" variant="tonal" label>
            {{ store.statusOf(rule).label }}
          </v-chip>
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
  </div>
</template>
