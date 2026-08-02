<script setup lang="ts">
/**
 * MappingTab — ID映射管理
 *
 * 功能: 流派/公司/关键词/语言/国家五大分类 CRUD + 从TMDB导入 + 导入导出备份
 */
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { userMappingApi } from '@/api'
import { useNotification, useConfirm, downloadJson } from '@/composables'
import AppGlassCard from '@/components/common/AppGlassCard.vue'

const { success, error: showError, info } = useNotification()
const { confirm } = useConfirm()

const mapActiveType = ref('genre')
const mapLoading = ref(false)
const mapImportLoading = ref(false)
const mapFileImportLoading = ref(false)

const mapData = reactive({
  genres: [] as any[],
  companies: [] as any[],
  keywords: [] as any[],
  languages: [] as any[],
  countries: [] as any[],
})
const mapMeta = reactive({
  companyTotal: 0, keywordTotal: 0,
  companyPage: 1, keywordPage: 1, pageSize: 20,
  genrePage: 1, languagePage: 1, countryPage: 1,
})
const mapSearch = reactive<Record<string, string>>({ genre: '', company: '', keyword: '', language: '', country: '' })
const refCounts = ref<any>({ ref: { genres: 0, companies: 0, keywords: 0 }, user: { genres: 0, companies: 0, keywords: 0, languages: 0, countries: 0 } })

// 映射编辑弹窗
const showMapModal = ref(false)
const isNewMapItem = ref(false)
const mapForm = reactive({ id: 0, name_zh: '', name_en: '', name: '', country: '', code: '' })

async function fetchMappings() {
  mapLoading.value = true
  try {
    const [genres, languages, countries] = await Promise.all([
      userMappingApi.getGenres(mapSearch.genre),
      userMappingApi.getLanguages(mapSearch.language),
      userMappingApi.getCountries(mapSearch.country),
    ])
    mapData.genres = genres as any[]
    mapData.languages = languages as any[]
    mapData.countries = countries as any[]
  } catch (e) { showError('获取映射数据失败') } finally { mapLoading.value = false }
}

async function fetchCompanies(page = 1) {
  try {
    const res = await userMappingApi.getCompanies({ page, page_size: mapMeta.pageSize, q: mapSearch.company })
    const data = res as any
    mapData.companies = data?.items || []
    mapMeta.companyTotal = data?.total || 0; mapMeta.companyPage = page
  } catch (e) { showError('获取公司映射失败') }
}

async function fetchKeywords(page = 1) {
  try {
    const res = await userMappingApi.getKeywords({ page, page_size: mapMeta.pageSize, q: mapSearch.keyword })
    const data = res as any
    mapData.keywords = data?.items || []
    mapMeta.keywordTotal = data?.total || 0; mapMeta.keywordPage = page
  } catch (e) { showError('获取关键词映射失败') }
}

async function fetchRefCounts() {
  try { refCounts.value = await userMappingApi.getRefCounts() } catch (e) { /* ignore */ }
}

watch(mapActiveType, (t) => {
  if (t === 'company' && mapData.companies.length === 0) fetchCompanies()
  else if (t === 'keyword' && mapData.keywords.length === 0) fetchKeywords()
})

function openAddMapItem() {
  isNewMapItem.value = true
  Object.assign(mapForm, { id: 0, name_zh: '', name_en: '', name: '', country: '', code: '' })
  showMapModal.value = true
}

function openEditMapItem(item: any) {
  isNewMapItem.value = false
  Object.assign(mapForm, { ...item, id: item.id || 0, code: item.code || String(item.id) })
  showMapModal.value = true
}

async function handleSaveMap() {
  let ok = false
  const t = mapActiveType.value
  try {
    if (t === 'genre') ok = (await userMappingApi.saveGenre(mapForm))?.status === 'success'
    else if (t === 'company') ok = (await userMappingApi.saveCompany(mapForm))?.status === 'success'
    else if (t === 'keyword') ok = (await userMappingApi.saveKeyword(mapForm))?.status === 'success'
    else if (t === 'language') ok = (await userMappingApi.saveLanguage({ code: mapForm.code || String(mapForm.id), name_zh: mapForm.name_zh, name_en: mapForm.name_en }))?.status === 'success'
    else ok = (await userMappingApi.saveCountry({ code: mapForm.code || String(mapForm.id), name_zh: mapForm.name_zh, name_en: mapForm.name_en }))?.status === 'success'
    if (ok) { success('保存成功'); showMapModal.value = false; refreshCurrentMappings() }
    else showError('保存失败')
  } catch (e) { showError('保存失败') }
}

