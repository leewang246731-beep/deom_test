<template>
  <div style="max-width:600px;margin:0 auto;padding:16px">
    <el-card style="margin-top:8px">
      <template #header>联系客服</template>
      <div ref="chatBox" style="height:400px;overflow-y:auto;margin-bottom:12px">
        <div v-for="m in msgs" :key="m.id" :style="{textAlign:m.sender_role==='buyer'?'right':'left',marginBottom:'8px'}">
          <div :style="{display:'inline-block',maxWidth:'70%',padding:'8px 12px',borderRadius:'8px',background:m.sender_role==='buyer'?'#409eff':'#f0f0f0',color:m.sender_role==='buyer'?'#fff':'#303133'}">
            <div style="font-size:11px;margin-bottom:2px;opacity:0.7">{{ m.sender_role === 'buyer' ? '我' : '客服' }}</div>
            {{m.content_json?.text||JSON.stringify(m.content_json)}}</div></div>
        <div v-if="!msgs.length" style="text-align:center;color:#909399;padding:60px 0">暂无消息，开始咨询吧</div>
      </div>
      <el-input v-model="txt" placeholder="输入消息..." @keyup.enter="send"><template #append><el-button @click="send" :disabled="!txt.trim()">发送</el-button></template></el-input>
    </el-card></div>
</template>
<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'; import { useRoute } from 'vue-router'; import { getMsgs, sendMsg, createConv } from '../api'
const route=useRoute(); const msgs=ref([]); const txt=ref(''); const chatBox=ref(null)
let pollTimer = null; let convId = null

async function initConv() {
  if (route.params.id && route.params.id !== 'new') { convId = route.params.id; return }
  try {
    const res = await createConv({ product_id: route.query.product_id || null })
    convId = res.data.id
    history.replaceState(null, '', `#/chat/${convId}`)
  } catch { /* fallback */ }
}

async function fetch(){ if (!convId) return; try { msgs.value = (await getMsgs(convId)).data || []; scrollDown() } catch {/* */} }
async function send(){
  if (!txt.value.trim() || !convId) return
  await sendMsg(convId, { msg_type:'text', content:{text:txt.value} })
  txt.value = ''; await fetch()
}
function scrollDown() { nextTick(() => { if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight }) }
onMounted(async () => { await initConv(); await fetch(); pollTimer = setInterval(fetch, 2000) })
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>
