<template>
  <div style="height:100%;display:flex;background:#fff">
    <!-- Left: Document browser -->
    <div style="width:280px;border-right:1px solid #e4e7ed;display:flex;flex-direction:column">
      <div style="padding:12px;border-bottom:1px solid #e4e7ed;background:#fafafa">
        <span style="font-weight:600;font-size:14px">知识文档</span>
        <el-button size="small" type="primary" style="margin-left:8px" @click="showAddDoc = true">
          <el-icon><DocumentAdd /></el-icon>
        </el-button>
        <span style="font-size:12px;color:#909399;margin-left:8px">{{ stats.document_count || 0 }} 篇</span>
      </div>
      <div style="flex:1;overflow-y:auto;padding:8px">
        <div v-if="!documents.length" style="text-align:center;color:#909399;padding:20px;font-size:13px">暂无文档</div>
        <div
          v-for="d in documents" :key="d.id"
          :style="{ padding:'8px 10px', marginBottom:'4px', borderRadius:'6px', cursor:'pointer', background: selectedDoc?.id === d.id ? '#ecf5ff' : 'transparent' }"
          @click="selectedDoc = d"
        >
          <div style="font-size:13px;font-weight:500;line-height:1.4">{{ d.title }}</div>
          <div style="display:flex;align-items:center;gap:6px;margin-top:4px">
            <el-tag size="small" :type="d.source_type === 'manual' ? '' : 'info'">{{ d.source_type }}</el-tag>
            <el-tag size="small" :type="d.status === 'done' ? 'success' : d.status === 'failed' ? 'danger' : 'warning'">{{ d.status }}</el-tag>
            <span style="font-size:11px;color:#909399">{{ d.chunk_count || 0 }}切片</span>
          </div>
          <div v-if="selectedDoc?.id === d.id && d.content" style="margin-top:6px;font-size:12px;color:#606266;max-height:120px;overflow-y:auto;white-space:pre-wrap;border:1px solid #e4e7ed;padding:6px;border-radius:4px;background:#fff">{{ d.content?.substring(0, 400) }}{{ d.content?.length > 400 ? '...' : '' }}</div>
        </div>
      </div>
    </div>

    <!-- Right: Chat panel -->
    <div style="flex:1;display:flex;flex-direction:column">
      <div style="display:flex;align-items:center;gap:12px;padding:8px 16px;border-bottom:1px solid #e4e7ed;background:#fafafa">
        <el-icon size="18"><Reading /></el-icon>
        <span style="font-weight:600">知识库问答</span>
        <el-button size="small" text style="margin-left:auto" @click="handleNewConv">新对话</el-button>
      </div>

      <div ref="chatBox" style="flex:1;overflow-y:auto;padding:16px">
        <div v-if="!messages.length" style="text-align:center;color:#909399;padding:60px 0">
          <el-icon size="40" style="color:#c0c4cc"><ChatDotSquare /></el-icon>
          <p style="margin-top:12px">在下方输入问题，查询店铺知识库</p>
        </div>

        <div v-for="(m, i) in messages" :key="i" style="margin-bottom:16px">
          <div v-if="m.role === 'user'" style="text-align:right;margin-bottom:12px">
            <div style="display:inline-block;background:#409eff;color:#fff;padding:8px 14px;border-radius:12px 12px 0 12px;max-width:75%;text-align:left;font-size:14px">{{ m.content }}</div>
          </div>
          <div v-else style="display:flex;gap:8px">
            <div style="width:28px;height:28px;border-radius:50%;background:#409eff;display:flex;align-items:center;justify-content:center;flex-shrink:0">
              <span style="color:#fff;font-size:12px;font-weight:bold">AI</span>
            </div>
            <div style="flex:1;max-width:85%">
              <div style="background:#f5f7fa;padding:10px 14px;border-radius:0 12px 12px 12px;font-size:14px;line-height:1.6;white-space:pre-wrap">
                {{ m.content }}
                <span v-if="m.streaming" style="display:inline-block;width:8px;height:14px;background:#409eff;animation:blink 1s infinite;vertical-align:text-bottom"> </span>
              </div>
              <div v-if="!m.streaming && m.references?.length" style="margin-top:8px;padding:8px 12px;background:#fafafa;border-radius:8px;border-left:3px solid #409eff">
                <div style="font-size:12px;color:#909399;margin-bottom:4px;font-weight:600">参考来源</div>
                <div v-for="ref in m.references.slice(0,5)" :key="ref.index" style="margin-bottom:4px">
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

      <div style="padding:12px 16px;border-top:1px solid #e4e7ed;display:flex;gap:8px">
        <el-input v-model="question" placeholder="输入问题..." :disabled="asking" @keyup.enter="handleAsk" clearable />
        <el-button type="primary" :loading="asking" @click="handleAsk">
          <el-icon><Promotion /></el-icon> 发送
        </el-button>
      </div>
    </div>

    <!-- Add Document Dialog -->
    <el-dialog v-model="showAddDoc" title="添加知识文档" width="500px">
      <el-form :model="docForm" label-width="80px">
        <el-form-item label="标题"><el-input v-model="docForm.title" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="docForm.source_type" style="width:100%">
            <el-option label="商品" value="product" />
            <el-option label="店铺信息" value="shop_info" />
            <el-option label="手动" value="manual" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="docForm.content" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDoc = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="handleAddDoc">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { kbGetDocuments, kbCreateDocument, kbCreateConversation, kbGetStats } from '../api'
import { streamKBAsk } from '../utils/sse'
import { ElMessage } from 'element-plus'

const messages = ref([])
const question = ref('')
const asking = ref(false)
const convId = ref(null)
const chatBox = ref(null)
const stats = ref({})
const token = localStorage.getItem('token') || ''

// Document browser
const documents = ref([])
const selectedDoc = ref(null)
const showAddDoc = ref(false)
const addLoading = ref(false)
const docForm = reactive({ title: '', content: '', source_type: 'manual' })

async function fetchDocs() {
  try { documents.value = (await kbGetDocuments({ page: 1, page_size: 100 }))?.items || [] } catch {}
}

onMounted(async () => {
  try { stats.value = await kbGetStats() || {} } catch {}
  await fetchDocs()
  await handleNewConv()
})

async function handleNewConv() {
  try {
    const r = await kbCreateConversation({ title: '客服知识库查询' })
    convId.value = r?.id; messages.value = []
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

async function handleAddDoc() {
  if (!docForm.title.trim() || !docForm.content.trim()) return ElMessage.warning('请填写标题和内容')
  addLoading.value = true
  try {
    await kbCreateDocument({ ...docForm })
    ElMessage.success('添加成功，正在向量化...')
    showAddDoc.value = false
    Object.assign(docForm, { title: '', content: '', source_type: 'manual' })
    fetchDocs()
    try { stats.value = await kbGetStats() || {} } catch {}
  } catch {} finally { addLoading.value = false }
}
</script>

<style scoped>
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
</style>
