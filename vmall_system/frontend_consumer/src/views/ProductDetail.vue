<template>
  <div style="max-width:800px;margin:0 auto;padding:16px" v-loading="loading">
    <el-row :gutter="24" style="margin-top:16px">
      <el-col :span="12"><el-image :src="p.main_image" fit="cover" style="width:100%;height:360px;border-radius:12px"/></el-col>
      <el-col :span="12">
        <h2>{{p.title}}</h2><p style="color:#e6a23c;font-size:28px;font-weight:bold">¥{{selectedSku?.price||p.price_min}}</p>
        <p style="color:#909399">已售 {{p.total_sales}} | 库存 {{selectedSku?.stock||p.total_stock}}</p>
        <p style="color:#606266;margin:12px 0">{{p.description}}</p>
        <div style="margin:12px 0"><strong>规格:</strong>
          <el-radio-group v-model="selectedSkuCode">
            <el-radio-button v-for="s in p.skus_json" :key="s.sku_code" :value="s.sku_code" :disabled="s.stock<=0">{{s.spec}} ({{s.stock}})</el-radio-button>
          </el-radio-group></div>
        <el-input-number v-model="qty" :min="1" :max="selectedSku?.stock||1" style="margin:8px 0;width:120px"/>
        <div style="margin-top:16px;display:flex;gap:12px">
          <el-button type="warning" size="large" @click="doBuy" :disabled="!selectedSkuCode" :loading="buying">立即购买</el-button>
          <el-button size="large" @click="doContact" :loading="contacting">联系客服</el-button></div>
      </el-col></el-row>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'; import { useRoute, useRouter } from 'vue-router'; import { getProduct, createOrder, createConv } from '../api'; import { ElMessage } from 'element-plus'
const route=useRoute(); const r=useRouter(); const p=ref({}); const loading=ref(false); const buying=ref(false); const contacting=ref(false)
const qty=ref(1); const selectedSkuCode=ref('')
const selectedSku=computed(()=>(p.value.skus_json||[]).find(s=>s.sku_code===selectedSkuCode.value))
async function fetch(){loading.value=true;try{p.value=(await getProduct(route.params.id)).data||{};if(p.value.skus_json?.length&&!selectedSkuCode.value)selectedSkuCode.value=p.value.skus_json[0].sku_code}catch{p.value={}}finally{loading.value=false}}
async function doBuy(){
  if(!selectedSkuCode.value)return ElMessage.warning('请选择规格')
  buying.value=true
  try{await createOrder({product_id:p.value.id,sku_code:selectedSkuCode.value,quantity:qty.value,receiver_name:'小明',receiver_phone:'13800138000',receiver_address:'江苏省南京市玄武区虚拟路1号'});ElMessage.success('下单成功!');r.push('/orders')}catch{/* error shown by interceptor */}finally{buying.value=false}}
async function doContact(){
  contacting.value=true
  try{const res=await createConv({product_id:p.value.id,order_id:null,ip_region:'江苏·南京'});r.push('/chat/'+res.data.id)}catch{/* error shown by interceptor */}finally{contacting.value=false}}
onMounted(fetch)
</script>
