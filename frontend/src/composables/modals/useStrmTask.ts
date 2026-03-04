import { reactive, ref, watch } from 'vue'
import { debounce } from 'lodash-es'

export function useStrmTask(props: any, emit: any) {
  const form = reactive<any>({
    id: '',
    name: '',
    source_path: '',
    target_path: '',
    content_prefix: '',
    content_suffix: '',
    url_encode: false,
    copy_meta: true,
    clean_target: false,
    clean_empty_dirs: true,
    overwrite_strm: true,
    overwrite_meta: false,
    target_extensions: ['.mp4', '.mkv', '.ts', '.iso', '.rmvb', '.avi', '.mov', '.mpeg', '.mpg', '.wmv', '.3gp', '.asf', '.m4v', '.flv', '.m2ts', '.tp', '.f4v'],
    meta_extensions: ['.nfo', '.jpg', '.jpeg', '.png', '.svg', '.ass', '.srt', '.sup', '.mp3', '.flac', '.wav', '.aac', '.webp', '.ssa', '.sub'],
    incremental_enabled: false,
    incremental_mode: 'realtime',
    monitor_interval: 10,
    scheduler_enabled: false,
    scheduler_interval: 3600,
    process_interval: 0,
    sync_mode: 'local',
    tree_file_path: '',
    webhook_enabled: true
  })

  const previewLoading = ref(false)
  const previewData = ref<any>(null)
  const showPicker = ref(false)
  const pickerTarget = ref<'source' | 'target' | 'tree'>('source')

  const updatePreview = debounce(async () => {
    if (!form.source_path || !props.show) return
    previewLoading.value = true
    try {
      const res = await fetch(`${props.apiBase}/api/strm/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      })
      previewData.value = await res.json()
    } catch (e) { console.error('Preview failed', e) }
    finally { previewLoading.value = false }
  }, 500)

  // Watchers
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
      if (!form.sync_mode) form.sync_mode = 'local'
      if (!form.tree_file_path) form.tree_file_path = ''
      if (form.source_path) updatePreview()
    }
  })

  watch(
    () => [form.content_prefix, form.content_suffix, form.url_encode, form.source_path],
    () => { if (props.show) updatePreview() }
  )

  const openPicker = (target: 'source' | 'target' | 'tree') => {
    pickerTarget.value = target
    showPicker.value = true
  }

  const handlePickerConfirm = (path: string) => {
    if (pickerTarget.value === 'source') form.source_path = path
    else if (pickerTarget.value === 'target') form.target_path = path
    else form.tree_file_path = path
  }

  const handleSave = () => {
    emit('save', { ...form })
  }

  const syncModeOptions = [
    { label: '📁 本地文件扫描', value: 'local' },
    { label: '📄 目录树文件', value: 'tree_file' }
  ]

  return {
    form,
    previewLoading,
    previewData,
    showPicker,
    pickerTarget,
    syncModeOptions,
    updatePreview,
    openPicker,
    handlePickerConfirm,
    handleSave
  }
}
