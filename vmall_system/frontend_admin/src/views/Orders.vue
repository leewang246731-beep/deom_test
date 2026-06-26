<template>
  <div>
    <h3 style="margin:0 0 16px">订单管理</h3>
    <el-card style="margin-bottom:16px"><el-row :gutter="12"><el-col :span="4"><el-select v-model="f.status" placeholder="状态" clearable><el-option v-for="s in ss" :key="s" :label="s" :value="s"/></el-select></el-col><el-col :span="4"><el-button type="primary" @click="fetch" :loading="loading">筛选</el-button></el-col></el-row></el-card>
    <el-table :data="orders" border stripe v-loading="loading">
      <el-table-column prop="order_no" label="单号" width="180"/><el-table-column prop="status" label="状态" width="100"/><el-table-column label="金额" width="100"><template #default="{row}">¥{{row.total_amount}}</template></el-table-column>
      <el-table-column prop="receiver_name" label="收货人" width="80"/><el-table-column prop="sku_count" label="件数" width="60"/>
      <el-table-column label="操作" width="200"><template #default="{row}">
        <el-button v-if="row.status==='paid'" size="small" type="primary" @click="openShip(row)">发货</el-button>
        <el-button size="small" text @click="getOrder(row.id).then(r=>showDetail=r.data)">详情</el-button></template></el-table-column></el-table>
    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total,prev,next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch"/>
    <el-dialog v-model="showShip" title="发货" width="400px"><el-form :model="sf"><el-form-item label="物流公司"><el-select v-model="sf.company"><el-option v-for="c in ['顺丰速运','中通快递','圆通速递','韵达快递','极兔速递']" :key="c" :label="c" :value="c"/></el-select></el-form-item><el-form-item label="运单号"><el-input v-model="sf.tracking_no"/></el-form-item></el-form><template #footer><el-button @click="showShip=null">取消</el-button><el-button type="primary" @click="doShip">确认发货</el-button></template></el-dialog>
    <el-dialog v-model="showDetail" title="订单详情" width="500px"><template v-if="showDetail"><el-descriptions :column="1" border size="small"><el-descriptions-item label="单号">{{showDetail.order_no}}</el-descriptions-item><el-descriptions-item label="状态">{{showDetail.status}}</el-descriptions-item><el-descriptions-item label="金额">¥{{showDetail.pay_amount}}</el-descriptions-item><el-descriptions-item label="收货人">{{showDetail.receiver_name}} {{showDetail.receiver_phone}}</el-descriptions-item><el-descriptions-item label="地址">{{showDetail.receiver_address}}</el-descriptions-item></el-descriptions></template></el-dialog>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'; import { getOrders, getOrder, shipOrder } from '../api'; import { ElMessage } from 'element-plus'
const orders=ref([]); const loading=ref(false); const total=ref(0); const page=ref(1); const f=reactive({status:''}); const showShip=ref(null); const showDetail=ref(null); const sf=reactive({company:'顺丰速运',tracking_no:''})
const ss=['pending_payment','paid','shipped','received','completed','closed']
async function fetch(){loading.value=true;try{const params={page:page.value,page_size:20};if(f.status)params.status=f.status;const res=await getOrders(params);orders.value=res.data?.items||[];total.value=res.data?.total||0}catch{orders.value=[];total.value=0}finally{loading.value=false}}
function openShip(o){showShip.value=o;sf.tracking_no='SF'+Date.now().toString().slice(-10)}
async function doShip(){if(!showShip.value)return;try{await shipOrder(showShip.value.id,{company:sf.company,tracking_no:sf.tracking_no});showShip.value=null;ElMessage.success('发货成功');fetch()}catch{/* error shown by interceptor */}}
onMounted(fetch)
</script>
