/* @vitest-environment jsdom */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import MaintenanceRuntimeSection from './MaintenanceRuntimeSection.vue'

describe('MaintenanceRuntimeSection', () => {
  it('renders worker lock values and emits worker lock actions', async () => {
    const wrapper = mount(MaintenanceRuntimeSection, {
      props: {
        workerLockStatus: {
          enabled: true,
          has_lock: true,
          owner: 'worker-a',
          ttl_seconds: 42,
        },
        workerLockLoading: false,
        workerLockResetLoading: false,
        workerLockStatusTtlLabel: '42s',
        workerLockResetResult: null,
      },
    })

    expect(wrapper.text()).toContain('Worker lock')
    expect(wrapper.text()).toContain('worker-a')
    expect(wrapper.text()).not.toContain('Runtime Configuration')

    const buttons = wrapper.findAll('button')
    const refreshButton = buttons.find((button) => button.text().includes('Refresh lock status'))
    const resetButton = buttons.find((button) => button.text().includes('Reset worker lock'))

    if (!refreshButton || !resetButton) {
      throw new Error('Expected worker lock action buttons')
    }

    await refreshButton.trigger('click')
    await resetButton.trigger('click')

    expect(wrapper.emitted('refresh-lock')).toHaveLength(1)
    expect(wrapper.emitted('reset-lock')).toHaveLength(1)
  })
})
