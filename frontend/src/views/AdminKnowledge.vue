<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 style="margin:0">企业知识库</h3>
      <div style="display:flex;gap:8px">
        <el-button type="primary" @click="handleSync" :loading="syncLoading">
          <el-icon><Refresh /></el-icon> 同步店铺知识
        </el-button>
        <el-button @click="showAddDoc = true"><el-icon><DocumentAdd /></el-icon> 添加文档</el-button>
      </div>
    </div>

    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6"><el-card shadow="hover"><strong>{{ stats.document_count || 0 }}</strong><br><small>文档数</small></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><strong>{{ stats.chunk_count || 0 }}</strong><br><small>切片数</small></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><strong>{{ stats.conversation_count || 0 }}</strong><br><small>问答会话</small></el-card></el-col>
    </el-row>

    <el-row :gutter="16" style="height:calc(100vh - 300px)">
      <!-- Q&A panel -->
      <el-col :span="10">
        <el-card style="height:100%;display:flex;flex-direction:column" body-style="flex:1;display:flex;flex-direction:column;overflow:hidden">
          <template #header>
            <div style="display:flex;align-items:center;gap:8px">
              <el-icon><ChatDotSquare /></el-icon> <span>知识库问答</span>
              <el-button size="small" text @click="newConversation" style="margin-left:auto">新对话</el-button>
            </div>
          </template>
          <div ref="chatBox" style="flex:1;overflow-y:auto;padding:8px 0">
            <div v-if="!messages.length" style="text-align:center;color:#909399;padding:40px">开始提问吧</div>
            <div v-for="(m, i) in messages" :key="i" style="margin-bottom:16px">
              <div v-if="m.role === 'user'" style="text-align:right">
                <div style="display:inline-block;background:#409eff;color:#fff;padding:8px 14px;border-radius:12px 12px 0 12px;max-width:80%;text-align:left">{{ m.content }}</div>
              </div>
              <div v-else style="display:flex;gap:8px;align-items:flex-start">
                <div style="flex:1;background:#f0f2f5;padding:8px 14px;border-radius:0 12px 12px 12px;max-width:90%">
                  <div v-if="m.streaming" style="white-space:pre-wrap">{{ m.content }}</div>
                  <div v-else style="white-space:pre-wrap">{{ m.content }}</div>
                  <div v-if="m.references?.length" style="margin-top:8px;border-top:1px solid #e4e7ed;padding-top:8px">
                    <small style="color:#909399">参考来源:</small>
                    <div v-for="ref in m.references" :key="ref.index" style="margin-top:4px">
                      <small>【{{ ref.index }}】 {{ ref.heading || '(无标题)' }} <el-tag size="small" :type="ref.score > 0.7 ? 'success' : 'info'">{{ (ref.score * 100).toFixed(0) }}%</el-tag></small>
                      <div><small style="color:#606266">{{ ref.content_snippet }}</small></div>
                    </div>
                  </div>
                  <div v-if="m.confidence != null" style="margin-top:4px"><small style="color:#909399">置信度: {{ (m.confidence * 100).toFixed(0) }}%</small></div>
                </div>
              </div>
            </div>
          </div>
          <div style="display:flex;gap:8px;margin-top:8px">
            <el-input v-model="question" placeholder="输入问题..." :disabled="asking" @keyup.enter="handleAsk" />
            <el-button type="primary" :loading="asking" @click="handleAsk">提问</el-button>
          </div>
        </el-card>
      </el-col>

      <!-- Documents panel -->
      <el-col :span="14">
        <el-card style="height:100%;overflow-y:auto">
          <template #header>知识文档</template>
          <el-table :data="documents" v-loading="docLoading" style="width:100%">
            <el-table-column prop="title" label="标题" />
            <el-table-column prop="source_type" label="来源" width="80">
              <template #default="{ row }">
                <el-tag size="small">{{ row.source_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'done' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="chunk_count" label="切片" width="60" />
            <el-table-column prop="created_at" label="时间" width="160">
              <template #default="{ row }">{{ row.created_at?.split('T')[0] }}</template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button size="small" type="danger" text @click="handleDeleteDoc(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- Add Document Dialog -->
    <el-dialog v-model="showAddDoc" title="添加知识文档" width="500px">
      <el-form ref="docFormRef" :model="docForm" label-width="80px">
        <el-form-item label="标题" prop="title" :rules="[{ required: true }]">
          <el-input v-model="docForm.title" />
        </el-form-item>
        <el-form-item label="类型" prop="source_type">
          <el-select v-model="docForm.source_type" style="width:100%">
            <el-option label="商品" value="product" />
            <el-option label="店铺信息" value="shop_info" />
            <el-option label="手动" value="manual" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" prop="content" :rules="[{ required: true }]">
          <el-input v-model="docForm.content" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDoc = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="handleAddDoc">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { kbGetDocuments, kbCreateDocument, kbDeleteDocument, kbGetConversations, kbCreateConversation, kbGetMessages, kbGetStats, kbSyncShop } from '../api'
import { streamKBAsk } from '../utils/sse'
import { ElMessage, ElMessageBox } from 'element-plus'

const stats = ref({})
const documents = ref([])
const messages = ref([])
const question = ref('')
const asking = ref(false)
const convId = ref(null)
const chatBox = ref(null)
const docLoading = ref(false)
const showAddDoc = ref(false)
const addLoading = ref(false)
const syncLoading = ref(false)
const docForm = reactive({ title: '', content: '', source_type: 'manual' })
const token = localStorage.getItem('token') || ''

async function fetchStats() { try { const r = await kbGetStats(); stats.value = r || {} } catch {} }
async function handleSync() {
  syncLoading.value = true
  try { await kbSyncShop({}); ElMessage.success('同步已启动'); fetchStats(); fetchDocs() }
  catch { /* */ } finally { syncLoading.value = false }
}
async function fetchDocs() {
  docLoading.value = true
  try { documents.value = (await kbGetDocuments({ page: 1, page_size: 50 }))?.items || [] } catch {}
  finally { docLoading.value = false }
}

async function newConversation() {
  try {
    const r = await kbCreateConversation({ title: '管理员知识库问答' })
    convId.value = r?.id
    messages.value = []
  } catch {}
}

async function handleAsk() {
  if (!question.value.trim() || asking.value) return
  if (!convId.value) await newConversation()
  asking.value = true
  const q = question.value.trim()
  question.value = ''
  messages.value.push({ role: 'user', content: q })
  messages.value.push({ role: 'assistant', content: '', streaming: true, references: [] })
  const idx = messages.value.length - 1

  streamKBAsk(q, convId.value, token, {
    onContext(data) {
      if (data.sources) messages.value[idx].references = data.sources
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
      messages.value[idx].content = '发生错误: ' + (e.message || e)
      messages.value[idx].streaming = false
      asking.value = false
    },
  })
}

async function handleAddDoc() {
  addLoading.value = true
  try {
    await kbCreateDocument({ ...docForm })
    ElMessage.success('添加成功，正在向量化...')
    showAddDoc.value = false
    docForm.title = ''; docForm.content = ''; docForm.source_type = 'manual'
    fetchDocs(); fetchStats()
  } catch {} finally { addLoading.value = false }
}

async function handleDeleteDoc(id) {
  await ElMessageBox.confirm('确定删除该文档？', '提示', { type: 'warning' })
  try {
    await kbDeleteDocument(id)
    ElMessage.success('已删除')
    fetchDocs(); fetchStats()
  } catch {}
}

onMounted(() => {
  fetchStats(); fetchDocs(); newConversation()
})
</script>
