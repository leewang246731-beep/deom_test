<template>
  <div v-loading="loading">
    <el-page-header @back="goBack" :content="ticket?.ticket_no" style="margin-bottom:16px" />

    <el-row :gutter="16">
      <el-col :span="16">
        <!-- 基本信息 -->
        <el-descriptions :column="2" border size="small" style="margin-bottom:16px">
          <el-descriptions-item label="标题" :span="2">{{ ticket?.title }}</el-descriptions-item>
          <el-descriptions-item label="优先级"><el-tag :type="priTag(ticket?.priority)" size="small">{{ ticket?.priority }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="状态"><el-tag :type="statusTag(ticket?.status)" size="small">{{ ticket?.status }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="处理人">{{ ticket?.assignee_name || '未分配' }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ ticket?.creator_name }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ ticket?.source }} #{{ ticket?.source_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ ticket?.category_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="SLA">{{ ticket?.sla_breached ? '超时' : '正常' }}{{ ticket?.sla_due_at ? ' · 截止' + ticket.sla_due_at?.slice(0,16) : '' }}</el-descriptions-item>
          <el-descriptions-item label="标签" :span="2"><el-tag v-for="t in (ticket?.ticket_tags||[])" :key="t" size="small" style="margin-right:4px">{{t}}</el-tag></el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ ticket?.description || '无' }}</el-descriptions-item>
          <el-descriptions-item v-if="ticket?.resolved_notes" label="处理纪要" :span="2">{{ ticket?.resolved_notes }}</el-descriptions-item>
        </el-descriptions>

        <!-- 时间线 -->
        <el-card header="时间线" shadow="never">
          <el-timeline>
            <el-timeline-item v-for="c in comments" :key="c.id" :timestamp="c.created_at?.slice(0,16)"
              :type="c.is_internal ? 'warning' : 'primary'"
              :hollow="c.is_internal">
              <span v-if="c.is_internal" style="color:#e6a23c">[内部] </span>
              {{ c.content }}
            </el-timeline-item>
          </el-timeline>
          <el-empty v-if="!comments.length" description="暂无评论" :image-size="40" />

          <div style="display:flex;gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid #ebeef5">
            <el-input v-model="newComment" placeholder="添加回复..." style="flex:1" @keyup.enter="sendComment" />
            <el-checkbox v-model="isInternal" style="align-self:center">内部</el-checkbox>
            <el-button type="primary" @click="sendComment" :disabled="!newComment.trim()">发送</el-button>
          </div>
        </el-card>
      </el-col>

      <!-- 操作面板 -->
      <el-col :span="8">
        <el-card header="状态操作" shadow="never" style="margin-bottom:12px">
          <el-radio-group v-model="nextStatus" style="display:flex;flex-direction:column;gap:6px" v-if="transitions.length">
            <el-radio v-for="s in transitions" :key="s" :value="s">{{ s }}</el-radio>
          </el-radio-group>
          <el-input v-if="nextStatus==='closed'" v-model="resolveNotes" placeholder="处理纪要" type="textarea" :rows="2" style="margin-top:8px" />
          <el-button type="primary" style="width:100%;margin-top:8px" :disabled="!nextStatus" @click="doStatus" :loading="statusLoading">更新状态</el-button>
        </el-card>

        <el-card header="分配" shadow="never" style="margin-bottom:12px">
          <el-select v-model="assignTo" placeholder="选择处理人" style="width:100%" filterable>
            <el-option v-for="u in userOptions" :key="u.id" :label="u.label" :value="u.id" />
          </el-select>
          <el-button style="width:100%;margin-top:8px" @click="doAssign" :disabled="!assignTo">改派</el-button>
          <el-button v-if="!ticket?.assigned_to" style="width:100%;margin-top:4px" @click="doClaim">领取工单</el-button>
        </el-card>

        <el-card header="AI 辅助" shadow="never">
          <el-button style="width:100%;margin-bottom:6px" @click="doAIClassify" :loading="aiLoading">智能分类</el-button>
          <el-button style="width:100%;margin-bottom:6px" @click="doAISuggest" :loading="aiLoading">生成回复建议</el-button>
          <el-button style="width:100%" @click="doAISummarize" :loading="aiLoading">自动总结</el-button>
          <div v-if="aiSuggestions.length" style="margin-top:8px">
            <div v-for="(s,i) in aiSuggestions" :key="i" style="padding:6px;background:#fafafa;border-radius:4px;margin-bottom:4px;font-size:12px;line-height:1.4">
              {{ s.content }}
              <el-button size="small" text @click="newComment=s.content;isInternal=false">填入回复</el-button>
            </div>
          </div>
          <div v-if="aiSummary" style="margin-top:8px;padding:8px;background:#f0f9eb;border-radius:4px;font-size:12px">
            <strong>AI 总结:</strong> {{ aiSummary }}
            <el-button size="small" text @click="resolveNotes=aiSummary">填入纪要</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getTicket, getTicketComments, addTicketComment, updateTicketStatus, assignTicket, claimTicket,
         autoClassifyTicket, autoSummarizeTicket, ticketAISuggest, getSkillGroups } from '../api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const ticket = ref(null); const loading = ref(false); const comments = ref([])
