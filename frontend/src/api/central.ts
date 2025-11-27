import { http } from './client'

export const Auth = {
  login: (username: string, password: string) =>
    http<{ access_token: string; token_type: string }>('/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    }),
}

export const Models = {
  current: () => http('/models/current'),
  list: () => http('/models'),
  promote: (model_id: string) => http('/models/promote?model_id=' + encodeURIComponent(model_id), { method: 'POST' }),
}

export const Rounds = {
  list: () => http('/rounds'),
  get: (id: string) => http(`/rounds/${id}`),
  aggregate: (id: string) => http(`/rounds/${id}/aggregate`, { method: 'POST' }),
  eventsURL: () => `/v1/events`
}
