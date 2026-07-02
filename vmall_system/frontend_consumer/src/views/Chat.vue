<template>
  <div style="max-width:600px;margin:0 auto;padding:16px">
    <!-- 当前咨询商品卡片 -->
    <el-card v-if="product" shadow="hover" style="margin-bottom:12px;cursor:pointer" @click="$router.push('/product/'+product.id)">
      <div style="display:flex;gap:12px;align-items:center">
        <el-image :src="product.image" fit="cover" style="width:64px;height:64px;border-radius:8px;flex-shrink:0" />
        <div style="flex:1;min-width:0">
          <div style="font-weight:bold;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ product.title }}</div>
          <div style="color:#e6a23c;font-size:16px;font-weight:bold;margin-top:2px">¥{{ product.price }}</div>
          <div style="color:#909399;font-size:12px">库存: {{ product.stock }}件</div>
        </div>
        <el-tag type="warning" size="small">咨询中</el-tag>
      </div>
    </el-card>

    <div v-if="product || myOrders.length" style="display:flex;gap:8px;margin-bottom:8px">
      <el-button v-if="product" size="small" type="primary" plain @click="askAboutProduct">咨询此商品</el-button>
      <el-button size="small" plain @click="orderPickerVisible=true">关联我的订单</el-button>
    </div>

    <el-dialog v-model="orderPickerVisible" title="选择要咨询的订单" width="90%">
      <div v-for="o in myOrders" :key="o.id" style="padding:8px;border-bottom:1px solid #eee;cursor:pointer" @click="askAboutOrder(o)">
        <div style="font-weight:bold">{{ o.order_no }}</div>
        <div style="color:#909399;font-size:12px">状态: {{ o.status }} · ¥{{ o.pay_amount }}</div>
      </div>
      <el-empty v-if="!myOrders.length" description="暂无订单" />
    </el-dialog>

    <el-card>
      <template #header>联系客服</template>
      <div ref="chatBox" style="height:400px;overflow-y:auto;margin-bottom:12px">
        <div v-for="m in msgs" :key="m.id" :style="{textAlign:m.sender_role==='buyer'?'right':'left',marginBottom:'8px'}">
          <!-- 卡片消息 -->
          <div v-if="m.content_json?.card" :style="{display:'inline-block',maxWidth:'75%'}">
            <el-card shadow="hover" style="cursor:pointer;text-align:left" body-style="padding:8px" @click="openCard(m.content_json.card)">
              <div v-if="m.content_json.card.type==='product'" style="display:flex;gap:8px;align-items:center">
                <el-image v-if="m.content_json.card.image" :src="m.content_json.card.image" fit="cover" style="width:48px;height:48px;border-radius:6px" />
                <div>
                  <div style="font-size:13px;font-weight:bold">{{ m.content_json.card.title }}</div>
                  <div style="color:#e6a23c;font-weight:bold">¥{{ m.content_json.card.price }}</div>
                </div>
              </div>
              <div v-else style="font-size:13px">
                <div style="font-weight:bold">📦 订单 {{ m.content_json.card.order_no }}</div>
                <div style="color:#909399">状态: {{ m.content_json.card.status }} · ¥{{ m.content_json.card.amount }}</div>
              </div>
              <div style="font-size:11px;color:#409eff;margin-top:4px">点击查看 ›</div>
            </el-card>
          </div>
          <!-- 文本消息 -->
          <div v-else :style="{display:'inline-block',maxWidth:'70%',padding:'8px 12px',borderRadius:'8px',background:m.sender_role==='buyer'?'#409eff':'#f0f0f0',color:m.sender_role==='buyer'?'#fff':'#303133'}">
            <div style="font-size:11px;margin-bottom:2px;opacity:0.7">{{ m.sender_role === 'buyer' ? '我' : '客服' }}</div>
            {{m.content_json?.text||fmtContent(m.content_json)}}</div>
        </div>
        <div v-if="!msgs.length" style="text-align:center;color:#909399;padding:60px 0">暂无消息，开始咨询吧</div>
      </div>
      <el-input v-model="txt" placeholder="输入消息..." @keyup.enter="send"><template #append><el-button @click="send" :disabled="!txt.trim()">发送</el-button></template></el-input>
    </el-card></div>
</template>
<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'; import { useRoute, useRouter } from 'vue-router'; import { getMsgs, sendMsg, createConv, getMyOrders } from '../api'
import { ElMessage } from 'element-plus'
import axios from 'axios'
const http = axios.create({ baseURL: '/api/v1', timeout: 15000 })
http.interceptors.request.use(c => { const t = localStorage.getItem('vmall_token'); if (t) c.headers.Authorization = `Bearer ${t}`; return c })
http.interceptors.response.use(r => r.data)

const route=useRoute(); const r=useRouter(); const msgs=ref([]); const txt=ref(''); const chatBox=ref(null); const product=ref(null)
const myOrders = ref([]); const orderPickerVisible = ref(false)
function fmtContent(c) { try { return typeof c === 'string' ? c : JSON.stringify(c) } catch { return String(c || '') } }
let pollTimer = null; let convId = null

async function initConv() {
  if (route.params.id && route.params.id !== 'new') { convId = route.params.id; return }
  try {
    const res = await createConv({ product_id: route.query.product_id ? Number(route.query.product_id) : null })
    convId = res.data.id
    history.replaceState(null, '', `#/chat/${convId}`)
  } catch { /* fallback */ }
}

async function loadProduct() {
  if (!convId) return
  try {
    const conv = await http.get(`/consumer/conversations/${convId}`)
    if (conv.data?.product) product.value = conv.data.product
  } catch { /* ok */ }
}

async function fetch(){ if (!convId) return; try { msgs.value = (await getMsgs(convId)).data || []; scrollDown() } catch {/* */} }
async function send(){
  if (!txt.value.trim() || !convId) return
  try { await sendMsg(convId, { msg_type:'text', content:{text:txt.value} }); txt.value = ''; await fetch() } catch { /* error shown by interceptor */ }
}
function scrollDown() { nextTick(() => { if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight }) }
async function loadOrders() {
  try { myOrders.value = (await getMyOrders({ page: 1 })).data?.items || [] } catch { /* ok */ }
}
async function askAboutProduct() {
  if (!product.value || !convId) return
  const card = { type: 'product', product_id: product.value.id, title: product.value.title,
                 price: product.value.price, image: product.value.image, link: `/product/${product.value.id}` }
  try {
    await sendMsg(convId, { msg_type: 'product_card', content: { text: `咨询：${product.value.title}`, card } })
    await fetch()
  } catch { /* ok */ }
}
async function askAboutOrder(o) {
  if (!convId) return
  const card = { type: 'order', order_no: o.order_no, status: o.status, amount: o.pay_amount, link: '/orders' }
  try {
    await sendMsg(convId, { msg_type: 'order_card', content: { text: `咨询订单 ${o.order_no}`, card } })
    orderPickerVisible.value = false
    await fetch()
  } catch { /* ok */ }
}
function openCard(card) {
  if (card.type === 'product' && card.product_id) { r.push(`/product/${card.product_id}`) }
  else if (card.type === 'order') { r.push('/orders') }
  else { ElMessage.warning('无法跳转，商品信息不完整') }
}
onMounted(async () => { await initConv(); await loadProduct(); await loadOrders(); await fetch(); pollTimer = setInterval(fetch, 2000) })
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>
