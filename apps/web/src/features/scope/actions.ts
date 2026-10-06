"use server"

import { getApiBaseUrl } from "../auth/config"

export type ScopeSignature = {
  id: string
  scopeId: string
  signerName: string
  signerRole: string
  organization?: string | null
  verificationCode: string
  signedAt: string
}

export async function getScopeSignatureAction(scopeId: string): Promise<ScopeSignature | null> {
  try {
    const baseUrl = getApiBaseUrl()
    const url = new URL(`/api/v1/scopes/${encodeURIComponent(scopeId)}/signature`, baseUrl)
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store"
    })
    if (!response.ok) return null
    const data = await response.json()
    if (!data) return null
    return {
      id: data.id,
      scopeId: data.scope_id,
      signerName: data.signer_name,
      signerRole: data.signer_role,
      organization: data.organization,
      verificationCode: data.verification_code,
      signedAt: data.signed_at
    }
  } catch {
    return null
  }
}

export async function signScopeAction(payload: {
  scopeId: string
  signerName: string
  signerRole: string
  organization?: string
}): Promise<{ success: boolean; signature?: ScopeSignature; message?: string }> {
  try {
    const baseUrl = getApiBaseUrl()
    const url = new URL(`/api/v1/scopes/${encodeURIComponent(payload.scopeId)}/sign`, baseUrl)
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify({
        signer_name: payload.signerName,
        signer_role: payload.signerRole,
        organization: payload.organization || null
      })
    })

    if (!response.ok) {
      return { success: false, message: "ثبت امضا در سرور با خطا مواجه شد." }
    }

    const data = await response.json()
    return {
      success: true,
      signature: {
        id: data.id,
        scopeId: data.scope_id,
        signerName: data.signer_name,
        signerRole: data.signer_role,
        organization: data.organization,
        verificationCode: data.verification_code,
        signedAt: data.signed_at
      }
    }
  } catch {
    return { success: false, message: "ارتباط با سرور برقرار نشد." }
  }
}
