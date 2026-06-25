<template>
  <div>
    <h3 style="margin-bottom:16px">客服会话</h3>
    <el-card>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="在线会话" name="active">
          <el-table :data="convs" v-loading="loading" style="width:100%">
            <el-table-column prop="id" label="会话ID" width="80" />
            <el-table-column prop="user_name" label="买家" />
            <el-table-column prop="last_message" label="最后消息" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button size="small" @click="openChat(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="历史会话" name="closed">
          <p style="color:#909399;text-align:center;padding:40px">暂无历史会话</p>
        </el-tab-pane>
      </el-tabs>
    </el-card>
    <el-dialog v-model="chatVisible" title="会话详情" width="600px">
      <div style="max-height:400px;overflow-y:auto">
        <div v-for="msg in messages" :key="msg.id" style="margin-bottom:12px">
          <div style="font-size:12px;color:#909399">{{ msg.sender === 'buyer' ? '买家' : '商户' }} {{ msg.created_at }}</div>
          <div :style="{ padding: '8px 12px', borderRadius: '8px', background: msg.sender === 'buyer' ? '#f0f2f5' : '#e6f4ff', marginTop: '4px', display: 'inline-block' }">
            {{ msg.content }}
          </div>
        </div>
        <div v-if="!messages.length" style="text-align:center;color:#909399;padding:20px">暂无消息</div>
      </div>
      <template #footer>
        <el-input v-model="replyText" placeholder="输入回复..." @keyup.enter="handleReply" />
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getConversations, getConvMessages, sendMessage } from '../api'
import { ElMessage } from 'element-plus'

const convs = ref([])
const messages = ref([])
const activeTab = ref('active')
const chatVisible = ref(false)
const replyText = ref('')
const currentConv = ref(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    convs.value = await getConversations({ status: 'active' })
  } catch { /* handled */ }
  finally { loading.value = false }
})

async function openChat(row) {
  currentConv.value = row
  chatVisible.value = true
  try {
    messages.value = await getConvMessages(row.id)
  } catch { /* handled */ }
}

async function handleReply() {
  if (!replyText.value.trim()) return
  try {
    await sendMessage(currentConv.value.id, { content: replyText.value, sender: 'merchant' })
    messages.value.push({ id: Date.now(), content: replyText.value, sender: 'merchant', created_at: new Date().toISOString() })
    replyText.value = ''
  } catch { /* handled */ }
}
</script>
