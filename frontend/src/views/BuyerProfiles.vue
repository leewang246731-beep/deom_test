<template>
  <div style="padding:16px">
    <!-- 总览统计卡片 -->
    <el-row :gutter="12" style="margin-bottom:16px">
      <el-col :span="6">
        <el-card shadow="hover"><div style="text-align:center">
          <div style="font-size:28px;font-weight:bold;color:#409eff">{{ stats.total || 0 }}</div>
          <div style="color:#909399;font-size:13px">画像用户总数</div>
        </div></el-card>
      </el-col>
      <el-col :span="6" v-for="(v,k) in stats.activity_breakdown||{}" :key="k">
        <el-card shadow="hover"><div style="text-align:center">
          <div style="font-size:28px;font-weight:bold" :style="{color: activityColor(k)}">{{ v }}</div>
          <div style="color:#909399;font-size:13px">{{ k }}</div>
        </div></el-card>
      </el-col>
    </el-row>

    <!-- Top Tags + 消费分层 -->
    <el-row :gutter="12" style="margin-bottom:16px">
      <el-col :span="14">
        <el-card shadow="hover">
          <template #header><span style="font-weight:bold">热门兴趣标签</span></template>
          <div style="display:flex;flex-wrap:wrap;gap:6px">
            <el-tag v-for="t in stats.top_tags||[]" :key="t.tag" :type="tagType(t.count)" size="small" effect="plain" style="cursor:pointer" @click="filterByTag(t.tag)">
              {{ t.tag }} ({{ t.count }})
            </el-tag>
            <el-empty v-if="!stats.top_tags?.length" description="暂无标签数据" :image-size="40" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header><span style="font-weight:bold">消费能力分层</span></template>
          <div style="display:flex;gap:8px;justify-content:space-around">
            <div v-for="(v,k) in stats.consumption_tiers||{}" :key="k" style="text-align:center">
              <div style="font-size:22px;font-weight:bold;color:#e6a23c">{{ v }}</div>
              <div style="font-size:12px;color:#909399">{{ tierLabel(k) }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选工具栏 -->
    <el-card shadow="never" style="margin-bottom:12px">
      <el-row :gutter="8" align="middle">
        <el-col :span="4">
          <el-select v-model="filters.activity_level" placeholder="活跃度" clearable @change="fetchList" style="width:100%">
            <el-option label="新用户" value="new" /><el-option label="活跃" value="active" />
            <el-option label="沉默" value="dormant" /><el-option label="流失" value="lost" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.sort_by" @change="fetchList" style="width:100%">
            <el-option label="最近更新" value="updated_at" /><el-option label="订单数↓" value="order_count" />
            <el-option label="消费额↓" value="total_spent" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-input v-model="filters.tag" placeholder="标签筛选" clearable @clear="fetchList" @keyup.enter="fetchList" />
        </el-col>
        <el-col :span="3"><el-button type="primary" @click="fetchList">搜索</el-button></el-col>
        <el-col :span="3"><el-button @click="resetFilters">重置</el-button></el-col>
        <el-col :span="6" style="text-align:right;color:#909399;font-size:13px">共 {{ total }} 条画像记录</el-col>
      </el-row>
    </el-card>

    <!-- 画像列表 -->
    <el-card shadow="never">
      <el-table :data="profiles" stripe v-loading="loading" @row-click="openDetail" style="cursor:pointer" max-height="600">
        <el-table-column prop="user_id" label="买家ID" width="140" />
        <el-table-column label="兴趣标签" min-width="200">
          <template #default="{row}">
            <el-tag v-for="t in (row.tags||[]).slice(0,5)" :key="t" size="small" effect="plain" style="margin:1px">{{ t }}</el-tag>
            <el-tag v-if="(row.tags||[]).length>5" size="small" type="info">+{{ row.tags.length-5 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="活跃度" width="90">
          <template #default="{row}">
            <el-tag :type="levelTagType(row.activity_level)" size="small">{{ levelLabel(row.activity_level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="order_count" label="订单数" width="80" sortable />
        <el-table-column label="消费总额" width="110">
          <template #default="{row}">¥{{ row.total_spent?.toFixed(0) || 0 }}</template>
        </el-table-column>
        <el-table-column label="客单价" width="100">
          <template #default="{row}">¥{{ row.avg_order_amount?.toFixed(0) || 0 }}</template>
        </el-table-column>
        <el-table-column label="最近活跃" width="140">
          <template #default="{row}">{{ row.updated_at?.slice(0,10) || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{row}">
            <el-button size="small" type="primary" link @click.stop="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top:12px;text-align:right">
        <el-pagination v-model:current-page="filters.page" :page-size="filters.page_size" :total="total"
          layout="prev, pager, next" @current-change="fetchList" background small />
      </div>
    </el-card>

    <!-- 画像详情抽屉 -->
    <el-drawer v-model="detailVisible" :title="'用户画像: ' + detailUser.user_id" size="500px" direction="rtl">
      <template v-if="detailLoading"><el-skeleton :rows="10" animated /></template>
      <template v-else>
        <!-- 基础属性 -->
        <el-descriptions title="基础属性" :column="1" border size="small" style="margin-bottom:16px">
          <el-descriptions-item v-for="(v,k) in detailUser.profile?.basic||{}" :key="k" :label="k">{{ v || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 偏好事实 -->
        <el-card shadow="never" style="margin-bottom:12px">
          <template #header><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-weight:bold">偏好事实</span><el-button size="small" text @click="editFacts">编辑</el-button></div></template>
          <div v-if="detailUser.profile?.facts && Object.keys(detailUser.profile.facts).length">
            <el-tag v-for="(v,k) in detailUser.profile.facts" :key="k" style="margin:2px" effect="plain">{{ k }}: {{ v }}</el-tag>
          </div>
          <el-empty v-else description="暂无" :image-size="30" />
        </el-card>

        <!-- 兴趣标签 -->
        <el-card shadow="never" style="margin-bottom:12px">
          <template #header><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-weight:bold">兴趣标签</span><el-button size="small" text @click="editTags">编辑</el-button></div></template>
          <div v-if="detailUser.profile?.tags?.length">
            <el-tag v-for="t in detailUser.profile.tags" :key="t" style="margin:2px" closable @close="removeTag(t)">{{ t }}</el-tag>
          </div>
          <el-empty v-else description="暂无标签" :image-size="30" />
          <div v-if="showTagInput" style="margin-top:8px;display:flex;gap:6px">
            <el-input v-model="newTag" size="small" placeholder="新标签" @keyup.enter="addTag" style="flex:1" />
            <el-button size="small" type="primary" @click="addTag">添加</el-button>
          </div>
        </el-card>

        <!-- 消费特征 -->
        <el-descriptions title="消费特征" :column="2" border size="small" style="margin-bottom:16px">
          <el-descriptions-item label="订单数">{{ detailUser.profile?.consumption?.order_count || 0 }}</el-descriptions-item>
          <el-descriptions-item label="消费总额">¥{{ detailUser.profile?.consumption?.total_spent?.toFixed(0) || 0 }}</el-descriptions-item>
          <el-descriptions-item label="客单价">¥{{ detailUser.profile?.consumption?.avg_order_amount?.toFixed(0) || 0 }}</el-descriptions-item>
          <el-descriptions-item label="活跃度">{{ levelLabel(detailUser.profile?.activity_level) }}</el-descriptions-item>
          <el-descriptions-item label="偏好价位" :span="2">{{ detailUser.profile?.consumption?.preferred_price_range || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 近期意图 -->
        <el-card shadow="never" style="margin-bottom:12px">
          <template #header><span style="font-weight:bold">近期意图</span></template>
          <div v-if="detailUser.profile?.intents?.length">
            <el-timeline><el-timeline-item v-for="(t,i) in detailUser.profile.intents" :key="i" :timestamp="''" placement="top">{{ t }}</el-timeline-item></el-timeline>
          </div>
          <el-empty v-else description="暂无" :image-size="30" />
        </el-card>

        <!-- 近期订单 -->
        <el-card shadow="never" style="margin-bottom:12px">
          <template #header><span style="font-weight:bold">近期订单 ({{ detailUser.recent_orders?.length || 0 }})</span></template>
          <el-table :data="detailUser.recent_orders||[]" size="small" max-height="300">
            <el-table-column prop="order_no" label="订单号" width="130" />
            <el-table-column prop="status" label="状态" width="80"><template #default="{row}"><el-tag size="small" :type="row.status==='completed'?'success':row.status==='paid'?'warning':'info'">{{ row.status }}</el-tag></template></el-table-column>
            <el-table-column label="金额" width="90"><template #default="{row}">¥{{ row.amount?.toFixed(0) }}</template></el-table-column>
            <el-table-column label="时间" width="110"><template #default="{row}">{{ row.created_at?.slice(0,10) }}</template></el-table-column>
          </el-table>
          <el-empty v-if="!detailUser.recent_orders?.length" description="暂无订单" :image-size="30" />
        </el-card>
      </template>
    </el-drawer>

    <!-- 编辑 Facts 对话框 -->
    <el-dialog v-model="factsDialogVisible" title="编辑偏好事实" width="400px">
      <el-form label-width="80px">
        <el-form-item v-for="(v,k) in editingFacts" :key="k" :label="k">
          <el-input v-model="editingFacts[k]" size="small" />
        </el-form-item>
        <el-form-item label="新增">
          <el-input v-model="newFactKey" size="small" placeholder="key" style="width:40%;margin-right:8px" />
          <el-input v-model="newFactVal" size="small" placeholder="value" style="width:40%" />
          <el-button size="small" @click="addFact">+</el-button>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="factsDialogVisible=false">取消</el-button><el-button type="primary" @click="saveFacts">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getBuyerProfileStats, getBuyerProfiles, getBuyerProfileDetail, updateBuyerProfileTags, updateBuyerProfileFacts } from '../api'

// 统计
const stats = ref({})
const loading = ref(false)
const total = ref(0)
const profiles = ref([])
const filters = reactive({ page: 1, page_size: 20, activity_level: '', sort_by: 'updated_at', tag: '' })

// 详情
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailUser = ref({})
const showTagInput = ref(false)
const newTag = ref('')

// Facts 编辑
const factsDialogVisible = ref(false)
const editingFacts = ref({})
const newFactKey = ref('')
const newFactVal = ref('')

// 标签
function activityColor(k) { return { '新用户':'#409eff','活跃':'#67c23a','沉默':'#e6a23c','流失':'#f56c6c' }[k] || '#909399' }
function levelLabel(v) { return { new:'新用户', active:'活跃', dormant:'沉默', lost:'流失' }[v] || v || '新用户' }
function levelTagType(v) { return { new:'', active:'success', dormant:'warning', lost:'danger' }[v] || '' }
function tagType(count) { return count>10 ? '' : count>5 ? 'success' : 'info' }
function tierLabel(k) { return { low:'低消费(<¥200)', mid:'中等(¥200-1000)', high:'高消费(¥1000-5000)', vip:'VIP(¥5000+)' }[k] || k }

async function fetchStats() {
  try { const r = await getBuyerProfileStats(); stats.value = r.data || {} } catch { /* ok */ }
}
async function fetchList() {
  loading.value = true
  try {
    const params = { page: filters.page, page_size: filters.page_size }
    if (filters.activity_level) params.activity_level = filters.activity_level
    if (filters.sort_by) params.sort_by = filters.sort_by
    if (filters.tag) params.tag = filters.tag
    const r = await getBuyerProfiles(params)
    profiles.value = r.data?.items || []
    total.value = r.data?.total || 0
  } finally { loading.value = false }
}

function resetFilters() {
  filters.page = 1; filters.activity_level = ''; filters.sort_by = 'updated_at'; filters.tag = ''
  fetchList()
}
function filterByTag(tag) { filters.tag = tag; filters.page = 1; fetchList() }

async function openDetail(row) {
  detailVisible.value = true; detailLoading.value = true
  try {
    const r = await getBuyerProfileDetail(row.user_id)
    detailUser.value = r.data || {}
  } finally { detailLoading.value = false }
}

// 标签编辑
function editTags() { showTagInput.value = !showTagInput.value }
async function addTag() {
  if (!newTag.value.trim()) return
  const tags = [...(detailUser.value.profile?.tags||[]), newTag.value.trim()]
  try {
    await updateBuyerProfileTags(detailUser.value.user_id, tags)
    detailUser.value.profile.tags = tags; newTag.value = ''
    ElMessage.success('标签已添加')
  } catch { ElMessage.error('更新失败') }
}
async function removeTag(tag) {
  const tags = (detailUser.value.profile?.tags||[]).filter(t => t !== tag)
  try {
    await updateBuyerProfileTags(detailUser.value.user_id, tags)
    detailUser.value.profile.tags = tags
    ElMessage.success('标签已移除')
  } catch { ElMessage.error('更新失败') }
}

// Facts 编辑
function editFacts() {
  editingFacts.value = { ...(detailUser.value.profile?.facts || {}) }
  newFactKey.value = ''; newFactVal.value = ''
  factsDialogVisible.value = true
}
function addFact() {
  if (!newFactKey.value.trim() || !newFactVal.value.trim()) return
  editingFacts.value[newFactKey.value.trim()] = newFactVal.value.trim()
  newFactKey.value = ''; newFactVal.value = ''
}
async function saveFacts() {
  try {
    await updateBuyerProfileFacts(detailUser.value.user_id, editingFacts.value)
    detailUser.value.profile.facts = { ...editingFacts.value }
    factsDialogVisible.value = false
    ElMessage.success('事实已更新')
  } catch { ElMessage.error('更新失败') }
}

onMounted(() => { fetchStats(); fetchList() })
</script>
