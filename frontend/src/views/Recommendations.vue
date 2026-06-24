<template>
  <div>
    <div style="margin-bottom:16px;display:flex;justify-content:space-between">
      <h3 style="margin:0">推荐管理</h3>
      <div>
        <el-button @click="handleRebuild" :loading="rebuilding">重建协同过滤</el-button>
        <el-button type="primary" @click="showAddRule = true">添加关联规则</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="热门商品" name="hot">
        <el-table :data="hot" border stripe v-loading="hotLoading">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="product.title" label="商品" min-width="200" show-overflow-tooltip />
          <el-table-column prop="product.price" label="价格" width="100"><template #default="{ row }">¥{{ row.product.price }}</template></el-table-column>
          <el-table-column prop="why" label="理由" min-width="160" />
          <el-table-column label="销量"><template #default="{ row }">{{ row.stats?.order_count }} 单</template></el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="关联规则" name="rules">
        <el-table :data="rules" border stripe v-loading="rulesLoading">
          <el-table-column prop="product_id" label="源商品ID" width="100" />
          <el-table-column prop="recommended_product_id" label="推荐商品ID" width="120" />
          <el-table-column prop="rule_type" label="类型" width="100" />
          <el-table-column prop="priority" label="优先级" width="80" />
          <el-table-column label="操作" width="80">
            <template #default="{ row }"><el-button size="small" type="danger" text @click="handleDeleteRule(row.id)">删除</el-button></template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showAddRule" title="添加推荐关联" width="450px">
      <el-form :model="ruleForm" label-width="100px">
        <el-form-item label="源商品ID"><el-input-number v-model="ruleForm.product_id" :min="1" style="width:100%" /></el-form-item>
        <el-form-item label="推荐商品ID"><el-input-number v-model="ruleForm.recommended_product_id" :min="1" style="width:100%" /></el-form-item>
        <el-form-item label="类型"><el-select v-model="ruleForm.rule_type" style="width:100%"><el-option label="手动关联" value="manual" /><el-option label="向上销售" value="upsell" /><el-option label="交叉销售" value="cross_sell" /></el-select></el-form-item>
        <el-form-item label="优先级"><el-input-number v-model="ruleForm.priority" :min="0" :max="100" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showAddRule = false">取消</el-button><el-button type="primary" @click="handleAddRule">添加</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getHotProducts, getRecommendationRules, createRecommendationRule, deleteRecommendationRule, rebuildCoPurchase } from '../api'
import { ElMessage } from 'element-plus'

const activeTab = ref('hot')
const hot = ref([]); const hotLoading = ref(false)
const rules = ref([]); const rulesLoading = ref(false)
const showAddRule = ref(false); const rebuilding = ref(false)
const ruleForm = reactive({ product_id: null, recommended_product_id: null, rule_type: 'manual', priority: 0 })

async function fetchHot() { hotLoading.value = true; try { const r = await getHotProducts({ top_k: 20 }); hot.value = r.data?.recommendations || [] } finally { hotLoading.value = false } }
async function fetchRules() { rulesLoading.value = true; try { const r = await getRecommendationRules(); rules.value = r.data || [] } finally { rulesLoading.value = false } }

async function handleAddRule() {
  if (!ruleForm.product_id || !ruleForm.recommended_product_id) return ElMessage.warning('请填写商品ID')
  await createRecommendationRule(ruleForm)
  ElMessage.success('已添加'); showAddRule.value = false; Object.assign(ruleForm, { product_id: null, recommended_product_id: null, rule_type: 'manual', priority: 0 }); fetchRules()
}

async function handleDeleteRule(id) { await deleteRecommendationRule(id); ElMessage.success('已删除'); fetchRules() }

async function handleRebuild() {
  rebuilding.value = true
  try { const r = await rebuildCoPurchase(); ElMessage.success(`重建完成: ${r.data?.co_purchase_pairs || 0} 共购对, ${r.data?.buyer_profiles || 0} 买家画像`) } finally { rebuilding.value = false }
}

onMounted(() => { fetchHot(); fetchRules() })
</script>
