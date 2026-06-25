<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 style="margin:0">实时监控</h3>
      <div style="display:flex;gap:8px;align-items:center">
        <el-tag :type="polling ? 'success' : 'info'" size="small">{{ polling ? '自动刷新中' : '已暂停' }}</el-tag>
        <el-button size="small" @click="polling = !polling">{{ polling ? '暂停' : '恢复' }}</el-button>
        <el-button size="small" @click="fetch" :loading="loading">刷新</el-button>
      </div>
    </div>

    <!-- Queue summary -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6">
        <el-card shadow="hover"><div style="text-align:center">
          <p style="color:#909399;font-size:13px;margin:0">在线坐席</p>
          <h2 style="margin:8px 0 0;color:#409eff">{{ data.total_agents }}</h2>
        </div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div style="text-align:center">
          <p style="color:#909399;font-size:13px;margin:0">待分配会话</p>
          <h2 style="margin:8px 0 0;color:#e6a23c">{{ data.queue?.unassigned_convs || 0 }}</h2>
        </div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div style="text-align:center">
          <p style="color:#909399;font-size:13px;margin:0">待分配工单</p>
          <h2 style="margin:8px 0 0;color:#f56c6c">{{ data.queue?.unassigned_tickets || 0 }}</h2>
        </div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div style="text-align:center">
          <p style="color:#909399;font-size:13px;margin:0">总负载</p>
          <h2 style="margin:8px 0 0;color:#303133">{{ totalLoad }}</h2>
        </div></el-card>
      </el-col>
    </el-row>

    <!-- Agent cards -->
    <el-row :gutter="16">
      <el-col :span="8" v-for="a in data.agents" :key="a.user_id" style="margin-bottom:16px">
        <el-card shadow="hover">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <div>
              <strong style="font-size:15px">{{ a.display_name }}</strong>
              <el-tag size="small" style="margin-left:6px">{{ a.role === 'admin' ? '管理员' : a.role === 'manager' ? '经理' : '客服' }}</el-tag>
            </div>
            <el-tag :type="a.total_load > 5 ? 'danger' : a.total_load > 2 ? 'warning' : 'success'" size="small">
              {{ a.total_load > 5 ? '繁忙' : a.total_load > 2 ? '正常' : '空闲' }}
            </el-tag>
          </div>
          <div style="display:flex;gap:16px">
            <div style="flex:1;text-align:center;padding:10px;background:#f0f9ff;border-radius:6px">
              <p style="margin:0;font-size:12px;color:#909399">活跃会话</p>
              <p style="margin:4px 0 0;font-size:20px;font-weight:bold;color:#409eff">{{ a.active_convs }}</p>
            </div>
            <div style="flex:1;text-align:center;padding:10px;background:#fef0f0;border-radius:6px">
              <p style="margin:0;font-size:12px;color:#909399">开放工单</p>
              <p style="margin:4px 0 0;font-size:20px;font-weight:bold;color:#f56c6c">{{ a.open_tickets }}</p>
            </div>
            <div style="flex:1;text-align:center;padding:10px;background:#f5f7fa;border-radius:6px">
              <p style="margin:0;font-size:12px;color:#909399">总负载</p>
              <p style="margin:4px 0 0;font-size:20px;font-weight:bold;color:#303133">{{ a.total_load }}</p>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!data.agents?.length" description="暂无坐席数据" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { getLiveMonitor } from '../api'

const data = ref({ agents: [], queue: {}, total_agents: 0 })
const loading = ref(false)
const polling = ref(true)
let timer = null

const totalLoad = computed(() =>
  (data.value.agents || []).reduce((s, a) => s + (a.total_load || 0), 0)
)

async function fetch() {
  loading.value = true
  try { const r = await getLiveMonitor(); data.value = r.data || data.value }
  catch { /* */ }
  finally { loading.value = false }
}

watch(polling, (v) => {
  if (v) { timer = setInterval(fetch, 10000); fetch() }
  else { clearInterval(timer) }
})

onMounted(() => {
  fetch()
  if (polling.value) timer = setInterval(fetch, 10000)
})
onUnmounted(() => clearInterval(timer))
</script>
