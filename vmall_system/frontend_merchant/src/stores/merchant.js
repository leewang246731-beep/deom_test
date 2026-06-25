import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useMerchantStore = defineStore('merchant', () => {
  const token = ref(localStorage.getItem('merchant_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('merchant_user') || 'null'))
  const isLoggedIn = computed(() => !!token.value)

  function login(data) {
    token.value = data.access_token
    user.value = data.merchant
    localStorage.setItem('merchant_token', data.access_token)
    localStorage.setItem('merchant_user', JSON.stringify(data.merchant))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('merchant_token')
    localStorage.removeItem('merchant_user')
  }

  return { token, user, isLoggedIn, login, logout }
})
