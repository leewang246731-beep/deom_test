<template>
  <div style="max-width:800px;margin:0 auto;padding:16px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2 style="margin:0">我的订单</h2><el-button text @click="$router.push('/home')">返回首页</el-button></div>
    <el-tabs v-model="tab" @tab-change="fetch"><el-tab-pane label="全部" value=""/><el-tab-pane label="待支付" value="pending_payment"/><el-tab-pane label="待发货" value="paid"/><el-tab-pane label="待收货" value="shipped"/></el-tabs>
    <el-card v-for="o in orders" :key="o.id" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div><strong>{{o.order_no}}</strong><br/><span style="color:#909399;font-size:12px">{{o.created_at?.slice(0,16)}}</span></div>
        <div style="color:#e6a23c;font-size:20px;font-weight:bold">¥{{o.pay_amount}}</div>
        <div><el-tag :type="st(o.status)">{{o.status}}</el-tag></div>
        <div>
          <el-button v-if="o.status==='pending_payment'" size="small" type="warning" @click="doPay(o.id)">支付</el-button>
          <el-button v-if="o.status==='received'||o.status==='completed'" size="small" @click="showRefund=o">申请售后</el-button>
          <el-button size="small" text @click="showDetail=o">详情</el-button></div></div>
      <div v-if="o.skus" style="margin-top:8px"><el-tag size="small" v-for="s in o.skus" :key="s.sku_code" style="margin-right:4px">{{s.spec}} x{{s.qty}}</el-tag></div>
    </el-card>
    <el-empty v-if="!orders.length" description="暂无订单"/>

    <el-dialog v-model="showDetail" title="订单详情" width="500px"><template v-if="showDetail">
      <el-descriptions :column="1" border size="small"><el-descriptions-item label="单号">{{showDetail.order_no}}</el-descriptions-item><el-descriptions-item label="金额">¥{{showDetail.pay_amount}}</el-descriptions-item><el-descriptions-item label="状态">{{showDetail.status}}</el-descriptions-item></el-descriptions></template></el-dialog>

    <el-dialog v-model="showRefund" title="申请售后" width="400px">
      <el-form :model="rf"><el-form-item label="类型"><el-select v-model="rf.type"><el-option label="仅退款" value="refund_only"/><el-option label="退货退款" value="return_refund"/></el-select></el-form-item><el-form-item label="原因"><el-input v-model="rf.reason" type="textarea"/></el-form-item></el-form>
      <template #footer><el-button @click="showRefund=null">取消</el-button><el-button type="primary" @click="doRefund">提交</el-button></template></el-dialog>
  </div>
</template>
<script setup>
import { ref, reactive } from 'vue'; import { getMyOrders, payOrder, applyAfterSale } from '../api'; import { ElMessage } from 'element-plus'
const orders=ref([]); const tab=ref(''); const showDetail=ref(null); const showRefund=ref(null); const rf=reactive({type:'refund_only',reason:''})
function st(s){const m={'pending_payment':'warning','paid':'','shipped':'primary','received':'success','completed':'','closed':'info'};return m[s]||''}
async function fetch(){const res=await getMyOrders({status:tab.value||undefined,page:1,page_size:50});orders.value=res.data?.items||[]}
async function doPay(id){await payOrder(id);ElMessage.success('支付处理中...');setTimeout(fetch,3000)}
async function doRefund(){if(!showRefund.value)return;await applyAfterSale({order_id:showRefund.value.id,type:rf.type,reason:rf.reason,refund_amount:showRefund.value.pay_amount});ElMessage.success('售后申请已提交');showRefund.value=null;fetch()}
import { onMounted } from 'vue'; onMounted(fetch)
</script>
