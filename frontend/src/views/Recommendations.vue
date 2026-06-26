<template>
  <div>
    <div style="margin-bottom:16px;display:flex;justify-content:space-between">
      <h3 style="margin:0">推荐管理</h3>
      <div style="display:flex;gap:8px">
        <el-button @click="handleRebuild" :loading="rebuilding">重建协同过滤</el-button>
        <el-button @click="handleAutoGenerate" :loading="autoGenLoading">自动生成规则</el-button>
        <el-button type="primary" @click="openAddRule">添加关联规则</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="热门商品" name="hot">
        <el-table :data="hot" border stripe v-loading="hotLoading">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="product.title" label="商品" min-width="200" show-overflow-tooltip />
          <el-table-column prop="product.price" label="价格" width="100"><template #default="{ row }">¥{{ row.product.price }}</template></el-table-column>
          <el-table-column prop="why" label="理由" min-width="160" />
          <el-table-column label="销量" width="80"><template #default="{ row }">{{ row.stats?.order_count }}</template></el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="关联规则" name="rules">
        <el-table :data="filteredRules" border stripe v-loading="rulesLoading">
          <el-table-column label="源商品" min-width="180">
            <template #default="{ row }">
              <span style="font-size:13px">{{ productTitles[row.product_id] || '#' + row.product_id }}</span>
            </template>
          </el-table-column>
          <el-table-column label="推荐商品" min-width="180">
            <template #default="{ row }">
              <span style="font-size:13px">{{ productTitles[row.recommended_product_id] || '#' + row.recommended_product_id }}</span>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.rule_type === 'auto' ? 'success' : ''">{{ ruleTypeLabel(row.rule_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="80" prop="priority" />
          <el-table-column label="启用" width="70">
            <template #default="{ row }">
              <el-switch v-model="row.is_active" :active-value="1" :inactive-value="0" size="small" @change="toggleActive(row)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button size="small" text @click="openEditRule(row)">编辑</el-button>
              <el-button size="small" text type="danger" @click="handleDeleteRule(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showRuleDialog" :title="isEdit ? '编辑规则' : '添加推荐关联'" width="450px">
      <el-form :model="ruleForm" label-width="100px">
        <el-form-item label="源商品ID"><el-input-number v-model="ruleForm.product_id" :min="1" :disabled="isEdit" style="width:100%" /></el-form-item>
        <el-form-item label="推荐商品ID"><el-input-number v-model="ruleForm.recommended_product_id" :min="1" :disabled="isEdit" style="width:100%" /></el-form-item>
        <el-form-item label="类型"><el-select v-model="ruleForm.rule_type" style="width:100%"><el-option label="手动关联" value="manual" /><el-option label="向上销售" value="upsell" /><el-option label="交叉销售" value="cross_sell" /></el-select></el-form-item>
        <el-form-item label="优先级"><el-input-number v-model="ruleForm.priority" :min="0" :max="100" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="ruleForm.is_active" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showRuleDialog=false">取消</el-button><el-button type="primary" @click="handleSaveRule">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getHotProducts, getRecommendationRules, createRecommendationRule, updateRecommendationRule, deleteRecommendationRule, autoGenerateRules, rebuildCoPurchase, getProducts } from '../api'
import { ElMessage } from 'element-plus'

const activeTab = ref('hot')
const hot = ref([]); const hotLoading = ref(false)
const rules = ref([]); const rulesLoading = ref(false)
const showRuleDialog = ref(false); const isEdit = ref(false)
const editRuleId = ref(null); const rebuilding = ref(false)
const autoGenLoading = ref(false)
const productTitles = ref({})

const ruleForm = reactive({ product_id: null, recommended_product_id: null, rule_type: 'manual', priority: 0, is_active: 1 })

const filteredRules = computed(() => rules.value)

function ruleTypeLabel(t) {
  const m = { manual: '手动', upsell: '向上', cross_sell: '交叉', auto: '自动' }
  return m[t] || t
}

async function fetchHot() { hotLoading.value = true; try { hot.value = (await getHotProducts({ top_k: 20 })).data?.recommendations || [] } catch { hot.value = [] } finally { hotLoading.value = false } }

async function fetchRules() {
  rulesLoading.value = true
  try { rules.value = (await getRecommendationRules()).data || [] } catch { rules.value = [] } finally { rulesLoading.value = false }
}

async function fetchProductTitles() {
  try {
    const ids = rules.value.flatMap(r => [r.product_id, r.recommended_product_id])
    if (!ids.length) return
    const res = await getProducts({ page: 1, page_size: 100 })
    for (const p of (res.data?.items || [])) { if (ids.includes(p.id)) productTitles.value[p.id] = p.title }
  } catch { /* non-critical */ }
}

function openAddRule() {
  isEdit.value = false; editRuleId.value = null
  Object.assign(ruleForm, { product_id: null, recommended_product_id: null, rule_type: 'manual', priority: 0, is_active: 1 })
  showRuleDialog.value = true
}

function openEditRule(row) {
  isEdit.value = true; editRuleId.value = row.id
  Object.assign(ruleForm, { product_id: row.product_id, recommended_product_id: row.recommended_product_id, rule_type: row.rule_type, priority: row.priority, is_active: row.is_active })
  showRuleDialog.value = true
}

async function handleSaveRule() {
  if (!ruleForm.product_id || !ruleForm.recommended_product_id) return ElMessage.warning('请选择商品和推荐商品')
  try {
    const data = { rule_type: ruleForm.rule_type, priority: ruleForm.priority, is_active: ruleForm.is_active }
    if (isEdit.value) { await updateRecommendationRule(editRuleId.value, data); ElMessage.success('规则已更新') }
    else { await createRecommendationRule({ ...ruleForm }); ElMessage.success('规则已添加') }
    showRuleDialog.value = false; fetchRules()
  } catch { /* error shown by interceptor */ }
}

async function toggleActive(row) {
  const prev = row.is_active
  try { await updateRecommendationRule(row.id, { is_active: row.is_active }) } catch { row.is_active = prev }
}

async function handleDeleteRule(id) {
  try { await deleteRecommendationRule(id); ElMessage.success('已删除'); fetchRules() } catch { /* error shown by interceptor */ }
}

async function handleRebuild() {
  rebuilding.value = true
  try { const r = await rebuildCoPurchase(); ElMessage.success(`重建完成: ${r?.data?.co_purchase_pairs || 0} 共购对`) } catch { /* error shown by interceptor */ } finally { rebuilding.value = false }
}

async function handleAutoGenerate() {
  autoGenLoading.value = true
  try { const r = await autoGenerateRules(20); ElMessage.success(r?.msg || '规则已生成'); fetchRules() } catch { /* error shown by interceptor */ } finally { autoGenLoading.value = false }
}

onMounted(async () => { await Promise.all([fetchHot(), fetchRules()]); fetchProductTitles() })
</script>
