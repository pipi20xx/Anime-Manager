<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { NSkeleton } from 'naive-ui'
import BangumiCard from '../../../components/BangumiCard.vue'
import { useRecommend } from '../../../composables/explore/useRecommend'

const {
  exploreData,
  currentScheduleTab,
  isSubscribed,
  openBangumi
} = useRecommend()

// 当前高亮的日期（滚动驱动）
const activeDate = ref('')

// 每个日期区块的 DOM 引用，用于滚动定位 & IntersectionObserver
const sectionRefs = ref<HTMLElement[]>([])
const setSectionRef = (el: any, idx: number) => {
  if (el) sectionRefs.value[idx] = el as HTMLElement
}

// 日期标签文案
const dayLabel = (day: any) => {
  const weekday = day.weekday_cn || ''
  const label = day.label ? `（${day.label}）` : ''
  const date = day.date ? day.date.slice(5).replace('-', '/') : ''
  const count = day.count ?? 0
  return { weekday, label, date, count, full: `${weekday}${label} ${date} · ${count}` }
}

// 点击导航 → 平滑滚动到对应区块
const scrollToDay = async (date: string) => {
  activeDate.value = date
  const idx = exploreData.schedule.findIndex((d: any) => d.date === date)
  if (idx < 0) return
  const el = sectionRefs.value[idx]
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// IntersectionObserver：滚动时高亮当前可视区块
let observer: IntersectionObserver | null = null
const setupObserver = () => {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      // 找到当前最靠近顶部且可见的区块
      const visible = entries
        .filter(e => e.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
      if (visible.length > 0) {
        const idx = Number((visible[0].target as HTMLElement).dataset.idx)
        const day = exploreData.schedule[idx]
        if (day) activeDate.value = day.date
      }
    },
    // 顶部偏移：吸顶导航条高度 + 一点缓冲，让区块刚露出时就触发
    { rootMargin: '-80px 0px -60% 0px', threshold: 0 }
  )
  sectionRefs.value.forEach(el => el && observer!.observe(el))
}

// ── 吸顶控制：sentinel + IntersectionObserver + position:fixed ──
// 不依赖 CSS sticky（受祖先 overflow 限制会失效），用 JS 精确控制
const sentinelRef = ref<HTMLElement | null>(null)
const navBarRef = ref<HTMLElement | null>(null)
const isPinned = ref(false)
// 记录导航条正常状态下的位置/尺寸，fixed 时复用以精确对齐
const navHeight = ref(0)
const navLeft = ref(0)
const navWidth = ref(0)
let pinObserver: IntersectionObserver | null = null

/** 读取导航条在正常流中的位置/尺寸（仅非 pinned 时调用） */
const captureNavRect = () => {
  if (!navBarRef.value || isPinned.value) return
  const rect = navBarRef.value.getBoundingClientRect()
  navHeight.value = rect.height
  navLeft.value = rect.left
  navWidth.value = rect.width
}

/** fixed 定位的 inline 样式：精确对齐原来的位置 */
const navPinStyle = computed(() => {
  if (!isPinned.value) return {}
  return {
    position: 'fixed',
    top: '0px',
    left: `${navLeft.value}px`,
    width: `${navWidth.value}px`,
    zIndex: '100'
  } as Record<string, string>
})

/** 初始化吸顶监听：sentinel 滚出视口顶部 → pin */
const setupPinObserver = () => {
  if (pinObserver) pinObserver.disconnect()
  if (!sentinelRef.value) return
  captureNavRect()
  pinObserver = new IntersectionObserver(
    ([entry]) => {
      // sentinel 的 top < 0 说明已滚出视口顶部 → 吸顶
      const shouldPin = entry.boundingClientRect.top < 0
      if (shouldPin && !isPinned.value) {
        // pin 前先记录位置（此时 nav 还在正常流中）
        captureNavRect()
      }
      isPinned.value = shouldPin
    },
    { threshold: 0 }
  )
  pinObserver.observe(sentinelRef.value)
}

/** 窗口尺寸变化（旋转屏幕等）时重新计算位置 */
const onResize = () => {
  // 先临时取消 pin 以读取正常流中的位置
  const wasPinned = isPinned.value
  isPinned.value = false
  nextTick(() => {
    captureNavRect()
    if (wasPinned) {
      // 重新判断是否需要 pin
      if (sentinelRef.value) {
        const r = sentinelRef.value.getBoundingClientRect()
        isPinned.value = r.top < 0
      }
    }
  })
}

// 数据加载完成后初始化
watch(() => exploreData.schedule, async (sched) => {
  if (sched.length > 0) {
    activeDate.value = currentScheduleTab.value || sched[0]?.date || ''
    await nextTick()
    setupObserver()
    setupPinObserver()
  }
}, { immediate: true })

onMounted(() => {
  if (exploreData.schedule.length > 0) {
    activeDate.value = currentScheduleTab.value || exploreData.schedule[0]?.date || ''
    nextTick(() => {
      setupObserver()
      setupPinObserver()
    })
  }
  window.addEventListener('resize', onResize)
  window.addEventListener('orientationchange', onResize)
})

onUnmounted(() => {
  if (observer) observer.disconnect()
  if (pinObserver) pinObserver.disconnect()
  window.removeEventListener('resize', onResize)
  window.removeEventListener('orientationchange', onResize)
})
</script>

