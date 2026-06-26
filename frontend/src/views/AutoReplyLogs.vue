<template>
  <div>
    <h3 style="margin:0 0 16px">AI 话术采纳日志</h3>

    <el-card style="margin-bottom:16px">
      <el-row :gutter="12">
        <el-col :span="5">
          <el-select v-model="filters.mode" placeholder="模式" clearable style="width:100%" @change="fetch">
            <el-option label="纯人工" value="manual" />
            <el-option label="人机协同" value="copilot" />
            <el-option label="全自动" value="auto" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.action_taken" placeholder="动作" clearable style="width:100%" @change="fetch">
            <el-option label="自动发送" value="auto_sent" />
            <el-option label="降级发送" value="fallback_sent" />
            <el-option label="转人工" value="transferred" />
            <el-option label="升级" value="escalated" />
          </el-select>
        </el-col>
        <el-col :span="4"><el-date-picker v-model="filters.date_from" type="date" placeholder="开始日期" style="width:100%" @change="fetch" /></el-col>
        <el-col :span="4"><el-date-picker v-model="filters.date_to" type="date" placeholder="结束日期" style="width:100%" @change="fetch" /></el-col>
        <el-col :span="4"><el-button @click="resetFilters">重置</el-button></el-col>
      </el-row>
    </el-card>

    <el-table :data="logs" border stripe v-loading="loading" empty-text="暂无记录">
      <el-table-column prop="conversation_id" label="会话ID" width="80" />
      <el-table-column prop="buyer_question" label="买家问题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="ai_reply" label="AI 回复" min-width="220" show-overflow-tooltip />
      <el-table-column label="置信度" width="90">
        <template #default="{ row }">{{ row.confidence != null ? (row.confidence * 100).toFixed(0) + '%' : '-' }}</template>
      </el-table-column>
      <el-table-column label="动作" width="110">
        <template #default="{ row }">
          <el-tag :type="actionTag(row.action_taken)" size="small">{{ actionLabel(row.action_taken) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="模式" width="90">
        <template #default="{ row }"><el-tag size="small">{{ modeLabel(row.mode) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="人工介入" width="90">
        <template #default="{ row }">{{ row.human_override ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="响应耗时" width="100">
        <template #default="{ row }">{{ row.response_time_ms ? (row.response_time_ms / 1000).toFixed(1) + 's' : '-' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="170" />
    </el-table>

    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch" />
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { getAutoReplyLogs } from '../api'

const logs = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const filters = reactive({ mode: '', action_taken: '', date_from: null, date_to: null })

function actionLabel(a) {
  const m = { auto_sent: '自动发送', fallback_sent: '降级发送', transferred: '转人工', escalated: '已升级' }
  return m[a] || a
}
function actionTag(a) {
  const m = { auto_sent: 'success', fallback_sent: 'warning', transferred: 'info', escalated: 'danger' }
  return m[a] || ''
}
function modeLabel(m) {
  const map = { manual: '纯人工', copilot: '人机协同', auto: '全自动' }
  return map[m] || m
}

async function fetch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (filters.mode) params.mode = filters.mode
    if (filters.action_taken) params.action_taken = filters.action_taken
    if (filters.date_from) params.date_from = toDateStr(filters.date_from)
    if (filters.date_to) params.date_to = toDateStr(filters.date_to)
    const res = await getAutoReplyLogs(params)
    logs.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch {
    logs.value = []
    total.value = 0
  } finally { loading.value = false }
}

function toDateStr(d) {
  if (d instanceof Date) return d.toISOString().split('T')[0]
  return d
}

function resetFilters() {
  Object.assign(filters, { mode: '', action_taken: '', date_from: null, date_to: null })
  page.value = 1
  fetch()
}

fetch()
</script>
