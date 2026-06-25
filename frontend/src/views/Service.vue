<template>
  <div>
    <div style="display:flex;height:calc(100vh - 120px);gap:12px">
    <!-- 左栏：会话列表 -->
    <div style="width:260px;flex-shrink:0;display:flex;flex-direction:column">
      <el-card shadow="never" style="flex:1;overflow:auto" body-style="padding:0">
        <template #header><span style="font-weight:bold">会话列表</span><el-tag size="small" style="margin-left:8px" type="danger">{{ pendingCount }}</el-tag><el-button size="small" text style="float:right" @click="handleExportConvs">导出</el-button></template>
        <div v-for="c in conversations" :key="c.id" :style="{padding:'12px',cursor:'pointer',background: activeConv?.id === c.id ? '#ecf5ff' : '',borderBottom:'1px solid #ebeef5'}" @click="selectConv(c)">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <strong style="font-size:14px">{{ c.buyer_nick }}</strong>
            <el-tag v-if="c.handled_status === 'pending'" type="danger" size="small" effect="dark">新</el-tag>
            <el-tag v-else-if="c.handled_status === 'replied'" type="success" size="small">已回</el-tag>
            <el-tag v-else type="info" size="small">关闭</el-tag>
          </div>
          <p style="margin:4px 0 0;color:#909399;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ c.preview }}</p>
        </div>
        <el-empty v-if="!conversations.length" description="暂无会话" />
      </el-card>
    </div>

    <!-- 中栏：聊天窗口 -->
    <div style="flex:1;display:flex;flex-direction:column">
      <el-card shadow="never" style="flex:1;display:flex;flex-direction:column" body-style="flex:1;overflow:auto;padding:12px">
        <template #header>
          <span style="font-weight:bold">{{ activeConv ? activeConv.buyer_nick + ' 的会话' : '请选择会话' }}</span>
          <span v-if="activeConv" style="float:right;font-size:12px;color:#909399">产品ID: {{ activeConv.product_id || '-' }}</span>
        </template>
        <div v-if="activeConv" style="flex:1;overflow-y:auto;padding-right:8px">
          <div v-for="(msg, i) in activeConv.messages_json || []" :key="i" :style="{marginBottom:'12px',textAlign:msg.role==='buyer'?'left':'right'}">
            <div :style="{display:'inline-block',maxWidth:'70%',padding:'8px 14px',borderRadius:'8px',background:msg.role==='buyer'?'#f0f0f0':'#409eff',color:msg.role==='buyer'?'#303133':'#fff',textAlign:'left',wordBreak:'break-word'}">
              <div style="font-size:12px;margin-bottom:2px;opacity:0.7">{{ msg.role === 'buyer' ? activeConv.buyer_nick : '客服' }} · {{ msg.time?.slice(11, 16) || '' }}</div>
              {{ msg.content }}
            </div>
          </div>
        </div>
        <el-empty v-else description="点击左侧会话开始对话" style="flex:1" />
        <div style="display:flex;gap:8px;margin-top:8px;padding-top:8px;border-top:1px solid #ebeef5" v-if="activeConv && activeConv.handled_status !== 'closed'">
          <el-input v-model="replyText" placeholder="输入回复..." @keyup.enter="sendReply" style="flex:1" />
          <el-button type="primary" @click="sendReply" :disabled="!replyText.trim()">发送</el-button>
          <el-button type="warning" @click="convertToTicket">转工单</el-button>
        </div>
        <el-tag v-else-if="activeConv" type="info" style="margin-top:8px">会话已关闭</el-tag>
      </el-card>
    </div>

    <!-- 右栏：AI 话术面板 -->
    <div style="width:280px;flex-shrink:0;display:flex;flex-direction:column">
      <el-card shadow="never" style="flex:1;overflow:auto" body-style="padding:12px">
        <template #header><span style="font-weight:bold">🤖 AI 推荐话术</span></template>
        <div v-if="!activeConv">
          <el-empty description="选择会话后自动生成" style="padding:20px 0" />
        </div>
        <div v-else v-for="(s, i) in suggestions" :key="i" style="margin-bottom:12px;padding:10px;background:#fafafa;border-radius:6px;border:1px solid #ebeef5">
          <p style="margin:0;font-size:13px;line-height:1.6;color:#303133">{{ s.content }}</p>
          <div style="margin-top:6px;display:flex;gap:4px;justify-content:flex-end;font-size:11px;color:#909399">
            <span v-if="s.confidence">置信度: {{ Math.round(s.confidence * 100) }}%</span>
          </div>
          <div style="margin-top:6px;display:flex;gap:6px">
            <el-button size="small" plain @click="copyText(s.content)">复制</el-button>
            <el-button size="small" type="primary" @click="useSuggestion(s.content)">填入</el-button>
          </div>
        </div>
        <el-empty v-if="activeConv && !suggestions.length" description="点击 AI 建议生成" style="padding:20px 0" />
        <el-button type="primary" style="width:100%;margin-top:8px" :loading="aiLoading" @click="fetchAISuggest" :disabled="!activeConv">生成 AI 建议</el-button>
      </el-card>

      <!-- 物流状态卡片 -->
      <el-card v-if="logistics" shadow="never" style="flex-shrink:0;margin-top:12px" body-style="padding:12px">
        <template #header><span style="font-weight:bold">📦 物流状态</span></template>
        <div style="font-size:13px;line-height:1.8">
          <p style="margin:0"><strong>{{ logistics.status_label || logistics.status }}</strong>
            <el-tag v-if="logistics.exception_code" type="danger" size="small" style="margin-left:4px">异常</el-tag></p>
          <p style="margin:2px 0;color:#606266">{{ logistics.current_node }}</p>
          <p style="margin:2px 0;color:#909399;font-size:12px">
            快递: {{ logistics.company }} {{ logistics.tracking_no }}<br/>
            预计 {{ logistics.estimated_days }} 天送达
          </p>
          <p v-if="logistics.exception_detail" style="margin:2px 0;color:#f56c6c;font-size:12px">⚠ {{ logistics.exception_detail }}</p>
        </div>
      </el-card>

      <!-- 推荐商品面板 -->
      <el-card shadow="never" style="flex-shrink:0;max-height:260px;overflow:auto;margin-top:12px" body-style="padding:12px">
        <template #header><span style="font-weight:bold">🛍️ 推荐商品</span></template>
        <div v-if="!activeConv">
          <el-empty description="选择会话后自动推荐" :image-size="40" />
        </div>
        <div v-else v-for="(r, i) in recommendations" :key="i" style="margin-bottom:8px;padding:8px;background:#fafafa;border-radius:6px;border:1px solid #ebeef5">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <strong style="font-size:13px;color:#303133;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.product.title }}</strong>
            <span style="color:#e6a23c;font-weight:bold;margin-left:4px">¥{{ r.product.price }}</span>
          </div>
          <p style="margin:4px 0 0;font-size:11px;color:#909399">{{ r.why }}</p>
          <div style="margin-top:4px">
            <el-button size="small" plain @click="sendProductCard(r)">发送商品卡片</el-button>
          </div>
        </div>
        <el-empty v-if="activeConv && !recommendations.length && !recLoading" description="暂无推荐" :image-size="40" />
        <el-button size="small" style="width:100%;margin-top:4px" :loading="recLoading" @click="fetchRecommendations" :disabled="!activeConv">刷新推荐</el-button>
      </el-card>
    </div>
  </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getConversations, getConversation, aiSuggest, aiSuggestLog, getSimilarProducts, createTicket, takeoverConv, sendConversationMessage, exportCSV } from '../api'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()
