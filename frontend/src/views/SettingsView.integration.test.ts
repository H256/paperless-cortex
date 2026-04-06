// @vitest-environment jsdom
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const toastPush = vi.fn()
const fetchModelProviderSettings = vi.fn()
const updateModelProviderSettings = vi.fn()
const discoverProviderModels = vi.fn()
const fetchHealthStatus = vi.fn()

vi.mock('../stores/toastStore', () => ({
  useToastStore: () => ({
    push: toastPush,
  }),
}))

vi.mock('../services/settings', () => ({
  fetchModelProviderSettings,
  updateModelProviderSettings,
  discoverProviderModels,
}))

vi.mock('../services/status', () => ({
  fetchHealthStatus,
}))

const flush = async () => {
  await Promise.resolve()
  await Promise.resolve()
}

describe('SettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn(async () => undefined) },
      configurable: true,
    })
    fetchModelProviderSettings.mockResolvedValue({
      items: [
        {
          role: 'text',
          base_url: 'http://text.local',
          model: 'text-default',
          api_key_configured: false,
          api_key_hint: null,
          base_url_overridden: false,
          model_overridden: false,
          api_key_overridden: false,
        },
        {
          role: 'chat',
          base_url: 'http://chat.local',
          model: 'chat-default',
          api_key_configured: true,
          api_key_hint: '...chat',
          base_url_overridden: true,
          model_overridden: true,
          api_key_overridden: true,
        },
        {
          role: 'embedding',
          base_url: 'http://embed.local',
          model: 'embed-default',
          api_key_configured: false,
          api_key_hint: null,
          base_url_overridden: false,
          model_overridden: false,
          api_key_overridden: false,
        },
        {
          role: 'vision',
          base_url: 'http://vision.local',
          model: 'vision-default',
          api_key_configured: false,
          api_key_hint: null,
          base_url_overridden: false,
          model_overridden: false,
          api_key_overridden: false,
        },
      ],
    })
    fetchHealthStatus.mockResolvedValue({
      paperless_base_url: 'http://paperless.local',
      text_base_url: 'http://text.local',
      chat_base_url: 'http://chat.local',
      embedding_base_url: 'http://embed.local',
      vision_base_url: 'http://vision.local',
      qdrant_url: 'http://qdrant.local',
      vector_store_provider: 'weaviate',
      vector_store_url: 'http://weaviate.local',
      redis_host: 'redis.local',
      text_model: 'text-default',
      chat_model: 'chat-default',
      embedding_model: 'embed-default',
      vision_model: 'vision-default',
      evidence_max_pages: 3,
      evidence_min_snippet_chars: 20,
    })
    discoverProviderModels.mockResolvedValue({
      ok: true,
      detail: 'ok',
      models: ['text-default', 'text-live'],
    })
    updateModelProviderSettings.mockResolvedValue({ items: [] })
  })

  it('renders runtime config and saves changed model provider settings', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    const SettingsView = (await import('./SettingsView.vue')).default
    const wrapper = mount(SettingsView, {
      global: {
        plugins: [[VueQueryPlugin, { queryClient }]],
      },
    })

    await flush()

    expect(wrapper.text()).toContain('Runtime Configuration')
    expect(wrapper.text()).toContain('Text model')
    expect(wrapper.text()).toContain('Chat model')

    const refreshButtons = wrapper.findAll('button').filter((button) => button.text() === 'Refresh models')
    const firstRefresh = refreshButtons[0]
    if (!firstRefresh) {
      throw new Error('Expected refresh models button')
    }
    await firstRefresh.trigger('click')
    await flush()

    expect(discoverProviderModels).toHaveBeenCalledWith({
      base_url: 'http://text.local',
      api_key: null,
    })
    expect(wrapper.text()).toContain('2 models loaded')

    const modelInputs = wrapper
      .findAll('input')
      .filter((input) => input.attributes('placeholder') === 'Choose or type a model')
    const firstModelInput = modelInputs[0]
    if (!firstModelInput) {
      throw new Error('Expected model input')
    }
    await firstModelInput.setValue('text-live')
    await flush()

    const saveButton = wrapper.findAll('button').find((button) => button.text().includes('Save changes'))
    if (!saveButton) {
      throw new Error('Expected save button')
    }
    await saveButton.trigger('click')
    await flush()

    expect(updateModelProviderSettings).toHaveBeenCalledWith([
      {
        role: 'text',
        base_url: 'http://text.local',
        model: 'text-live',
        api_key: null,
        clear_api_key: false,
      },
    ])
    expect(toastPush).not.toHaveBeenCalledWith(expect.stringContaining('Failed'), 'danger', 'Error')
  })
})
