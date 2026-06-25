<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px">
      <template #header>物流查询</template>
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="订单ID"><el-input v-model="orderId" placeholder="输入订单ID查询物流" style="width:200px" /></el-form-item>
        <el-form-item><el-button type="primary" @click="queryLogistics" :loading="loading">查询</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="logistics" shadow="never" v-loading="loading">
      <template #header>物流详情</template>
      <el-descriptions :column="2" border style="margin-bottom:16px">
        <el-descriptions-item label="订单ID">{{ logistics.order_id }}</el-descriptions-item>
        <el-descriptions-item label="物流公司">{{ logistics.company }}</el-descriptions-item>
        <el-descriptions-item label="运单号">{{ logistics.tracking_no }}</el-descriptions-item>
        <el-descriptions-item label="当前状态">
          <el-tag :type="logistics.status==='delivered'?'success':logistics.status==='failed'?'danger':''">{{ logistics.status_label || logistics.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="logistics.courier_name" label="快递员">{{ logistics.courier_name }} {{ logistics.courier_phone }}</el-descriptions-item>
        <el-descriptions-item v-if="logistics.current_city" label="当前位置">{{ logistics.current_city }}</el-descriptions-item>
        <el-descriptions-item v-if="logistics.exception_detail" label="异常详情" :span="2">
          <span style="color:#f56c6c">{{ logistics.exception_detail }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <div style="margin-bottom:16px">
        <el-timeline v-if="logistics.tracks && logistics.tracks.length">
          <el-timeline-item v-for="(t,i) in logistics.tracks" :key="i" :timestamp="t.time" :color="i===0?'#409eff':''">{{ t.status }}</el-timeline-item>
        </el-timeline>
      </div>

      <div style="display:flex;gap:8px">
        <el-popconfirm title="确定执行发货？" @confirm="doShip">
          <template #reference><el-button type="primary" :disabled="!!logistics.id || !orderId">发货</el-button></template>
        </el-popconfirm>
        <el-popconfirm title="确定推进到下一节点？" @confirm="doAdvance">
          <template #reference><el-button :disabled="!logistics.id">推进节点</el-button></template>
        </el-popconfirm>
        <el-popconfirm title="确定标记异常？" @confirm="doException">
          <template #reference><el-button type="warning" :disabled="!logistics.id">标记异常</el-button></template>
        </el-popconfirm>
        <el-popconfirm title="确定解除异常？" @confirm="doResolve">
          <template #reference><el-button type="success" :disabled="!logistics.id || !logistics.exception_code">解除异常</el-button></template>
        </el-popconfirm>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { getLogistics, shipLogistics, advanceLogistics, exceptionLogistics, resolveLogistics } from '../api'
import { ElMessage } from 'element-plus'

const orderId = ref('')
const logistics = ref(null)
const loading = ref(false)

async function queryLogistics() {
  if (!orderId.value) return ElMessage.warning('请输入订单ID')
  loading.value = true
  try { logistics.value = (await getLogistics(orderId.value)).data } catch { logistics.value = null }
  finally { loading.value = false }
}

async function doShip() {
  try { logistics.value = (await shipLogistics(orderId.value, { company: '顺丰速运' })).data; ElMessage.success('发货成功') } catch { /* */ }
}

async function doAdvance() {
  try { logistics.value = (await advanceLogistics(logistics.value.id)).data; ElMessage.success('已推进') } catch { /* */ }
}

async function doException() {
  try { logistics.value = (await exceptionLogistics(logistics.value.id, { exception_code: 'STUCK', exception_detail: '物流停滞' })).data; ElMessage.success('已标记') } catch { /* */ }
}

async function doResolve() {
  try { logistics.value = (await resolveLogistics(logistics.value.id)).data; ElMessage.success('已解除') } catch { /* */ }
}
</script>
