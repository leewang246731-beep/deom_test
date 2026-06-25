<template>
  <div>
    <h3 style="margin:0 0 16px">客服模式配置</h3>
    <el-alert type="info" :closable="false" style="margin-bottom:16px">
      修改客服工作台默认模式，与客服端实时同步。客服端重新加载或刷新页面后将采用新配置。
    </el-alert>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span style="font-weight:bold">默认客服模式</span></template>
          <el-radio-group v-model="form.default_mode" size="large" @change="markDirty">
            <el-radio value="manual" border style="margin-bottom:12px;width:100%">
              <strong>纯人工模式</strong>
              <p style="margin:4px 0 0;font-size:12px;color:#909399">所有买家消息需客服手动回复，不触发AI</p>
            </el-radio>
            <el-radio value="copilot" border style="margin-bottom:12px;width:100%">
              <strong>人机协同模式</strong>
              <p style="margin:4px 0 0;font-size:12px;color:#909399">AI生成建议话术，客服可选择采纳或忽略</p>
            </el-radio>
            <el-radio value="auto" border style="width:100%">
              <strong>全自动模式</strong>
              <p style="margin:4px 0 0;font-size:12px;color:#909399">AI自动回复，仅在置信度不足时转人工</p>
            </el-radio>
          </el-radio-group>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span style="font-weight:bold">自动模式参数</span></template>
          <el-form :model="form" label-width="140px" size="default">
            <el-form-item label="AI置信度阈值">
              <el-slider v-model="form.auto_confidence_threshold" :min="0.5" :max="0.99" :step="0.01" show-input @change="markDirty" />
              <span style="font-size:11px;color:#909399">高于此阈值AI自动发送，低于则转人工</span>
            </el-form-item>
            <el-form-item label="兜底置信度阈值">
              <el-slider v-model="form.fallback_confidence_threshold" :min="0.3" :max="0.8" :step="0.01" show-input @change="markDirty" />
              <span style="font-size:11px;color:#909399">低于此阈值直接转人工</span>
            </el-form-item>
            <el-form-item label="人工响应超时(秒)">
              <el-input-number v-model="form.human_response_timeout_seconds" :min="30" :max="600" :step="30" @change="markDirty" />
            </el-form-item>
            <el-form-item label="兜底消息模板">
              <el-input v-model="form.fallback_template" type="textarea" :rows="2" @change="markDirty" />
            </el-form-item>
            <el-form-item label="繁忙提示模板">
              <el-input v-model="form.busy_template" type="textarea" :rows="2" @change="markDirty" />
            </el-form-item>
            <el-form-item label="离线提示模板">
              <el-input v-model="form.offline_template" type="textarea" :rows="2" @change="markDirty" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <div style="margin-top:16px;display:flex;gap:8px">
      <el-button type="primary" :loading="saving" @click="handleSave" :disabled="!dirty">保存配置</el-button>
      <el-button @click="handleReset" :disabled="!dirty">重置</el-button>
      <span v-if="saved" style="color:#67c23a;line-height:32px;margin-left:8px">已保存</span>
    </div>

    <el-card shadow="never" style="margin-top:16px">
      <template #header><span style="font-weight:bold">自动回复统计</span></template>
      <el-row :gutter="16">
        <el-col :span="6"><el-statistic title="总处理" :value="stats.total || 0" /></el-col>
        <el-col :span="6"><el-statistic title="自动发送" :value="stats.auto_sent || 0" /></el-col>
        <el-col :span="6"><el-statistic title="兜底发送" :value="stats.fallback_sent || 0" /></el-col>
        <el-col :span="6"><el-statistic title="转人工" :value="stats.transferred || 0" /></el-col>
      </el-row>
      <el-row :gutter="16" style="margin-top:12px">
        <el-col :span="12">
          <span style="font-size:13px;color:#606266">自动化率: {{ ((stats.auto_rate || 0) * 100).toFixed(0) }}%</span>
          <el-progress :percentage="(stats.auto_rate || 0) * 100" :stroke-width="8" />
        </el-col>
        <el-col :span="12">
          <span style="font-size:13px;color:#606266">转人工率: {{ ((stats.transfer_rate || 0) * 100).toFixed(0) }}%</span>
          <el-progress :percentage="(stats.transfer_rate || 0) * 100" :stroke-width="8" status="warning" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getServiceModeConfig, updateServiceModeConfig, getAutoReplyStats } from '../api'
import { ElMessage } from 'element-plus'

const saving = ref(false)
const saved = ref(false)
const dirty = ref(false)
const stats = ref({})

const form = reactive({
  default_mode: 'copilot',
  auto_confidence_threshold: 0.80,
  fallback_confidence_threshold: 0.50,
  human_response_timeout_seconds: 120,
  fallback_template: '您的问题已收到，客服稍后回复您。',
  busy_template: '当前咨询人数较多，请稍候。',
  offline_template: '当前非工作时间，客服上线后将回复您。',
})

function markDirty() { dirty.value = true; saved.value = false }

async function loadConfig() {
  try {
    const res = await getServiceModeConfig()
    if (res.data) Object.assign(form, res.data)
    dirty.value = false
  } catch { /* */ }
}

async function handleSave() {
  saving.value = true
  try {
    await updateServiceModeConfig({ ...form })
    saved.value = true; dirty.value = false
    ElMessage.success('配置已保存，客服端将同步更新')
  } catch { /* */ } finally { saving.value = false }
}

function handleReset() {
  loadConfig()
}

async function loadStats() {
  try { stats.value = await getAutoReplyStats() || {} } catch { /* */ }
}

onMounted(() => { loadConfig(); loadStats() })
</script>
