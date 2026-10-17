<script setup lang="ts">
/**
 * FontStatusBar — 字体管家顶部状态条（常驻，不随 Tab 切换）
 *
 * assfonts 版本/来源、参数帮助、检查更新、索引状态、字体库路径、
 * 库目录警告、任务统计；「设置」入口也在这里。
 */
import { ref } from 'vue'
import { fontManagerApi } from '@/api'
import type { FontBinaryHelp, FontUpdateInfo, FontManagerConfig } from '@/api/fontManager'
import { useFontManager } from './useFontManager'

defineOptions({ name: 'FontManagerStatusBar' })

const emit = defineEmits<{
  (e: 'open-settings'): void
  (e: 'pick-library'): void
  (e: 'open-help'): void
}>()

const {
  success, showError, warning, showInfo, confirm,
  status, statusLoading, binary, indexInfo, libraryInfo, jobCounts, runOptions,
  libraryPaths, libraryWarnings, hasLibrary, indexReady, effectiveOptionsText,
  tempFontActive, tempFonts,
  fetchStatus, refreshAll, activeTab, fetchFonts, librarySaving,
} = useFontManager()

// ── 索引重建 ──────────────────────────────────────────────
const rebuilding = ref(false)

async function rebuildIndex() {
  rebuilding.value = true
  try {
    const res = await fontManagerApi.rebuildIndex()
    success(res?.message || '字体索引已重建')
    await fetchStatus()
    if (activeTab.value === 'library') await fetchFonts()
  } catch (e: any) {
    showError(e?.message || '索引重建失败')
  } finally {
    rebuilding.value = false
  }
}

// ── 内核更新 ──────────────────────────────────────────────
const checkingUpdate = ref(false)
const applyingUpdate = ref(false)
const updateInfo = ref<FontUpdateInfo | null>(null)

async function checkUpdate() {
  checkingUpdate.value = true
  try {
    const res = await fontManagerApi.checkUpdate()
    const info = res?.data || null
    updateInfo.value = info
    if (info?.error) {
      showError(info.error)
      return
    }
    if (info?.has_update) {
      showInfo(`发现新版本 v${info.latest}，可点击「立即更新」升级内核`)
    } else {
      success(`已是最新版本${info?.current ? ` v${info.current}` : ''}`)
    }
  } catch (e: any) {
    showError(e?.message || '检查更新失败')
  } finally {
    checkingUpdate.value = false
  }
}

async function applyUpdate() {
  const ok = await confirm({
    title: '更新 assfonts 内核',
    content: `将从 GitHub 下载并替换内置 assfonts${
      updateInfo.value?.latest ? `（最新 v${updateInfo.value.latest}）` : ''
    }，下载期间请勿关闭页面。是否继续？`,
    confirmText: '立即更新',
    confirmColor: 'primary',
  })
  if (!ok) return
  applyingUpdate.value = true
  try {
    const res = await fontManagerApi.applyUpdate({})
    const data = res?.data
    if (data && data.success === false) {
      showError(data.message || '更新失败')
      return
    }
    success(data?.message || 'assfonts 内核已更新')
    updateInfo.value = null
    await refreshAll()
  } catch (e: any) {
    showError(e?.message || '更新失败')
  } finally {
    applyingUpdate.value = false
  }
}
</script>

