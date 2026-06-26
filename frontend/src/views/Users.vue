<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 style="margin:0">用户管理</h3>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 新增用户</el-button>
    </div>

    <el-card style="margin-bottom:16px">
      <el-row :gutter="12">
        <el-col :span="4">
          <el-select v-model="filterRole" placeholder="角色筛选" clearable style="width:100%" @change="fetch">
            <el-option label="管理员" value="admin" />
            <el-option label="经理" value="manager" />
            <el-option label="客服" value="service" />
          </el-select>
        </el-col>
      </el-row>
    </el-card>

    <el-table :data="users" border stripe v-loading="loading" empty-text="暂无用户">
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="display_name" label="显示名" width="140" />
      <el-table-column label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="roleType(row.role)" size="small">{{ roleLabel(row.role) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">{{ row.status === 1 ? '正常' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="最后登录" width="170" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch" />

    <el-dialog v-model="showDialog" :title="isEdit ? '编辑用户' : '新增用户'" width="460px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" :disabled="isEdit" /></el-form-item>
        <el-form-item label="显示名" prop="display_name"><el-input v-model="form.display_name" /></el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" style="width:100%">
            <el-option label="管理员 (admin)" value="admin" />
            <el-option label="经理 (manager)" value="manager" />
            <el-option label="客服 (service)" value="service" />
          </el-select>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" :placeholder="isEdit ? '留空则不修改' : '默认 123456'" show-password />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="禁用" />
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
import { ref, reactive } from 'vue'
import { getUsers, createUser, updateUser, deleteUser } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const users = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const filterRole = ref('')

const showDialog = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const saving = ref(false)
const formRef = ref(null)

const form = reactive({
  username: '', display_name: '', role: 'service', password: '', status: 1,
})
const rules = {
  username: [{ required: true, message: '请输入用户名' }],
  role: [{ required: true, message: '请选择角色' }],
}

function roleLabel(r) {
  const m = { admin: '管理员', manager: '经理', service: '客服' }
  return m[r] || r
}
function roleType(r) {
  const m = { admin: 'danger', manager: 'warning', service: '' }
  return m[r] || ''
}

async function fetch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (filterRole.value) params.role = filterRole.value
    const res = await getUsers(params)
    users.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch {
    users.value = []
    total.value = 0
  } finally { loading.value = false }
}

function resetForm() {
  editId.value = null
  Object.assign(form, { username: '', display_name: '', role: 'service', password: '', status: 1 })
}

function openCreate() {
  isEdit.value = false; resetForm(); showDialog.value = true
}

function openEdit(row) {
  isEdit.value = true; editId.value = row.id
  Object.assign(form, {
    username: row.username, display_name: row.display_name || '',
    role: row.role, password: '', status: row.status,
  })
  showDialog.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const data = { ...form }
    if (!data.password) delete data.password
    if (isEdit.value) {
      await updateUser(editId.value, data)
      ElMessage.success('用户信息已更新')
    } else {
      await createUser(data)
      ElMessage.success('用户已创建')
    }
    showDialog.value = false
    fetch()
  } catch {
    // error shown by interceptor
  } finally { saving.value = false }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户"${row.username}"？`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await deleteUser(row.id)
    ElMessage.success('用户已删除')
    fetch()
  } catch {
    // error shown by interceptor
  }
}

fetch()
</script>
