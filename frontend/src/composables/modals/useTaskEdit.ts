import { reactive, watch, ref, toRef } from 'vue'

export function useTaskEdit(props: any, emit: any) {
  const form = reactive<any>({
    id: '',
    name: '',
    rule_id: '',
    source_dir: '',
    target_dir: '',
    action_type: 'move',
    overwrite_mode: false,
    anime_priority: true,
    incremental_enabled: false,
    incremental_mode: 'realtime',
    monitor_interval: 10,
    scheduler_enabled: false,
    scheduler_interval: 3600,
    process_interval: 0,
    ignore_file_regex: [],
    ignore_dir_regex: [],
    trigger_strm: false,
    ignore_history: false,
    check_emby_exists: false,
    calculate_hash: false
  })

  const showPicker = ref(false)
  const pickerTarget = ref<'source' | 'target'>('source')

  watch(() => props.show, (newVal) => {
    if (newVal) {
      const rawData = JSON.parse(JSON.stringify(props.taskData))
      
      if (rawData.monitor_mode) {
        if (rawData.monitor_mode === 'realtime') {
          rawData.incremental_enabled = true
          rawData.incremental_mode = 'realtime'
        } else if (rawData.monitor_mode === 'polling') {
          rawData.incremental_enabled = true
          rawData.incremental_mode = 'polling'
        } else if (rawData.monitor_mode === 'scheduled') {
          rawData.scheduler_enabled = true
        }
        delete rawData.monitor_mode
      }
      
      if (rawData.incremental_enabled === undefined) rawData.incremental_enabled = false
      if (rawData.incremental_mode === undefined) rawData.incremental_mode = 'realtime'
      if (rawData.scheduler_enabled === undefined) rawData.scheduler_enabled = false
      if (rawData.scheduler_interval === undefined) rawData.scheduler_interval = 3600
      if (rawData.monitor_interval === undefined) rawData.monitor_interval = 10

      Object.assign(form, rawData)
    }
  })

  const openPicker = (target: 'source' | 'target') => {
    pickerTarget.value = target
    showPicker.value = true
  }

  const handlePickerConfirm = (path: string) => {
    if (pickerTarget.value === 'source') form.source_dir = path
    else form.target_dir = path
  }

  const handleSave = () => {
    emit('save', { ...form })
  }

  const actionOptions = [
    { label: '物理移动', value: 'move' },
    { label: '完整复制', value: 'copy' },
    { label: '建立硬链', value: 'link' },
    { label: 'CD2 移动', value: 'cd2_move' },
    { label: 'CD2 复制', value: 'cd2_copy' }
  ]

  return {
    form,
    showPicker,
    pickerTarget,
    openPicker,
    handlePickerConfirm,
    handleSave,
    actionOptions
  }
}