const newComment = ref(''); const isInternal = ref(false)
const nextStatus = ref(''); const resolveNotes = ref(''); const statusLoading = ref(false)
const assignTo = ref(null); const userOptions = ref([])
const aiLoading = ref(false); const aiSuggestions = ref([]); const aiSummary = ref('')

const transitions = computed(() => {
  if (!ticket.value) return []
  const map = { pending: ['in_progress','closed'], in_progress: ['waiting_customer','resolved','closed'],
    waiting_customer: ['in_progress'], resolved: ['closed','in_progress'], closed: [] }
  return map[ticket.value.status] || []
})

function priTag(p) { return {P0:'danger',P1:'warning',P2:'',P3:'info'}[p]||'' }
function statusTag(s) { return {pending:'warning',in_progress:'primary',waiting_customer:'info',resolved:'success',closed:''}[s]||'' }

async function fetchAll() {
  loading.value = true
  try {
    const [t, c] = await Promise.all([getTicket(route.params.id), getTicketComments(route.params.id)])
    ticket.value = t.data; comments.value = c.data || []
    nextStatus.value = ''
    aiSuggestions.value = []; aiSummary.value = ''
  } finally { loading.value = false }
}

async function sendComment() {
  if (!newComment.value.trim()) return
  await addTicketComment(route.params.id, { content: newComment.value, is_internal: isInternal.value ? 1 : 0 })
  newComment.value = ''; isInternal.value = false; fetchAll()
}

async function doStatus() {
  statusLoading.value = true
  try { await updateTicketStatus(route.params.id, { status: nextStatus.value, resolved_notes: resolveNotes.value || undefined }); ElMessage.success('状态已更新'); fetchAll() } finally { statusLoading.value = false }
}

function goBack() {
  if (window.history.length > 2) router.back()
  else router.push('/tickets')
}

async function doAssign() { await assignTicket(route.params.id, assignTo.value); ElMessage.success('已改派'); fetchAll() }
async function doClaim() { await claimTicket(route.params.id); ElMessage.success('已领取'); fetchAll() }

async function doAIClassify() { aiLoading.value = true; try { const r = await autoClassifyTicket(route.params.id); ElMessage.success(`建议优先级: ${r.data.suggested_priority}`); fetchAll() } finally { aiLoading.value = false } }
async function doAISummarize() { aiLoading.value = true; try { const r = await autoSummarizeTicket(route.params.id); aiSummary.value = r.data.summary } finally { aiLoading.value = false } }

async function doAISuggest() {
  aiLoading.value = true
  try { const r = await ticketAISuggest(route.params.id); aiSuggestions.value = r.data.suggestions || [] } finally { aiLoading.value = false }
}

onMounted(async () => {
  fetchAll()
  try { const g = await getSkillGroups(); const users = new Map(); (g.data||[]).forEach(grp => (grp.members||[]).forEach(m => users.set(m.user_id, {id:m.user_id, label:m.display_name||`用户${m.user_id}`}))); userOptions.value = [...users.values()] } catch { /* */ }
})
</script>
