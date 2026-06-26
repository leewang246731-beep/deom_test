<template>
  <div>
    <div style="margin-bottom:16px;display:flex;justify-content:space-between">
      <h3 style="margin:0">工单分类管理</h3>
      <el-button type="primary" @click="openAdd()">新建分类</el-button>
    </div>
    <el-card>
      <el-tree :data="tree" :props="{ children: 'children', label: 'name' }" node-key="id" default-expand-all highlight-current>
        <template #default="{ data }">
          <span style="font-size:14px">{{ data.name }}</span>
          <span style="margin-left:8px;color:#909399;font-size:12px">Lv{{ data.level }}</span>
          <span style="margin-left:12px">
            <el-button size="small" text @click="openAdd(data)">添加子分类</el-button>
            <el-button size="small" text @click="openEdit(data)">编辑</el-button>
            <el-button size="small" text type="danger" @click="handleDelete(data)">删除</el-button>
          </span>
        </template>
      </el-tree>
    </el-card>

    <el-dialog v-model="showDialog" :title="isEdit ? '编辑分类' : '新建分类'" width="400px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" placeholder="分类名称" /></el-form-item>
        <el-form-item label="父级" v-if="form.parent_id"><el-input :model-value="parentName" disabled /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="handleSave">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getTicketCategories, createTicketCategory, updateTicketCategory, deleteTicketCategory } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const tree = ref([])
const showDialog = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const form = ref({ name: '', parent_id: null })
const parentName = ref('')

async function fetch() {
  try { tree.value = (await getTicketCategories()).data || [] } catch { tree.value = [] }
}

function openAdd(parent) {
  isEdit.value = false; editId.value = null
  form.value = { name: '', parent_id: parent?.id || null }
  parentName.value = parent?.name || ''
  showDialog.value = true
}

function openEdit(data) {
  isEdit.value = true; editId.value = data.id
  form.value = { name: data.name, parent_id: data.parent_id || null }
  parentName.value = ''
  showDialog.value = true
}

async function handleSave() {
  if (!form.value.name.trim()) return ElMessage.warning('请输入分类名称')
  try {
    if (isEdit.value) { await updateTicketCategory(editId.value, { name: form.value.name }); ElMessage.success('分类已更新') }
    else { await createTicketCategory({ name: form.value.name, parent_id: form.value.parent_id || undefined }); ElMessage.success('分类已创建') }
    showDialog.value = false; fetch()
  } catch { /* error shown by interceptor */ }
}

async function handleDelete(data) {
  try { await ElMessageBox.confirm(`确定删除分类"${data.name}"？`, '提示', { type: 'warning' }) } catch { return }
  try { await deleteTicketCategory(data.id); ElMessage.success('已删除'); fetch() } catch { /* error shown by interceptor */ }
}

onMounted(fetch)
</script>
