import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'

export function usePriorityRules(props: { show: boolean }, emit: any) {
  const message = useMessage()
  const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

  // ================= Data State =================
  const activeTab = ref('profiles')
  const rules = ref<any[]>([])
  const profiles = ref<any[]>([])
  const loading = ref(false)

  // ================= Editors State =================
  const showRuleEdit = ref(false)
  const currentRule = ref<any>({})
  const showProfileEdit = ref(false)
  const currentProfile = ref<any>({})

  // ================= API Methods =================
  const fetchRules = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/priority/rules`)
      if (res.ok) rules.value = await res.json()
    } catch (e) { message.error('加载规则失败') }
  }

  const fetchProfiles = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/priority/profiles`)
      if (res.ok) profiles.value = await res.json()
    } catch (e) { message.error('加载策略失败') }
  }

  const init = () => {
    fetchRules()
    fetchProfiles()
  }

  watch(() => props.show, (val) => {
    if (val) init()
  })

  // ================= Rule Editor Logic =================
  const defaultCondition = {
    resolution: null,
    source: null,
    video_encode: null,
    audio_encode: null,
    video_effect: null,
    subtitle: null,
    platform: null,
    team: null,
    must_contain: '',
    must_not_contain: ''
  }

  const openAddRule = () => {
    currentRule.value = { name: '', conditions: { ...defaultCondition } }
    showRuleEdit.value = true
  }

  const openEditRule = (rule: any) => {
    currentRule.value = JSON.parse(JSON.stringify(rule))
    if (!currentRule.value.conditions) currentRule.value.conditions = { ...defaultCondition }
    showRuleEdit.value = true
  }

  const saveRule = async () => {
    if (!currentRule.value.name) return message.warning('规则名称不能为空')
    try {
      const res = await fetch(`${API_BASE}/api/priority/rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentRule.value)
      })
      if (!res.ok) throw new Error((await res.json()).detail || '保存失败')
      message.success('规则保存成功')
      showRuleEdit.value = false
      fetchRules()
    } catch (e: any) {
      message.error(e.message)
    }
  }

  const deleteRule = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/priority/rules/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error((await res.json()).detail || '删除失败')
      message.success('已删除')
      fetchRules()
    } catch (e: any) {
      message.error(e.message)
    }
  }

  // ================= Profile Editor Logic =================
  const availableRules = computed(() => {
    if (!currentProfile.value.rules_config) return rules.value
    const usedIds = currentProfile.value.rules_config.map((x: any) => x.rule_id)
    return rules.value.filter(r => !usedIds.includes(r.id))
  })

  const openAddProfile = () => {
    currentProfile.value = { 
      name: '', 
      rules_config: [], 
      upgrade_allowed: false, 
      cutoff_score: 0 
    }
    showProfileEdit.value = true
  }

  const openEditProfile = (profile: any) => {
    currentProfile.value = JSON.parse(JSON.stringify(profile))
    if (!currentProfile.value.rules_config) currentProfile.value.rules_config = []
    showProfileEdit.value = true
  }

  const addRuleToProfile = (ruleId: number) => {
    const rule = rules.value.find(r => r.id === ruleId)
    if (!rule) return
    let defaultScore = 1000
    if (currentProfile.value.rules_config.length > 0) {
      const minScore = Math.min(...currentProfile.value.rules_config.map((r: any) => r.score || 0))
      defaultScore = Math.max(0, minScore - 100)
    }
    currentProfile.value.rules_config.push({
      rule_id: rule.id,
      name: rule.name,
      score: defaultScore
    })
  }

  const removeRuleFromProfile = (index: number) => {
    currentProfile.value.rules_config.splice(index, 1)
  }

  const saveProfile = async () => {
    if (!currentProfile.value.name) return message.warning('策略名称不能为空')
    try {
      const res = await fetch(`${API_BASE}/api/priority/profiles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentProfile.value)
      })
      if (!res.ok) throw new Error((await res.json()).detail || '保存失败')
      message.success('策略保存成功')
      showProfileEdit.value = false
      fetchProfiles()
    } catch (e: any) {
      message.error(e.message)
    }
  }

  const deleteProfile = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/priority/profiles/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error((await res.json()).detail || '删除失败')
      message.success('已删除')
      fetchProfiles()
    } catch (e: any) {
      message.error(e.message)
    }
  }

  const close = () => {
    emit('update:show', false)
  }

  return {
    activeTab, rules, profiles, loading,
    showRuleEdit, currentRule, showProfileEdit, currentProfile,
    availableRules,
    openAddRule, openEditRule, saveRule, deleteRule,
    openAddProfile, openEditProfile, saveProfile, deleteProfile,
    addRuleToProfile, removeRuleFromProfile,
    close
  }
}