<template>
  <v-card class="glass-card mb-4" variant="flat">
    <v-card-text class="pa-4">
      <div class="d-flex align-center flex-wrap ga-3">
        <v-icon color="primary" size="28">mdi-format-font</v-icon>
        <span class="text-h6 font-weight-medium">字体管家</span>

        <v-chip size="small" variant="tonal" :color="binary?.ready ? 'primary' : 'error'">
          <v-progress-circular v-if="statusLoading && !status" indeterminate size="12" width="2" class="mr-1" />
          {{ binary?.ready ? `assfonts v${binary.version || '未知'}` : 'assfonts 不可用' }}
        </v-chip>
        <v-chip v-if="binary?.source_label" size="small" variant="flat" color="grey">
          {{ binary.source_label }}
        </v-chip>

        <v-chip
          v-if="tempFontActive"
          size="small"
          variant="tonal"
          color="success"
          prepend-icon="mdi-timer-outline"
          title="临时字体池已启用：当前处理会自动把它们作为补充字体源（-f）带上"
        >
          临时字体 {{ tempFonts?.count || 0 }}
        </v-chip>

        <v-btn
          size="small"
          variant="tonal"
          color="info"
          prepend-icon="mdi-cloud-download-outline"
          :loading="checkingUpdate"
          @click="checkUpdate"
        >
          检查更新
        </v-btn>
        <template v-if="updateInfo?.has_update">
          <v-chip size="small" variant="flat" color="success">最新 v{{ updateInfo.latest }}</v-chip>
          <v-btn
            size="small"
            variant="flat"
            color="primary"
            prepend-icon="mdi-download"
            :loading="applyingUpdate"
            @click="applyUpdate"
          >
            立即更新
          </v-btn>
        </template>

        <v-spacer />
        <v-btn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="statusLoading" @click="refreshAll">刷新</v-btn>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-cog-outline" @click="emit('open-settings')">设置</v-btn>
      </div>

      <v-alert
        v-if="applyingUpdate"
        type="info"
        variant="tonal"
        density="compact"
        class="mt-3"
        icon="mdi-progress-download"
      >
        正在下载更新…
      </v-alert>

      <!-- 索引 / 字体库 摘要行 -->
      <div class="d-flex align-center flex-wrap ga-4 mt-3 text-body-2">
        <span class="d-flex align-center ga-1">
          <v-icon size="16" :color="indexReady ? 'success' : 'warning'">mdi-database-outline</v-icon>
          <template v-if="indexReady">
            索引 {{ indexInfo?.count }} 个字体（{{ indexInfo?.built_at || '未知时间' }}）
          </template>
          <template v-else>尚未构建字体索引</template>
        </span>
        <span class="d-flex align-center ga-1" style="min-width: 0">
          <v-icon size="16" :color="hasLibrary ? 'success' : 'error'">mdi-folder-outline</v-icon>
          <span class="text-truncate" :title="libraryPaths.join('\n')">
            字体库：{{ libraryInfo?.path || '未设置' }}
          </span>
          <v-chip
            v-if="libraryPaths.length > 1"
            size="x-small"
            variant="tonal"
            :title="libraryPaths.join('\n')"
          >
            +{{ libraryPaths.length - 1 }} 个额外目录
          </v-chip>
        </span>
        <v-btn
          v-if="hasLibrary"
          size="small"
          variant="tonal"
          :color="indexReady ? undefined : 'warning'"
          prepend-icon="mdi-refresh"
          :loading="rebuilding"
          @click="rebuildIndex"
        >
          重建索引
        </v-btn>
        <v-chip
          v-if="runOptions"
          size="x-small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-tune"
          :title="effectiveOptionsText"
        >
          生效：{{ runOptions.mode_label }}
        </v-chip>
      </div>

      <!-- 红条：未设置字体库 -->
      <v-alert
        v-if="!hasLibrary"
        type="error"
        variant="tonal"
        density="compact"
        class="mt-3"
        icon="mdi-folder-alert-outline"
      >
        {{ libraryInfo?.message || '尚未选择字体库文件夹，无法进行字体子集化。' }}
        <template #append>
          <v-btn size="small" color="error" variant="flat" :loading="librarySaving" @click="emit('pick-library')">
            选择文件夹
          </v-btn>
        </template>
      </v-alert>
      <!-- 黄条：索引未构建 -->
      <v-alert
        v-else-if="!indexReady"
        type="warning"
        variant="tonal"
        density="compact"
        class="mt-3"
        icon="mdi-alert-outline"
      >
        字体索引尚未构建（或索引为空），子集化前需要先建立索引。
        <template #append>
          <v-btn size="small" color="warning" variant="flat" :loading="rebuilding" @click="rebuildIndex">重建索引</v-btn>
        </template>
      </v-alert>

      <v-alert
        v-if="binary && !binary.ready"
        type="error"
        variant="tonal"
        density="compact"
        class="mt-3"
        icon="mdi-alert-circle-outline"
      >
        {{ binary.message || 'assfonts 二进制不可用，请检查设置或尝试一键更新' }}
      </v-alert>
      <div v-if="indexInfo?.error" class="text-caption text-error mt-2">{{ indexInfo.error }}</div>

      <!-- 字体库 / 输出目录等警告 -->
      <v-alert
        v-for="(w, i) in libraryWarnings"
        :key="`lib-warn-${i}`"
        type="warning"
        variant="tonal"
        density="compact"
        class="mt-3"
        icon="mdi-alert-outline"
      >
        {{ w }}
      </v-alert>

      <!-- 任务统计 -->
      <div class="d-flex flex-wrap ga-2 mt-3">
        <v-chip size="x-small" variant="tonal">共 {{ jobCounts?.total || 0 }}</v-chip>
        <v-chip size="x-small" variant="flat" color="grey">待处理 {{ jobCounts?.pending || 0 }}</v-chip>
        <v-chip size="x-small" variant="flat" color="info">处理中 {{ jobCounts?.running || 0 }}</v-chip>
        <v-chip size="x-small" variant="flat" color="success">已完成 {{ jobCounts?.success || 0 }}</v-chip>
        <v-chip size="x-small" variant="flat" color="warning">缺字体 {{ jobCounts?.missing || 0 }}</v-chip>
        <v-chip size="x-small" variant="flat" color="error">失败 {{ jobCounts?.failed || 0 }}</v-chip>
        <v-chip v-if="jobCounts?.skipped" size="x-small" variant="flat" color="grey">已跳过 {{ jobCounts.skipped }}</v-chip>
      </div>
    </v-card-text>
  </v-card>
</template>
