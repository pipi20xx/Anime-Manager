import { ref, onMounted, computed } from 'vue'
import { useMessage } from 'naive-ui'

interface MappingCache {
  genres: Record<string, string>
  companies: Record<string, string>
  keywords: Record<string, string>
  languages: Record<string, string>
  countries: Record<string, string>
}

export function useSecondaryRule() {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const rules = ref<any[]>([])
  const showRuleModal = ref(false)
  const editingRule = ref<any>(null)
  const isNewRule = ref(false)
  const editingIndex = ref(-1)
  const importLoading = ref(false)
  const fileInput = ref<HTMLInputElement | null>(null)
  const draggedIndex = ref<number | null>(null)

  const mappingCache = ref<MappingCache>({
    genres: {},
    companies: {},
    keywords: {},
    languages: {},
    countries: {}
  })

  const fetchMappings = async () => {
    try {
      const [genres, companies, keywords, languages, countries] = await Promise.all([
        fetch(`${API_BASE}/api/user_mapping/search?type=genre`).then(r => r.json()),
        fetch(`${API_BASE}/api/user_mapping/search?type=company`).then(r => r.json()),
        fetch(`${API_BASE}/api/user_mapping/search?type=keyword`).then(r => r.json()),
        fetch(`${API_BASE}/api/user_mapping/search?type=language`).then(r => r.json()),
        fetch(`${API_BASE}/api/user_mapping/search?type=country`).then(r => r.json())
      ])
      
      mappingCache.value = {
        genres: Object.fromEntries(genres.map((g: any) => [g.id, g.name])),
        companies: Object.fromEntries(companies.map((c: any) => [c.id, c.name])),
        keywords: Object.fromEntries(keywords.map((k: any) => [k.id, k.name])),
        languages: Object.fromEntries(languages.map((l: any) => [l.id, l.name])),
        countries: Object.fromEntries(countries.map((c: any) => [c.id, c.name]))
      }
    } catch (e) {
      console.error('获取映射失败', e)
    }
  }

  const translateIds = (ids: string, type: 'genres' | 'companies' | 'keywords' | 'languages' | 'countries'): string => {
    if (!ids) return ''
    const idList = ids.split(',').map((s: string) => s.trim()).filter(Boolean)
    const translated = idList.map(id => mappingCache.value[type][id] || id)
    return translated.join(', ')
  }

  const fetchRules = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tmdb_full/rules`)
      rules.value = await res.json()
    } catch (e) { rules.value = [] }
  }

  const handleSaveRule = async (ruleData: any) => {
    if (isNewRule.value) rules.value.push(ruleData)
    else rules.value[editingIndex.value] = ruleData
    await saveRulesToBackend()
  }

  const saveRulesToBackend = async () => {
    try {
      await fetch(`${API_BASE}/api/tmdb_full/rules`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify(rules.value) 
      })
      message.success('规则已保存并同步')
      await fetchRules()
    } catch (e) { message.error('保存失败') }
  }

  const deleteRule = async (index: number) => {
    const rule = rules.value[index]
    if (!rule.id) {
      rules.value.splice(index, 1)
      return
    }

    try {
      const res = await fetch(`${API_BASE}/api/tmdb_full/rules/${rule.id}`, {
        method: 'DELETE'
      })
      const data = await res.json()
      
      if (res.ok && data.status === 'success') {
        message.success('规则已删除')
        rules.value.splice(index, 1)
      } else {
        message.error(data.detail || '删除失败')
      }
    } catch (e) {
      message.error('网络请求失败')
    }
  }

  const handleExport = () => {
    fetch(`${API_BASE}/api/tmdb_full/rules/export`)
      .then(res => res.blob())
      .then(blob => {
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `secondary_rules_${new Date().toISOString().split('T')[0]}.json`
        link.click()
        window.URL.revokeObjectURL(url)
        message.success("导出成功")
      })
      .catch(() => message.error("导出失败"))
  }

  const triggerImport = () => {
    fileInput.value?.click()
  }

  const handleFileChange = async (event: Event) => {
    const file = (event.target as HTMLInputElement).files?.[0]
    if (!file) return
    
    const reader = new FileReader()
    reader.onload = async (e) => {
      try {
        const json = JSON.parse(e.target?.result as string)
        importLoading.value = true
        const res = await fetch(`${API_BASE}/api/tmdb_full/rules/import?mode=append`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(json)
        })
        const data = await res.json()
        if (data.status === 'success') {
          message.success(`成功导入 ${data.count} 条规则`)
          fetchRules()
        } else {
          message.error("导入失败")
        }
      } catch (err) {
        message.error("文件解析错误")
      } finally {
        importLoading.value = false
        if (fileInput.value) fileInput.value.value = ''
      }
    }
    reader.readAsText(file)
  }

  const onDragStart = (index: number) => { draggedIndex.value = index }
  const onDragOver = (e: DragEvent) => { e.preventDefault() }
  const onDrop = async (index: number) => {
    if (draggedIndex.value === null || draggedIndex.value === index) return
    const item = rules.value.splice(draggedIndex.value, 1)[0]
    rules.value.splice(index, 0, item)
    draggedIndex.value = null
    await saveRulesToBackend()
  }

  onMounted(() => {
    fetchMappings()
    fetchRules()
  })

  return {
    rules,
    showRuleModal,
    editingRule,
    isNewRule,
    editingIndex,
    importLoading,
    fileInput,
    draggedIndex,
    fetchRules,
    handleSaveRule,
    saveRulesToBackend,
    deleteRule,
    handleExport,
    triggerImport,
    handleFileChange,
    onDragStart,
    onDragOver,
    onDrop,
    translateIds
  }
}
