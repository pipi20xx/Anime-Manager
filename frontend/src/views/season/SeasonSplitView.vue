<script setup lang="ts">
/**
 * SeasonSplitView — 番剧分季 (骨架)
 *
 * 仅负责顶部状态条 / 帮助说明 / Tab 切换，各功能模块拆分至子组件:
 * - RuleLibraryTab: 规则库
 * - WorkbenchTab: 分组工作台
 * - AdvancedTab: 高级（默认参数 / 参照门槛 / 黑名单 / 调试器）
 *
 * 共享状态由 useSeasonSplitStore 统一管理。
 */
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useDynamicHeaderTab } from '@/composables/useDynamicHeaderTab'
import { useSeasonSplitStore } from '@/stores'
import RuleLibraryTab from './RuleLibraryTab.vue'
import WorkbenchTab from './WorkbenchTab.vue'
import AdvancedTab from './AdvancedTab.vue'

defineOptions({ name: 'SeasonSplitView' })

const store = useSeasonSplitStore()
const { activeTab } = storeToRefs(store)

// 注册动态顶栏 Tab
const { registerHeaderTab } = useDynamicHeaderTab()
registerHeaderTab({
  items: [
    { title: '规则库', icon: 'mdi-format-list-bulleted', tab: 'library' },
    { title: '分组工作台', icon: 'mdi-vector-polyline-edit', tab: 'workbench' },
    { title: '高级', icon: 'mdi-tune-variant', tab: 'advanced' },
  ],
  modelValue: activeTab,
})

onMounted(() => {
  store.init()
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <!-- 顶部状态条 -->
    <v-card class="glass-card mb-4">
      <div class="d-flex flex-wrap align-center ga-3 pa-3">
        <v-btn-toggle
          v-model="store.settings.mode"
          mandatory
          divided
          density="compact"
          variant="outlined"
          @update:model-value="store.saveSettings"
        >
          <v-btn value="off" size="small" prepend-icon="mdi-power">关闭</v-btn>
          <v-btn value="preview" size="small" prepend-icon="mdi-eye-outline">只预览</v-btn>
          <v-btn value="on" size="small" prepend-icon="mdi-check-circle-outline">启用</v-btn>
        </v-btn-toggle>
        <v-chip :color="store.modeColor" size="small" variant="tonal" label>{{ store.modeLabel }}</v-chip>

        <v-divider vertical class="mx-1" />

        <v-switch
          v-model="store.settings.scope.organize"
          label="整理"
          density="compact"
          hide-details
          color="primary"
          @update:model-value="store.saveSettings"
        />
        <v-switch
          v-model="store.settings.scope.subscription"
          label="订阅匹配"
          density="compact"
          hide-details
          color="primary"
          @update:model-value="store.saveSettings"
        />
        <v-switch
          v-model="store.settings.scope.recognition_test"
          label="识别测试"
          density="compact"
          hide-details
          color="primary"
          @update:model-value="store.saveSettings"
        />

        <v-spacer />
        <v-chip size="small" variant="tonal" prepend-icon="mdi-format-list-bulleted">
          生效规则 {{ store.settings.cache.count }}
        </v-chip>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-refresh" @click="store.reloadCache">重载缓存</v-btn>
      </div>
      <v-alert v-if="store.settings.mode === 'preview'" type="warning" variant="tonal" density="compact" class="mx-3 mb-3">
        只预览模式：规则不会注入识别流程，整理结果仍按 TMDB 原始季号。确认方案无误后切到「启用」。
      </v-alert>
    </v-card>

    <v-expansion-panels variant="accordion" flat class="mb-4">
      <v-expansion-panel>
        <v-expansion-panel-title class="text-body-2">
          <v-icon start size="small" color="primary">mdi-help-circle-outline</v-icon>
          这个功能怎么工作（拆分流程 · 生效方式 · 与渲染词的关系）
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="text-body-2 mb-2">
            把 TMDB 合并成一季的番（例如 S1 共 36 集）拆回「第 1 季 / 第 2 季…」，产出两样东西：
          </div>
          <ul class="text-body-2 pl-5 mb-3">
            <li><b>渲染词</b>：交给识别引擎在最后一步执行，改写整理用的季集号（→ <code>Season 2/S02E01</code>）</li>
            <li><b>剧集组 JSON</b>：点「写 SYTMDB」推送，让 Emby 按多季显示</li>
          </ul>

          <div class="section-title mb-1">拆分流程</div>
          <ol class="text-body-2 pl-5 mb-3">
            <li>规则表（高级里启用时）命中该 TMDB ID → 出一套候选</li>
            <li>TVDB、Bangumi <b>各出一套候选</b>（默认只对「日本动画且有效季数 1~2」，高级里可强制）</li>
            <li>三套候选并列在右侧「自动生成」里，可逐个切换对比；「参照优先级」只决定默认选中哪一个</li>
            <li>仅当某套参照的集数 &lt; TMDB 实际集数，才认为这套「需要拆分」（列表上方 chip 会标出来）</li>
            <li>拉全原始季 → 同日跨季去重 → 按播出日期摊平</li>
            <li>按选定定义逐季重灌：集号从 1 重排，切出虚拟季</li>
            <li>编译成渲染词 + 剧集组；没有参照时可用「播出间隔 / 年份 / finale / 固定集数」自动分组</li>
            <li>保存为「生效」后整理时自动套用；Emby 显示还要另外点「写 SYTMDB」</li>
          </ol>

          <div class="section-title mb-1">执行顺序</div>
          <div class="text-body-2 mb-3">
            你自己的「自定义渲染词」先执行 → 分季规则最后执行。两者冲突时以分季结果为准；
            要否决某番，用黑名单或直接在分组里改，不要靠再写一条规则盖回去。
          </div>

          <v-alert type="info" variant="tonal" density="compact">
            规则只在<b>识别最后一步</b>生效：识别结果里的季集号已经是拆分后的编号，
            因此 Emby 存在性检查、改名模板 <code>{'{season}'}/{'{episode}'}</code>、整理历史、STRM、通知都用同一套编号。
          </v-alert>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <div>
      <RuleLibraryTab v-if="store.activeTab === 'library'" />
      <WorkbenchTab v-else-if="store.activeTab === 'workbench'" />
      <AdvancedTab v-else-if="store.activeTab === 'advanced'" />
    </div>
  </v-container>
</template>