const conversations = ref([])
const activeConv = ref(null)
const replyText = ref('')
const suggestions = ref([])
const aiLoading = ref(false)
const pendingCount = ref(0)
const recLoading = ref(false)
const recommendations = ref([])
const logistics = ref(null)
let ws = null
let pollTimer = null

async function fetchList() {
  try {
    const res = await getConversations({ page: 1, page_size: 99 })
    conversations.value = res.data?.items || []
    pendingCount.value = res.data?.items?.filter(c => c.handled_status === 'pending').length || 0
  } catch { /* ok */ }
}

async function selectConv(c) {
  try {
    const res = await getConversation(c.id)
    activeConv.value = res.data
    suggestions.value = []
    recommendations.value = []
    fetchRecommendations()
  } catch { /* ok */ }
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制')
    trackAdoption(text, 1)
  })
}

function trackAdoption(suggestionText, wasAdopted) {
  if (!activeConv.value) return
  const msgs = activeConv.value.messages_json || []
  const lastBuyer = [...msgs].reverse().find(m => m.role === 'buyer')
  aiSuggestLog({
    conversation_id: activeConv.value.id,
    buyer_question: lastBuyer?.content || '',
    ai_suggestion: suggestionText,
    was_adopted: wasAdopted,
    final_message: wasAdopted === 2 ? replyText.value : null,
  }).catch(() => { /* silent */ })
}