<template>
  <div class="schedule-tab">
    <!-- 加载占位 -->
    <div v-if="exploreData.schedule.length === 0" class="section-loading">
      <n-skeleton v-for="i in 6" :key="i" class="skeleton-card" />
    </div>

    <!-- 主体：吸顶导航 + 长列表 -->
    <template v-else>
      <!-- 吸顶哨兵：高度 0，仅用于检测何时需要 pin 导航条 -->
      <div ref="sentinelRef" class="day-nav-sentinel"></div>

      <!-- 吸顶日期导航：单行紧凑布局 + 毛玻璃透明 -->
      <div class="day-nav" ref="navBarRef" :class="{ 'is-pinned': isPinned }" :style="navPinStyle">
        <button
          v-for="(day, idx) in exploreData.schedule"
          :key="day.date"
          class="day-nav-btn"
          :class="{ 'is-active': activeDate === day.date }"
          @click="scrollToDay(day.date)"
        >
          <span class="dn-weekday">{{ dayLabel(day).weekday }}<template v-if="dayLabel(day).label">{{ dayLabel(day).label }}</template></span>
          <span class="dn-date">{{ dayLabel(day).date }}</span>
          <span class="dn-count">{{ dayLabel(day).count }}</span>
        </button>
      </div>

      <!-- 占位：nav 被 fixed 脱离文档流时撑住空间，防止内容上跳 -->
      <div v-show="isPinned" class="day-nav-spacer" :style="{ height: navHeight + 'px' }"></div>

      <!-- 7 天内容纵向展开 -->
      <div class="schedule-stream">
        <section
          v-for="(day, idx) in exploreData.schedule"
          :key="day.date"
          :ref="(el) => setSectionRef(el, idx)"
          :data-idx="idx"
          class="day-section"
        >
          <h3 class="day-section-title">
            <span class="ds-weekday">{{ dayLabel(day).weekday }}</span>
            <span class="ds-date">{{ dayLabel(day).date }}</span>
            <span v-if="dayLabel(day).label" class="ds-label">{{ dayLabel(day).label }}</span>
            <span class="ds-count">{{ dayLabel(day).count }} 部</span>
          </h3>
          <div class="calendar-grid">
            <BangumiCard
              v-for="bgm in day.items"
              :key="bgm.id"
              :item="bgm"
              :is-subscribed="isSubscribed(bgm, 'bangumi')"
              @click="openBangumi(bgm)"
            />
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.schedule-tab { width: 100%; padding-bottom: var(--space-10); }

/* 加载占位 */
.section-loading { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-5); margin-top: var(--space-4); }
.skeleton-card { height: 210px; border-radius: var(--radius-xl); }

/* 吸顶哨兵：高度 0 的检测点 */
.day-nav-sentinel { height: 0; }

/* 吸顶日期导航：横向滚动 + 毛玻璃透明 */
.day-nav {
  position: sticky; /* 桌面端 fallback；移动端由 JS fixed 接管 */
  top: 0;
  z-index: 10;
  display: flex;
  gap: 2px;
  padding: 6px 8px;
  margin-bottom: var(--space-4);
  /* 毛玻璃透明：默认状态不遮住下方内容 */
  background: color-mix(in srgb, var(--bg-surface) 60%, transparent);
  backdrop-filter: blur(12px) saturate(1.4);
  -webkit-backdrop-filter: blur(12px) saturate(1.4);
  border-radius: var(--radius-lg);
  border: 1px solid color-mix(in srgb, var(--border-light) 50%, transparent);
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.day-nav::-webkit-scrollbar { display: none; }

/* pinned (fixed) 状态：贴满屏幕顶部，去掉圆角/边距与页面融合 */
.day-nav.is-pinned {
  margin: 0;
  border-radius: 0;
  border-left: none;
  border-right: none;
  border-top: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

.day-nav-btn {
  flex: 0 0 auto;
  min-width: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 10px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
  color: var(--text-secondary);
  font-family: inherit;
  white-space: nowrap;
}
.day-nav-btn:hover {
  background: color-mix(in srgb, var(--n-primary-color) 12%, transparent);
  color: var(--text-primary);
}
.day-nav-btn.is-active {
  background: var(--n-primary-color);
  color: #fff;
  box-shadow: var(--shadow-sm);
}
.dn-weekday { font-size: var(--text-sm); font-weight: 700; line-height: 1.2; }
.dn-date { font-size: var(--text-xs); opacity: 0.7; line-height: 1.2; }
.dn-count {
  font-size: var(--text-xs);
  font-weight: 600;
  opacity: 0.6;
  padding: 0 6px;
  border-radius: 999px;
  background: color-mix(in srgb, currentColor 12%, transparent);
}
.day-nav-btn.is-active .dn-count {
  opacity: 0.95;
  background: rgba(255,255,255,0.25);
}

/* 占位符：nav fixed 时撑住空间 */
.day-nav-spacer { width: 100%; }

/* 长列表容器 */
.schedule-stream { display: flex; flex-direction: column; gap: var(--space-8); }

/* 每日区块 */
.day-section {
  /* scrollIntoView 的 block:start 会让区块顶部对齐视口顶部，
     这里留出吸顶导航条的高度（约 64px）作为偏移 */
  scroll-margin-top: 72px;
}
.day-section-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 0 0 var(--space-4) 0;
  padding: 0 var(--m-1);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
}
.ds-weekday { font-weight: 800; }
.ds-date { font-size: var(--text-base); color: var(--text-tertiary); font-weight: 500; }
.ds-label { font-size: var(--text-sm); color: var(--n-primary-color); font-weight: 600; }
.ds-count { font-size: var(--text-sm); color: var(--text-tertiary); margin-left: auto; }

/* 卡片网格 */
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--space-5);
}
</style>
