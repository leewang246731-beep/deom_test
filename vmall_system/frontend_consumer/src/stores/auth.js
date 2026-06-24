import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('vmall_token')||'')
  const user = ref(JSON.parse(localStorage.getItem('vmall_user')||'null'))
  const isLoggedIn = computed(() => !!token.value)
  function login(data) {
    token.value = data.access_token; user.value = data.user
    localStorage.setItem('vmall_token', data.access_token)
    localStorage.setItem('vmall_user', JSON.stringify(data.user))
  }
  function logout() { token.value=''; user.value=null; localStorage.removeItem('vmall_token'); localStorage.removeItem('vmall_user') }
  return { token, user, isLoggedIn, login, logout }
})
