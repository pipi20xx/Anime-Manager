<script setup lang="ts">
/**
 * BlacklistTab — 番剧分季「黑名单」子 Tab
 *
 * 名称 / 年份 / 海报来自项目内永久缓存与数据中心的元数据资产（MetaCacheManager），
 * 不联网。卡片式展示，方便查看与移除。
 */
import { onMounted } from 'vue'
import { getImg } from '@/composables'
import { useSeasonSplitStore } from '@/stores'

defineOptions({ name: 'BlacklistTab' })

const store = useSeasonSplitStore()

onMounted(() => {
  store.loadBlacklistMeta()
})
</script>

<template>
  <div>
    <div class="d-flex ga-2 mb-4 flex-wrap align-center">
      <span class="section-title">番剧黑名单</span>
      <v-chip size="small" variant="tonal" color="grey" label>{{ store.blacklistItems.length }} 个</v-chip>
      <v-spacer />
      <v-text-field
        v-model="store.blacklistInput"
        label="添加 TMDB ID"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width: 200px"
        @keyup.enter="store.addBlacklist"
      />
      <v-btn variant="tonal" color="primary" prepend-icon="mdi-plus" @click="store.addBlacklist">添加</v-btn>
      <v-btn variant="text" prepend-icon="mdi-refresh" @click="store.loadBlacklistMeta">刷新</v-btn>
    </div>

    <div class="text-caption text-medium-emphasis mb-3 px-1">
      黑名单里的番永远不会套用分季规则。开启「自动生成规则」后，判定无需拆分的番会自动加进来；
      名称与海报读取自本地永久缓存 / 数据中心元数据资产，不联网，查不到就显示「未收录」。
    </div>

    <v-skeleton-loader v-if="store.blacklistLoading" type="card@3" />

    <div v-else-if="store.blacklistItems.length" class="card-grid">
      <v-card v-for="item in store.blacklistItems" :key="item.tmdb_id" class="glass-card manage-card">
        <div class="manage-card__header">
          <div class="manage-card__title" :title="item.title || `TMDB ${item.tmdb_id}`">
            {{ item.title || `TMDB ${item.tmdb_id}` }}
          </div>
          <v-chip
            class="manage-card__badge"
            size="x-small"
            :color="item.has_meta ? 'success' : 'warning'"
            variant="tonal"
            label
          >
            {{ item.has_meta ? (item.is_custom ? '已收录 · 固定名' : '已收录') : '未收录' }}
          </v-chip>
        </div>

        <div class="manage-card__body">
          <div class="d-flex ga-3 align-start">
            <v-img
              v-if="item.poster_path"
              :src="getImg(item.poster_path)"
              width="52"
              height="78"
              cover
              class="rounded flex-shrink-0"
            />
            <div
              v-else
              class="flex-shrink-0 d-flex align-center justify-center rounded bg-grey-lighten-3"
              style="width: 52px; height: 78px"
            >
              <v-icon color="grey">mdi-television-classic</v-icon>
            </div>

            <div class="flex-grow-1 d-flex flex-column ga-1 min-width-0">
              <div class="manage-card__info">
                <span class="manage-card__info-label">TMDB</span>
                <span class="manage-card__info-value font-mono">{{ item.tmdb_id }}</span>
              </div>
              <div class="manage-card__info">
                <span class="manage-card__info-label">年份</span>
                <span class="manage-card__info-value">{{ item.year || '—' }}</span>
              </div>
              <div class="manage-card__info">
                <span class="manage-card__info-label">来源</span>
                <span class="manage-card__info-value">
                  {{ item.has_meta ? '永久缓存 / 数据中心' : '未收录（仅显示 ID）' }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <v-card-actions class="manage-card__actions">
          <v-spacer />
          <v-btn
            size="small"
            variant="tonal"
            color="error"
            prepend-icon="mdi-delete-outline"
            @click="store.removeBlacklist(item.tmdb_id)"
          >
            移出黑名单
          </v-btn>
        </v-card-actions>
      </v-card>
    </div>

    <v-card v-else class="glass-card">
      <div class="empty-state">
        <v-icon size="40" color="grey" class="mb-2">mdi-shield-off-outline</v-icon>
        <div class="text-body-2 text-medium-emphasis">
          黑名单是空的。上方输入 TMDB ID 手动添加，或等「自动生成规则」判定后自动加入。
        </div>
      </div>
    </v-card>
  </div>
</template>
