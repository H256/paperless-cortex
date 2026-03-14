/* @vitest-environment jsdom */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import MaintenanceRuntimeSection from './MaintenanceRuntimeSection.vue'

describe('MaintenanceRuntimeSection', () => {
  it('renders runtime values and emits worker lock actions', async () => {
    const wrapper = mount(MaintenanceRuntimeSection, {
      props: {
        runtime: {
          paperless_base_url: 'http://paperless.local',
          llm_base_url: 'http://llm.local',
          qdrant_url: 'http://qdrant.local',
          redis_host: 'redis.local',
          text_model: 'gpt-test',
          chat_model: 'gpt-chat-test',
          embedding_model: 'embed-test',
          vision_model: 'vision-test',
          evidence_max_pages: 3,
          evidence_min_snippet_chars: 20,
        },
        copiedKey: null,
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
    expect(wrapper.text()).toContain('http://paperless.local')
    expect(wrapper.text()).toContain('gpt-chat-test')

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
