<script setup lang="ts">
import RecognitionFinalCard from '../RecognitionFinalCard.vue'
import RecognitionRawCard from '../RecognitionRawCard.vue'
import RecognitionTmdbCard from '../RecognitionTmdbCard.vue'
</script>

<template>
  <div class="results-wrapper">
    <RecognitionFinalCard />
    <div class="sub-cards-layout">
      <RecognitionRawCard />
      <RecognitionTmdbCard />
    </div>
  </div>
</template>

<style scoped>
.results-wrapper { display: flex; flex-direction: column; gap: 16px; }
.sub-cards-layout { display: flex; gap: 16px; }
</style>