async function handleDeleteMap(id: number | string) {
  const ok = await confirm({ title: '确认删除', content: '确定要删除这条映射记录吗？', confirmColor: 'error' })
  if (!ok) return
  const t = mapActiveType.value
  try {
    if (t === 'genre') await userMappingApi.deleteGenre(Number(id))
    else if (t === 'company') await userMappingApi.deleteCompany(Number(id))
    else if (t === 'keyword') await userMappingApi.deleteKeyword(Number(id))
    else if (t === 'language') await userMappingApi.deleteLanguage(String(id))
    else await userMappingApi.deleteCountry(String(id))
    success('删除成功'); refreshCurrentMappings()
  } catch (e) { showError('删除失败') }
}

async function handleImportFromRef() {
  mapImportLoading.value = true
  try {
    const data = await userMappingApi.importFromRef(mapActiveType.value) as any
    if (data?.status === 'success') {
      const imp = data.imported || {}
      const total = (imp.genres || 0) + (imp.companies || 0) + (imp.keywords || 0)
      if (total > 0) success(`成功导入 ${total} 条数据`)
      else info('所有数据已存在，无需导入')
      refreshCurrentMappings(); fetchRefCounts()
    }
  } catch (e) { showError('导入失败') } finally { mapImportLoading.value = false }
}

async function handleExportMappings() {
  try {
    const data = await userMappingApi.exportMappings()
    downloadJson(data, `user_mappings_${new Date().toISOString().slice(0, 10)}.json`)
    success('导出成功')
  } catch (e) { showError('导出失败') }
}

function handleImportMappings() {
  const input = document.createElement('input')
  input.type = 'file'; input.accept = '.json'
  input.onchange = async (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return
    try {
      const text = await file.text()
      const json = JSON.parse(text)
      mapFileImportLoading.value = true
      const data = await userMappingApi.importMappings(json, 'append') as any
      if (data?.status === 'success') {
        const imp = data.imported || {}
        const total = (imp.genres || 0) + (imp.companies || 0) + (imp.keywords || 0) + (imp.languages || 0) + (imp.countries || 0)
        success(`成功导入 ${total} 条映射`); refreshCurrentMappings(); fetchRefCounts()
      } else showError('导入失败')
    } catch (e) { showError('文件解析错误') } finally { mapFileImportLoading.value = false }
  }
  input.click()
}

function refreshCurrentMappings() {
  const t = mapActiveType.value
  if (t === 'genre' || t === 'language' || t === 'country') fetchMappings()
  else if (t === 'company') fetchCompanies()
  else if (t === 'keyword') fetchKeywords()
}

// 分页计算
const mapPaginatedData = computed(() => {
  const t = mapActiveType.value
  let items: any[] = []
  let page = 1
  if (t === 'genre') { items = mapData.genres; page = mapMeta.genrePage }
  else if (t === 'language') { items = mapData.languages; page = mapMeta.languagePage }
  else if (t === 'country') { items = mapData.countries; page = mapMeta.countryPage }
  else if (t === 'company') { items = mapData.companies; page = mapMeta.companyPage }
  else { items = mapData.keywords; page = mapMeta.keywordPage }
  const start = (page - 1) * mapMeta.pageSize
  return items.slice(start, start + mapMeta.pageSize)
})

const mapTotal = computed(() => {
  const t = mapActiveType.value
  if (t === 'genre') return mapData.genres.length
  if (t === 'language') return mapData.languages.length
  if (t === 'country') return mapData.countries.length
  if (t === 'company') return mapMeta.companyTotal
  return mapMeta.keywordTotal
})

onMounted(() => {
  fetchMappings()
  fetchRefCounts()
})

defineExpose({ fetchMappings, fetchRefCounts })
</script>

