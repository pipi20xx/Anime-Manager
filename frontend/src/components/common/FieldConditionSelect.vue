<script setup lang="ts">
/**
 * FieldConditionSelect — 媒体规格筛选条件输入
 *
 * 多选 combobox: 点开选规范值, 也可手输列表外的值 (回车添加)。
 * modelValue 为后端约定的逗号分隔字符串, 组件内部与数组互转。
 */
import { computed, onMounted } from 'vue'
import { useFieldOptions } from '@/composables/useFieldOptions'

const props = withDefaults(defineProps<{
  /** 选项字段名 (resolution/team/source/video_encode/audio_encode/subtitle/video_effect/platform) */
  field: string
  label: string
  modelValue?: string | null
  placeholder?: string
}>(), { modelValue: '', placeholder: '选择或输入, 可多个' })

const emit = defineEmits<{ (e: 'update:modelValue', v: string | null): void }>()

const { options, load } = useFieldOptions()
onMounted(() => { load() })

const selected = computed<string[]>({
  get: () => props.modelValue
    ? String(props.modelValue).split(',').map(s => s.trim()).filter(Boolean)
    : [],
  set: v => emit('update:modelValue', v?.length ? v.join(', ') : null),
})
</script>

<template>
  <v-combobox
    v-model="selected"
    :items="options[field] || []"
    :label="label"
    :placeholder="selected.length ? undefined : placeholder"
    multiple
    chips
    closable-chips
    variant="outlined"
    density="compact"
    hide-no-data
    hide-selected
  />
</template>
