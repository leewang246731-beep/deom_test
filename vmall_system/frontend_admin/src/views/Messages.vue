<template>
  <div style="display:flex;gap:12px;height:calc(100vh - 140px)">
    <div style="width:260px;flex-shrink:0"><el-card header="会话列表" shadow="never" body-style="padding:0" style="height:100%;overflow:auto">
      <div v-for="c in convs" :key="c.id" :style="{padding:'10px 12px',cursor:'pointer',borderBottom:'1px solid #ebeef5',background:active?.id===c.id?'#ecf5ff':''}" @click="selectConv(c)">
        <strong>买家#{{c.buyer_id}}</strong><br/><span style="font-size:12px;color:#909399">{{c.buyer_ip_region}} · {{c.last_message_at?.slice(0,16)||'-'}}</span></div>
      <el-empty v-if="!convs.length" description="暂无会话" :image-size="40"/></el-card></div>
    <div style="flex:1;display:flex;flex-direction:column"><el-card header="聊天" shadow="never" body-style="flex:1;overflow:auto" style="flex:1;display:flex;flex-direction:column">
      <div style="flex:1;overflow-y:auto;margin-bottom:8px">
        <div v-for="m in msgs" :key="m.id" :style="{textAlign:m.sender_role==='admin'?'right':'left',marginBottom:'8px'}">
          <div :style="{display:'inline-block',maxWidth:'60%',padding:'6px 12px',borderRadius:'8px',background:m.sender_role==='admin'?'#409eff':'#f0f0f0',color:m.sender_role==='admin'?'#fff':'#303133'}">{{m.content_json?.text||JSON.stringify(m.content_json)}}</div></div></div>
      <el-input v-model="txt" placeholder="回复..." @keyup.enter="sendMsg" :disabled="!active"><template #append><el-button @click="sendMsg" :disabled="!txt.trim()||!active">发送</el-button></template></el-input></el-card></div></div>
</template>
<script setup>
import { ref, onMounted } from 'vue'; import { getConvs, getConvMsgs, replyConv } from '../api'
const convs=ref([]); const active=ref(null); const msgs=ref([]); const txt=ref('')
async function fetch(){try{convs.value=(await getConvs({page:1,page_size:50})).data?.items||[]}catch{/* */}}
async function selectConv(c){active.value=c;msgs.value=(await getConvMsgs(c.id)).data||[]}
async function sendMsg(){if(!txt.value.trim()||!active.value)return;await replyConv(active.value.id,{msg_type:'text',content:{text:txt.value}});await selectConv(active.value);txt.value=''}
onMounted(fetch)
</script>
