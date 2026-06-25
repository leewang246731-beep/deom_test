<template>
  <div>
    <h3 style="margin-bottom:16px">SaaS 平台绑定</h3>

    <!-- Bound state -->
    <el-card v-if="status && status.bound" v-loading="loading">
      <el-result icon="success" title="已绑定到 SaaS 智能托管平台" :sub-title="`店铺「${status.saas_shop_name || '-'}」已接入 SaaS 平台，享受智能客服、商品推荐、订单同步等服务`">
        <template #extra>
          <el-descriptions :column="2" border style="margin-bottom:16px">
            <el-descriptions-item label="SaaS 地址">{{ status.saas_url || '-' }}</el-descriptions-item>
            <el-descriptions-item label="SaaS 店铺ID">{{ status.saas_shop_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="绑定时间">{{ status.saas_bind_time || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag type="success">已激活</el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <el-popconfirm title="解绑后智能托管将停止，确定解绑？" @confirm="handleUnbind">
            <template #reference>
              <el-button type="danger">解除绑定</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-result>
    </el-card>

    <!-- Unbound state -->
    <el-card v-else v-loading="loading">
      <el-result icon="info" title="尚未绑定 SaaS 平台" sub-title="绑定后，您的店铺将由 SaaS 平台智能托管，包括智能客服、商品推荐、订单同步等功能">
        <template #extra>
          <el-button type="primary" size="large" @click="showBindDialog = true">开始绑定</el-button>
        </template>
      </el-result>
    </el-card>

    <!-- Bind dialog -->
    <el-dialog v-model="showBindDialog" title="绑定到 SaaS 平台" width="500px" :close-on-click-modal="false">
      <el-alert type="info" :closable="false" style="margin-bottom:16px">
        <template #title>
          请从 SaaS 管理后台的「店铺管理」中获取绑定码，粘贴到下方完成绑定
        </template>
      </el-alert>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" size="default">
        <el-form-item label="SaaS 平台地址" prop="saas_url">
          <el-input v-model="form.saas_url" placeholder="例如 http://127.0.0.1:8010">
            <template #prepend>URL</template>
          </el-input>
          <div style="font-size:11px;color:#909399;margin-top:2px">SaaS 平台后端 API 地址（非前端页面地址）</div>
        </el-form-item>
        <el-form-item label="绑定码" prop="bind_token">
          <el-input v-model="form.bind_token" placeholder="粘贴从 SaaS 管理后台复制的绑定码" style="font-family:monospace;font-size:15px" clearable />
          <div style="font-size:11px;color:#909399;margin-top:2px">由 SaaS 管理员在「店铺管理 → 生成绑定码」提供</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBindDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleConfirm">
          {{ submitting ? '验证中...' : '确认绑定' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getBindingStatus, confirmBinding, unbindSaaS } from '../api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const status = ref(null)
const showBindDialog = ref(false)
const formRef = ref(null)
const form = reactive({ saas_url: 'http://127.0.0.1:8010', bind_token: '' })
const rules = {
  saas_url: [{ required: true, message: '请输入 SaaS 平台地址', trigger: 'blur' }],
  bind_token: [{ required: true, message: '请输入绑定码', trigger: 'blur' }],
}

async function fetchStatus() {
  loading.value = true
  try { status.value = await getBindingStatus() } catch { /* */ }
  finally { loading.value = false }
}

async function handleConfirm() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const res = await confirmBinding({ ...form })
    ElMessage.success(res.msg || '绑定成功！')
    showBindDialog.value = false
    form.bind_token = ''
    await fetchStatus()
  } catch { /* */ }
  finally { submitting.value = false }
}

async function handleUnbind() {
  try {
    await unbindSaaS()
    ElMessage.success('已解绑')
    await fetchStatus()
  } catch { /* */ }
}

onMounted(fetchStatus)
</script>
