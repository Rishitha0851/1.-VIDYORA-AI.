/**
 * VIDYORA AI - Authentication API & Session Management Service
 * 
 * Manages JWT tokens, authorization headers, login, registration,
 * and current user retrieval.
 */

import type {
  TokenResponse,
  User,
  UserLoginRequest,
  UserRegisterRequest,
} from '../types/auth'

const defaultUrl = import.meta.env.PROD
  ? 'https://vidyora-ai-backend.onrender.com'
  : 'http://127.0.0.1:8000'

const rawEnvUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim().replace(/\/+$/, '')

export const API_BASE_URL = rawEnvUrl || defaultUrl
const BASE_URL = API_BASE_URL
const AUTH_TOKEN_KEY = 'vidyora_auth_token'

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY)
  } catch {
    return null
  }
}

export function setAuthToken(token: string): void {
  try {
    localStorage.setItem(AUTH_TOKEN_KEY, token)
  } catch {
    // LocalStorage might be restricted
  }
}

export function clearAuthToken(): void {
  try {
    localStorage.removeItem(AUTH_TOKEN_KEY)
  } catch {
    // LocalStorage might be restricted
  }
}

export function getAuthHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const token = getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

async function handleAuthResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorDetail = `Request failed with HTTP ${response.status}`
    try {
      const errJson = await response.json()
      if (errJson.detail) {
        if (typeof errJson.detail === 'string') {
          errorDetail = errJson.detail
        } else if (Array.isArray(errJson.detail)) {
          errorDetail = errJson.detail.map((d: { msg?: string }) => d.msg || 'Validation error').join(', ')
        } else {
          errorDetail = JSON.stringify(errJson.detail)
        }
      }
    } catch {
      // Fallback
    }

    if (response.status === 401) {
      clearAuthToken()
    }
    throw new Error(errorDetail)
  }
  return response.json()
}

/**
 * Registers a new learner account.
 */
export async function registerApi(payload: UserRegisterRequest): Promise<TokenResponse> {
  const response = await fetch(`${BASE_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const tokenData = await handleAuthResponse<TokenResponse>(response)
  if (tokenData.access_token) {
    setAuthToken(tokenData.access_token)
  }
  return tokenData
}

/**
 * Authenticates user credentials and retrieves JWT access token.
 */
export async function loginApi(credentials: UserLoginRequest): Promise<TokenResponse> {
  const response = await fetch(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })
  const tokenData = await handleAuthResponse<TokenResponse>(response)
  if (tokenData.access_token) {
    setAuthToken(tokenData.access_token)
  }
  return tokenData
}

/**
 * Retrieves the currently authenticated user's profile.
 */
export async function getCurrentUserApi(): Promise<User> {
  const token = getAuthToken()
  if (!token) {
    throw new Error('No authentication token found.')
  }
  const response = await fetch(`${BASE_URL}/api/auth/me`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })
  return handleAuthResponse<User>(response)
}
