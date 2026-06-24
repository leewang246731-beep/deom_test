<template>
  <div>
    <h3 style="margin:0 0 16px">商品库</h3>
    <el-card style="margin-bottom:16px">
      <el-row :gutter="12">
        <el-col :span="6"><el-input v-model="keyword" placeholder="搜索商品..." clearable @keyup.enter="search" /></el-col>
        <el-col :span="4"><el-select v-model="filters.shop_id" placeholder="店铺" clearable style="width:100%"><el-option v-for="s in shops" :key="s.id" :label="s.shop_name" :value="s.id" /></el-select></el-col>
        <el-col :span="4"><el-input v-model="filters.price_min" placeholder="最低价" type="number" /></el-col>
        <el-col :span="4"><el-input v-model="filters.price_max" placeholder="最高价" type="number" /></el-col>
        <el-col :span="4">
          <el-button type="primary" @click="fetch" :loading="loading">筛选</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>
      <el-row style="margin-top:12px">
        <el-col :span="8">
          <el-input v-model="searchQ" placeholder="语义搜索（例：适合送礼的数码产品）" @keyup.enter="doSearch">
            <template #append><el-button @click="doSearch" :loading="searching">语义搜索</el-button></template>
          </el-input>
        </el-col>
      </el-row>
    </el-card>
    <el-table :data="searchResults.length ? searchResults : products" border stripe v-loading="loading" empty-text="暂无商品">
      <el-table-column prop="title" label="商品名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="category_path" label="分类" width="150" show-overflow-tooltip />
      <el-table-column label="价格" width="100"><template #default="{ row }">¥{{ row.price }}</template></el-table-column>
      <el-table-column prop="stock" label="库存" width="80" />
      <el-table-column label="向量状态" width="100">
        <template #default="{ row }"><el-tag :type="row.embedding_status === 'done' ? 'success' : 'warning'" size="small">{{ row.embedding_status }}</el-tag></template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">{{ row.status === 1 ? '在售' : '下架' }}</el-tag></template>
      </el-table-column>
    </el-table>
    <el-pagination v-if="!searchResults.length" style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getProducts, searchProducts, getShops } from '../api'

const products = ref([])
const searchResults = ref([])
const shops = ref([])
const loading = ref(false)
const searching = ref(false)
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const searchQ = ref('')
const filters = reactive({ shop_id: null, price_min: null, price_max: null })

async function fetch() {
  loading.value = true; searchResults.value = []
  try {
    const params = { page: page.value, page_size: 20 }
    if (filters.shop_id) params.shop_id = filters.shop_id
    if (filters.price_min) params.price_min = filters.price_min
    if (filters.price_max) params.price_max = filters.price_max
    if (keyword.value) params.keyword = keyword.value
    const res = await getProducts(params)
    products.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally { loading.value = false }
}

async function doSearch() {
  if (!searchQ.value.trim()) return
  searching.value = true
  try {
    const res = await searchProducts(searchQ.value)
    searchResults.value = (res.data?.results || []).map(r => ({ ...r, price: r.price || 0, stock: r.stock || 0, embedding_status: r.embedding_status || 'pending', status: r.status || 1 }))
  } finally { searching.value = false }
}

function resetFilters() {
  Object.assign(filters, { shop_id: null, price_min: null, price_max: null })
  keyword.value = ''
  fetch()
}

onMounted(async () => {
  try { const res = await getShops(); shops.value = res.data || [] } catch { /* ok */ }
  fetch()
})
</script>
