<script setup lang="ts">
/**
 * TmdbPersonDetailView — TMDB 人物详情页
 *
 * 功能:
 * - 人物头像 + 基本信息
 * - 参演作品卡片网格
 * - 参与制作的作品
 */
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { tmdbApi } from '@/api'
import { useNotification } from '@/composables'
import { getImg } from '@/composables/useDataCenter'
import { useNavigationStore } from '@/stores'

defineOptions({ name: 'TmdbPersonDetailView' })

const route = useRoute()
const { error: showError } = useNotification()
const navStore = useNavigationStore()

const person = ref<any>(null)
const credits = ref<any>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const activeCreditsTab = ref('cast')

// 使用统一的 getImg 函数（自动附加 token 和处理代理路径）
function getPosterUrl(path: string): string {
  if (!path) return ''
  return getImg(path)
}

async function fetchPerson(retryCount = 0) {
  const id = route.params.id as string
  if (!id) return

  loading.value = true
  error.value = null
  const MAX_RETRIES = 3

  try {
    const [personData, creditsData] = await Promise.allSettled([
      tmdbApi.getPerson(id),
      tmdbApi.getPersonCredits(id),
    ])

    // 检查人物详情请求是否失败
    if (personData.status === 'rejected') {
      const errMsg = String(personData.reason)
      if (retryCount < MAX_RETRIES - 1 &&
          (errMsg.includes('fetch') || errMsg.includes('network') || errMsg.includes('timeout'))) {
        console.log(`[Person Detail] 请求失败，${retryCount + 1}/${MAX_RETRIES} 秒后重试...`)
        await new Promise(r => setTimeout(r, 1000 * (retryCount + 1)))
        return fetchPerson(retryCount + 1)
      }
      throw personData.reason
    }

    if (personData.status === 'fulfilled') {
      person.value = personData.value
    }
    if (creditsData.status === 'fulfilled') {
      credits.value = creditsData.value
    }
  } catch (err: any) {
    error.value = err?.message || '加载人物详情失败，请检查网络连接'
    console.error('[Person Detail] 加载失败:', err)
  } finally {
    loading.value = false
  }
}

function openDetail(item: any) {
  const mediaType = item.media_type || (item.first_air_date ? 'tv' : 'movie')
  navStore.openTmdbDetail(item.id, mediaType)
}

function calculateAge(birthday: string, deathday?: string): string {
  if (!birthday) return ''
  const birth = new Date(birthday)
  const end = deathday ? new Date(deathday) : new Date()
  let age = end.getFullYear() - birth.getFullYear()
  const m = end.getMonth() - birth.getMonth()
  if (m < 0 || (m === 0 && end.getDate() < birth.getDate())) {
    age--
  }
  return `${age} 岁`
}

watch(() => route.params.id, () => {
  if (route.params.id) {
    window.scrollTo(0, 0)
    fetchPerson()
  }
})

onMounted(() => {
  fetchPerson()
})
</script>

