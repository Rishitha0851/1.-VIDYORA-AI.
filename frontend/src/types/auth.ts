/**
 * VIDYORA AI - Authentication Types & Interfaces
 */

export interface User {
  id: string
  email: string
  username?: string | null
  full_name?: string | null
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in?: number
  user: User
}

export interface UserLoginRequest {
  email: string
  password: string
}

export interface UserRegisterRequest {
  email: string
  password: string
  full_name?: string
  username?: string
}
