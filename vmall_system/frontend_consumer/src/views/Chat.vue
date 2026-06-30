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

    <el-card>
      <template #header>联系客服</template>
      <div ref="chatBox" style="height:400px;overflow-y:auto;margin-bottom:12px">
        <div v-for="m in msgs" :key="m.id" :style="{textAlign:m.sender_role==='buyer'?'right':'left',marginBottom:'8px'}">
          <div :style="{display:'inline-block',maxWidth:'70%',padding:'8px 12px',borderRadius:'8px',background:m.sender_role==='buyer'?'#409eff':'#f0f0f0',color:m.sender_role==='buyer'?'#fff':'#303133'}">
            <div style="font-size:11px;margin-bottom:2px;opacity:0.7">{{ m.sender_role === 'buyer' ? '我' : '客服' }}</div>
            {{m.content_json?.text||fmtContent(m.content_json)}}</div></div>
        <div v-if="!msgs.length" style="text-align:center;color:#909399;padding:60px 0">暂无消息，开始咨询吧</div>
      </div>
      <el-input v-model="txt" placeholder="输入消息..." @keyup.enter="send"><template #append><el-button @click="send" :disabled="!txt.trim()">发送</el-button></template></el-input>
    </el-card></div>
</template>
<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'; import { useRoute, useRouter } from 'vue-router'; import { getMsgs, sendMsg, createConv } from '../api'
import axios from 'axios'
const http = axios.create({ baseURL: '/api/v1', timeout: 15000 })
http.interceptors.request.use(c => { const t = localStorage.getItem('vmall_token'); if (t) c.headers.Authorization = `Bearer ${t}`; return c })
http.interceptors.response.use(r => r.data)

const route=useRoute(); const r=useRouter(); const msgs=ref([]); const txt=ref(''); const chatBox=ref(null); const product=ref(null)
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
onMounted(async () => { await initConv(); await loadProduct(); await fetch(); pollTimer = setInterval(fetch, 2000) })
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>
