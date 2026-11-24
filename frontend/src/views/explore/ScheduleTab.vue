<script setup lang="ts">
/**
 * ScheduleTab — 播出时间表
 *
 * 整周（今天起 7 天）全部铺在同一页，不用 Tab 切换；版式参考 anibt.net「今日放送」：
 *   - 顶部：今日概览（已播 / 待播）+ 今日播出时间轴
 *   - 下方：逐日分块（周二 11/24 [今天] 8 部 → 海报卡片网格）
 *   - 卡片：海报 + 平台 / 评分角标 + 放大的播出时间角标
 *   - 状态：未播出写「待播出」，已播出写「已播出」；全周下一部播出的那张卡片
 *           额外挂一个「下一部」角标
 *
 * 数据：GET /api/bangumi/calendar_local（今天起 7 天分组）
 *   每项含 { id, title, original_title, broadcast_time, image, rating, platform }
 *   broadcast_time 形如 "周二 20:25" / "END" / null
 */
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { bangumiApi } from '@/api'
import { useNotification } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { EmptyState } from '@/components/common'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'ScheduleTab' })

const { error: showError } = useNotification()
const navStore = useNavigationStore()

/* ───────────────────────── 数据结构 ───────────────────────── */

/** 后端原始日分组 */
interface RawDay {
  date: string
  weekday?: { id: number; cn: string }
  weekday_cn?: string
  is_today?: boolean
  day_offset?: number
  label?: string
  count?: number
  items?: any[]
}

/** 视图模型：单部番剧 */
interface ScheduleItem {
  id: number
  title: string
  poster: string
  rating: number | null
  platform: string
  /** 当日播出分钟数（0-1439）；无固定播出时间/已完结为 null */
  minutes: number | null
  /** 展示用时间，如 "20:25" / "END" / "待定" */
  timeText: string
  ended: boolean
  /** 今天已过播出时刻（往日全部视为已播） */
  aired: boolean
}

/** 视图模型：单日 */
interface ScheduleDay {
  date: string
  weekdayCn: string
  shortDate: string
  isToday: boolean
  offset: number
  items: ScheduleItem[]
}

/* ───────────────────────── 状态 ───────────────────────── */

const schedule = ref<RawDay[]>([])
const loading = ref(false)
const failed = ref(false)
/** 日期按钮当前高亮的那一天（点击跳转后更新） */
const activeDate = ref('')
/** 已加载数据对应的「今天」（YYYY-MM-DD），用于跨夜自动刷新 */
const loadedToday = ref('')

/** 实时时钟：驱动「已播 / 待播」与时间轴游标，每 30s 刷新一次 */
const now = ref(new Date())
let clockTimer: ReturnType<typeof setInterval> | undefined

/** 时间轴可用宽度（px）——刻度密度据此自适应，避免窄屏标签重叠 */
const axisEl = ref<HTMLElement | null>(null)
const axisWidth = ref(0)
let axisObserver: ResizeObserver | undefined

/* ───────────────────────── 生命周期 ───────────────────────── */

/** 时间表被 keep-alive 缓存时停表，回到前台立即校准 */
function startClock() {
  now.value = new Date()
  if (clockTimer) return
  clockTimer = setInterval(() => {
    now.value = new Date()
  }, 30_000)
}

function stopClock() {
  if (!clockTimer) return
  clearInterval(clockTimer)
  clockTimer = undefined
}

onMounted(() => {
  startClock()
  if (typeof ResizeObserver !== 'undefined') {
    axisObserver = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0
      if (w > 0) axisWidth.value = w
    })
  }
  load()
})

onActivated(startClock)
onDeactivated(stopClock)

// 时间轴出现后再开始观察宽度
watch(axisEl, (el) => {
  axisObserver?.disconnect()
  if (el) axisObserver?.observe(el)
}, { flush: 'post' })

