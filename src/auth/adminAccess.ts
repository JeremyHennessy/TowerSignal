import { neonClient } from './client'

let generation = 0
let pending: Promise<boolean> | undefined

export function resetAdminAccess() {
  generation += 1
  pending = undefined
}

async function verifyAdminAccess(started: number): Promise<boolean> {
  // Cold authentication/data requests can briefly fail or return a negative
  // check. Keep pages in their checking state during this bounded recovery.
  for (const delay of [0, 300, 900]) {
    if (delay) await new Promise(resolve => setTimeout(resolve, delay))
    if (started !== generation) throw new Error('Your session changed. Please retry the access check.')
    let result
    try {
      result = await neonClient.rpc('towersignal_is_admin')
    } catch (error) {
      if (delay !== 900) continue
      throw error
    }
    if (started !== generation) throw new Error('Your session changed. Please retry the access check.')
    if (!result.error && result.data === true) return true
    if (delay !== 900) continue
    if (result.error) throw new Error('Unable to verify administrator access. Please retry.')
    if (result.data === false) return false
    throw new Error('Administrator verification returned no result. Please retry.')
  }
  throw new Error('Unable to verify administrator access. Please retry.')
}

export function loadAdminAccess(): Promise<boolean> {
  // Share only in-flight checks, never a remembered permission decision.
  if (!pending) {
    const request = verifyAdminAccess(generation).finally(() => {
      if (pending === request) pending = undefined
    })
    pending = request
  }
  return pending
}
