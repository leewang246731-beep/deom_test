<template>
  <div>
    <div style="margin-bottom:16px;display:flex;justify-content:space-between">
      <h3 style="margin:0">工单管理</h3>
      <div>
        <el-button @click="handleExport">导出CSV</el-button>
        <el-button type="primary" @click="showCreate = true">新建工单</el-button>
      </div>
    </div>

    <el-card style="margin-bottom:16px">
      <el-row :gutter="12">
        <el-col :span="3"><el-select v-model="f.status" placeholder="状态" clearable style="width:100%"><el-option v-for="s in statuses" :key="s" :label="s" :value="s"/></el-select></el-col>
        <el-col :span="3"><el-select v-model="f.priority" placeholder="优先级" clearable style="width:100%"><el-option v-for="p in ['P0','P1','P2','P3']" :key="p" :label="p" :value="p"/></el-select></el-col>
        <el-col :span="3"><el-select v-model="f.assigned_to" placeholder="处理人" clearable style="width:100%"><el-option v-for="u in userOptions" :key="u.id" :label="u.label" :value="u.id"/></el-select></el-col>
        <el-col :span="5"><el-button type="primary" @click="fetch" :loading="loading">筛选</el-button><el-button @click="resetFilter">重置</el-button></el-col>
      </el-row>
    </el-card>

    <div v-if="selectedRows.length" style="margin-bottom:12px;display:flex;align-items:center;gap:8px;padding:8px 16px;background:#ecf5ff;border-radius:6px">
      <span style="font-size:13px">已选 <strong>{{ selectedRows.length }}</strong> 个工单</span>
      <el-select v-model="batchAssignTo" placeholder="选择处理人" size="small" style="width:160px" filterable clearable>
        <el-option v-for="u in userOptions" :key="u.id" :label="u.label" :value="u.id" />
      </el-select>
      <el-button size="small" :disabled="!batchAssignTo" @click="handleBatchAssign">批量分配</el-button>
      <el-button size="small" type="danger" @click="handleBatchClose">批量关闭</el-button>
      <el-button size="small" text @click="selectedRows = []">取消选择</el-button>
    </div>

    <el-table :data="tickets" border stripe v-loading="loading" @row-click="goDetail" @selection-change="onSelectChange" style="cursor:pointer">
      <el-table-column type="selection" width="40" />
      <el-table-column prop="ticket_no" label="编号" width="120" />
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column label="优先级" width="80"><template #default="{row}"><el-tag :type="priTag(row.priority)" size="small">{{row.priority}}</el-tag></template></el-table-column>
      <el-table-column label="状态" width="110"><template #default="{row}"><el-tag :type="statusTag(row.status)" size="small">{{row.status}}</el-tag></template></el-table-column>
      <el-table-column prop="assignee_name" label="处理人" width="90" />
      <el-table-column prop="sla_breached" label="SLA" width="70"><template #default="{row}"><el-tag v-if="row.sla_breached" type="danger" size="small">超时</el-tag><span v-else style="color:#67c23a">正常</span></template></el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170"><template #default="{row}">{{row.created_at?.slice(0,16)}}</template></el-table-column>
    </el-table>
    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total,prev,pager,next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch" />

    <!-- 新建 -->
    <el-dialog v-model="showCreate" title="新建工单" width="560px">
      <el-form :model="create" label-width="80px">
        <el-form-item label="标题" required><el-input v-model="create.title"/></el-form-item>
        <el-form-item label="描述"><el-input v-model="create.description" type="textarea" :rows="3"/></el-form-item>
        <el-form-item label="优先级"><el-select v-model="create.priority" style="width:100%"><el-option v-for="p in ['P0','P1','P2','P3']" :key="p" :label="p" :value="p"/></el-select></el-form-item>
        <el-form-item label="来源"><el-select v-model="create.source" style="width:100%"><el-option label="手动" value="manual"/><el-option label="会话" value="conversation"/><el-option label="订单" value="order"/></el-select></el-form-item>
        <el-form-item label="关联ID"><el-input-number v-model="create.source_id" :min="1" style="width:100%" placeholder="会话ID或订单ID"/></el-form-item>
        <el-form-item><el-button @click="autoClassify" :loading="aiClassifying" size="small">AI 智能分类</el-button><span v-if="aiResult" style="margin-left:8px;color:#409eff;font-size:12px">{{aiResult}}</span></el-form-item>
      </el-form>
      <template #footer><el-button @click="showCreate=false">取消</el-button><el-button type="primary" @click="handleCreate" :loading="creating">创建</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getTickets, createTicket, batchTickets, preClassify, getSkillGroups, exportCSV } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const tickets = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1)
