<template>
  <div style="max-width:600px;margin:0 auto;padding:16px">
    <el-button text @click="$router.back()">← 返回</el-button>
    <el-card style="margin-top:8px">
      <template #header>联系客服</template>
      <div style="height:400px;overflow-y:auto;margin-bottom:12px">
        <div v-for="m in msgs" :key="m.id" :style="{textAlign:m.sender_role==='buyer'?'right':'left',marginBottom:'8px'}">
          <div :style="{display:'inline-block',maxWidth:'70%',padding:'8px 12px',borderRadius:'8px',background:m.sender_role==='buyer'?'#409eff':'#f0f0f0',color:m.sender_role==='buyer'?'#fff':'#303133'}">
            {{m.content_json?.text||JSON.stringify(m.content_json)}}</div></div></div>
      <el-input v-model="txt" placeholder="输入消息..." @keyup.enter="send"><template #append><el-button @click="send" :disabled="!txt.trim()">发送</el-button></template></el-input>
    </el-card></div>
</template>
<script setup>
import { ref, onMounted } from 'vue'; import { useRoute } from 'vue-router'; import { getMsgs, sendMsg } from '../api'
const route=useRoute(); const msgs=ref([]); const txt=ref('')
async function fetch(){try{msgs.value=(await getMsgs(route.params.id)).data||[]}catch{/* */}}
async function send(){if(!txt.value.trim())return;await sendMsg(route.params.id,{msg_type:'text',content:{text:txt.value}});await fetch();txt.value=''}
onMounted(fetch)
</script>
