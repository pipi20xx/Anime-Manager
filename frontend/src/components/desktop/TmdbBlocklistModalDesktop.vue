<script setup lang="ts">
import AppGlassModal from '../AppGlassModal.vue'
import AppGlassCard from '../AppGlassCard.vue'
import { NButton, NSpace, NIcon, NEmpty, NInput, NSelect } from 'naive-ui'
import { useBackDialog } from '../../composables/useBackDialog'
import { PlusIcon as AddIcon, TrashIcon as DeleteIcon } from '@heroicons/vue/24/outline'
import { useTmdbBlocklist } from '../../composables/components/useTmdbBlocklist'
import { getButtonStyle } from '../../composables/useButtonStyles'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits(['update:show'])

const dialog = useBackDialog()

const handleDelete = (item: any) => {
  dialog.warning({
    title: '确认删除',
    content: `确定删除屏蔽条目「TMDB ${item.tmdb_id}」吗？`,
    positiveText: '确定删除',
    negativeText: '取消',
    onPositiveClick: () => remove(item.id)
  })
}

const {
  blocklist, showAdd, currentItem,
  openAdd, save, remove, close
} = useTmdbBlocklist(props, emit)

const mediaTypeOptions = [
  { label: '剧集 (TV)', value: 'tv' },
  { label: '电影 (Movie)', value: 'movie' }
]
</script>

<template>
  <AppGlassModal
    appearance-key="tmdb-blocklist-modal"
    :show="show"
    @update:show="close"
    style="width: 720px;"
    title="TMDB 屏蔽列表"
    bordered
    size="huge"
  >
    <div class="main-container">
      <div class="tab-header">
        <div class="desc">
          手动填入 TMDB ID 与类型，订阅源识别命中后直接标记已下载，跳过下载规则与追剧订阅。用于主动屏蔽不想要的剧集/电影。
        </div>
        <n-button v-bind="getButtonStyle('primary')" @click="openAdd">
          添加屏蔽
        </n-button>
      </div>

      <div class="block-list">
        <AppGlassCard
          v-for="item in blocklist"
          :key="item.id"
          appearance-key="tmdb-blocklist-card"
          bordered
          embedded
          class="block-card"
        >
          <div class="card-header mb-2">
            <span class="card-name">TMDB {{ item.tmdb_id }}</span>
            <span class="card-type">{{ item.media_type === 'tv' ? '剧集' : '电影' }}</span>
          </div>
          <div class="b-disp">
            <div class="b-row" v-if="item.title">
              <span class="b-label">备注</span>
              <div class="b-v">{{ item.title }}</div>
            </div>
            <div class="b-row" v-if="item.reason">
              <span class="b-label">原因</span>
              <div class="b-v">{{ item.reason }}</div>
            </div>
            <div class="b-row" v-if="item.created_at">
              <span class="b-label">添加于</span>
              <div class="b-v">{{ new Date(item.created_at).toLocaleString() }}</div>
            </div>
          </div>
          <template #action>
            <n-space justify="end">
              <n-button v-bind="getButtonStyle('iconDanger')" size="small" @click="handleDelete(item)">
                <template #icon><n-icon><DeleteIcon /></n-icon></template>
              </n-button>
            </n-space>
          </template>
        </AppGlassCard>
        <n-empty v-if="blocklist.length === 0" description="暂无屏蔽条目，请点击右上角添加" class="mt-4" />
      </div>
    </div>

    <AppGlassModal
      appearance-key="tmdb-blocklist-edit"
      v-model:show="showAdd"
      title="添加屏蔽条目"
      style="width: 500px;"
      bordered
      size="large"
    >
      <div class="edit-form">
        <div class="form-row">
          <label>TMDB ID *</label>
          <n-input v-model:value="currentItem.tmdb_id" placeholder="如 1399" />
        </div>
        <div class="form-row">
          <label>类型</label>
          <n-select v-model:value="currentItem.media_type" :options="mediaTypeOptions" />
        </div>
        <div class="form-row">
          <label>备注名</label>
          <n-input v-model:value="currentItem.title" placeholder="如：权力的游戏（可选）" />
        </div>
        <div class="form-row">
          <label>屏蔽原因</label>
          <n-input v-model:value="currentItem.reason" placeholder="如：不想下载（可选）" />
        </div>
        <div class="form-actions">
          <n-button @click="showAdd = false">取消</n-button>
          <n-button v-bind="getButtonStyle('primary')" @click="save">添加</n-button>
        </div>
      </div>
    </AppGlassModal>
  </AppGlassModal>
</template>

<style scoped>
.main-container { padding: 8px 4px; }
.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}
.desc {
  color: var(--text-tertiary, #999);
  font-size: 13px;
  line-height: 1.6;
  max-width: 480px;
}
.block-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.block-card .card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-name { font-weight: 600; font-size: 15px; }
.card-type {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-secondary, #eee);
  color: var(--text-secondary, #666);
}
.b-disp { font-size: 13px; }
.b-row { display: flex; gap: 8px; margin: 4px 0; }
.b-label { color: var(--text-tertiary, #999); min-width: 56px; }
.b-v { color: var(--text-primary, #333); }
.edit-form { display: flex; flex-direction: column; gap: 16px; }
.form-row { display: flex; flex-direction: column; gap: 6px; }
.form-row label { font-size: 13px; color: var(--text-secondary, #666); }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.mt-4 { margin-top: 16px; }
.mb-2 { margin-bottom: 8px; }
</style>
