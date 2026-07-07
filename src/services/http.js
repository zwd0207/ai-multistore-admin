const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000/api/v1';
const configuredApiBaseUrl = (import.meta.env?.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/+$/, '');
const shouldUseLocalDevProxy = import.meta.env?.DEV
  && /^https?:\/\/(?:127\.0\.0\.1|localhost):8012\/api\/v1$/i.test(configuredApiBaseUrl);
const API_BASE_URL = shouldUseLocalDevProxy ? '/api/v1' : configuredApiBaseUrl;
const SENSITIVE_KEY_PATTERN = /(?:access[_-]?key|secret[_-]?key|password|token|credential|proxy[_-]?password|remote[_-]?desktop[_-]?password)/i;

function businessHttpMessage(status) {
  if (status === 401 || status === 403) {
    return '当前店铺连接或访问权限需要检查，请联系管理员确认平台连接资料。';
  }
  if (status === 404) {
    return '当前功能暂时不可用，请稍后再试或联系管理员确认系统配置。';
  }
  if (status >= 500) {
    return '本地服务暂时不可用，请确认系统服务已启动后再刷新页面。';
  }
  return '请求暂时没有成功，请稍后重试。';
}

function sanitizeForError(value) {
  if (Array.isArray(value)) return value.map(sanitizeForError);
  if (!value || typeof value !== 'object') return value;

  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      SENSITIVE_KEY_PATTERN.test(key) ? '[已隐藏]' : sanitizeForError(item),
    ]),
  );
}

function buildUrl(path, params) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const url = new URL(
    `${API_BASE_URL}${normalizedPath}`,
    typeof window === 'undefined' ? 'http://127.0.0.1' : window.location.origin,
  );

  Object.entries(params || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (Array.isArray(value)) {
      value.forEach((item) => url.searchParams.append(key, String(item)));
      return;
    }
    url.searchParams.set(key, String(value));
  });

  return url.toString();
}

async function request(path, options = {}) {
  const { params, timeout = 10000, headers, body, ...fetchOptions } = options;
  const token = typeof localStorage === 'undefined' ? null : localStorage.getItem('access_token');
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(buildUrl(path, params), {
      ...fetchOptions,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      body: body !== undefined && typeof body !== 'string' ? JSON.stringify(body) : body,
      signal: options.signal || controller.signal,
    });

    let result = null;
    try {
      result = await response.json();
    } catch {
      result = null;
    }

    if (!response.ok) {
      const error = new Error(result?.message || businessHttpMessage(response.status));
      error.name = 'HttpError';
      error.status = response.status;
      error.errorCode = result?.error_code || 'HTTP_ERROR';
      error.data = sanitizeForError(result);
      throw error;
    }

    return result;
  } catch (error) {
    if (error.name === 'AbortError') {
      const timeoutError = new Error('系统服务响应较慢，请稍后刷新，或确认本地服务已经启动。');
      timeoutError.name = 'HttpError';
      timeoutError.status = 0;
      timeoutError.errorCode = 'REQUEST_TIMEOUT';
      throw timeoutError;
    }
    if (error.name === 'HttpError') throw error;

    const networkError = new Error('本地服务暂时连接不上，请确认系统服务已启动后再刷新页面。');
    networkError.name = 'HttpError';
    networkError.status = 0;
    networkError.errorCode = 'NETWORK_ERROR';
    throw networkError;
  } finally {
    clearTimeout(timeoutId);
  }
}

export const http = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  delete: (path, options) => request(path, { ...options, method: 'DELETE' }),
};

export { API_BASE_URL, DEFAULT_API_BASE_URL, buildUrl, sanitizeForError };
export default http;
