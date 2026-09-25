import { createClient } from '@neondatabase/neon-js'

// Sign-in and every private workspace must use the same authentication client.
export const neonClient = createClient({
  auth: { url: import.meta.env.VITE_NEON_AUTH_URL || 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth' },
  dataApi: {
    url: import.meta.env.VITE_NEON_DATA_API_URL || 'https://ep-silent-moon-au2icaki.apirest.c-10.us-east-1.aws.neon.tech/neondb/rest/v1',
    options: { global: { fetch: (input, init) => fetch(input, { ...init, cache: 'no-store' }) } },
  },
})
