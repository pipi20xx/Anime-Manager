<script setup lang="ts">
import RecognitionFinalCard from '../RecognitionFinalCard.vue'
import RecognitionRawCard from '../RecognitionRawCard.vue'
import RecognitionTmdbCard from '../RecognitionTmdbCard.vue'
</script>

<template>
  <div class="results-wrapper-mobile">
    <RecognitionFinalCard />
    <RecognitionRawCard />
    <RecognitionTmdbCard />
  </div>
</template>

<style scoped>
.results-wrapper-mobile { display: flex; flex-direction: column; gap: 12px; }
</style>