<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 style="margin:0">SLA 策略管理</h3>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 新建策略</el-button>
    </div>

    <el-table :data="policies" border stripe v-loading="loading" empty-text="暂无策略">
      <el-table-column label="优先级" width="90">
        <template #default="{ row }">
          <el-tag :type="row.priority === 'P0' ? 'danger' : row.priority === 'P1' ? 'warning' : 'info'" size="small">{{ row.priority }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="分类" width="140">
        <template #default="{ row }">{{ row.category_name || '全部' }}</template>
      </el-table-column>
      <el-table-column label="响应时限(分)" width="120">
        <template #default="{ row }">{{ row.response_minutes || '-' }}</template>
      </el-table-column>
      <el-table-column label="解决时限(分)" width="120">
        <template #default="{ row }">{{ row.resolve_minutes || '-' }}</template>
      </el-table-column>
      <el-table-column label="升级时限(分)" width="120">
        <template #default="{ row }">{{ row.escalate_minutes || '-' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDialog" :title="isEdit ? '编辑策略' : '新建策略'" width="500px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-form-item label="优先级" prop="priority">
          <el-select v-model="form.priority" style="width:100%">
            <el-option label="P0 - 最高" value="P0" />
            <el-option label="P1 - 高" value="P1" />
            <el-option label="P2 - 中" value="P2" />
            <el-option label="P3 - 低" value="P3" />
          </el-select>
        </el-form-item>
        <el-form-item label="响应时限(分钟)" prop="response_minutes">
          <el-input v-model.number="form.response_minutes" type="number" />
        </el-form-item>
        <el-form-item label="解决时限(分钟)" prop="resolve_minutes">
          <el-input v-model.number="form.resolve_minutes" type="number" />
        </el-form-item>
        <el-form-item label="升级时限(分钟)">
          <el-input v-model.number="form.escalate_minutes" type="number" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" />
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
import { getSLAPolicies, createSLAPolicy, updateSLAPolicy, deleteSLAPolicy } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const policies = ref([])
const loading = ref(false)
const showDialog = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const saving = ref(false)
const formRef = ref(null)

const form = reactive({
  priority: 'P2', response_minutes: 60, resolve_minutes: 480, escalate_minutes: 120, is_active: 1,
})
const rules = {
  priority: [{ required: true }],
  response_minutes: [{ required: true, message: '请输入响应时限' }],
  resolve_minutes: [{ required: true, message: '请输入解决时限' }],
}

async function fetch() {
  loading.value = true
  try { policies.value = (await getSLAPolicies()).data || [] } catch { policies.value = [] }
  finally { loading.value = false }
}

function resetForm() {
  editId.value = null
  Object.assign(form, { priority: 'P2', response_minutes: 60, resolve_minutes: 480, escalate_minutes: 120, is_active: 1 })
}

function openCreate() { isEdit.value = false; resetForm(); showDialog.value = true }
function openEdit(row) {
  isEdit.value = true; editId.value = row.id
  Object.assign(form, {
    priority: row.priority, response_minutes: row.response_minutes || 0,
    resolve_minutes: row.resolve_minutes || 0, escalate_minutes: row.escalate_minutes || 0,
    is_active: row.is_active,
  })
  showDialog.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const data = { ...form }
    if (isEdit.value) { await updateSLAPolicy(editId.value, data); ElMessage.success('策略已更新') }
    else { await createSLAPolicy(data); ElMessage.success('策略已创建') }
    showDialog.value = false; fetch()
  } catch { /* error shown by interceptor */ } finally { saving.value = false }
}

async function handleDelete(row) {
  try { await ElMessageBox.confirm('确定删除此 SLA 策略？', '提示', { type: 'warning' }) } catch { return }
  try { await deleteSLAPolicy(row.id); ElMessage.success('已删除'); fetch() } catch { /* error shown by interceptor */ }
}

fetch()
</script>
