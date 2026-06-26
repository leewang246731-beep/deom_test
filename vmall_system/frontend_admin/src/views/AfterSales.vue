<template>
  <div>
    <h3 style="margin:0 0 16px">售后审核</h3>
    <el-card style="margin-bottom:16px"><el-row :gutter="12"><el-col :span="4"><el-select v-model="f.status" placeholder="状态" clearable><el-option label="待审核" value="pending_review"/><el-option label="已通过" value="approved"/><el-option label="买家已寄回" value="buyer_shipped"/><el-option label="已退款" value="refunded"/><el-option label="已拒绝" value="rejected"/></el-select></el-col><el-col :span="4"><el-button type="primary" @click="fetch" :loading="loading">筛选</el-button></el-col></el-row></el-card>
    <el-table :data="items" border stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="60"/><el-table-column prop="type" label="类型" width="80"/><el-table-column prop="reason" label="原因" min-width="150" show-overflow-tooltip/>
      <el-table-column label="金额" width="100"><template #default="{row}">¥{{row.refund_amount}}</template></el-table-column><el-table-column prop="status" label="状态" width="110"/>
      <el-table-column label="操作" width="200"><template #default="{row}">
        <el-button v-if="row.status==='pending_review'" size="small" type="primary" @click="review(row,'approve')">通过</el-button>
        <el-button v-if="row.status==='pending_review'" size="small" type="danger" @click="review(row,'reject')">拒绝</el-button>
        <el-button v-if="row.status==='buyer_shipped'" size="small" type="success" @click="doConfirm(row)">确认收货</el-button></template></el-table-column></el-table>
    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total,prev,next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch"/>
    <el-dialog v-model="showReview" title="审核备注" width="400px"><el-input v-model="remark" type="textarea"/><template #footer><el-button @click="showReview=null">取消</el-button><el-button type="primary" @click="confirmReview">确认</el-button></template></el-dialog>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'; import { getAfterSales, reviewAfterSale, confirmReceive } from '../api'; import { ElMessage } from 'element-plus'
const items=ref([]); const loading=ref(false); const total=ref(0); const page=ref(1); const f=reactive({status:'pending_review'})
const showReview=ref(null); const remark=ref(''); let reviewAction=''
function review(r,action){showReview.value=r;reviewAction=action;remark.value=action==='approve'?'审核通过':'审核拒绝'}
async function confirmReview(){if(!showReview.value)return;try{await reviewAfterSale(showReview.value.id,{action:reviewAction,remark:remark.value});showReview.value=null;ElMessage.success('已审核');fetch()}catch{/* error shown by interceptor */}}
async function doConfirm(r){try{await confirmReceive(r.id);ElMessage.success('已确认收货');fetch()}catch{/* error shown by interceptor */}}
async function fetch(){loading.value=true;try{const params={page:page.value,page_size:20};if(f.status)params.status=f.status;const res=await getAfterSales(params);items.value=res.data?.items||[];total.value=res.data?.total||0}catch{items.value=[];total.value=0}finally{loading.value=false}}
onMounted(fetch)
</script>
