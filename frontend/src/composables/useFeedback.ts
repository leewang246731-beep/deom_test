/**
 * useFeedback — Unified user feedback (success/error/confirm)
 *
 * Replaces direct ElMessage/ElMessageBox calls.
 * Usage:
 *   const { showSuccess, showError, showConfirm } = useFeedback()
 *   showSuccess('保存成功')
 *   await showConfirm('确定删除？')
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { MessageBoxData } from 'element-plus'

export function useFeedback() {
  function showSuccess(msg: string) {
    ElMessage.success(msg)
  }

  function showError(msg: string) {
    ElMessage.error(msg)
  }

  function showWarning(msg: string) {
    ElMessage.warning(msg)
  }

  function showInfo(msg: string) {
    ElMessage.info(msg)
  }

  async function showConfirm(
    msg: string,
    title = '确认操作',
    opts?: { confirmText?: string; cancelText?: string; type?: 'warning' | 'info' | 'danger' }
  ): Promise<boolean> {
    try {
      await ElMessageBox.confirm(msg, title, {
        confirmButtonText: opts?.confirmText || '确定',
        cancelButtonText: opts?.cancelText || '取消',
        type: opts?.type || 'warning',
      })
      return true
    } catch {
      return false
    }
  }

  async function showPrompt(
    msg: string,
    title = '请输入',
    defaultValue = ''
  ): Promise<string | null> {
    try {
      const { value } = await ElMessageBox.prompt(msg, title, {
        inputValue: defaultValue,
      })
      return value || null
    } catch {
      return null
    }
  }

  return { showSuccess, showError, showWarning, showInfo, showConfirm, showPrompt }
}
