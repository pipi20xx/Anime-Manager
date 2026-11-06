<script setup lang="ts">
/**
 * AdvancedTab — 番剧分季「高级」子 Tab（默认参数 / 参照门槛 / 黑名单 / 调试器）
 */
import { useSeasonSplitStore } from '@/stores'

defineOptions({ name: 'AdvancedTab' })

const store = useSeasonSplitStore()
</script>

<template>
  <div>
    <div class="d-flex align-center ga-2 mb-4">
      <span class="section-title">高级设置</span>
      <v-spacer />
      <v-btn color="primary" variant="tonal" prepend-icon="mdi-content-save" @click="store.saveAdvanced">
        保存设置
      </v-btn>
    </div>
    <v-row>
      <v-col cols="12" md="6">
        <v-card class="glass-card mb-4">
          <v-card-title class="text-subtitle-2">默认参数</v-card-title>
          <v-divider />
          <div class="pa-3 d-flex flex-column ga-3">
            <v-select
              v-model="store.settings.priority"
              :items="store.priorityOptions"
              label="参照优先级（只决定默认选中哪个）"
              density="compact"
              variant="outlined"
              hide-details
            />
            <div class="d-flex flex-wrap ga-4">
              <v-switch
                v-model="store.settings.use_source"
                label="启用 CureTMDb 规则表"
                density="compact"
                hide-details
                color="primary"
              />
              <v-switch
                v-model="store.settings.force_reference"
                label="强制参照（跳过「日本动画 + 季数 1~2」门槛）"
                density="compact"
                hide-details
                color="primary"
              />
              <v-switch
                v-model="store.settings.use_includes_rules"
                label="使用 includes 年份渲染词"
                density="compact"
                hide-details
                color="primary"
              />
            </div>
            <div class="text-caption text-medium-emphasis">
              includes 渲染词按虚拟季首播年份做文件名包含匹配（例：<code>includes=2016</code>）；关闭后只生成集号/季号规则。
            </div>
            <v-text-field
              v-model="store.settings.source"
              label="CureTMDb 规则表地址（留空 = 不使用）"
              density="compact"
              variant="outlined"
              hide-details
            />
            <div class="text-caption text-medium-emphasis">
              规则表命中会直接作为分季定义；留空时「生成方案」里勾了也不会去拉取。
            </div>
            <v-text-field
              v-model.number="store.settings.gap_days"
              type="number"
              label="间隔切分阈值（天）"
              density="compact"
              variant="outlined"
              hide-details
            />
            <div class="text-caption text-medium-emphasis">
              「播出间隔」作为切分依据时，相邻两集首播日期相差超过这个天数就切一刀。默认 45 天。
            </div>
            <div class="d-flex flex-wrap align-center ga-2">
              <v-chip size="small" :color="store.settings.tvdb_key_configured ? 'success' : 'grey'" variant="tonal">
                TVDB Key：{{ store.settings.tvdb_key_configured ? '已自定义' : '官方共用 Key' }}
              </v-chip>
              <v-text-field
                v-model="store.tvdbInput"
                label="覆盖为自己申请的 Key（可选）"
                density="compact"
                variant="outlined"
                hide-details
                type="password"
                style="max-width: 320px"
              />
              <v-btn variant="tonal" @click="store.saveTvdbKey">保存</v-btn>
            </div>
          </div>
        </v-card>

        <v-card class="glass-card mb-4">
          <v-card-title class="text-subtitle-2 d-flex align-center">
            参照门槛与自动生成
            <v-spacer />
            <v-btn size="small" variant="text" prepend-icon="mdi-restore" @click="store.resetReferenceDefaults">
              恢复默认
            </v-btn>
          </v-card-title>
          <v-divider />
          <div class="pa-3 d-flex flex-column ga-3">
            <div class="text-caption text-medium-emphasis">
              自动拉取 TVDB / Bangumi 时的门槛（未开「强制参照」时生效）；列表留空表示不限制该项。
            </div>
            <v-text-field
              v-model="store.refGenreIdsText"
              label="动画类型（TMDB genre id，逗号分隔）"
              density="compact"
              variant="outlined"
              hide-details
            />
            <v-text-field
              v-model="store.refCountriesText"
              label="出品国家（ISO 代码，逗号分隔）"
              density="compact"
              variant="outlined"
              hide-details
            />
            <div class="d-flex ga-2">
              <v-text-field
                v-model.number="store.settings.ref_season_min"
                type="number"
                label="有效季数下限"
                density="compact"
                variant="outlined"
                hide-details
              />
              <v-text-field
                v-model.number="store.settings.ref_season_max"
                type="number"
                label="有效季数上限"
                density="compact"
                variant="outlined"
                hide-details
              />
            </div>
            <v-text-field
              v-model="store.fixedSizesText"
              label="固定集数兜底（每季集数，逗号分隔）"
              density="compact"
              variant="outlined"
              hide-details
            />
            <v-text-field
              v-model.number="store.settings.gap_mark_days"
              type="number"
              label="间隔虚线显示阈值（天）"
              density="compact"
              variant="outlined"
              hide-details
            />
            <div class="text-caption text-medium-emphasis">
              固定集数兜底会出现在右侧「自动生成」里；间隔虚线阈值只影响原始季列表的虚线显示，不影响切分。
            </div>
          </div>
        </v-card>

        <v-card class="glass-card">
          <v-card-title class="text-subtitle-2">番剧黑名单</v-card-title>
          <v-divider />
          <div class="pa-3 d-flex flex-column ga-2">
            <div class="text-caption text-medium-emphasis">黑名单里的番永远不会套用分季规则（规则可保留）。</div>
            <div class="d-flex flex-wrap ga-2">
              <v-chip
                v-for="(id, i) in store.settings.blacklist"
                :key="id"
                size="small"
                closable
                variant="tonal"
                @click:close="store.settings.blacklist.splice(i, 1)"
              >
                {{ id }}
              </v-chip>
              <span v-if="!store.settings.blacklist.length" class="text-caption">（空）</span>
            </div>
            <div class="d-flex ga-2">
              <v-text-field
                v-model="store.blacklistInput"
                label="添加 TMDB ID"
                density="compact"
                variant="outlined"
                hide-details
                style="max-width: 200px"
                @keyup.enter="store.addBlacklist"
              />
              <v-btn variant="tonal" @click="store.addBlacklist">添加</v-btn>
            </div>
          </div>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card class="glass-card">
          <v-card-title class="text-subtitle-2">映射调试器</v-card-title>
          <v-divider />
          <div class="pa-3 d-flex flex-column ga-3">
            <div class="text-caption text-medium-emphasis">
              输入该番已保存规则里的一集原始坐标，回放规则看会被改成什么；填文件名可验证「年份 includes」规则是否命中。
            </div>
            <div class="d-flex flex-wrap ga-2">
              <v-text-field v-model="store.debugForm.tmdb_id" label="TMDB ID" density="compact" variant="outlined" hide-details style="max-width: 140px" />
              <v-text-field v-model.number="store.debugForm.season" type="number" label="季" density="compact" variant="outlined" hide-details style="max-width: 100px" />
              <v-text-field v-model.number="store.debugForm.episode" type="number" label="集" density="compact" variant="outlined" hide-details style="max-width: 100px" />
              <v-btn variant="tonal" @click="store.runDebug">回放</v-btn>
            </div>
            <v-text-field
              v-model="store.debugForm.filename"
              label="文件名（可选，用于验证 includes 年份规则）"
              density="compact"
              variant="outlined"
              hide-details
            />
            <v-alert v-if="store.debugResult" :type="store.debugResult.changed ? 'success' : 'info'" variant="tonal" density="compact">
              S{{ store.debugResult.from[0] }}E{{ store.debugResult.from[1] }}
              →
              S{{ store.debugResult.to[0] }}E{{ store.debugResult.to[1] }}
              （状态 {{ store.debugResult.rule_status }}，依据 {{ store.labelOf(store.debugResult.reference) }}）
            </v-alert>
            <pre v-if="store.debugResult" class="code-block">{{ store.debugResult.render_words }}</pre>
          </div>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>
