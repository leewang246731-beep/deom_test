<template>
  <div style="height:100vh;display:flex;flex-direction:column;background:#f5f7fa">
    <div style="background:#fff;border-bottom:1px solid #e4e7ed;padding:8px 20px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0">
      <div style="display:flex;align-items:center;gap:16px">
        <span style="font-weight:bold;font-size:16px;color:#303133;cursor:pointer" @click="$router.push('/service/workbench')">客服工作台</span>
        <el-segmented v-model="globalMode" :options="modeOptions" @change="onModeChange" size="small" />
        <el-tabs v-model="activeTab" @tab-change="onTabChange" style="margin-left:8px">
          <el-tab-pane label="会话" name="workbench" />
          <el-tab-pane label="知识库" name="knowledge" />
        </el-tabs>
      </div>
      <div style="display:flex;align-items:center;gap:12px">
        <span style="color:#606266;font-size:13px">{{ auth.user?.display_name || auth.user?.username }}</span>
        <el-button type="danger" text size="small" @click="handleLogout">退出</el-button>
      </div>
    </div>
    <div style="flex:1;overflow:hidden">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { updateServiceModeConfig, getServiceModeConfig } from '../api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const globalMode = ref('copilot')
const modeOptions = [
  { label: '纯人工', value: 'manual' },
  { label: '人机协同', value: 'copilot' },
  { label: '全自动', value: 'auto' },
]

const activeTab = computed(() => route.path === '/service/knowledge' ? 'knowledge' : 'workbench')

function onTabChange(name) {
  router.push(name === 'knowledge' ? '/service/knowledge' : '/service/workbench')
}

async function onModeChange(mode) {
  try {
    await updateServiceModeConfig({ default_mode: mode })
    ElMessage.success(`默认模式已切换为 ${modeOptions.find(o => o.value === mode)?.label || mode}`)
  } catch { /* */ }
}

function handleLogout() {
  auth.logout()
  router.replace('/login')
}

onMounted(async () => {
  try {
    const res = await getServiceModeConfig()
    if (res.data?.default_mode) globalMode.value = res.data.default_mode
  } catch { /* */ }
})
</script>
