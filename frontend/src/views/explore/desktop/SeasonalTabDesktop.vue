<script setup lang="ts">
import { computed } from 'vue'
import { NEmpty, NSelect, NTag, NBackTop, NSkeleton } from 'naive-ui'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  CalendarDaysIcon
} from '@heroicons/vue/24/outline'
import BangumiCard from '../../../components/BangumiCard.vue'
import { useSeasonal, type Season } from '../../../composables/explore/useSeasonal'

const {
  SEASONS,
  SEASON_CN,
  selectedYear,
  selectedSeason,
  data,
  yearOptions,
  goToPrevSeason,
  goToNextSeason,
  goToCurrentSeason,
  isSubscribed,
  openBangumi
} = useSeasonal()

// 年份下拉选项
const yearSelectOptions = computed(() =>
  yearOptions.value.map(y => ({ label: `${y} 年`, value: y }))
)

// 标题
const headerTitle = computed(
  () => `${selectedYear.value} 年 ${SEASON_CN[selectedSeason.value]}新番`
)

const selectSeason = (s: Season) => {
  selectedSeason.value = s
}
</script>

<template>
  <div class="seasonal-tab">
    <!-- 顶部控制栏：年份选择 + 季度切换 + 季度导航 -->
    <div class="control-bar">
      <div class="control-left">
        <button class="nav-arrow" @click="goToPrevSeason" title="上一季">
          <ChevronLeftIcon class="icon" />
        </button>

        <div class="season-display">
          <CalendarDaysIcon class="icon cal-icon" />
          <span class="season-title">{{ headerTitle }}</span>
          <span class="season-count" v-if="!data.loading">{{ data.count }} 部</span>
        </div>

        <button class="nav-arrow" @click="goToNextSeason" title="下一季">
          <ChevronRightIcon class="icon" />
        </button>

        <button class="current-btn" @click="goToCurrentSeason">本季</button>
      </div>

      <div class="control-right">
        <n-select
          v-model:value="selectedYear"
          :options="yearSelectOptions"
          size="small"
          style="width: 120px"
        />
      </div>
    </div>

    <!-- 季度选择标签 -->
    <div class="season-tabs">
      <n-tag
        v-for="s in SEASONS"
        :key="s"
        checkable
        :checked="selectedSeason === s"
        @click="selectSeason(s as Season)"
        class="season-tag"
        :type="selectedSeason === s ? 'primary' : 'default'"
      >
        {{ SEASON_CN[s] }}新番
      </n-tag>
    </div>

    <!-- 内容区 -->
    <div class="content-area">
      <!-- 加载占位 -->
      <div v-if="data.loading && data.items.length === 0" class="skeleton-grid">
        <n-skeleton v-for="i in 12" :key="i" class="skeleton-card" />
      </div>

      <!-- 空结果 -->
      <div v-else-if="data.items.length === 0" class="empty-state">
        <n-empty description="该季度暂无番剧数据" size="large" />
      </div>

      <!-- 平铺网格展示 -->
      <div v-else class="media-grid">
        <BangumiCard
          v-for="item in data.items"
          :key="item.id"
          :item="item"
          :is-subscribed="isSubscribed(item)"
          @click="openBangumi(item)"
        />
      </div>
    </div>

    <n-back-top :right="40" :bottom="40" />
  </div>
</template>

<style scoped>
.seasonal-tab {
  width: 100%;
  min-height: 80vh;
  display: flex;
  flex-direction: column;
}

/* 顶部控制栏 */
.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--app-surface-card-mixed);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-light);
  margin-bottom: var(--space-3);
}

.control-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nav-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.nav-arrow:hover {
  background: color-mix(in srgb, var(--n-primary-color) 12%, transparent);
  color: var(--n-primary-color);
  border-color: var(--n-primary-color);
}
.nav-arrow .icon { width: 20px; height: 20px; }

.season-display {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
}
.cal-icon { width: 20px; height: 20px; color: var(--n-primary-color); }
.season-title {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
}
.season-count {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  padding: 2px 10px;
  background: color-mix(in srgb, var(--n-primary-color) 10%, transparent);
  border-radius: 999px;
  font-weight: 600;
}

.current-btn {
  padding: 6px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.current-btn:hover {
  background: var(--n-primary-color);
  color: #fff;
  border-color: var(--n-primary-color);
}

/* 季度标签栏 */
.season-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: var(--space-5);
  padding: 4px 2px;
  flex-wrap: wrap;
}
.season-tag {
  cursor: pointer;
  transition: all var(--transition-fast);
  padding: 8px 18px;
  font-size: var(--text-base);
  font-weight: 600;
}

/* 内容区 */
.content-area { flex: 1; }

.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--space-5);
}
.skeleton-card { height: 210px; border-radius: var(--radius-xl); }

.empty-state { padding: 80px; }

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--space-5);
}
</style>
