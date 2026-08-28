import { apiGet, apiPost } from "./client";
import type { TokenResponse, User, UserCreate, UserLogin } from "@/types/auth";

export async function registerUser(payload: UserCreate): Promise<User> {
  return apiPost<User>("/auth/register", payload);
}

export async function loginUser(payload: UserLogin): Promise<TokenResponse> {
  return apiPost<TokenResponse>("/auth/login", payload);
}

export async function getCurrentUser(token: string): Promise<User> {
  return apiGet<User>("/auth/me", token);
}