const showCreate = ref(false); const creating = ref(false); const aiClassifying = ref(false); const aiResult = ref('')
const f = reactive({ status: null, priority: null, assigned_to: null })
const create = reactive({ title: '', description: '', priority: 'P3', source: 'manual', source_id: null })
const userOptions = ref([])
const selectedRows = ref([])
const batchAssignTo = ref(null)
const statuses = ['pending', 'in_progress', 'waiting_customer', 'resolved', 'closed']

function priTag(p) { return {P0:'danger',P1:'warning',P2:'',P3:'info'}[p]||'' }
function statusTag(s) { return {pending:'warning',in_progress:'primary',waiting_customer:'info',resolved:'success',closed:''}[s]||'' }

async function fetch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (f.status) params.status = f.status
    if (f.priority) params.priority = f.priority
    if (f.assigned_to) params.assigned_to = f.assigned_to
    const res = await getTickets(params)
    tickets.value = res.data?.items || []; total.value = res.data?.total || 0
  } catch {
    tickets.value = []; total.value = 0
  } finally { loading.value = false }
}

function resetFilter() { Object.assign(f, { status: null, priority: null, assigned_to: null }); fetch() }
function goDetail(row) { router.push(`/tickets/${row.id}`) }

async function handleCreate() {
  if (!create.title.trim()) return ElMessage.warning('请输入标题')
  creating.value = true
  try {
    const r = await createTicket({ ...create })
    showCreate.value = false
    Object.assign(create, { title: '', description: '', priority: 'P3', source: 'manual', source_id: null })
    ElMessage.success(`工单 ${r.data?.ticket_no || ''} 已创建`)
    fetch()
  } catch {
    // error shown by interceptor
  } finally { creating.value = false }
}

async function autoClassify() {
  if (!create.title.trim()) return ElMessage.warning('请先输入标题')
  aiClassifying.value = true
  try {
    const r = await preClassify({ title: create.title, description: create.description })
    const d = r.data
    aiResult.value = `建议: 优先级${d.suggested_priority}`
    create.priority = d.suggested_priority
  } catch {
    aiResult.value = '分类失败，请手动选择'
  } finally { aiClassifying.value = false }
}

function onSelectChange(rows) { selectedRows.value = rows }

async function handleBatchAssign() {
  if (!batchAssignTo.value) return ElMessage.warning('请选择处理人')
  const ids = selectedRows.value.map(r => r.id)
  const targetUser = userOptions.value.find(u => u.id === batchAssignTo.value)
  const label = targetUser?.label || `用户${batchAssignTo.value}`
  try {
    await ElMessageBox.confirm(`确定将 ${ids.length} 个工单分配给 ${label}?`, '确认')
  } catch { return }
  try {
    await batchTickets({ action: 'assign', ticket_ids: ids, to_user_id: batchAssignTo.value })
    ElMessage.success(`已分配 ${ids.length} 个工单给 ${label}`)
    selectedRows.value = []
    batchAssignTo.value = null
    fetch()
  } catch {
    // error shown by interceptor
  }
}

async function handleBatchClose() {
  const ids = selectedRows.value.map(r => r.id)
  try {
    await ElMessageBox.confirm(`确定批量关闭 ${ids.length} 个工单？`, '危险操作', { type: 'warning' })
  } catch { return }
  try {
    await batchTickets({ action: 'close', ticket_ids: ids })
    ElMessage.success(`已关闭 ${ids.length} 个工单`)
    selectedRows.value = []
    fetch()
  } catch {
    // error shown by interceptor
  }
}

function handleExport() {
  const p = {}
  if (f.status) p.status = f.status
  if (f.priority) p.priority = f.priority
  if (f.assigned_to) p.assigned_to = f.assigned_to
  exportCSV('tickets', p)
}

onMounted(async () => {
  fetch()
  try {
    const g = await getSkillGroups()
    const users = new Map()
    ;(g.data || []).forEach(grp =>
      (grp.members || []).forEach(m => users.set(m.user_id, { id: m.user_id, label: m.display_name }))
    )
    userOptions.value = [...users.values()]
  } catch {
    // user list not critical
  }
})
</script>
