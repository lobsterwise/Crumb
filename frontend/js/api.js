const request = async (path, options = {}) => {
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
  });
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(data?.error || `Request failed (${response.status}).`);
  return data;
};
const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) });
const put = (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body) });
export const api = {
  subjects: () => request('/api/subjects'),
  lessons: (query = {}) => request(`/api/lessons?${new URLSearchParams(query)}`),
  lesson: id => request(`/api/lessons/${encodeURIComponent(id)}`),
  randomLesson: () => request('/api/lessons/random'),
  generate: prompt => post('/api/lessons/generate', { prompt }),
  generateRandom: () => post('/api/lessons/generate', { randomTopic: true }),
  progress: () => request('/api/progress'),
  me: () => request('/api/me'),
  preferences: () => request('/api/preferences'),
  savePreferences: data => put('/api/preferences', data),
  complete: lessonId => post('/api/completions', { lessonId }),
  register: data => post('/api/register', data),
  login: data => post('/api/login', data),
  logout: () => post('/api/logout', {}),
};