function useSuggestion(text) { replyText.value = text }

async function sendReply() {
  if (!replyText.value.trim() || !activeConv.value) return
  const matched = suggestions.value.find(s => s.content === replyText.value)
  const sent = replyText.value
  replyText.value = ''
  try {
    const res = await sendConversationMessage(activeConv.value.id, { content: sent })
    activeConv.value.messages_json = res.data?.messages_json || []
    ElMessage.success('已发送')
    if (matched) trackAdoption(sent, 1)
    fetchList()
  } catch { /* error shown by interceptor */ }
}

async function fetchAISuggest() {
  if (!activeConv.value) return
  aiLoading.value = true
  try {
    const msgs = activeConv.value.messages_json || []
    const lastBuyer = [...msgs].reverse().find(m => m.role === 'buyer')
    const res = await aiSuggest({
      shop_id: activeConv.value.shop_id,
      buyer_question: lastBuyer?.content || '有什么可以帮您的？',
      conversation_history: msgs.slice(-6),
      product_id: activeConv.value.product_id,
    })
    suggestions.value = res.data?.suggestions || []
    logistics.value = res.data?.logistics || null
  } finally { aiLoading.value = false }
}

async function fetchRecommendations() {
  if (!activeConv.value) return
  recLoading.value = true
  try {
    const res = await getSimilarProducts({ product_id: activeConv.value.product_id, shop_id: activeConv.value.shop_id, top_k: 5 })
    recommendations.value = (res.data?.recommendations || []).slice(0, 5)
  } catch { /* ok */ } finally { recLoading.value = false }
}

async function sendProductCard(r) {
  if (!activeConv.value) return
  try {
    const cardText = `[商品推荐] ${r.product.title}  ¥${r.product.price}\n${r.why}`
    const res = await sendConversationMessage(activeConv.value.id, { content: cardText })
    activeConv.value.messages_json = res.data?.messages_json || []
    ElMessage.success('已发送商品卡片')
  } catch { /* error shown by interceptor */ }
}

async function convertToTicket() {
  if (!activeConv.value) return
  const msgs = activeConv.value.messages_json || []
  const lastBuyer = [...msgs].reverse().find(m => m.role === 'buyer')
  try {
    const r = await createTicket({
      title: `会话升级: ${lastBuyer?.content?.slice(0, 50) || '买家咨询'}`,
      description: `来自会话 #${activeConv.value.id}，买家 ${activeConv.value.buyer_nick}`,
      source: 'conversation', source_id: activeConv.value.id,
      priority: 'P2', buyer_openid: activeConv.value.buyer_nick,
    })
    ElMessage.success(`工单 ${r.data.ticket_no} 已创建`)
    router.push(`/tickets/${r.data.id}`)
  } catch { /* error shown */ }
}

function setupWS() {
  const token = auth.token
  ws = new WebSocket(`ws://${location.host}/ws/service?token=${token}`)
  ws.onopen = () => console.log('[WS] connected')
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.type === 'new_conversation' || data.type === 'new_message') fetchList()
    } catch { /* ignore */ }
  }
  ws.onclose = () => { setTimeout(setupWS, 5000) }
}

onMounted(async () => {
  fetchList(); setupWS(); pollTimer = setInterval(fetchList, 3000)
})
function handleExportConvs() { exportCSV('conversations') }
onUnmounted(() => { if (ws) ws.close(); if (pollTimer) clearInterval(pollTimer) })
</script>
