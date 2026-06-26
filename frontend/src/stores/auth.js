import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const platformToken = ref(localStorage.getItem('platform_token') || '')
  const platformUser = ref(JSON.parse(localStorage.getItem('platform_user') || 'null'))

  const isLoggedIn = computed(() => !!token.value || !!platformToken.value)

  // 商户端登录
  function login(data) {
    token.value = data.access_token
    user.value = data.user
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token)
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('refresh_token')
  }

  // 平台端登录
  function loginPlatform(data) {
    platformToken.value = data.access_token
    platformUser.value = data.user
    localStorage.setItem('platform_token', data.access_token)
    localStorage.setItem('platform_user', JSON.stringify(data.user))
  }

  function logoutPlatform() {
    platformToken.value = ''
    platformUser.value = null
    localStorage.removeItem('platform_token')
    localStorage.removeItem('platform_user')
  }

  return { token, user, platformToken, platformUser, isLoggedIn, login, logout, loginPlatform, logoutPlatform }
})
