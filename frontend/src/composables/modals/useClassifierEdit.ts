import { ref, watch } from 'vue'

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

interface RefSearchResult {
  id: string
  name: string
  type: string
  source?: string
}

export function useClassifierEdit(props: any, emit: any) {
  const formModel = ref<any>({
    name: '',
    target: 'all',
    enabled: true,
    criteria: {
      genre_ids: '',
      original_language: '',
      origin_country: '',
      company_ids: '',
      keyword_ids: '',
      year: '',
      title: ''
    }
  })

  const genreLoading = ref(false)
  const companyLoading = ref(false)
  const keywordLoading = ref(false)
  const languageLoading = ref(false)
  const countryLoading = ref(false)
  
  const genreOptions = ref<{label: string, value: string}[]>([])
  const companyOptions = ref<{label: string, value: string}[]>([])
  const keywordOptions = ref<{label: string, value: string}[]>([])
  const languageOptions = ref<{label: string, value: string}[]>([])
  const countryOptions = ref<{label: string, value: string}[]>([])

  const searchMapping = async (query: string, type: 'genre' | 'company' | 'keyword' | 'language' | 'country'): Promise<RefSearchResult[]> => {
    try {
      const url = `${API_BASE}/api/user_mapping/search?type=${type}${query ? `&q=${encodeURIComponent(query)}` : ''}`
      const res = await fetch(url)
      return await res.json()
    } catch {
      return []
    }
  }

  const loadAllGenres = async () => {
    genreLoading.value = true
    try {
      const results = await searchMapping('', 'genre')
      genreOptions.value = results.map(r => ({
        label: `${r.name} (ID: ${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
        value: r.id
      }))
    } finally {
      genreLoading.value = false
    }
  }

  const loadAllCompanies = async () => {
    companyLoading.value = true
    try {
      const results = await searchMapping('', 'company')
      companyOptions.value = results.map(r => ({
        label: `${r.name} (ID: ${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
        value: r.id
      }))
    } finally {
      companyLoading.value = false
    }
  }

  const loadAllKeywords = async () => {
    keywordLoading.value = true
    try {
      const results = await searchMapping('', 'keyword')
      keywordOptions.value = results.map(r => ({
        label: `${r.name} (ID: ${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
        value: r.id
      }))
    } finally {
      keywordLoading.value = false
    }
  }

  const loadAllLanguages = async () => {
    languageLoading.value = true
    try {
      const results = await searchMapping('', 'language')
      languageOptions.value = results.map(r => ({
        label: `${r.name} (${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
        value: r.id
      }))
    } finally {
      languageLoading.value = false
    }
  }

  const loadAllCountries = async () => {
    countryLoading.value = true
    try {
      const results = await searchMapping('', 'country')
      countryOptions.value = results.map(r => ({
        label: `${r.name} (${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
        value: r.id
      }))
    } finally {
      countryLoading.value = false
    }
  }

  const handleGenreSearch = async (query: string) => {
    if (!query) {
      await loadAllGenres()
      return
    }
    genreLoading.value = true
    try {
      const results = await searchMapping(query, 'genre')
      genreOptions.value = results.map(r => ({
        label: `${r.name} (ID: ${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
        value: r.id
      }))
    } finally {
      genreLoading.value = false
    }
  }

  const handleCompanySearch = async (query: string) => {
    if (!query) {
      await loadAllCompanies()
      return
    }
    companyLoading.value = true
    try {
      const results = await searchMapping(query, 'company')
      companyOptions.value = results.map(r => ({
        label: `${r.name} (ID: ${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
        value: r.id
      }))
    } finally {
      companyLoading.value = false
    }
  }

  const handleKeywordSearch = async (query: string) => {
    if (!query) {
      await loadAllKeywords()
      return
    }
    keywordLoading.value = true
    try {
      const results = await searchMapping(query, 'keyword')
      keywordOptions.value = results.map(r => ({
        label: `${r.name} (ID: ${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
        value: r.id
      }))
    } finally {
      keywordLoading.value = false
    }
  }

  const handleLanguageSearch = async (query: string) => {
    if (!query) {
      await loadAllLanguages()
      return
    }
    languageLoading.value = true
    try {
      const results = await searchMapping(query, 'language')
      languageOptions.value = results.map(r => ({
        label: `${r.name} (${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
        value: r.id
      }))
    } finally {
      languageLoading.value = false
    }
  }

  const handleCountrySearch = async (query: string) => {
    if (!query) {
      await loadAllCountries()
      return
    }
    countryLoading.value = true
    try {
      const results = await searchMapping(query, 'country')
      countryOptions.value = results.map(r => ({
        label: `${r.name} (${r.id})${r.source === '用户自定义' ? ' ★' : ''}`,
        value: r.id
      }))
    } finally {
      countryLoading.value = false
    }
  }

  const handleGenreDropdownOpen = (open: boolean) => {
    if (open && genreOptions.value.length === 0) {
      loadAllGenres()
    }
  }

  const handleCompanyDropdownOpen = (open: boolean) => {
    if (open && companyOptions.value.length === 0) {
      loadAllCompanies()
    }
  }

  const handleKeywordDropdownOpen = (open: boolean) => {
    if (open && keywordOptions.value.length === 0) {
      loadAllKeywords()
    }
  }

  const handleLanguageDropdownOpen = (open: boolean) => {
    if (open && languageOptions.value.length === 0) {
      loadAllLanguages()
    }
  }

  const handleCountryDropdownOpen = (open: boolean) => {
    if (open && countryOptions.value.length === 0) {
      loadAllCountries()
    }
  }

  const getSelectedGenreIds = () => {
    const current = formModel.value.criteria.genre_ids || ''
    return current ? current.split(',').map((s: string) => s.trim()).filter(Boolean) : []
  }

  const getSelectedCompanyIds = () => {
    const current = formModel.value.criteria.company_ids || ''
    return current ? current.split(',').map((s: string) => s.trim()).filter(Boolean) : []
  }

  const getSelectedKeywordIds = () => {
    const current = formModel.value.criteria.keyword_ids || ''
    return current ? current.split(',').map((s: string) => s.trim()).filter(Boolean) : []
  }

  const getSelectedLanguageCodes = () => {
    const current = formModel.value.criteria.original_language || ''
    return current ? current.split(',').map((s: string) => s.trim()).filter(Boolean) : []
  }

  const getSelectedCountryCodes = () => {
    const current = formModel.value.criteria.origin_country || ''
    return current ? current.split(',').map((s: string) => s.trim()).filter(Boolean) : []
  }

  const handleGenreSelect = (vals: string[]) => {
    formModel.value.criteria.genre_ids = vals.join(',')
  }

  const handleCompanySelect = (vals: string[]) => {
    formModel.value.criteria.company_ids = vals.join(',')
  }

  const handleKeywordSelect = (vals: string[]) => {
    formModel.value.criteria.keyword_ids = vals.join(',')
  }

  const handleLanguageSelect = (vals: string[]) => {
    formModel.value.criteria.original_language = vals.join(',')
  }

  const handleCountrySelect = (vals: string[]) => {
    formModel.value.criteria.origin_country = vals.join(',')
  }

  watch(() => props.show, (val) => {
    if (val) {
      genreOptions.value = []
      companyOptions.value = []
      keywordOptions.value = []
      languageOptions.value = []
      countryOptions.value = []
      if (props.isNew) {
        formModel.value = {
          name: '', target: 'all', enabled: true,
          criteria: { genre_ids: '', original_language: '', origin_country: '', company_ids: '', keyword_ids: '', year: '', title: '' }
        }
      } else {
        formModel.value = JSON.parse(JSON.stringify(props.ruleData))
      }
    }
  })

  const handleSave = () => {
    if (!formModel.value.name) return
    emit('save', formModel.value)
    emit('update:show', false)
  }

  return {
    formModel,
    handleSave,
    genreLoading,
    companyLoading,
    keywordLoading,
    languageLoading,
    countryLoading,
    genreOptions,
    companyOptions,
    keywordOptions,
    languageOptions,
    countryOptions,
    handleGenreSearch,
    handleCompanySearch,
    handleKeywordSearch,
    handleLanguageSearch,
    handleCountrySearch,
    handleGenreSelect,
    handleCompanySelect,
    handleKeywordSelect,
    handleLanguageSelect,
    handleCountrySelect,
    handleGenreDropdownOpen,
    handleCompanyDropdownOpen,
    handleKeywordDropdownOpen,
    handleLanguageDropdownOpen,
    handleCountryDropdownOpen,
    getSelectedGenreIds,
    getSelectedCompanyIds,
    getSelectedKeywordIds,
    getSelectedLanguageCodes,
    getSelectedCountryCodes
  }
}
