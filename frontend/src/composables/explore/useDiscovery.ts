import { reactive, ref, watch, onMounted, onUnmounted, nextTick } from 'vue'

export function useDiscovery() {
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  const config = reactive({
      genres: [] as any[],
      years: [] as string[],
      languages: [] as any[],
      sort_options: [] as any[],
      bangumi_types: [] as any[],
      bangumi_sources: [] as any[],
      bangumi_regions: [] as any[],
      bangumi_audiences: [] as any[]
  })

  const filters = reactive({
      source: 'bangumi',
      media_type: 'tv',
      genre: null as string | null,
      year: null as string | null,
      language: null as string | null,
      sort_by: 'popularity.desc',
      page: 1,
      subtype: null as string | null,
      story_source: null as string | null,
      region: null as string | null,
      audience: null as string | null
  })

  const data = reactive({
      items: [] as any[],
      total_pages: 0,
      loading: false,
      subscriptions: [] as any[],
      hasMore: true
  })

  const tmdbDetail = reactive({
      show: false,
      id: '' as string | number,
      type: 'tv',
      initial: null as any
  })

  const bgmDetail = reactive({
      show: false,
      id: '' as string | number,
      initial: null as any
  })

  const loadTrigger = ref<HTMLElement | null>(null)
  let observer: IntersectionObserver | null = null

  const fetchConfig = async () => {
      try {
          const res = await fetch(`${API_BASE}/api/explore/config?source=${filters.source}`)
          if (res.ok) {
              const json = await res.json()
              config.genres = json.genres || []
              config.years = json.years || []
              config.languages = json.languages || []
              config.sort_options = json.sort_options || []
              config.bangumi_types = json.bangumi_types || []
              config.bangumi_sources = json.bangumi_sources || []
              config.bangumi_regions = json.bangumi_regions || []
              config.bangumi_audiences = json.bangumi_audiences || []

              if (!config.sort_options.some((o: any) => o.value === filters.sort_by)) {
                  filters.sort_by = config.sort_options[0]?.value || 'popularity.desc'
              }
          }
      } catch (e) {
          console.error("Failed to load explore config", e)
      }
  }

  const fetchSubscriptions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions`)
      if (res.ok) data.subscriptions = await res.json()
    } catch (e) { console.error(e) }
  }

  const isSubscribed = (item: any) => {
      if (filters.source === 'bangumi') {
           return data.subscriptions.some((sub: any) => sub.bangumi_id && String(sub.bangumi_id) === String(item.id))
      }
      return data.subscriptions.some((sub: any) => String(sub.tmdb_id) === String(item.id))
  }

  const fetchData = async (mode: 'replace' | 'append' = 'replace') => {
      if (data.loading) return
      if (mode === 'append' && !data.hasMore) return

      data.loading = true
      try {
          const params = new URLSearchParams({
              source: filters.source,
              media_type: filters.media_type,
              sort_by: filters.sort_by,
              page: String(filters.page)
          })
          if (filters.genre) params.append('with_genres', filters.genre)
          if (filters.year) params.append('year', filters.year)
          if (filters.language) params.append('language', filters.language)
          if (filters.subtype) params.append('subtype', filters.subtype)
          if (filters.story_source) params.append('story_source', filters.story_source)
          if (filters.region) params.append('region', filters.region)
          if (filters.audience) params.append('audience', filters.audience)

          const res = await fetch(`${API_BASE}/api/explore/list?${params.toString()}`)
          if (res.ok) {
              const json = await res.json()
              const newItems = json.results || []
              
              if (mode === 'replace') {
                  data.items = newItems
              } else {
                  const existingIds = new Set(data.items.map((i: any) => i.id))
                  for (const item of newItems) {
                      if (!existingIds.has(item.id)) {
                          data.items.push(item)
                      }
                  }
              }
              
              data.total_pages = Math.min(json.total_pages || 0, 500)
              data.hasMore = filters.page < data.total_pages
          }
      } catch (e) {
          console.error("Fetch explore list failed", e)
      } finally {
          data.loading = false
      }
  }

  const openDetail = (item: any) => {
      if (filters.source === 'bangumi') {
          bgmDetail.id = item.id
          bgmDetail.initial = item
          bgmDetail.show = true
      } else {
          tmdbDetail.id = item.id
          tmdbDetail.type = filters.media_type
          tmdbDetail.initial = item
          tmdbDetail.show = true
      }
  }

  const resetAndReload = () => {
      filters.page = 1
      data.hasMore = true
      // window.scrollTo({ top: 0, behavior: 'instant' }) // Removing window scroll as it might be component specific
      fetchData('replace')
  }

  watch(() => filters.source, async () => {
      filters.genre = null
      filters.language = null
      filters.year = null
      filters.subtype = null
      filters.story_source = null
      filters.region = null
      filters.audience = null
      
      await fetchConfig()
      resetAndReload()
  })
  watch(() => filters.media_type, resetAndReload)
  watch(() => filters.genre, resetAndReload)
  watch(() => filters.year, resetAndReload)
  watch(() => filters.language, resetAndReload)
  watch(() => filters.subtype, resetAndReload)
  watch(() => filters.story_source, resetAndReload)
  watch(() => filters.region, resetAndReload)
  watch(() => filters.audience, resetAndReload)
  watch(() => filters.sort_by, resetAndReload)

  const setupObserver = () => {
      if (observer) observer.disconnect()
      
      observer = new IntersectionObserver((entries) => {
          if (entries[0].isIntersecting && data.hasMore && !data.loading) {
              filters.page++
              fetchData('append')
          }
      }, {
          root: null,
          rootMargin: '200px',
          threshold: 0.1
      })
      
      if (loadTrigger.value) observer.observe(loadTrigger.value)
  }

  onMounted(async () => {
      await fetchConfig()
      await fetchSubscriptions()
      await fetchData('replace')
      
      nextTick(() => {
          setupObserver()
      })
  })

  onUnmounted(() => {
      if (observer) observer.disconnect()
  })

  return {
    config,
    filters,
    data,
    tmdbDetail,
    bgmDetail,
    loadTrigger,
    fetchConfig,
    fetchSubscriptions,
    isSubscribed,
    fetchData,
    openDetail,
    resetAndReload,
    setupObserver
  }
}
