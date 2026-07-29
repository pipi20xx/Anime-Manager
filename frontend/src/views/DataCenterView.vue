<script setup lang="ts">
/**
 * DataCenterView — 数据中心 (骨架)
 *
 * 仅负责 Tab 切换，各功能模块拆分至子组件:
 * - MetadataTab: 元数据资产
 * - RulesTab: 二级分类规则
 * - MappingTab: ID映射管理
 * - SqlLabTab: SQL 实验室
 * - EngineConfigTab: 引擎配置
 * - MaintenanceTab: 维护中心
 */
import { ref } from 'vue'
import MetadataTab from './datacenter/MetadataTab.vue'
import RulesTab from './datacenter/RulesTab.vue'
import MappingTab from './datacenter/MappingTab.vue'
import SqlLabTab from './datacenter/SqlLabTab.vue'
import EngineConfigTab from './datacenter/EngineConfigTab.vue'
import MaintenanceTab from './datacenter/MaintenanceTab.vue'

defineOptions({ name: 'DataCenterView' })

const activeTab = ref('metadata')
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 页面头部 -->
    <div class="app-page-header mb-6">
      <div>
        <h1 class="text-h5 font-weight-bold">数据中心</h1>
        <div class="text-body-2 text-medium-emphasis mt-1">高性能 PostgreSQL 引擎与超级元数据资产管理</div>
      </div>
    </div>

    <!-- 标签切换 -->
    <v-tabs v-model="activeTab" color="primary" class="sticky-tabs">
      <v-tab value="metadata"><v-icon start size="18">mdi-image-multiple-outline</v-icon>元数据资产</v-tab>
      <v-tab value="rules"><v-icon start size="18">mdi-tag-multiple-outline</v-icon>二级分类规则</v-tab>
      <v-tab value="mapping"><v-icon start size="18">mdi-swap-horizontal</v-icon>ID映射管理</v-tab>
      <v-tab value="sqllab"><v-icon start size="18">mdi-code-braces</v-icon>SQL 实验室</v-tab>
      <v-tab value="dbconfig"><v-icon start size="18">mdi-database-cog-outline</v-icon>引擎配置</v-tab>
      <v-tab value="maintenance"><v-icon start size="18">mdi-wrench-outline</v-icon>维护中心</v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <v-window-item value="metadata"><MetadataTab /></v-window-item>
      <v-window-item value="rules"><RulesTab /></v-window-item>
      <v-window-item value="mapping"><MappingTab /></v-window-item>
      <v-window-item value="sqllab"><SqlLabTab /></v-window-item>
      <v-window-item value="dbconfig"><EngineConfigTab /></v-window-item>
      <v-window-item value="maintenance"><MaintenanceTab /></v-window-item>
    </v-window>
  </v-container>
</template>
