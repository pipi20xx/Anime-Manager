<script setup lang="ts">
/**
 * RecognitionResult - 统一识别结果展示
 *
 * 通过 CSS 媒体查询自动适配:
 * - 桌面: FinalCard 在上, RawCard + TmdbCard 并排, RulesCard 在下
 * - 移动: 卡片纵向堆叠
 */
import { NEmpty } from 'naive-ui'
import { recognitionState } from '../store/recognitionStore'
import RecognitionFinalCard from './RecognitionFinalCard.vue'
import RecognitionRawCard from './RecognitionRawCard.vue'
import RecognitionTmdbCard from './RecognitionTmdbCard.vue'
import RecognitionRulesCard from './RecognitionRulesCard.vue'
</script>

<template>
  <div class="recognition-result-container">
    <div v-if="!recognitionState.data" class="empty-state">
      <n-empty description="暂无识别结果，请在上方输入文件名开始解析" />
    </div>

    <div v-else class="results-wrapper">
      <RecognitionFinalCard />
      <div class="sub-cards-layout">
        <RecognitionRawCard />
        <RecognitionTmdbCard />
      </div>
      <RecognitionRulesCard />
    </div>
  </div>
</template>

<style scoped>
.recognition-result-container {
  width: 100%;
  margin-top: var(--space-3);
}

.empty-state {
  padding: 60px 0;
}

.results-wrapper {
  display: flex;
  flex-direction: column;
  gap: var(--rsp-grid-gap);
}

/* 移动端: 子卡片纵向堆叠 (默认) */
.sub-cards-layout {
  display: flex;
  flex-direction: column;
  gap: var(--rsp-grid-gap);
}

/* 桌面端: RawCard 和 TmdbCard 并排 */
@media (min-width: 768px) {
  .sub-cards-layout {
    flex-direction: row;
  }
}
</style>
