<script setup lang="ts">
/**
 * FontSettingsDialog — 字体管家设置对话框
 *
 * 字体来源 / 字幕处理（模式 + 处理参数） / 内核与网络 三段分组；
 * 目录浏览复用 FolderBrowserModal（由主视图挂载，事件走 store）。
 */
import { EmptyState, DialogTitle } from '@/components/common'
import { useFontManager } from './useFontManager'

defineOptions({ name: 'FontManagerSettingsDialog' })

const {
  modeOptions, configModeDescription,
  showSettings, configLoading, savingConfig, configForm,
  hdrEnabled, verboseItems,
  addExtraLibraryDir, removeExtraLibraryDir, setExtraLibraryDir,
  openSettings, saveSettings, openFolderPicker,
} = useFontManager()
</script>

<template>
  <v-dialog v-model="showSettings" max-width="680" scrollable>
    <v-card class="glass-card">
      <DialogTitle icon="mdi-cog-outline" icon-color="primary" title="字体管家设置" @close="showSettings = false" />
      <v-divider />

      <v-card-text class="pa-4 dialog-scroll-body">
        <v-skeleton-loader v-if="configLoading" type="list-item@6" />

        <template v-else>
          <!-- ── 字体来源 ── -->
          <div class="section-title mb-2">
            <v-icon size="16" color="primary">mdi-folder-outline</v-icon>
            字体来源
          </div>
          <div class="d-flex align-center ga-2 mb-3">
            <v-text-field
              v-model="configForm.library_dir"
              label="字体库目录 (library_dir)"
              variant="outlined"
              density="compact"
              hide-details
              placeholder="存放字体的文件夹，如 /vol1/fonts"
            />
            <v-btn
              variant="tonal"
              color="info"
              prepend-icon="mdi-folder-search-outline"
              @click="openFolderPicker({ type: 'settings-library' })"
            >
              浏览
            </v-btn>
          </div>

          <!-- 额外字体库目录（可增删） -->
          <div class="text-caption text-medium-emphasis mb-1">
            额外字体库目录 (extra_library_dirs)：与主目录一起建立索引、参与缺字体判定
          </div>
          <div
            v-for="(dir, i) in configForm.extra_library_dirs"
            :key="`extra-lib-${i}`"
            class="d-flex align-center ga-2 mb-2"
          >
            <v-text-field
              :model-value="dir"
              variant="outlined"
              density="compact"
              hide-details
              placeholder="额外字体库目录，如 /vol2/fonts"
              @update:model-value="(v: string) => setExtraLibraryDir(i, v)"
            />
            <v-btn
              size="small"
              variant="tonal"
              color="info"
              icon="mdi-folder-search-outline"
              title="选择目录"
              @click="openFolderPicker({ type: 'extra-library', index: i })"
            />
            <v-btn
              size="small"
              variant="text"
              color="error"
              icon="mdi-delete-outline"
              title="删除该目录"
              @click="removeExtraLibraryDir(i)"
            />
          </div>
          <v-btn size="small" variant="tonal" prepend-icon="mdi-plus" class="mb-3" @click="addExtraLibraryDir">
            添加目录
          </v-btn>

          <v-row density="compact" class="mb-1">
            <v-col cols="12" sm="6">
              <v-text-field
                :model-value="configForm.index_dir"
                label="索引目录 (index_dir)"
                variant="outlined"
                density="compact"
                hide-details
                readonly
                placeholder="由后端自动管理"
              />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model="configForm.workspace_dir"
                label="任务工作目录 (workspace_dir)"
                variant="outlined"
                density="compact"
                hide-details
              />
            </v-col>
          </v-row>

          <v-divider class="my-3" />
          <!-- ── 字幕处理（处理模式与重命名/HDR 等处理参数同属一类） ── -->
          <div class="section-title mb-2">
            <v-icon size="16" color="primary">mdi-cog-play-outline</v-icon>
            字幕处理
          </div>
          <v-select
            v-model="configForm.mode"
            :items="modeOptions"
            item-title="label"
            item-value="value"
            label="默认处理模式 (mode)"
            variant="outlined"
            density="compact"
            hide-details
            class="mb-1"
          />
          <div class="text-caption text-medium-emphasis mb-3" style="line-height: 1.4">
            {{ configModeDescription || '模式列表读取中…' }}
          </div>

          <div class="switch-row mb-2">
            <v-switch v-model="configForm.rename_fonts" color="primary" hide-details density="compact" />
            <div>
              <div class="switch-label">重命名字体 (rename_fonts)</div>
              <div class="text-caption text-medium-emphasis">对应 assfonts -r，避免与系统字体冲突</div>
            </div>
          </div>

          <div class="d-flex align-center flex-wrap ga-3 mb-1">
            <div class="switch-row" style="min-width: 240px">
              <v-switch v-model="hdrEnabled" color="primary" hide-details density="compact" />
              <div>
                <div class="switch-label">HDR 亮度压暗 (hdr_luminance)</div>
                <div class="text-caption text-medium-emphasis">关闭 = 0（不处理）</div>
              </div>
            </div>
            <v-text-field
              v-model.number="configForm.hdr_luminance"
              type="number"
              min="0"
              max="1000"
              :disabled="!hdrEnabled"
              variant="outlined"
              density="compact"
              hide-details
              style="max-width: 140px"
            />
          </div>
          <div class="text-caption text-medium-emphasis mb-3">
            对应 assfonts -l，范围 0-1000；开启后默认 203，会给成品名加上 .hdr 后缀
          </div>

          <div class="d-flex align-center ga-2 mb-1">
            <v-text-field
              v-model="configForm.extra_font_dir"
              label="额外字体目录 (-f)"
              variant="outlined"
              density="compact"
              hide-details
              placeholder="留空 = 仅使用字体库"
            />
            <v-btn
              variant="tonal"
              color="info"
              prepend-icon="mdi-folder-search-outline"
              @click="openFolderPicker({ type: 'extra-font' })"
            >
              浏览
            </v-btn>
            <v-btn
              v-if="configForm.extra_font_dir"
              variant="text"
              color="warning"
              icon="mdi-close"
              title="清空"
              @click="configForm.extra_font_dir = ''"
            />
          </div>
          <div class="text-caption text-medium-emphasis mb-3">
            本次处理额外加载的字体目录，用于「仅内嵌」等需要指定字体来源的场景
          </div>

          <div class="d-flex align-center ga-2 mb-1">
            <v-text-field
              v-model="configForm.output_dir"
              label="输出目录 (-o)"
              variant="outlined"
              density="compact"
              hide-details
              placeholder="留空 = 输出到任务工作目录"
            />
            <v-btn
              variant="tonal"
              color="info"
              prepend-icon="mdi-folder-search-outline"
              @click="openFolderPicker({ type: 'output' })"
            >
              浏览
            </v-btn>
            <v-btn
              v-if="configForm.output_dir"
              variant="text"
              color="warning"
              icon="mdi-close"
              title="清空"
              @click="configForm.output_dir = ''"
            />
          </div>
          <div class="text-caption text-medium-emphasis mb-3">
            留空则输出到任务工作目录；开启后所有成品都放这里
          </div>

          <div class="d-flex align-center flex-wrap ga-3 mb-1">
            <v-text-field
              v-model.number="configForm.internal_threads"
              label="内核内部线程数 (-m)"
              type="number"
              min="0"
              max="128"
              variant="outlined"
              density="compact"
              hide-details
              style="max-width: 220px"
            />
            <div class="text-caption text-medium-emphasis">0 = 内核默认，范围 0-128</div>
          </div>
          <div class="text-caption text-medium-emphasis mb-3">
            过大反而会因上下文切换变慢，一般保持 0 即可
          </div>

          <v-select
            v-model="configForm.verbose_level"
            :items="verboseItems"
            label="内核日志级别 (-v)"
            variant="outlined"
            density="compact"
            hide-details
            class="mb-1"
            style="max-width: 340px"
          />
          <div class="text-caption text-medium-emphasis mb-3" style="line-height: 1.4">
            ⚠️ 低于 2 时内核不再输出缺字体提示，系统会自动改用索引比对兜底判定缺失字体
          </div>

          <div class="switch-row mb-2">
            <v-switch v-model="configForm.keep_subset_dir" color="primary" hide-details density="compact" />
            <div>
              <div class="switch-label">保留子集字体文件夹 (keep_subset_dir)</div>
              <div class="text-caption text-medium-emphasis">保留 _subsetted 目录，便于排查缺失字形</div>
            </div>
          </div>

          <div class="switch-row mb-3">
            <v-switch v-model="configForm.delete_source" color="warning" hide-details density="compact" />
            <div>
              <div class="switch-label">成功后删除上传的源字幕副本 (delete_source)</div>
              <div class="text-caption text-medium-emphasis">⚠️ 删除后无法再次重试该任务</div>
            </div>
          </div>

          <v-divider class="my-3" />
          <div class="section-title mb-2">
            <v-icon size="16" color="primary">mdi-cube-outline</v-icon>
            内核与网络
          </div>
          <v-text-field
            v-model="configForm.binary_path"
            label="assfonts 二进制路径 (binary_path)"
            variant="outlined"
            density="compact"
            hide-details
            placeholder="留空 = 自动（data/bin > 镜像内置）"
            class="mb-3"
          />
          <div class="switch-row">
            <v-switch v-model="configForm.proxy_for_update" color="primary" hide-details density="compact" />
            <div>
              <div class="switch-label">更新时走系统代理 (proxy_for_update)</div>
              <div class="text-caption text-medium-emphasis">检查/下载 assfonts 更新时使用系统代理设置</div>
            </div>
          </div>
        </template>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="showSettings = false">取消</v-btn>
        <v-btn
          variant="tonal"
          color="primary"
          prepend-icon="mdi-content-save-outline"
          :loading="savingConfig"
          :disabled="configLoading"
          @click="saveSettings"
        >
          保存设置
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
