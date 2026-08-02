<script setup lang="ts">
/**
 * RulePreviewModal — 规则预览弹窗
 * 测试重命名效果
 */
import { ref, watch } from 'vue'
import { organizerApi } from '@/api'
import { useNotification } from '@/composables'

defineOptions({ name: 'RulePreviewModal' })

const props = defineProps<{
  modelValue: boolean
  ruleId: string
  ruleName: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const { warning } = useNotification()

const show = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const previewResultData = ref<any>(null)
const previewNewPath = ref('')
const previewPatternUsed = ref('')
const previewError = ref('')
const previewLoading = ref(false)

watch(() => props.modelValue, (val) => {
  if (val) {
    previewResultData.value = null
    previewNewPath.value = ''
    previewPatternUsed.value = ''
    previewError.value = ''
  }
})

async function submitPreview() {
  if (!previewResultData.value || !props.ruleId) {
    warning('请先填入识别结果数据')
    return
  }
  previewLoading.value = true
  previewError.value = ''
  previewNewPath.value = ''
  try {
    let data = previewResultData.value
    if (typeof data === 'string') {
      try { data = JSON.parse(data) } catch { /* keep as string */ }
    }
    const result = await organizerApi.renamePreview({
      rule_id: props.ruleId,
      result_data: data,
    })
    if (result?.status === 'success') {
      previewNewPath.value = result.new_path
      previewPatternUsed.value = result.pattern_used
    } else {
      previewError.value = result?.message || '预览失败'
    }
  } catch (e: any) {
    previewError.value = e.message || '预览请求失败'
  } finally {
    previewLoading.value = false
  }
}
</script>

<template>
  <v-dialog v-model="show" max-width="720" scrollable>
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">
        <v-icon start color="primary">mdi-eye-outline</v-icon>
        规则预览 — {{ ruleName }}
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="show = false" />
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <div class="text-body-2 text-medium-emphasis mb-4">
          粘贴或输入一段完整的识别结果 JSON，系统将根据规则 <strong>{{ ruleName }}</strong> 计算目标路径。
        </div>

        <v-textarea
          v-model="previewResultData"
          label="识别结果 JSON"
          placeholder='{"final_result": {"title": "葬送的芙莉莲", "year": "2023", "category": "剧集", "season": 1, "episode": 1, "filename": "Frieren - S01E01.mkv"}}'
          variant="outlined"
          density="compact"
          rows="6"
          auto-grow
          class="mb-4"
        />

        <v-btn color="primary" variant="flat" :loading="previewLoading" prepend-icon="mdi-play-outline" @click="submitPreview" block>
          执行预览
        </v-btn>

        <!-- 结果 -->
        <div v-if="previewNewPath" class="org-preview-result mt-4">
          <div class="text-subtitle-2 font-weight-medium mb-2">预览结果</div>
          <div class="org-preview-path">{{ previewNewPath }}</div>
          <div v-if="previewPatternUsed" class="text-caption text-medium-emphasis mt-1">
            使用模板: <code>{{ previewPatternUsed }}</code>
          </div>
        </div>

        <v-alert v-if="previewError" type="error" variant="tonal" class="mt-4" density="compact">
          {{ previewError }}
        </v-alert>
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="show = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
