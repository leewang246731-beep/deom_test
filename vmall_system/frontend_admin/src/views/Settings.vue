<template>
  <div>
    <h3 style="margin:0 0 16px">系统设置</h3>
    <el-card><el-form :model="f" label-width="120px" style="max-width:600px">
      <el-form-item label="店铺名称"><el-input v-model="f.shop_name"/></el-form-item>
      <el-form-item label="Logo URL"><el-input v-model="f.logo_url" placeholder="https://..."/></el-form-item>
      <el-form-item label="SaaS Webhook 地址"><el-input v-model="f.saas_webhook_url" placeholder="http://127.0.0.1:8010/api/v1/webhooks/vmall"/></el-form-item>
      <el-form-item label="AccessToken 密钥"><el-input v-model="f.access_token_secret" show-password/></el-form-item>
      <el-form-item><el-button type="primary" @click="doSave" :loading="saving">保存设置</el-button><span style="margin-left:12px;color:#909399;font-size:12px">Webhook 地址指向 SaaS 后端接收端点</span></el-form-item></el-form></el-card></div>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'; import { getSettings, updateSettings } from '../api'; import { ElMessage } from 'element-plus'
const f=reactive({shop_name:'',logo_url:'',saas_webhook_url:'',access_token_secret:''}); const saving=ref(false)
onMounted(async()=>{try{const d=(await getSettings()).data;Object.assign(f,d)}catch{/* */}})
async function doSave(){saving.value=true;try{await updateSettings({...f});ElMessage.success('已保存')}finally{saving.value=false}}
</script>
