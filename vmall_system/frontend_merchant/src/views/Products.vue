<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 style="margin:0">商品管理</h3>
      <el-button type="primary" @click="$router.push('/products/add')">添加商品</el-button>
    </div>
    <el-card>
      <el-table :data="list" v-loading="loading" style="width:100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="商品名称" />
        <el-table-column prop="price" label="价格" width="100" />
        <el-table-column prop="stock" label="库存" width="80" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">{{ row.status === 1 ? '上架' : '下架' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/products/${row.id}/edit`)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top:16px;justify-content:flex-end"
        v-model:current-page="page"
        :page-size="size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getProducts, deleteProduct } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const list = ref([])
const loading = ref(false)
const page = ref(1)
const size = ref(10)
const total = ref(0)

async function fetchData() {
  loading.value = true
  try {
    const data = await getProducts({ page: page.value, size: size.value })
    list.value = data.data?.items || []
    total.value = data.data?.total || 0
  } catch { list.value = []; total.value = 0 }
  finally { loading.value = false }
}

async function handleDelete(id) {
  try { await ElMessageBox.confirm('确定删除该商品？', '提示', { type: 'warning' }) } catch { return }
  try {
    await deleteProduct(id)
    ElMessage.success('已删除')
    fetchData()
  } catch { /* error shown by interceptor */ }
}

onMounted(fetchData)
</script>
