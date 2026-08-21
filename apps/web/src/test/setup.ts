import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { apiClient } from '../api/client'

Object.defineProperty(window, 'scrollTo', { value: () => undefined, writable: true })
Object.defineProperty(HTMLElement.prototype, 'scrollTo', { value: () => undefined, writable: true })
Object.defineProperty(window, 'matchMedia', {
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
})

afterEach(() => apiClient.reset?.())
