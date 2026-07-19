import { reactive, ref, computed, watch } from 'vue'
import { openBangumiDetail } from '../../store/navigationStore'

export type Season = 'WINTER' | 'SPRING' | 'SUMMER' | 'FALL'

export function useSeasonal() {
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  // 4 个季度定义（1-3冬 / 4-6春 / 7-9夏 / 10-12秋）
  const SEASONS: Season[] = ['WINTER', 'SPRING', 'SUMMER', 'FALL']
  const SEASON_CN: Record<Season, string> = {
    WINTER: '冬季',
    SPRING: '春季',
    SUMMER: '夏季',
    FALL: '秋季'
  }

  // 当前选中的年份和季度
  const selectedYear = ref<number>(new Date().getFullYear())
  const selectedSeason = ref<Season>(computeDefaultSeason())

  const data = reactive({
    items: [] as any[],
    loading: false,
    count: 0,
    season_cn: ''
  })

  // 订阅列表（用于显示已订阅角标）
  const subscriptions = ref<any[]>([])

  // 已订阅 Bangumi ID 集合（缓存以避免每次渲染都遍历）
  const subscribedBgmIds = computed(() => {
    const ids = new Set<string>()
    const titles = new Set<string>()
    for (const sub of subscriptions.value) {
      if (sub.bangumi_id) ids.add(String(sub.bangumi_id))
      if (sub.title) titles.add(sub.title)
    }
    return { ids, titles }
  })

  const isSubscribed = (item: any) => {
    if (subscribedBgmIds.value.ids.has(String(item.id))) return true
    const title = item.title || item.name
    const orig = item.original_title || item.name
    return subscribedBgmIds.value.titles.has(title) || subscribedBgmIds.value.titles.has(orig)
  }

  // 按当前月份推算默认季度
  function computeDefaultSeason(): Season {
    const m = new Date().getMonth() + 1
    if (m <= 3) return 'WINTER'
    if (m <= 6) return 'SPRING'
    if (m <= 9) return 'SUMMER'
    return 'FALL'
  }

  // 切换到上一季 / 下一季（跨年自动处理）
  const goToPrevSeason = () => {
    const idx = SEASONS.indexOf(selectedSeason.value)
    if (idx === 0) {
      selectedSeason.value = 'FALL'
      selectedYear.value -= 1
    } else {
      selectedSeason.value = SEASONS[idx - 1]
    }
  }

  const goToNextSeason = () => {
    const idx = SEASONS.indexOf(selectedSeason.value)
    if (idx === SEASONS.length - 1) {
      selectedSeason.value = 'WINTER'
      selectedYear.value += 1
    } else {
      selectedSeason.value = SEASONS[idx + 1]
    }
  }

  // 跳转到当前实际季度
  const goToCurrentSeason = () => {
    selectedYear.value = new Date().getFullYear()
    selectedSeason.value = computeDefaultSeason()
  }

  // 年份选择列表（当前年前后各 3 年）
  const yearOptions = computed(() => {
    const cur = new Date().getFullYear()
    const opts: number[] = []
    for (let y = cur + 2; y >= cur - 3; y--) opts.push(y)
    return opts
  })

  const fetchSubscriptions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/subscriptions`)
      if (res.ok) subscriptions.value = await res.json()
    } catch (e) {
      console.error('Fetch subscriptions failed', e)
    }
  }

  const fetchSeasonal = async () => {
    data.loading = true
    try {
      const res = await fetch(
        `${API_BASE}/api/bangumi/seasonal?year=${selectedYear.value}&season=${selectedSeason.value}`
      )
      if (res.ok) {
        const json = await res.json()
        data.items = json.data || []
        data.count = json.count || 0
        data.season_cn = json.season_cn || ''
      } else {
        data.items = []
        data.count = 0
      }
    } catch (e) {
      console.error('Fetch seasonal failed', e)
      data.items = []
      data.count = 0
    } finally {
      data.loading = false
    }
  }

  const openBangumi = (item: any) => {
    openBangumiDetail(item.id, item)
  }

  // 年份/季度变化时自动重新加载
  watch([selectedYear, selectedSeason], () => {
    fetchSeasonal()
  }, { immediate: false })

  // 首次挂载：拉订阅 + 拉本季数据
  fetchSubscriptions()
  fetchSeasonal()

  return {
    SEASONS,
    SEASON_CN,
    selectedYear,
    selectedSeason,
    data,
    yearOptions,
    goToPrevSeason,
    goToNextSeason,
    goToCurrentSeason,
    fetchSeasonal,
    isSubscribed,
    openBangumi
  }
}
