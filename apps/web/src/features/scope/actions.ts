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

export type ScopeChangeRequest = {
  id: string
  scopeId: string
  requesterName: string
  requesterRole: string
  category: string
  requestedChanges: string
  status: string
  createdAt: string
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

export async function getScopeChangeRequestsAction(
  scopeId: string
): Promise<ScopeChangeRequest[]> {
  try {
    const baseUrl = getApiBaseUrl()
    const url = new URL(
      `/api/v1/scopes/${encodeURIComponent(scopeId)}/change-requests`,
      baseUrl
    )
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store"
    })
    if (!response.ok) return []
    const json = await response.json()
    if (!json || !Array.isArray(json.data)) return []
    return json.data.map((r: {
      id: string
      scope_id: string
      requester_name: string
      requester_role: string
      category: string
      requested_changes: string
      status: string
      created_at: string
    }) => ({
      id: r.id,
      scopeId: r.scope_id,
      requesterName: r.requester_name,
      requesterRole: r.requester_role,
      category: r.category,
      requestedChanges: r.requested_changes,
      status: r.status,
      createdAt: r.created_at
    }))
  } catch {
    return []
  }
}

export async function submitScopeChangeRequestAction(payload: {
  scopeId: string
  requesterName: string
  requesterRole: string
  category: string
  requestedChanges: string
}): Promise<{ success: boolean; changeRequest?: ScopeChangeRequest; message?: string }> {
  try {
    const baseUrl = getApiBaseUrl()
    const url = new URL(
      `/api/v1/scopes/${encodeURIComponent(payload.scopeId)}/change-requests`,
      baseUrl
    )
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify({
        requester_name: payload.requesterName,
        requester_role: payload.requesterRole,
        category: payload.category,
        requested_changes: payload.requestedChanges
      })
    })

    if (!response.ok) {
      return { success: false, message: "ثبت درخواست تغییر با خطا مواجه شد." }
    }

    const data = await response.json()
    return {
      success: true,
      changeRequest: {
        id: data.id,
        scopeId: data.scope_id,
        requesterName: data.requester_name,
        requesterRole: data.requester_role,
        category: data.category,
        requestedChanges: data.requested_changes,
        status: data.status,
        createdAt: data.created_at
      }
    }
  } catch {
    return { success: false, message: "ارتباط با سرور برقرار نشد." }
  }
}