<template>
  <div class="person-detail-view">
    <!-- 加载骨架屏 -->
    <template v-if="loading">
      <v-container fluid class="pa-4 pa-md-6">
        <v-row>
          <v-col cols="12" sm="3" md="2">
            <v-skeleton-loader type="image" />
          </v-col>
          <v-col cols="12" sm="9" md="10">
            <v-skeleton-loader type="heading, paragraph, paragraph" />
          </v-col>
        </v-row>
      </v-container>
    </template>

    <!-- 详情内容 -->
    <template v-else-if="person">
      <v-container fluid class="pa-4 pa-md-6">
        <v-row>
          <!-- 头像 -->
          <v-col cols="12" sm="3" md="2">
            <v-img
              v-if="person.profile_path"
              :src="getImg(person.profile_path)"
              cover
              rounded="xl"
              aspect-ratio="2/3"
              class="elevation-4"
            />
            <v-avatar v-else size="200" rounded="xl" color="surface-variant">
              <v-icon icon="mdi-account" size="80" />
            </v-avatar>
          </v-col>

          <!-- 信息 -->
          <v-col cols="12" sm="9" md="10">
            <h1 class="page-title text-h4 font-weight-bold">{{ person.name }}</h1>
            <div v-if="person.known_for_department" class="page-subtitle text-body-1 mt-1">
              {{ person.known_for_department === 'Acting' ? '演员' : person.known_for_department === 'Directing' ? '导演' : person.known_for_department }}
            </div>

            <!-- 基本信息标签 -->
            <v-chip-group class="mt-3">
              <v-chip v-if="person.birthday" size="small" variant="tonal">
                <v-icon start size="16">mdi-cake-variant-outline</v-icon>
                {{ person.birthday }}
                <span v-if="!person.deathday" class="ml-1">({{ calculateAge(person.birthday) }})</span>
              </v-chip>
              <v-chip v-if="person.deathday" size="small" variant="tonal" color="error">
                <v-icon start size="16">mdi-cross</v-icon>
                {{ person.deathday }}
                <span class="ml-1">({{ calculateAge(person.birthday, person.deathday) }})</span>
              </v-chip>
              <v-chip v-if="person.gender" size="small" variant="tonal">
                {{ person.gender === 1 ? '女' : person.gender === 2 ? '男' : '未知' }}
              </v-chip>
              <v-chip v-if="person.place_of_birth" size="small" variant="tonal">
                <v-icon start size="16">mdi-map-marker-outline</v-icon>
                {{ person.place_of_birth }}
              </v-chip>
              <v-chip v-if="person.popularity" size="small" variant="tonal" color="primary">
                热度 {{ person.popularity?.toFixed(1) }}
              </v-chip>
            </v-chip-group>

            <!-- 别名 -->
            <div v-if="person.also_known_as?.length" class="mt-3">
              <div class="section-title text-subtitle-2 font-weight-medium mb-1">别名</div>
              <div class="d-flex flex-wrap ga-1">
                <v-chip v-for="name in person.also_known_as.slice(0, 8)" :key="name" size="small" variant="tonal" color="primary">
                  {{ name }}
                </v-chip>
              </div>
            </div>

            <!-- 简介 -->
            <div v-if="person.biography" class="mt-4">
              <div class="section-title text-subtitle-2 font-weight-medium mb-1">简介</div>
              <div class="page-subtitle text-body-2">{{ person.biography }}</div>
            </div>
            <div v-else class="mt-4">
              <div class="text-body-2 text-medium-emphasis">暂无中文简介</div>
            </div>
          </v-col>
        </v-row>

        <!-- 参演作品 -->
        <div v-if="credits" class="mt-8">
          <v-tabs v-model="activeCreditsTab" color="primary" class="mb-4">
            <v-tab value="cast">
              演员作品
              <v-chip v-if="credits.cast?.length" size="x-small" variant="tonal" class="ml-2">{{ credits.cast.length }}</v-chip>
            </v-tab>
            <v-tab value="crew">
              参与制作
              <v-chip v-if="credits.crew?.length" size="x-small" variant="tonal" class="ml-2">{{ credits.crew.length }}</v-chip>
            </v-tab>
          </v-tabs>

          <v-window v-model="activeCreditsTab">
            <!-- 演员作品 -->
            <v-window-item value="cast">
              <div v-if="credits.cast?.length" class="media-card-grid">
                <v-card
                  v-for="item in credits.cast.slice(0, 24)"
                  :key="item.credit_id || item.id"
                  class="glass-card media-card cursor-pointer"
                  @click="openDetail(item)"
                >
                  <div class="media-card__poster">
                    <v-img
                      v-if="item.poster_path"
                      :src="getPosterUrl(item.poster_path)"
                      cover
                      class="rounded-t-xl"
                    >
                      <template #placeholder>
                        <v-skeleton-loader type="image" />
                      </template>
                    </v-img>
                    <span class="media-card__type" :class="item.media_type === 'movie' ? 'media-card__type--tmdb-movie' : 'media-card__type--tmdb-tv'">
                      {{ item.media_type === 'movie' ? '电影' : '剧集' }}
                    </span>
                    <span v-if="item.vote_average" class="media-card__rating">⭐ {{ item.vote_average?.toFixed(1) }}</span>
                  </div>
                  <div class="media-card__info">
                    <div class="media-card__title">{{ item.title || item.name }}</div>
                    <div class="media-card__year">{{ (item.release_date || item.first_air_date || '').slice(0, 4) }}</div>
                    <div v-if="item.character" class="media-card__subtitle">饰 {{ item.character }}</div>
                  </div>
                </v-card>
              </div>
              <div v-else class="text-center pa-8">
                <v-icon size="48" color="primary" class="mb-3">mdi-movie-open-outline</v-icon>
                <div class="text-body-1">暂无演员作品</div>
              </div>
            </v-window-item>

            <!-- 参与制作 -->
            <v-window-item value="crew">
              <div v-if="credits.crew?.length" class="media-card-grid">
                <v-card
                  v-for="item in credits.crew.slice(0, 24)"
                  :key="item.credit_id || item.id"
                  class="glass-card media-card cursor-pointer"
                  @click="openDetail(item)"
                >
                  <div class="media-card__poster">
                    <v-img
                      v-if="item.poster_path"
                      :src="getPosterUrl(item.poster_path)"
                      cover
                      class="rounded-t-xl"
                    >
                      <template #placeholder>
                        <v-skeleton-loader type="image" />
                      </template>
                    </v-img>
                    <span class="media-card__type" :class="item.media_type === 'movie' ? 'media-card__type--tmdb-movie' : 'media-card__type--tmdb-tv'">
                      {{ item.media_type === 'movie' ? '电影' : '剧集' }}
                    </span>
                    <span v-if="item.vote_average" class="media-card__rating">⭐ {{ item.vote_average?.toFixed(1) }}</span>
                  </div>
                  <div class="media-card__info">
                    <div class="media-card__title">{{ item.title || item.name }}</div>
                    <div class="media-card__year">{{ (item.release_date || item.first_air_date || '').slice(0, 4) }}</div>
                    <div v-if="item.job || item.department" class="media-card__subtitle">{{ item.job || item.department }}</div>
                  </div>
                </v-card>
              </div>
              <div v-else class="text-center pa-8">
                <v-icon size="48" color="primary" class="mb-3">mdi-movie-open-outline</v-icon>
                <div class="text-body-1">暂无制作作品</div>
              </div>
            </v-window-item>
          </v-window>
        </div>
      </v-container>
    </template>

    <!-- 错误状态 -->
    <div v-else-if="error" class="text-center pa-8">
      <v-icon size="64" color="error" class="mb-4">mdi-alert-circle-outline</v-icon>
      <div class="text-h6 mb-2">加载失败</div>
      <div class="text-body-2 text-medium-emphasis mb-4">{{ error }}</div>
      <v-btn color="primary" prepend-icon="mdi-refresh" @click="fetchPerson()">
        重新加载
      </v-btn>
    </div>

    <!-- 空状态 -->
    <div v-else class="text-center pa-8">
      <v-icon size="64" color="grey" class="mb-4">mdi-account-off</v-icon>
      <div class="text-h6">暂无数据</div>
    </div>
  </div>
</template>


