<script setup lang="ts">
/**
 * FontHelpDialog — 内核参数帮助对话框
 *
 * 内核 -h 原文 + 内核参数 → 本页位置对照表。
 */
import { ref, computed } from 'vue'
import { fontManagerApi } from '@/api'
import type { FontBinaryHelp } from '@/api/fontManager'
import { useClipboard } from '@/composables'
import { DialogTitle } from '@/components/common'
import { useFontManager } from './useFontManager'

defineOptions({ name: 'FontManagerHelpDialog' })

const { copy } = useClipboard()
const { showError, binary } = useFontManager()

const showHelpDialog = ref(false)
const helpLoading = ref(false)
const helpError = ref('')
const binaryHelp = ref<FontBinaryHelp | null>(null)

/** 对话框标题里的内核版本/来源（帮助尚未加载时退回状态条数据） */
const helpVersionText = computed(
  () => binaryHelp.value?.version || binary.value?.version || '未知',
)
const helpSourceText = computed(
  () => binaryHelp.value?.source_label || binary.value?.source_label || '未知来源',
)

/** 静态对照表：内核参数 → 本页位置 */
interface KernelArgMapRow {
  arg: string
  desc: string
  where: string
}

const KERNEL_ARG_MAP: KernelArgMapRow[] = [
  { arg: '-i, --input', desc: '输入字幕', where: '拖拽 / 选择文件上传' },
  { arg: '-o, --output', desc: '输出目录', where: '设置 → 字幕处理 → 输出目录' },
  { arg: '-f, --fontpath', desc: '字体目录', where: '设置 → 字体来源（主库 / 额外库）+ 字幕处理 → 额外字体目录' },
  { arg: '-b, --build', desc: '建立字体索引', where: '顶部「重建索引」' },
  { arg: '-d, --dbpath', desc: '索引存放目录', where: '设置 → 字体来源 → 索引目录' },
  { arg: '-s, --subset-only', desc: '仅子集化字体', where: '处理模式 → 仅子集化字体' },
  { arg: '-e, --embed-only', desc: '仅嵌入字体', where: '处理模式 → 仅内嵌字体' },
  { arg: '-r, --rename', desc: '重命名子集化字体', where: '设置 → 字幕处理 → 重命名字体' },
  { arg: '-l, --luminance', desc: 'HDR 亮度', where: '设置 → 字幕处理 → HDR 亮度' },
  { arg: '-m, --multi-thread', desc: '内部线程数', where: '设置 → 字幕处理 → 内核线程数' },
  { arg: '-c, --font-combined', desc: '合并同名字体', where: '处理模式 → 合并子集化（两阶段）' },
  { arg: '-v, --verbose', desc: '日志级别', where: '设置 → 字幕处理 → 内核日志级别' },
  { arg: '-h, --help', desc: '帮助信息', where: '本对话框' },
]

async function open() {
  showHelpDialog.value = true
  helpLoading.value = true
  helpError.value = ''
  try {
    binaryHelp.value = await fontManagerApi.getBinaryHelp()
  } catch (e: any) {
    binaryHelp.value = null
    helpError.value = e?.message || '读取内核帮助失败'
  } finally {
    helpLoading.value = false
  }
}

async function copyBinaryHelp() {
  await copy(binaryHelp.value?.help || '', '已复制内核帮助原文')
}

defineExpose({ open })
</script>

<template>
  <v-dialog v-model="showHelpDialog" max-width="760" scrollable>
    <v-card class="glass-card">
      <DialogTitle
        icon="mdi-console"
        icon-color="primary"
        :title="`内核参数帮助 · assfonts v${helpVersionText}（${helpSourceText}）`"
        @close="showHelpDialog = false"
      />
      <v-divider />

      <v-card-text class="pa-4">
        <!-- ① 内核原始帮助 -->
        <div class="d-flex justify-center pa-6" v-if="helpLoading">
          <v-progress-circular indeterminate color="primary" />
        </div>

        <v-alert v-else-if="helpError" type="error" variant="tonal" density="compact" icon="mdi-alert-circle-outline">
          {{ helpError }}
        </v-alert>

        <template v-else-if="binaryHelp">
          <pre class="kernel-help">{{ binaryHelp.help || '（内核没有输出帮助内容）' }}</pre>
          <div class="text-caption text-medium-emphasis mt-2" style="line-height: 1.4">
            以上内容直接来自当前内核的 <code>-h</code> 输出 —— 更新内核后会自动同步。
            <span v-if="binaryHelp.path" class="ml-2">内核路径：{{ binaryHelp.path }}</span>
          </div>
        </template>
      </v-card-text>

      <v-divider />

      <!-- ② 内核参数 → 本页位置 对照表 -->
      <v-card-text class="pa-4 pt-3">
        <div class="section-title mb-2">
          <v-icon size="16" color="primary">mdi-table-arrow-down</v-icon>
          内核参数 → 本页位置
        </div>
        <v-table density="compact" class="kernel-args-table">
          <thead>
            <tr>
              <th class="text-left" style="width: 180px">参数</th>
              <th class="text-left" style="width: 130px">作用</th>
              <th class="text-left">在本页的位置</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in KERNEL_ARG_MAP" :key="row.arg">
              <td class="text-body-2 font-mono">{{ row.arg }}</td>
              <td class="text-body-2">{{ row.desc }}</td>
              <td class="text-body-2">{{ row.where }}</td>
            </tr>
          </tbody>
        </v-table>
        <div class="text-caption text-medium-emphasis mt-2" style="line-height: 1.4">
          内核报错退出码恒为 0，本页以「产物是否生成 + 日志文本 + 索引比对」判定成败；
          <code>-v</code> 低于 2 时内核不再输出缺字体提示，本页会自动改用索引比对。
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-content-copy"
          :disabled="!binaryHelp?.help"
          @click="copyBinaryHelp"
        >
          复制帮助原文
        </v-btn>
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="showHelpDialog = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
/* 内核 -h 原文：等宽 + 保留缩进 + 横向滚动 */
.kernel-help {
  margin: 0;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(var(--v-theme-surface-variant), 0.45);
  border: var(--am-content-border, 1px solid rgba(var(--v-theme-on-surface), 0.12));
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre;
  tab-size: 4;
  overflow: auto;
  max-height: 42vh;
}
.kernel-args-table {
  background: transparent;
}
</style>
