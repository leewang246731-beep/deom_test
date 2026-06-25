<template>
  <div>
    <div style="margin-bottom:16px;display:flex;justify-content:space-between">
      <h3 style="margin:0">技能组管理</h3>
      <el-button type="primary" @click="openAddGroup">新建技能组</el-button>
    </div>

    <el-row :gutter="16" v-loading="loading">
      <el-col :span="8" v-for="g in groups" :key="g.id">
        <el-card>
          <template #header>
            <span style="font-weight:bold">{{ g.name }}</span>
            <el-tag v-if="!g.is_active" type="info" size="small" style="margin-left:8px">停用</el-tag>
            <span style="float:right">
              <el-button size="small" text @click="openEditGroup(g)">编辑</el-button>
              <el-button size="small" text type="danger" @click="handleDeleteGroup(g.id)">删除</el-button>
            </span>
          </template>
          <p style="font-size:12px;color:#909399;margin:0 0 8px">{{ g.description || '无描述' }}</p>
          <el-tag v-for="m in g.members" :key="m.user_id" style="margin:2px" closable @close="handleRemoveMember(g.id, m.user_id)">
            {{ m.display_name || '用户'+m.user_id }}
            <span v-if="m.skill_tags?.length" style="color:#909399"> · {{ m.skill_tags.join(' ') }}</span>
            <span style="color:#e6a23c"> ({{ m.current_load }}单)</span>
          </el-tag>
          <el-button size="small" style="margin-top:8px;width:100%" @click="openAddMember(g)">+ 添加成员</el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- Group Dialog -->
    <el-dialog v-model="showGroupDialog" title="技能组" width="400px">
      <el-form :model="groupForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="groupForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="groupForm.description" type="textarea" /></el-form-item>
        <el-form-item label="状态"><el-switch v-model="groupForm.is_active" active-text="启用" inactive-text="停用" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showGroupDialog=false">取消</el-button><el-button type="primary" @click="handleSaveGroup">保存</el-button></template>
    </el-dialog>

    <!-- Member Dialog -->
    <el-dialog v-model="showMemberDialog" title="添加成员" width="450px">
      <el-form :model="memberForm" label-width="80px">
        <el-form-item label="客服">
          <el-select v-model="memberForm.user_id" placeholder="选择客服" style="width:100%" filterable>
            <el-option v-for="u in userOptions" :key="u.id" :label="u.label" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="技能标签">
          <el-select v-model="memberForm.skill_tags" multiple filterable allow-create placeholder="输入标签后回车" style="width:100%">
            <el-option label="精通3C数码" value="精通3C数码" />
            <el-option label="擅长安抚情绪" value="擅长安抚情绪" />
            <el-option label="熟悉售后流程" value="熟悉售后流程" />
            <el-option label="熟悉各家快递" value="熟悉各家快递" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="showMemberDialog=false">取消</el-button><el-button type="primary" @click="handleAddMember">添加</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getSkillGroups, createSkillGroup, updateSkillGroup, deleteSkillGroup, addSkillMember, removeSkillMember } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const groups = ref([]); const userOptions = ref([]); const loading = ref(false)
const showGroupDialog = ref(false); const showMemberDialog = ref(false)
const editGroupId = ref(null); const addMemberGid = ref(null)

const groupForm = reactive({ name: '', description: '', is_active: true })
const memberForm = reactive({ user_id: null, skill_tags: [] })

async function fetch() {
  loading.value = true
  try { groups.value = (await getSkillGroups()).data || [] } catch { /* */ }
  finally { loading.value = false }
}

function openAddGroup() { editGroupId.value = null; Object.assign(groupForm, { name: '', description: '', is_active: true }); showGroupDialog.value = true }
function openEditGroup(g) { editGroupId.value = g.id; Object.assign(groupForm, { name: g.name, description: g.description || '', is_active: !!g.is_active }); showGroupDialog.value = true }

async function handleSaveGroup() {
  if (!groupForm.name.trim()) return ElMessage.warning('请输入名称')
  const data = { name: groupForm.name, description: groupForm.description, is_active: groupForm.is_active ? 1 : 0 }
  if (editGroupId.value) { await updateSkillGroup(editGroupId.value, data) } else { await createSkillGroup(data) }
  ElMessage.success('已保存'); showGroupDialog.value = false; fetch()
}

async function handleDeleteGroup(id) {
  await ElMessageBox.confirm('确定删除？', '提示', { type: 'warning' })
  try { await deleteSkillGroup(id); ElMessage.success('已删除'); fetch() } catch { /* */ }
}

function openAddMember(g) { addMemberGid.value = g.id; Object.assign(memberForm, { user_id: null, skill_tags: [] }); showMemberDialog.value = true }

async function handleAddMember() {
  if (!memberForm.user_id) return ElMessage.warning('请选择客服')
  await addSkillMember(addMemberGid.value, memberForm)
  ElMessage.success('已添加'); showMemberDialog.value = false; fetch()
}

async function handleRemoveMember(gid, uid) { await removeSkillMember(gid, uid); ElMessage.success('已移除'); fetch() }

onMounted(async () => {
  fetch()
  // Get all users for member picker (via shop API or skill groups)
  try { const g = await getSkillGroups(); const users = new Map(); (g.data||[]).forEach(grp => (grp.members||[]).forEach(m => users.set(m.user_id, {id:m.user_id, label:m.display_name||'User '+m.user_id}))); userOptions.value = [...users.values()] } catch { /* */ }
})
</script>
