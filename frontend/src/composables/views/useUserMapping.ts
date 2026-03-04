import { ref, onMounted, watch } from 'vue'
import { useMessage } from 'naive-ui'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

function useDebounce<T extends (...args: unknown[]) => void>(fn: T, delay: number): T {
  let timer: ReturnType<typeof setTimeout> | null = null
  return ((...args: unknown[]) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }) as T
}

export interface MappingItem {
  id: number | string
  name_zh?: string
  name_en?: string
  name?: string
  country?: string
  code?: string
  source?: string
}

export interface RefCounts {
  ref: {
    genres: number
    companies: number
    keywords: number
  }
  user: {
    genres: number
    companies: number
    keywords: number
    languages: number
    countries: number
  }
}

export function useUserMapping() {
  const message = useMessage()
  const loading = ref(false)
  const importLoading = ref(false)
  const activeType = ref('genre')
  
  const genreMappings = ref<MappingItem[]>([])
  const companyMappings = ref<MappingItem[]>([])
  const keywordMappings = ref<MappingItem[]>([])
  const languageMappings = ref<MappingItem[]>([])
  const countryMappings = ref<MappingItem[]>([])
  
  const companyTotal = ref(0)
  const keywordTotal = ref(0)
  const companyPage = ref(1)
  const keywordPage = ref(1)
  const companyLoading = ref(false)
  const keywordLoading = ref(false)
  
  const genreSearch = ref('')
  const companySearch = ref('')
  const keywordSearch = ref('')
  const languageSearch = ref('')
  const countrySearch = ref('')
  
  const refCounts = ref<RefCounts>({
    ref: { genres: 0, companies: 0, keywords: 0 },
    user: { genres: 0, companies: 0, keywords: 0, languages: 0, countries: 0 }
  })

  const fetchMappings = async () => {
    loading.value = true
    try {
      const [genres, languages, countries] = await Promise.all([
        fetch(`${API_BASE}/api/user_mapping/genres?q=${encodeURIComponent(genreSearch.value)}`).then(r => r.json()),
        fetch(`${API_BASE}/api/user_mapping/languages?q=${encodeURIComponent(languageSearch.value)}`).then(r => r.json()),
        fetch(`${API_BASE}/api/user_mapping/countries?q=${encodeURIComponent(countrySearch.value)}`).then(r => r.json())
      ])
      genreMappings.value = genres
      languageMappings.value = languages
      countryMappings.value = countries
    } catch (e) {
      message.error('获取映射数据失败')
    } finally {
      loading.value = false
    }
  }

  const fetchCompanies = async (page: number = 1, append: boolean = false) => {
    if (companyLoading.value) return
    companyLoading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/user_mapping/companies?page=${page}&page_size=100&q=${encodeURIComponent(companySearch.value)}`)
      const data = await res.json()
      if (append) {
        companyMappings.value = [...companyMappings.value, ...data.items]
      } else {
        companyMappings.value = data.items
      }
      companyTotal.value = data.total
      companyPage.value = page
    } catch (e) {
      message.error('获取公司映射失败')
    } finally {
      companyLoading.value = false
    }
  }

  const fetchKeywords = async (page: number = 1, append: boolean = false) => {
    if (keywordLoading.value) return
    keywordLoading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/user_mapping/keywords?page=${page}&page_size=100&q=${encodeURIComponent(keywordSearch.value)}`)
      const data = await res.json()
      if (append) {
        keywordMappings.value = [...keywordMappings.value, ...data.items]
      } else {
        keywordMappings.value = data.items
      }
      keywordTotal.value = data.total
      keywordPage.value = page
    } catch (e) {
      message.error('获取关键词映射失败')
    } finally {
      keywordLoading.value = false
    }
  }

  const debouncedSearchGenre = useDebounce(() => {
    fetchMappings()
  }, 300)

  const debouncedSearchCompany = useDebounce(() => {
    companyPage.value = 1
    companyMappings.value = []
    fetchCompanies()
  }, 300)

  const debouncedSearchKeyword = useDebounce(() => {
    keywordPage.value = 1
    keywordMappings.value = []
    fetchKeywords()
  }, 300)

  const debouncedSearchLanguage = useDebounce(() => {
    fetchMappings()
  }, 300)

  const debouncedSearchCountry = useDebounce(() => {
    fetchMappings()
  }, 300)

  watch(genreSearch, () => {
    debouncedSearchGenre()
  })

  watch(companySearch, () => {
    debouncedSearchCompany()
  })

  watch(keywordSearch, () => {
    debouncedSearchKeyword()
  })

  watch(languageSearch, () => {
    debouncedSearchLanguage()
  })

  watch(countrySearch, () => {
    debouncedSearchCountry()
  })

  const loadMoreCompanies = async () => {
    if (companyMappings.value.length < companyTotal.value) {
      await fetchCompanies(companyPage.value + 1, true)
    }
  }

  const loadMoreKeywords = async () => {
    if (keywordMappings.value.length < keywordTotal.value) {
      await fetchKeywords(keywordPage.value + 1, true)
    }
  }

  const fetchRefCounts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/user_mapping/ref_counts`)
      refCounts.value = await res.json()
    } catch (e) {
      console.error('获取统计失败', e)
    }
  }

  const importFromRef = async (type: string = 'all') => {
    importLoading.value = true
    try {
      const res = await fetch(`${API_BASE}/api/user_mapping/import_from_ref?type=${type}`, {
        method: 'POST'
      })
      const data = await res.json()
      if (data.status === 'success') {
        const { genres, companies, keywords } = data.imported
        const total = genres + companies + keywords
        if (total > 0) {
          message.success(`成功导入 ${total} 条数据 (流派: ${genres}, 公司: ${companies}, 关键词: ${keywords})`)
        } else {
          message.info('所有数据已存在，无需导入')
        }
        await fetchMappings()
        await fetchRefCounts()
      }
    } catch (e) {
      message.error('导入失败')
    } finally {
      importLoading.value = false
    }
  }

  const saveGenreMapping = async (item: MappingItem) => {
    try {
      const res = await fetch(`${API_BASE}/api/user_mapping/genres`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item)
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('保存成功')
        await fetchMappings()
        return true
      }
      return false
    } catch (e) {
      message.error('保存失败')
      return false
    }
  }

  const deleteGenreMapping = async (id: number) => {
    try {
      await fetch(`${API_BASE}/api/user_mapping/genres/${id}`, { method: 'DELETE' })
      message.success('删除成功')
      await fetchMappings()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const saveCompanyMapping = async (item: MappingItem) => {
    try {
      const res = await fetch(`${API_BASE}/api/user_mapping/companies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item)
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('保存成功')
        await fetchMappings()
        return true
      }
      return false
    } catch (e) {
      message.error('保存失败')
      return false
    }
  }

  const deleteCompanyMapping = async (id: number) => {
    try {
      await fetch(`${API_BASE}/api/user_mapping/companies/${id}`, { method: 'DELETE' })
      message.success('删除成功')
      await fetchMappings()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const saveKeywordMapping = async (item: MappingItem) => {
    try {
      const res = await fetch(`${API_BASE}/api/user_mapping/keywords`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item)
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('保存成功')
        await fetchMappings()
        return true
      }
      return false
    } catch (e) {
      message.error('保存失败')
      return false
    }
  }

  const deleteKeywordMapping = async (id: number) => {
    try {
      await fetch(`${API_BASE}/api/user_mapping/keywords/${id}`, { method: 'DELETE' })
      message.success('删除成功')
      await fetchMappings()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const saveLanguageMapping = async (item: MappingItem) => {
    try {
      const res = await fetch(`${API_BASE}/api/user_mapping/languages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: item.code || item.id, name_zh: item.name_zh, name_en: item.name_en })
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('保存成功')
        await fetchMappings()
        return true
      }
      return false
    } catch (e) {
      message.error('保存失败')
      return false
    }
  }

  const deleteLanguageMapping = async (code: string) => {
    try {
      await fetch(`${API_BASE}/api/user_mapping/languages/${code}`, { method: 'DELETE' })
      message.success('删除成功')
      await fetchMappings()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const saveCountryMapping = async (item: MappingItem) => {
    try {
      const res = await fetch(`${API_BASE}/api/user_mapping/countries`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: item.code || item.id, name_zh: item.name_zh, name_en: item.name_en })
      })
      const data = await res.json()
      if (data.status === 'success') {
        message.success('保存成功')
        await fetchMappings()
        return true
      }
      return false
    } catch (e) {
      message.error('保存失败')
      return false
    }
  }

  const deleteCountryMapping = async (code: string) => {
    try {
      await fetch(`${API_BASE}/api/user_mapping/countries/${code}`, { method: 'DELETE' })
      message.success('删除成功')
      await fetchMappings()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const searchMapping = async (q: string, type: string = 'all'): Promise<MappingItem[]> => {
    try {
      const url = `${API_BASE}/api/user_mapping/search?type=${type}${q ? `&q=${encodeURIComponent(q)}` : ''}`
      const res = await fetch(url)
      return await res.json()
    } catch (e) {
      return []
    }
  }

  const exportMappings = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/user_mapping/export`)
      const data = await res.json()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `user_mappings_${new Date().toISOString().split('T')[0]}.json`
      link.click()
      window.URL.revokeObjectURL(url)
      message.success('导出成功')
    } catch (e) {
      message.error('导出失败')
    }
  }

  const fileInput = ref<HTMLInputElement | null>(null)
  const fileImportLoading = ref(false)

  const triggerImport = () => {
    fileInput.value?.click()
  }

  const handleFileImport = async (event: Event) => {
    const file = (event.target as HTMLInputElement).files?.[0]
    if (!file) return
    
    const reader = new FileReader()
    reader.onload = async (e) => {
      try {
        const json = JSON.parse(e.target?.result as string)
        fileImportLoading.value = true
        const res = await fetch(`${API_BASE}/api/user_mapping/import?mode=append`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(json)
        })
        const data = await res.json()
        if (data.status === 'success') {
          const { genres, companies, keywords, languages, countries } = data.imported
          const total = genres + companies + keywords + languages + countries
          message.success(`成功导入 ${total} 条映射`)
          await fetchMappings()
          await fetchRefCounts()
        } else {
          message.error('导入失败')
        }
      } catch (err) {
        message.error('文件解析错误')
      } finally {
        fileImportLoading.value = false
        if (fileInput.value) fileInput.value.value = ''
      }
    }
    reader.readAsText(file)
  }

  onMounted(() => {
    fetchMappings()
    fetchRefCounts()
  })

  return {
    loading,
    importLoading,
    activeType,
    genreMappings,
    companyMappings,
    keywordMappings,
    languageMappings,
    countryMappings,
    refCounts,
    companyTotal,
    keywordTotal,
    companyPage,
    keywordPage,
    companyLoading,
    keywordLoading,
    genreSearch,
    companySearch,
    keywordSearch,
    languageSearch,
    countrySearch,
    fetchMappings,
    fetchRefCounts,
    fetchCompanies,
    fetchKeywords,
    loadMoreCompanies,
    loadMoreKeywords,
    importFromRef,
    saveGenreMapping,
    deleteGenreMapping,
    saveCompanyMapping,
    deleteCompanyMapping,
    saveKeywordMapping,
    deleteKeywordMapping,
    saveLanguageMapping,
    deleteLanguageMapping,
    saveCountryMapping,
    deleteCountryMapping,
    searchMapping,
    exportMappings,
    fileInput,
    fileImportLoading,
    triggerImport,
    handleFileImport
  }
}