<template>
  <!-- 统计概览 -->
  <v-row class="mb-4" dense>
    <v-col cols="6" sm="4" md="2"><AppGlassCard title="流派" icon="mdi-tag-outline">{{ refCounts.ref?.genres || 0 }} / {{ refCounts.user?.genres || 0 }}</AppGlassCard></v-col>
    <v-col cols="6" sm="4" md="2"><AppGlassCard title="制作公司" icon="mdi-office-building-outline">{{ refCounts.ref?.companies || 0 }} / {{ refCounts.user?.companies || 0 }}</AppGlassCard></v-col>
    <v-col cols="6" sm="4" md="2"><AppGlassCard title="关键词" icon="mdi-tag-heart-outline">{{ refCounts.ref?.keywords || 0 }} / {{ refCounts.user?.keywords || 0 }}</AppGlassCard></v-col>
    <v-col cols="6" sm="4" md="2"><AppGlassCard title="语言" icon="mdi-translate">{{ refCounts.user?.languages || 0 }}</AppGlassCard></v-col>
    <v-col cols="6" sm="4" md="2"><AppGlassCard title="国家" icon="mdi-earth">{{ refCounts.user?.countries || 0 }}</AppGlassCard></v-col>
  </v-row>

  <v-card class="glass-card pa-4">
    <div class="d-flex justify-space-between align-center mb-3 flex-wrap ga-2">
      <div class="text-subtitle-1 font-weight-bold">ID 映射管理</div>
      <div class="d-flex ga-2">
        <v-btn variant="tonal" size="small" prepend-icon="mdi-download-outline" @click="handleExportMappings">导出备份</v-btn>
        <v-btn variant="tonal" size="small" prepend-icon="mdi-upload-outline" :loading="mapFileImportLoading" @click="handleImportMappings">导入备份</v-btn>
        <v-btn v-if="['genre','company','keyword'].includes(mapActiveType)" variant="tonal" size="small" prepend-icon="mdi-import" :loading="mapImportLoading" @click="handleImportFromRef">导入当前分类</v-btn>
        <v-btn color="primary" variant="flat" size="small" prepend-icon="mdi-plus" @click="openAddMapItem">添加映射</v-btn>
      </div>
    </div>

    <v-tabs v-model="mapActiveType" density="compact" class="mb-3">
      <v-tab value="genre">流派</v-tab>
      <v-tab value="company">制作公司</v-tab>
      <v-tab value="keyword">关键词</v-tab>
      <v-tab value="language">原始语言</v-tab>
      <v-tab value="country">原始国家</v-tab>
    </v-tabs>

    <!-- 搜索 -->
    <v-text-field v-model="mapSearch[mapActiveType]" density="compact" variant="outlined" prepend-inner-icon="mdi-magnify" clearable hide-details class="mb-3" placeholder="搜索 ID 或名称..." @keyup.enter="refreshCurrentMappings" @click:clear="refreshCurrentMappings" />

    <!-- 数据表 -->
    <v-table density="compact" class="rounded" v-if="mapPaginatedData.length > 0">
      <thead>
        <tr>
          <th>ID/代码</th>
          <th>中文名称</th>
          <th>英文名称</th>
          <th v-if="mapActiveType === 'company'">国家</th>
          <th style="width:100px">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in mapPaginatedData" :key="item.id || item.code">
          <td class="font-weight-medium">{{ item.code || item.id }}</td>
          <td>{{ item.name_zh || item.name || '-' }}</td>
          <td>{{ item.name_en || '-' }}</td>
          <td v-if="mapActiveType === 'company'">{{ item.country || '-' }}</td>
          <td>
            <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-pencil-outline" @click="openEditMapItem(item)">编辑</v-btn>
            <v-btn size="small" variant="tonal" color="error" prepend-icon="mdi-delete-outline" @click="handleDeleteMap(item.code || item.id)">删除</v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>
    <div v-else class="text-center pa-6 text-body-2 text-medium-emphasis">暂无{{ mapActiveType === 'genre' ? '流派' : mapActiveType === 'company' ? '公司' : mapActiveType === 'keyword' ? '关键词' : mapActiveType === 'language' ? '语言' : '国家' }}映射</div>
  </v-card>

  <!-- 映射编辑弹窗 -->
  <v-dialog v-model="showMapModal" max-width="500">
    <v-card class="glass-card">
      <v-card-title class="pa-4 d-flex align-center">{{ isNewMapItem ? '添加映射' : '编辑映射' }}
<v-spacer />
<v-btn icon="mdi-close" variant="text" size="small" @click="showMapModal = false" />
</v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <template v-if="mapActiveType === 'genre'">
          <v-text-field v-model="mapForm.id" label="ID" type="number" :disabled="!isNewMapItem" variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="mapForm.name_zh" label="中文名" variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="mapForm.name_en" label="英文名" variant="outlined" density="compact" class="mb-3" />
        </template>
        <template v-else-if="mapActiveType === 'company'">
          <v-text-field v-model="mapForm.id" label="ID" type="number" :disabled="!isNewMapItem" variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="mapForm.name" label="名称" variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="mapForm.country" label="国家" variant="outlined" density="compact" class="mb-3" placeholder="如: JP, CN, US" />
        </template>
        <template v-else-if="mapActiveType === 'keyword'">
          <v-text-field v-model="mapForm.id" label="ID" type="number" :disabled="!isNewMapItem" variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="mapForm.name_zh" label="中文名" variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="mapForm.name_en" label="英文名" variant="outlined" density="compact" class="mb-3" />
        </template>
        <template v-else>
          <v-text-field v-model="mapForm.code" label="代码" :disabled="!isNewMapItem" variant="outlined" density="compact" class="mb-3" :placeholder="mapActiveType === 'language' ? '如: ja, zh, en' : '如: JP, CN, US'" />
          <v-text-field v-model="mapForm.name_zh" label="中文名" variant="outlined" density="compact" class="mb-3" />
          <v-text-field v-model="mapForm.name_en" label="英文名" variant="outlined" density="compact" class="mb-3" />
        </template>
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="showMapModal = false">取消</v-btn>
        <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="handleSaveMap">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
