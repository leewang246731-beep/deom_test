<template>
  <div style="height:100%;display:flex;flex-direction:column;background:#fff">
    <!-- KB header -->
    <div style="display:flex;align-items:center;gap:12px;padding:12px 16px;border-bottom:1px solid #e4e7ed;background:#fafafa">
      <el-icon size="18"><Reading /></el-icon>
      <span style="font-weight:600">企业知识库</span>
      <span style="color:#909399;font-size:12px">基于店铺知识的智能回答</span>
      <el-button size="small" text style="margin-left:auto" @click="handleNewConv">新对话</el-button>
      <span style="font-size:12px;color:#909399">文档: {{ stats.document_count || 0 }} · 切片: {{ stats.chunk_count || 0 }}</span>
    </div>

    <!-- Messages -->
    <div ref="chatBox" style="flex:1;overflow-y:auto;padding:16px">
      <div v-if="!messages.length" style="text-align:center;color:#909399;padding:60px 0">
        <el-icon size="40" style="color:#c0c4cc"><ChatDotSquare /></el-icon>
        <p style="margin-top:12px">在下方输入问题，查询店铺知识库</p>
        <p style="font-size:12px;color:#c0c4cc">示例: "店铺有哪些护肤品"、"这款手机有什么特点"</p>
      </div>

      <div v-for="(m, i) in messages" :key="i" style="margin-bottom:16px">
        <!-- user -->
        <div v-if="m.role === 'user'" style="text-align:right;margin-bottom:12px">
          <div style="display:inline-block;background:#409eff;color:#fff;padding:8px 14px;border-radius:12px 12px 0 12px;max-width:75%;text-align:left;font-size:14px">{{ m.content }}</div>
        </div>
        <!-- assistant -->
        <div v-else style="display:flex;gap:8px">
          <div style="width:28px;height:28px;border-radius:50%;background:#409eff;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <span style="color:#fff;font-size:12px;font-weight:bold">AI</span>
          </div>
          <div style="flex:1;max-width:85%">
            <div style="background:#f5f7fa;padding:10px 14px;border-radius:0 12px 12px 12px;font-size:14px;line-height:1.6;white-space:pre-wrap">
              {{ m.content }}
              <span v-if="m.streaming" style="display:inline-block;width:8px;height:14px;background:#409eff;animation:blink 1s infinite;vertical-align:text-bottom"> </span>
            </div>
            <!-- references -->
            <div v-if="!m.streaming && m.references?.length" style="margin-top:8px;padding:8px 12px;background:#fafafa;border-radius:8px;border-left:3px solid #409eff">
              <div style="font-size:12px;color:#909399;margin-bottom:4px;font-weight:600">参考来源</div>
              <div v-for="ref in m.references.slice(0, 5)" :key="ref.index" style="margin-bottom:4px">
                <div style="font-size:12px;display:flex;align-items:center;gap:6px">
                  <span style="color:#409eff;font-weight:600">#{{ ref.index }}</span>
                  <span>{{ ref.heading || '(无标题)' }}</span>
                  <el-tag size="small" :type="ref.score > 0.7 ? 'success' : 'info'">{{ (ref.score * 100).toFixed(0) }}%</el-tag>
                </div>
                <div style="font-size:12px;color:#606266;padding-left:16px">{{ ref.content_snippet?.substring(0, 100) }}</div>
              </div>
            </div>
            <div v-if="!m.streaming && m.confidence != null" style="margin-top:4px;text-align:right">
              <small style="color:#909399">置信度 {{ (m.confidence * 100).toFixed(0) }}%</small>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- input -->
    <div style="padding:12px 16px;border-top:1px solid #e4e7ed;display:flex;gap:8px">
      <el-input v-model="question" placeholder="输入问题..." :disabled="asking" @keyup.enter="handleAsk" clearable />
      <el-button type="primary" :loading="asking" @click="handleAsk">
        <el-icon><Promotion /></el-icon> 发送
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { kbCreateConversation, kbGetStats } from '../api'
import { streamKBAsk } from '../utils/sse'
import { ElMessage } from 'element-plus'

const messages = ref([])
const question = ref('')
const asking = ref(false)
const convId = ref(null)
const chatBox = ref(null)
const stats = ref({})
const token = localStorage.getItem('token') || ''

onMounted(async () => {
  try { stats.value = await kbGetStats() || {} } catch {}
  await handleNewConv()
})

async function handleNewConv() {
  try {
    const r = await kbCreateConversation({ title: '客服知识库查询' })
    convId.value = r?.id
    messages.value = []
  } catch {}
}

async function handleAsk() {
  if (!question.value.trim() || asking.value) return
  if (!convId.value) await handleNewConv()
  asking.value = true
  const q = question.value.trim()
  question.value = ''
  messages.value.push({ role: 'user', content: q })
  messages.value.push({ role: 'assistant', content: '', streaming: true, references: [] })
  const idx = messages.value.length - 1

  streamKBAsk(q, convId.value, token, {
    onContext(data) {
      if (data.sources) messages.value[idx].references = data.sources
      if (data.warning) ElMessage.warning(data.warning)
    },
    onToken(text) {
      messages.value[idx].content += text
      nextTick(() => { if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight })
    },
    onDone(data) {
      messages.value[idx].streaming = false
      messages.value[idx].confidence = data.confidence
      messages.value[idx].references = data.references || messages.value[idx].references
      asking.value = false
    },
    onError(e) {
      messages.value[idx].content = '抱歉，查询知识库时发生错误。'
      messages.value[idx].streaming = false
      asking.value = false
    },
  })
}
</script>

<style scoped>
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
</style>
