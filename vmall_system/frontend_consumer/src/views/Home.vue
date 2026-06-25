<template>
  <div style="max-width:1200px;margin:0 auto;padding:16px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2 style="margin:0">商品列表</h2>
    </div>
    <el-row :gutter="12" style="margin-bottom:12px">
      <el-col :span="6"><el-select v-model="f.category" placeholder="分类" clearable style="width:100%"><el-option v-for="c in cats" :key="c" :label="c" :value="c"/></el-select></el-col>
      <el-col :span="6"><el-select v-model="f.sort" placeholder="排序" style="width:100%"><el-option label="默认" value="default"/><el-option label="价格升序" value="price_asc"/><el-option label="价格降序" value="price_desc"/><el-option label="销量优先" value="sales"/></el-select></el-col>
      <el-col :span="6"><el-button type="primary" @click="fetch" :loading="loading">筛选</el-button></el-col></el-row>
    <el-row :gutter="16">
      <el-col :span="6" v-for="p in products" :key="p.id" style="margin-bottom:16px">
        <el-card shadow="hover" :body-style="{padding:'12px'}" @click="$router.push('/product/'+p.id)" style="cursor:pointer">
          <el-image :src="p.main_image" fit="cover" style="width:100%;height:180px;border-radius:8px"/>
          <h4 style="margin:8px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{p.title}}</h4>
          <div style="display:flex;justify-content:space-between;align-items:center"><span style="color:#e6a23c;font-weight:bold;font-size:18px">¥{{p.price_min}}</span><span style="color:#909399;font-size:12px">已售 {{p.total_sales}}</span></div>
        </el-card></el-col></el-row>
    <el-pagination style="margin-top:16px;justify-content:center" background layout="prev,next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch"/>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'; import { useRouter } from 'vue-router'; import { useAuthStore } from '../stores/auth'; import { getProducts } from '../api'
const r=useRouter(); const a=useAuthStore()
const products=ref([]); const total=ref(0); const page=ref(1); const loading=ref(false)
const f=reactive({category:'',sort:'default'})
const cats=['数码','女装','美妆','食品','家居','数码/手机','数码/耳机','数码/笔记本','女装/连衣裙','女装/外套']
function logout(){a.logout();r.replace('/login')}
async function fetch(){loading.value=true;try{const res=await getProducts({page:page.value,page_size:20,category:f.category,sort:f.sort});products.value=res.data?.items||[];total.value=res.data?.total||0}finally{loading.value=false}}
onMounted(fetch)
</script>