onBeforeUnmount(() => {
  stopClock()
  axisObserver?.disconnect()
})

async function load() {
  loading.value = true
  failed.value = false
  try {
    const res = await bangumiApi.getCalendarLocal()
    schedule.value = Array.isArray(res?.data) ? res.data : []
    const todayRaw = schedule.value.find((d) => d.is_today) || schedule.value[0]
    loadedToday.value = todayRaw?.date || ''
    activeDate.value = todayRaw?.date || ''
  } catch {
    failed.value = true
    showError('加载放送表失败')
  } finally {
    loading.value = false
  }
}

function todayISO(): string {
  const d = now.value
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

// 页面跨夜挂着时自动刷新，避免「今天」指向前一天
watch(
  () => todayISO(),
  (cur) => {
    if (loadedToday.value && cur !== loadedToday.value) load()
  },
)

/* ───────────────────────── 工具 ───────────────────────── */

const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

/** 从 "周二 20:25" 取出分钟数；取不到返回 null */
function toMinutes(time?: string | null): number | null {
  if (!time) return null
  const m = /(\d{1,2}):(\d{1,2})/.exec(time)
  if (!m) return null
  const h = Number(m[1])
  const min = Number(m[2])
  if (!Number.isFinite(h) || !Number.isFinite(min) || h > 24 || min > 59) return null
  return h * 60 + min
}

/** 分钟数 → "HH:MM"（1440 显示为 24:00） */
function toHHMM(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

/** "2026-11-24" → "11/24" */
function toShortDate(iso?: string): string {
  const parts = (iso || '').split('-')
  return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : iso || ''
}

/** 由日期字符串兜底推算周几（后端未带 weekday 时） */
function weekdayFromDate(iso?: string): string {
  if (!iso) return ''
  const dt = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(dt.getTime())) return ''
  return WEEKDAYS[(dt.getDay() + 6) % 7]
}

/* ───────────────────────── 派生数据 ───────────────────────── */

const days = computed<ScheduleDay[]>(() => {
  const cur = now.value
  const nowMin = cur.getHours() * 60 + cur.getMinutes()

  return schedule.value.map((d) => {
    const offset = Number(d.day_offset ?? 0)
    const isToday = offset === 0 || d.is_today === true

    const items: ScheduleItem[] = (d.items || []).map((it: any) => {
      const ended = it.broadcast_time === 'END'
      const minutes = ended ? null : toMinutes(it.broadcast_time)
      const aired =
        ended || offset < 0 || (offset === 0 && minutes !== null && minutes <= nowMin)
      return {
        id: Number(it.id),
        title: it.title || it.original_title || '未知番剧',
        poster: it.image ? getImg(it.image) : '',
        rating: it.rating ? Number(it.rating) : null,
        platform: it.platform || '',
        minutes,
        timeText: ended ? 'END' : minutes === null ? '待定' : toHHMM(minutes),
        ended,
        aired,
      }
    })

    // 播出时间升序；已完结/无时间排在最后
    items.sort((a, b) => {
      if (a.ended !== b.ended) return a.ended ? 1 : -1
      if (a.minutes === null && b.minutes === null) return 0
      if (a.minutes === null) return 1
      if (b.minutes === null) return -1
      return a.minutes - b.minutes
    })

    const weekdayCn = d.weekday?.cn || d.weekday_cn || weekdayFromDate(d.date)

    return {
      date: d.date,
      weekdayCn,
      shortDate: toShortDate(d.date),
      isToday,
      offset,
      items,
    }
  })
})

/** 今天（时间轴与「已播/待播」统计都以它为准） */
const today = computed<ScheduleDay | null>(() => {
  if (!days.value.length) return null
  return days.value.find((d) => d.isToday) || days.value[0]
})

const airedCount = computed(() => today.value?.items.filter((i) => i.aired).length ?? 0)
const pendingCount = computed(() => today.value?.items.filter((i) => !i.aired).length ?? 0)
const nowText = computed(() => toHHMM(now.value.getHours() * 60 + now.value.getMinutes()))

/** 「下一部」：按日期→播出时间顺序，第一部还没播出的番剧 */
const nextItemId = computed<number | null>(() => {
  for (const d of days.value) {
    for (const item of d.items) {
      if (!item.aired && !item.ended) return item.id
    }
  }
  return null
})

/** 当日播出时间轴：小时刻度 + 各播出时刻圆点 + 「现在」游标 */
const ruler = computed(() => {
  const day = today.value
  if (!day) return null
  const mins = day.items
    .map((i) => i.minutes)
    .filter((m): m is number => m !== null)
  if (!mins.length) return null

  let lo = Math.min(...mins)
  let hi = Math.max(...mins)
  // 跨度太小（只有 1-2 部）时撑开到 3 小时，时间轴才有可读性
  if (hi - lo < 180) {
    const mid = Math.round((hi + lo) / 2)
    lo = mid - 90
    hi = mid + 90
  }
  lo = Math.max(0, Math.floor(lo / 60) * 60)
  hi = Math.min(1440, Math.ceil(hi / 60) * 60)
  if (hi - lo < 60) hi = lo + 60

  const span = hi - lo
  const pct = (m: number) => Math.min(100, Math.max(0, ((m - lo) / span) * 100))

  // 刻度间隔自适应：同时约束「标签不重叠」与「标签数量不过多」，两端始终保留刻度
  const candidates = [30, 60, 90, 120, 180, 240, 300, 360, 480, 600, 720]
  const pxWidth = axisWidth.value
  const maxTicks = pxWidth > 0 ? Math.min(9, Math.max(4, Math.round(pxWidth / 110))) : 9
  // 标签约 25px 宽，留 9px 呼吸间隙
  const minGapMin = pxWidth > 0 ? (34 / pxWidth) * span : 0
  let tickList: number[] = [lo, hi]
  for (const step of candidates) {
    const marks = new Set<number>([lo, hi])
    for (let t = Math.ceil(lo / step) * step; t < hi; t += step) marks.add(t)
    const sorted = [...marks].sort((a, b) => a - b)
    tickList = sorted
    if (sorted.length > maxTicks) continue
    const minGap = Math.min(...sorted.slice(1).map((v, i) => v - sorted[i]))
    if (minGap >= minGapMin) break
  }
  const ticks = tickList.map((t) => ({ key: t, pos: pct(t), label: toHHMM(t) }))

  // 同一时刻多部番剧只画一个点，tooltip 里给出数量
  const dotMap = new Map<number, number>()
  day.items.forEach((i) => {
    if (i.minutes === null) return
    dotMap.set(i.minutes, (dotMap.get(i.minutes) || 0) + 1)
  })
  const dots = [...dotMap.entries()].map(([m, count]) => ({
    key: m,
    pos: pct(m),
    count,
    label: toHHMM(m),
  }))

  const nowMin = now.value.getHours() * 60 + now.value.getMinutes()
  const showNow = day.isToday && nowMin >= lo && nowMin <= hi

  return {
    ticks,
    dots,
    loLabel: toHHMM(lo),
    hiLabel: toHHMM(hi),
    nowPos: showNow ? pct(nowMin) : null,
    progress: showNow ? pct(nowMin) : 0,
  }
})

/* ───────────────────────── 交互 ───────────────────────── */

/** 边缘刻度标签贴边对齐，避免溢出容器 */
function labelStyle(pos: number) {
  const transform = pos <= 2 ? 'translateX(0)' : pos >= 98 ? 'translateX(-100%)' : 'translateX(-50%)'
  return { left: `${pos}%`, transform }
}

function openDetail(item: { id: number }) {
  navStore.openBangumiDetail(item.id)
}

/** 日期按钮上的短标签：今天 / 明天 / 周X */
function dayName(d: ScheduleDay): string {
  if (d.isToday) return '今天'
  if (d.offset === 1) return '明天'
  return d.weekdayCn
}

/** 找到真正承担滚动的祖先（应用里通常是 v-main，未限制时回落到窗口） */
function findScrollParent(el: HTMLElement | null): HTMLElement | null {
  let node = el?.parentElement ?? null
  while (node) {
    if (/(auto|scroll|overlay)/.test(getComputedStyle(node).overflowY)) return node
    node = node.parentElement
  }
  return null
}

/** 点击日期按钮：滚动到对应那天的分块，顶部不被固定顶栏遮住 */
function jumpToDay(date: string) {
  activeDate.value = date
  const el = document.querySelector<HTMLElement>(`[data-day="${date}"]`)
  if (!el) return

  const barHeight = document.querySelector<HTMLElement>('.v-app-bar')?.offsetHeight ?? 0
  const offset = barHeight + 14
  const scroller = findScrollParent(el)

  if (scroller) {
    const top =
      el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - offset
    scroller.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  } else {
    const top = el.getBoundingClientRect().top + window.scrollY - offset
    window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  }
}
</script>

<template>
  <div class="schedule-tab pa-4">
    <!-- 加载骨架屏 -->
    <template v-if="loading">
      <div class="schedule-head mb-4">
        <v-skeleton-loader type="text" width="180" />
      </div>
      <div class="media-card-grid">
        <v-skeleton-loader v-for="i in 12" :key="i" type="card" />
      </div>
    </template>

    <!-- 加载失败 -->
    <EmptyState
      v-else-if="failed"
      pad="large"
      icon="mdi-alert-circle-outline"
      icon-color="error"
      title="加载放送表失败"
      description="请检查后端服务与网络连接后重试"
    >
      <template #actions>
        <v-btn color="primary" prepend-icon="mdi-refresh" @click="load">重新加载</v-btn>
      </template>
    </EmptyState>

    <template v-else-if="days.length">
      <!-- ① 今日概览（整周已全部展开，这里只汇总今天） -->
      <div class="schedule-head mb-3">
        <div class="schedule-head__text">
          <div class="schedule-head__title">
            今日放送
            <span class="schedule-head__count">{{ today?.items.length ?? 0 }} 部</span>
          </div>
          <div class="schedule-head__sub">
            {{ today?.shortDate }} {{ today?.weekdayCn }} · 已播 {{ airedCount }} · 待播 {{ pendingCount }}
          </div>
        </div>
        <div class="schedule-head__actions">
          <v-btn size="small" icon="mdi-refresh" title="刷新" @click="load" />
        </div>
      </div>

      <!-- ② 日期跳转（整周已展开，点击滚动到对应那天） -->
      <div class="schedule-daystrip mb-4">
        <button
          v-for="d in days"
          :key="d.date"
          type="button"
          class="schedule-day"
          :class="{
            'schedule-day--active': d.date === activeDate,
            'schedule-day--today': d.isToday,
          }"
          @click="jumpToDay(d.date)"
        >
          <span class="schedule-day__label">{{ dayName(d) }}</span>
          <span class="schedule-day__date">{{ d.shortDate }}</span>
          <span class="schedule-day__count">{{ d.items.length }}</span>
        </button>
      </div>

      <!-- ③ 今日播出时间轴 -->
      <div v-if="ruler" class="schedule-ruler mb-5">
        <div ref="axisEl" class="schedule-ruler__axis">
          <div class="schedule-ruler__track">
            <div
              v-if="ruler.progress"
              class="schedule-ruler__fill"
              :style="{ width: ruler.progress + '%' }"
            />
            <span
              v-for="t in ruler.ticks"
              :key="'tick-' + t.key"
              class="schedule-ruler__tick"
              :style="{ left: t.pos + '%' }"
            />
            <span
              v-for="d in ruler.dots"
              :key="'dot-' + d.key"
              class="schedule-ruler__dot"
              :class="{ 'schedule-ruler__dot--multi': d.count > 1 }"
              :style="{ left: d.pos + '%' }"
              :title="`${d.label} · ${d.count} 部`"
            />
            <span
              v-if="ruler.nowPos !== null"
              class="schedule-ruler__now"
              :style="{ left: ruler.nowPos + '%' }"
              title="当前时间"
            />
          </div>
          <div class="schedule-ruler__labels">
            <span
              v-for="t in ruler.ticks"
              :key="'label-' + t.key"
              class="schedule-ruler__label"
              :style="labelStyle(t.pos)"
            >{{ t.label }}</span>
          </div>
        </div>

        <div class="schedule-ruler__legend">
          <span class="schedule-ruler__legend-item">
            <v-icon size="11">mdi-clock-outline</v-icon>现在 {{ nowText }}
          </span>
          <span class="schedule-ruler__legend-item">
            <i class="schedule-ruler__legend-dot schedule-ruler__legend-dot--aired" />已播 {{ airedCount }}
          </span>
          <span class="schedule-ruler__legend-item">
            <i class="schedule-ruler__legend-dot" />待播 {{ pendingCount }}
          </span>
          <span class="schedule-ruler__legend-item schedule-ruler__legend-range">
            {{ ruler.loLabel }} – {{ ruler.hiLabel }}
          </span>
        </div>
      </div>

      <!-- ④ 整周放送：7 天全部展开，无需切换 -->
      <section v-for="d in days" :key="d.date" :data-day="d.date" class="schedule-section">
        <div class="schedule-section__head">
          <span class="schedule-section__title">{{ d.weekdayCn }}</span>
          <span class="schedule-section__date">{{ d.shortDate }}</span>
          <span v-if="d.isToday" class="schedule-section__tag schedule-section__tag--today">今天</span>
          <span v-else-if="d.offset === 1" class="schedule-section__tag">明天</span>
          <span class="schedule-section__count">{{ d.items.length }} 部</span>
        </div>

        <div v-if="d.items.length" class="media-card-grid">
          <v-card
            v-for="item in d.items"
            :key="item.id"
            class="glass-card media-card schedule-card cursor-pointer"
            @click="openDetail(item)"
          >
            <div class="media-card__poster">
              <v-img v-if="item.poster" :src="item.poster" cover>
                <template #placeholder>
                  <v-skeleton-loader type="image" />
                </template>
              </v-img>
              <span v-if="item.platform" class="media-card__type media-card__type--bgm">{{ item.platform }}</span>
              <span v-if="item.rating" class="media-card__rating">⭐ {{ item.rating.toFixed(1) }}</span>
              <!-- 播出时间角标 -->
              <span v-if="item.ended" class="media-card__broadcast media-card__broadcast--end">END</span>
              <span v-else-if="item.minutes !== null" class="media-card__broadcast">
                <v-icon size="12" style="color: inherit">mdi-clock-outline</v-icon>
                {{ item.timeText }}
              </span>
              <!-- 下一部角标 -->
              <span v-if="item.id === nextItemId" class="schedule-card__next">下一部</span>
            </div>
            <div class="media-card__info">
              <div class="media-card__title">{{ item.title }}</div>
              <div class="media-card__year">
                {{ item.ended ? '已完结' : item.aired ? '已播出' : '待播出' }}
              </div>
            </div>
          </v-card>
        </div>

        <div v-else class="schedule-section__empty">本日无放送</div>
      </section>
    </template>

    <!-- 整体空状态 -->
    <EmptyState
      v-else
      icon="mdi-calendar-blank-outline"
      title="暂无放送数据"
      description="番剧库为空，或尚未同步 Bangumi 条目"
    />
  </div>
</template>

<!-- 样式见 styles/cards.css §38「放送时间表」 -->
