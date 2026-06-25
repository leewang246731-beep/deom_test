<template>
  <div>
    <h3 style="margin-bottom:16px">店铺设置</h3>
    <el-card v-loading="loading">
      <el-form ref="formRef" :model="form" label-width="100px" style="max-width:500px">
        <el-form-item label="店铺名称" prop="shop_name">
          <el-input v-model="form.shop_name" />
        </el-form-item>
        <el-form-item label="店铺Logo" prop="shop_logo">
          <el-input v-model="form.shop_logo" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="店铺简介" prop="shop_desc">
          <el-input v-model="form.shop_desc" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="联系人" prop="contact_name">
          <el-input v-model="form.contact_name" />
        </el-form-item>
        <el-form-item label="联系电话" prop="contact_phone">
          <el-input v-model="form.contact_phone" />
        </el-form-item>
        <el-form-item label="联系邮箱" prop="contact_email">
          <el-input v-model="form.contact_email" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getSettings, updateSettings } from '../api'
import { ElMessage } from 'element-plus'

const formRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const form = reactive({
  shop_name: '', shop_logo: '', shop_desc: '',
  contact_name: '', contact_phone: '', contact_email: '',
})

onMounted(async () => {
  loading.value = true
  try {
    const data = await getSettings()
    Object.assign(form, data)
  } catch { /* handled */ }
  finally { loading.value = false }
})

async function handleSave() {
  saving.value = true
  try {
    await updateSettings({ ...form })
    ElMessage.success('保存成功')
  } catch { /* handled */ }
  finally { saving.value = false }
}
</script>
