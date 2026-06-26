<template>
  <div>
    <div style="margin-bottom:16px;display:flex;justify-content:space-between">
      <h3 style="margin:0">AI 话术风格配置</h3>
      <el-button type="primary" @click="openAdd">新建风格</el-button>
    </div>
    <el-row :gutter="16">
      <el-col :span="8" v-for="s in styles" :key="s.id">
        <el-card :style="{border: s.is_default ? '2px solid #409eff' : ''}">
          <template #header>
            <span style="font-weight:bold">{{ s.name }}</span>
            <el-tag v-if="s.is_default" type="primary" size="small" effect="dark" style="margin-left:8px">默认</el-tag>
            <span style="float:right;font-size:12px;color:#909399">{{ s.style_key }}</span>
          </template>
          <p style="font-size:13px;margin:4px 0">语气: {{ s.tone || '-' }}</p>
          <p style="font-size:13px;margin:4px 0">开场: {{ (s.greeting || '-').slice(0, 30) }}{{ (s.greeting || '').length > 30 ? '...' : '' }}</p>
          <p style="font-size:12px;color:#909399;margin:4px 0">{{ fmtFeatures(s.features) }}</p>
          <div style="margin-top:8px;display:flex;gap:6px">
            <el-button size="small" @click="setDefault(s.id)" v-if="!s.is_default">设为默认</el-button>
            <el-button size="small" plain @click="openEdit(s)">编辑</el-button>
            <el-button size="small" type="danger" text @click="handleDelete(s)" :disabled="s.style_key !== 'custom'">删除</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showDialog" title="话术风格" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="语气标签"><el-input v-model="form.tone" placeholder="例：亲切、活泼" /></el-form-item>
        <el-form-item label="开场问候语"><el-input v-model="form.greeting" placeholder="例：亲，您好呀～" /></el-form-item>
        <el-form-item label="回答长度">
          <el-radio-group v-model="form.features.长度"><el-radio value="简洁">简洁</el-radio><el-radio value="适中">适中</el-radio><el-radio value="详细">详细</el-radio></el-radio-group>
        </el-form-item>
        <el-form-item label="表情使用">
          <el-radio-group v-model="form.features.表情"><el-radio value="少量">少量</el-radio><el-radio value="适量">适量</el-radio><el-radio value="丰富">丰富</el-radio></el-radio-group>
        </el-form-item>
        <el-form-item label="促单强度">
          <el-radio-group v-model="form.features.促单"><el-radio value="温和">温和</el-radio><el-radio value="适中">适中</el-radio><el-radio value="积极">积极</el-radio></el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getAIStyles, createAIStyle, updateAIStyle, deleteAIStyle, setDefaultStyle } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const styles = ref([])
const showDialog = ref(false)
const editId = ref(null)
const form = reactive({ name: '', tone: '', greeting: '', features: { '长度': '适中', '表情': '适量', '促单': '温和' } })

async function fetch() { try { const r = await getAIStyles(); styles.value = r.data || [] } catch { styles.value = [] } }
function fmtFeatures(f) { if (!f) return '{}'; try { return JSON.stringify(f) } catch { return String(f) } }

function openAdd() { editId.value = null; Object.assign(form, { name: '', tone: '', greeting: '', features: { '长度': '适中', '表情': '适量', '促单': '温和' } }); showDialog.value = true }

function openEdit(s) { editId.value = s.id; Object.assign(form, { name: s.name, tone: s.tone || '', greeting: s.greeting || '', features: s.features || {} }); showDialog.value = true }

async function handleSave() {
  if (!form.name.trim()) return ElMessage.warning('请输入风格名称')
  try {
    if (editId.value) { await updateAIStyle(editId.value, { ...form, style_key: 'custom' }) } else { await createAIStyle({ ...form, style_key: 'custom' }) }
    ElMessage.success('已保存'); showDialog.value = false; fetch()
  } catch { /* error shown by interceptor */ }
}

async function setDefault(id) {
  try { await setDefaultStyle(id); ElMessage.success('已设为默认'); fetch() } catch { /* error shown by interceptor */ }
}

async function handleDelete(s) {
  try { await ElMessageBox.confirm('确定删除该AI风格？', '提示', { type: 'warning' }) } catch { return }
  try { await deleteAIStyle(s.id); ElMessage.success('已删除'); fetch() } catch { /* error shown by interceptor */ }
}

onMounted(fetch)
</script>
