<template>
  <div style="display:flex;gap:12px;height:calc(100vh - 140px)">
    <div style="width:280px;flex-shrink:0"><el-card header="会话列表" shadow="never" body-style="padding:0" style="height:100%;overflow:auto">
      <div v-for="c in convs" :key="c.id" :style="{padding:'10px 12px',cursor:'pointer',borderBottom:'1px solid #ebeef5',background:active?.id===c.id?'#ecf5ff':''}" @click="selectConv(c)">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <strong>买家#{{c.buyer_id}}</strong>
          <el-tag v-if="c.status" size="small" :type="c.status==='open'?'success':'info'">{{c.status}}</el-tag>
        </div>
        <div style="font-size:12px;color:#909399;margin-top:4px">{{c.buyer_ip_region || '未知'} · {{c.last_message_at?.slice(0,16)||'-'}}</div>
      </div>
      <el-empty v-if="!convs.length" description="暂无会话" :image-size="40"/></el-card></div>
    <div style="flex:1;display:flex;flex-direction:column">
      <el-card header="聊天" shadow="never" body-style="flex:1;overflow:auto" style="flex:1;display:flex;flex-direction:column">
        <template v-if="active">
          <div style="flex:1;overflow-y:auto;margin-bottom:8px;min-height:0">
            <div v-for="m in msgs" :key="m.id" :style="{textAlign:m.sender_role==='admin'?'right':'left',marginBottom:'8px'}">
              <div :style="{display:'inline-block',maxWidth:'60%',padding:'8px 14px',borderRadius:'8px',background:m.sender_role==='admin'?'#409eff':'#f0f0f0',color:m.sender_role==='admin'?'#fff':'#303133',fontSize:'14px'}">{{m.content_json?.text||JSON.stringify(m.content_json)}}</div>
              <div style="font-size:11px;color:#c0c4cc;margin-top:2px">{{m.created_at?.slice(11,16)}}</div>
            </div>
          </div>
          <el-input v-model="txt" placeholder="输入回复..." @keyup.enter="sendMsg"><template #append><el-button @click="sendMsg" :disabled="!txt.trim()">发送</el-button></template></el-input>
        </template>
        <el-empty v-else description="请选择一个会话" :image-size="60" />
      </el-card></div></div>
</template>
<script setup>
import { ref, onMounted } from 'vue'; import { getConvs, getConvMsgs, replyConv } from '../api'
const convs=ref([]); const active=ref(null); const msgs=ref([]); const txt=ref('')
async function fetch(){try{convs.value=(await getConvs({page:1,page_size:50})).data?.items||[]}catch{/* */}}
async function selectConv(c){active.value=c;msgs.value=(await getConvMsgs(c.id)).data||[]}
async function sendMsg(){if(!txt.value.trim()||!active.value)return;await replyConv(active.value.id,{msg_type:'text',content:{text:txt.value}});txt.value='';await selectConv(active.value)}
onMounted(fetch)
</script>
