import { defineStore } from 'pinia'
import { ref } from 'vue'

// 行业知识 skill 问答（POST /api/v1/industry-knowledge/query + /feedback）。
// 当前后端没有「skill 列表」接口，面板直接让用户填 skill_id；默认指向本地演示 skill
// （固废政策知识，fulltext 模式）。生产应由 skill 选择器或配置下发，而非写死。
const DEFAULT_SKILL_ID = '33333333-3333-3333-3333-333333333333'

// 合法 UUID 形状校验，避免把明显的笔误打到后端再吃一个 400 往返
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export const useIndustryKnowledgeStore = defineStore('industryKnowledge', () => {
  const ikSkillId = ref(DEFAULT_SKILL_ID)
  const ikQuery   = ref('')
  const ikTopK    = ref(5)

  const ikAnswer     = ref('')
  const ikReferences = ref([])
  const ikQueryLogId = ref('')          // /feedback 需要它来定位本次问答
  const ikLoading    = ref(false)
  const ikError      = ref('')
  const ikDone       = ref(false)       // 已执行过一次，用于区分「未提问」与「无依据」

  // 针对本次问答（ikQueryLogId）的反馈状态：'up' | 'down' | ''
  const ikFeedback           = ref('')
  const ikFeedbackSubmitting = ref(false)

  // 检索 + LLM 问答；与 knowledge.js 的 runRetrieve 同构（loading/error/done 三态）
  async function runQuery() {
    const q = ikQuery.value.trim()
    const skillId = ikSkillId.value.trim()
    if (!q || ikLoading.value) return
    if (!skillId) {
      ikError.value = '请先填写 skill_id'
      ikDone.value = true
      return
    }
    if (!UUID_RE.test(skillId)) {
      ikError.value = 'skill_id 不是合法 UUID'
      ikDone.value = true
      return
    }
    // 进入新一次问答前清空上一轮的全部结果状态：否则在响应回来前，
    // 反馈按钮仍指向上一条回答的 query_log_id，可能把反馈错挂到旧问答上。
    ikLoading.value = true
    ikError.value = ''
    ikAnswer.value = ''
    ikReferences.value = []
    ikQueryLogId.value = ''
    ikFeedback.value = ''
    ikDone.value = false
    try {
      const resp = await fetch('/api/v1/industry-knowledge/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_id: skillId, query: q, top_k: ikTopK.value })
      })
      if (!resp.ok) {
        // 后端把业务错误（skill 不存在/未启用等）映射成 400 JSON {detail}，尽量透传给用户
        let msg = `HTTP ${resp.status}`
        try {
          const e = await resp.json()
          if (e && e.detail) msg = typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail)
        } catch (_) { /* 非 JSON 错误体，沿用 HTTP 状态 */ }
        throw new Error(msg)
      }
      const data = await resp.json()
      ikAnswer.value     = data.answer || ''
      ikReferences.value = Array.isArray(data.references) ? data.references : []
      ikQueryLogId.value = data.query_log_id || ''
    } catch (err) {
      ikError.value      = err.message || '问答失败'
      ikAnswer.value     = ''
      ikReferences.value = []
      ikQueryLogId.value = ''
    } finally {
      ikDone.value = true
      ikLoading.value = false
    }
  }

  // 提交赞/踩反馈；依赖上次问答返回的 query_log_id。返回 boolean，由组件决定是否 toast。
  async function submitFeedback(isHelpful) {
    // 已投过票则不再重复提交，避免赞/踩反复点出现重复反馈记录
    if (!ikQueryLogId.value || ikFeedbackSubmitting.value || ikFeedback.value) return false
    ikFeedbackSubmitting.value = true
    try {
      const resp = await fetch('/api/v1/industry-knowledge/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query_log_id: ikQueryLogId.value,
          is_helpful: isHelpful,
          rating: isHelpful ? 5 : 2
        })
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      ikFeedback.value = isHelpful ? 'up' : 'down'
      return true
    } catch (_) {
      return false
    } finally {
      ikFeedbackSubmitting.value = false
    }
  }

  return {
    ikSkillId, ikQuery, ikTopK,
    ikAnswer, ikReferences, ikQueryLogId,
    ikLoading, ikError, ikDone,
    ikFeedback, ikFeedbackSubmitting,
    runQuery, submitFeedback
  }
})
