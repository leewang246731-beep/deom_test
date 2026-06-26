<template>
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <el-button @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
      <h3 style="margin:0">{{ isEdit ? '编辑商品' : '添加商品' }}</h3>
    </div>
    <el-card>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" style="max-width:600px">
        <el-form-item label="商品名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="价格" prop="price">
          <el-input-number v-model="form.price" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="库存" prop="stock">
          <el-input-number v-model="form.stock" :min="0" />
        </el-form-item>
        <el-form-item label="分类" prop="category_id">
          <el-select v-model="form.category_id" placeholder="请选择分类" style="width:100%">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="图片URL" prop="image_url">
          <el-input v-model="form.image_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="上架" inactive-text="下架" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleSave">保存</el-button>
          <el-button @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getProduct, createProduct, updateProduct } from '../api'
import { ElMessage } from 'element-plus'

const route = useRoute()
import { ArrowLeft } from '@element-plus/icons-vue'
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const formRef = ref(null)
const loading = ref(false)
const categories = ref([])

const form = reactive({
  name: '', price: 0, stock: 0, category_id: null,
  description: '', image_url: '', status: 1,
})

const rules = {
  name: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  price: [{ required: true, type: 'number', message: '请输入价格', trigger: 'blur' }],
}

onMounted(async () => {
  if (isEdit.value) {
    try {
      const data = await getProduct(route.params.id)
      Object.assign(form, data)
    } catch { /* handled */ }
  }
})

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const payload = { ...form }
    if (isEdit.value) {
      await updateProduct(route.params.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createProduct(payload)
      ElMessage.success('添加成功')
    }
    router.back()
  } catch { /* handled */ }
  finally { loading.value = false }
}
</script>
