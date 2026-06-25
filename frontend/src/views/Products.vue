<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 style="margin:0">商品库</h3>
      <div>
        <el-button @click="handleExport">导出CSV</el-button>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 新增商品</el-button>
      </div>
    </div>
    <el-card style="margin-bottom:16px">
      <el-row :gutter="12">
        <el-col :span="6"><el-input v-model="keyword" placeholder="搜索商品..." clearable @keyup.enter="fetch" /></el-col>
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
    <el-table :data="searchResults.length ? searchResults : products" border stripe v-loading="loading" empty-text="暂无商品" @selection-change="onSelectionChange">
      <el-table-column type="selection" width="40" />
      <el-table-column prop="title" label="商品名称" min-width="180" show-overflow-tooltip />
      <el-table-column prop="category_path" label="分类" width="140" show-overflow-tooltip />
      <el-table-column label="价格" width="90"><template #default="{ row }">¥{{ row.price }}</template></el-table-column>
      <el-table-column prop="stock" label="库存" width="70" />
      <el-table-column label="向量" width="80">
        <template #default="{ row }"><el-tag :type="row.embedding_status === 'done' ? 'success' : 'warning'" size="small">{{ row.embedding_status }}</el-tag></template>
      </el-table-column>
      <el-table-column label="状态" width="70">
        <template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">{{ row.status === 1 ? '在售' : '下架' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-if="!searchResults.length" style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch" />

    <!-- Product Dialog -->
    <el-dialog v-model="showDialog" :title="isEdit ? '编辑商品' : '新增商品'" width="560px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="所属店铺" prop="shop_id">
          <el-select v-model="form.shop_id" placeholder="选择店铺" style="width:100%" :disabled="isEdit">
            <el-option v-for="s in shops" :key="s.id" :label="s.shop_name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="商品名称" prop="title"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="价格" prop="price"><el-input v-model.number="form.price" type="number" /></el-form-item>
        <el-form-item label="库存" prop="stock"><el-input v-model.number="form.stock" type="number" /></el-form-item>
        <el-form-item label="分类路径" prop="category_path"><el-input v-model="form.category_path" placeholder="如：数码/手机/华为" /></el-form-item>
        <el-form-item label="描述" prop="description"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="在售" inactive-text="下架" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getProducts, searchProducts, createProduct, updateProduct, deleteProduct, getShops, exportCSV } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

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

const showDialog = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const saving = ref(false)
const formRef = ref(null)
const selectedRows = ref([])

const form = reactive({ shop_id: null, title: '', price: 0, stock: 0, description: '', category_path: '', status: 1 })
const rules = {
  shop_id: [{ required: true, message: '请选择店铺' }],
  title: [{ required: true, message: '请输入商品名称' }],
  price: [{ required: true, message: '请输入价格' }],
}

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
    const res = await searchProducts(searchQ.value, filters.shop_id)
    searchResults.value = (res.data?.results || []).map(r => ({ ...r, price: r.price || 0, stock: r.stock || 0, embedding_status: r.embedding_status || 'pending', status: r.status || 1 }))
  } catch { /* */ } finally { searching.value = false }
}

function resetFilters() {
  Object.assign(filters, { shop_id: null, price_min: null, price_max: null })
  keyword.value = ''; page.value = 1
  fetch()
}

function resetForm() {
  editId.value = null
  Object.assign(form, { shop_id: null, title: '', price: 0, stock: 0, description: '', category_path: '', status: 1 })
}

function openCreate() {
  isEdit.value = false; resetForm(); showDialog.value = true
}

function openEdit(row) {
  isEdit.value = true; editId.value = row.id
  Object.assign(form, {
    shop_id: row.shop_id, title: row.title, price: row.price,
    stock: row.stock, description: row.description || '',
    category_path: row.category_path || '', status: row.status,
  })
  showDialog.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const data = { ...form }
    if (isEdit.value) {
      await updateProduct(editId.value, data)
      ElMessage.success('已更新')
    } else {
      await createProduct(data)
      ElMessage.success('已创建')
    }
    showDialog.value = false
    fetch()
  } catch { /* error shown by interceptor */ }
  finally { saving.value = false }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除"${row.title}"？`, '提示', { type: 'warning' })
  try {
    await deleteProduct(row.id)
    ElMessage.success('已删除')
    fetch()
  } catch { /* */ }
}

function onSelectionChange(rows) { selectedRows.value = rows }

function handleExport() {
  const p = {}
  if (filters.shop_id) p.shop_id = filters.shop_id
  if (keyword.value) p.keyword = keyword.value
  exportCSV('products', p)
}

onMounted(async () => {
  try { const res = await getShops(); shops.value = res.data || [] } catch { /* */ }
  fetch()
})
</script>
