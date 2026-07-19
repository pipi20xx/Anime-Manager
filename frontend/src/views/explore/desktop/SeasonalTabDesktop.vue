<script setup lang="ts">
import { computed } from 'vue'
import { NEmpty, NSelect, NTag, NBackTop, NSkeleton } from 'naive-ui'
import {
  ChevronLeftIcon,
  ChevronRightIcon
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

const selectSeason = (s: Season) => {
  selectedSeason.value = s
}
</script>

<template>
  <div class="seasonal-tab">
    <!-- 顶部控制栏：年份导航（季度切换由下方标签完成，避免重复） -->
    <div class="control-bar">
      <button class="nav-arrow" @click="goToPrevSeason" title="上一季">
        <ChevronLeftIcon class="icon" />
      </button>

      <n-select
        v-model:value="selectedYear"
        :options="yearSelectOptions"
        size="small"
        class="year-select"
      />

      <span class="season-count" v-if="!data.loading">{{ data.count }} 部</span>

      <button class="nav-arrow" @click="goToNextSeason" title="下一季">
        <ChevronRightIcon class="icon" />
      </button>

      <button class="current-btn" @click="goToCurrentSeason">本季</button>
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
        {{ SEASON_CN[s] }}番组
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

/* 顶部控制栏：透明工具条，靠左排列，避免卡片包裹导致两边留白 */
.control-bar {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 4px 2px;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}

.nav-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
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

/* 年份下拉：固定宽度，不压缩 */
.year-select {
  width: 120px;
  flex-shrink: 0;
}

.season-count {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  padding: 2px 10px;
  background: color-mix(in srgb, var(--n-primary-color) 10%, transparent);
  border-radius: 999px;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
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
  white-space: nowrap;
  flex-shrink: 0;
}
.current-btn:hover {
  background: var(--n-primary-color);
  color: #fff;
  border-color: var(--n-primary-color);
}

/* 季度标签栏：横向滚动 */
.season-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: var(--space-5);
  padding: 4px 2px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.season-tabs::-webkit-scrollbar { display: none; }
.season-tag {
  cursor: pointer;
  transition: all var(--transition-fast);
  padding: 8px 18px;
  font-size: var(--text-base);
  font-weight: 600;
  flex-shrink: 0;
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

/* ============ 移动端适配 ============ */
@media (max-width: 767px) {
  .control-bar {
    padding: 4px 2px;
    gap: 6px;
  }

  .nav-arrow {
    width: 32px;
    height: 32px;
  }
  .nav-arrow .icon { width: 18px; height: 18px; }

  .year-select {
    width: 112px;
  }

  .season-count {
    font-size: var(--text-xs);
    padding: 1px 8px;
  }

  .current-btn {
    padding: 5px 10px;
    font-size: var(--text-sm);
  }

  .season-tabs {
    gap: 6px;
    margin-bottom: var(--space-4);
  }
  .season-tag {
    padding: 6px 14px;
    font-size: var(--text-sm);
  }
}

/* 超窄屏 (≤380px)：进一步压缩 */
@media (max-width: 380px) {
  .control-bar {
    gap: 4px;
  }
  .year-select {
    width: 104px;
  }
  .current-btn {
    padding: 5px 8px;
  }
}
</style>
