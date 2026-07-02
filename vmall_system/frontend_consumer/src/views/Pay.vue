<template>
  <div style="max-width:500px;margin:0 auto;padding:16px">
    <el-card v-if="loading" shadow="never"><div style="text-align:center;padding:40px">加载中...</div></el-card>

    <el-card v-else-if="error" shadow="never">
      <el-result icon="error" title="链接无效" :sub-title="error">
        <template #extra><el-button type="primary" @click="$router.push('/')">返回首页</el-button></template>
      </el-result>
    </el-card>

    <template v-else>
      <el-card shadow="hover" style="margin-bottom:16px">
        <template #header><span style="font-weight:bold">确认订单</span></template>
        <div v-if="info.product" style="display:flex;gap:12px;align-items:center;margin-bottom:16px">
          <el-image v-if="info.product.image" :src="info.product.image" fit="cover" style="width:80px;height:80px;border-radius:8px" />
          <div>
            <div style="font-weight:bold;font-size:15px">{{info.product.title}}</div>
            <div style="color:#909399;font-size:13px">数量: {{info.quantity}}件</div>
          </div>
        </div>
        <el-divider />
        <div style="display:flex;justify-content:space-between;font-size:14px;margin-bottom:8px">
          <span>商品金额</span><span>¥{{info.pay_amount + info.discount_amount}}</span>
        </div>
        <div v-if="info.discount_amount>0" style="display:flex;justify-content:space-between;font-size:14px;margin-bottom:8px;color:#e6a23c">
          <span>优惠</span><span>-¥{{info.discount_amount}}</span>
        </div>
        <el-divider />
        <div style="display:flex;justify-content:space-between;font-weight:bold;font-size:18px;color:#e6a23c">
          <span>应付</span><span>¥{{info.pay_amount}}</span>
        </div>
        <div style="color:#909399;font-size:12px;margin-top:8px">链接剩余有效期: {{info.expires_in}}分钟</div>
      </el-card>

      <el-button type="primary" size="large" style="width:100%" @click="doPay" :loading="paying" :disabled="info.status!=='pending'">
        💳 确认支付 ¥{{info.pay_amount}}
      </el-button>
      <div v-if="info.status!=='pending'" style="text-align:center;color:#909399;margin-top:8px">
        该订单已{{ info.status==='paid'?'支付':'处理' }}
      </div>
      <div style="text-align:center;margin-top:12px">
        <el-button text @click="$router.push('/')">返回首页</el-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'; import { useRoute, useRouter } from 'vue-router'; import { ElMessage } from 'element-plus'
import axios from 'axios'
const http = axios.create({ baseURL: '/api/v1', timeout: 15000 })
http.interceptors.request.use(c => { const t = localStorage.getItem('vmall_token'); if (t) c.headers.Authorization = `Bearer ${t}`; return c })
http.interceptors.response.use(r => r.data)

const route = useRoute(); const r = useRouter()
const info = ref({}); const loading = ref(true); const error = ref(''); const paying = ref(false)

onMounted(async () => {
  const token = route.params.token
  if (!token) { error.value = '缺少链接参数'; loading.value = false; return }
  try {
    const res = await http.get(`/consumer/orders/payment-link/${token}`)
    info.value = res.data || {}
  } catch (e) {
    error.value = e.response?.data?.detail?.msg || '链接已过期或不存在'
  } finally { loading.value = false }
})

async function doPay() {
  const token = route.params.token
  paying.value = true
  try {
    const res = await http.post(`/consumer/orders/payment-link/${token}/confirm`)
    if (res.data?.success) {
      ElMessage.success('支付成功！')
      info.value.status = 'paid'
      setTimeout(() => r.push('/orders'), 1500)
    } else {
      ElMessage.warning(res.data?.msg || '支付失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail?.msg || '支付失败，请稍后重试')
  } finally { paying.value = false }
}
</script>
