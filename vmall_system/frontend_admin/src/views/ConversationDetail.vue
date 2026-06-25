<template>
  <div style="display:flex;flex-direction:column;height:calc(100vh - 140px)">
    <div style="margin-bottom:8px">
      <el-button @click="$router.push('/conversations')"><el-icon><ArrowLeft /></el-icon> 返回会话列表</el-button>
      <span style="margin-left:12px">会话 #{{ route.params.id }}</span>
    </div>
    <el-card shadow="never" style="flex:1;display:flex;flex-direction:column" body-style="flex:1;overflow:auto;display:flex;flex-direction:column">
      <div style="flex:1;overflow-y:auto;margin-bottom:8px;min-height:0">
        <div v-for="m in msgs" :key="m.id" :style="{textAlign:m.sender_role==='admin'?'right':'left',marginBottom:'8px'}">
          <div :style="{display:'inline-block',maxWidth:'60%',padding:'8px 14px',borderRadius:'8px',background:m.sender_role==='admin'?'#409eff':'#f0f0f0',color:m.sender_role==='admin'?'#fff':'#303133',fontSize:'14px'}">{{m.content_json?.text||JSON.stringify(m.content_json)}}</div>
          <div style="font-size:11px;color:#c0c4cc;margin-top:2px">{{m.created_at?.slice(11,16)}}</div>
        </div>
      </div>
      <el-input v-model="txt" placeholder="输入回复..." @keyup.enter="sendMsg"><template #append><el-button @click="sendMsg" :disabled="!txt.trim()">发送</el-button></template></el-input>
    </el-card>
  </div>
</template>
<script setup>
import { ref, onMounted, watch } from 'vue'; import { useRoute } from 'vue-router'; import { getConvMsgs, replyConv } from '../api'
const route = useRoute()
const msgs = ref([]); const txt = ref('')
async function fetch() { try { msgs.value = (await getConvMsgs(route.params.id)).data || [] } catch { /* */ } }
async function sendMsg() { if(!txt.value.trim()) return; await replyConv(route.params.id, { msg_type:'text', content:{text:txt.value} }); txt.value=''; await fetch() }
watch(()=>route.params.id, fetch)
onMounted(fetch)
</script>
