<template>
  <div>
    <el-row :gutter="16"><el-col :span="6" v-for="c in cards" :key="c.t">
      <el-card shadow="hover"><div style="display:flex;justify-content:space-between;align-items:center"><div><p style="color:#909399;font-size:13px;margin:0">{{c.t}}</p><h2 style="margin:6px 0 0">{{c.v}}</h2></div><el-icon :size="36" :color="c.c"><component :is="c.i"/></el-icon></div></el-card></el-col></el-row>
  </div>
</template>
<script setup>
import { reactive, onMounted } from 'vue'; import { getDashboard } from '../api'
const cards=reactive([{t:'今日订单',v:0,c:'#409eff',i:'Document'},{t:'待发货',v:0,c:'#e6a23c',i:'Box'},{t:'待审核售后',v:0,c:'#f56c6c',i:'Warning'},{t:'今日GMV',v:0,c:'#67c23a',i:'Money'}])
onMounted(async()=>{try{const d=(await getDashboard()).data;cards[0].v=d.today_orders;cards[1].v=d.pending_ship;cards[2].v=d.pending_review;cards[3].v='¥'+d.today_gmv}catch{/* */}})
</script>
