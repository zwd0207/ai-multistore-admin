import { Fragment } from 'react';

export const TECHNICAL_REDACTED_VALUE = '[已隐藏]';

const SAFE_LABEL_HINTS = [
  'configured',
  'decryptable',
  'saved',
  'redacted',
  'masked',
  'hash',
  'safe_hash',
  'safe_keyword',
  'count',
  'total',
  'amount',
  'status',
  'label',
  'flag',
  'available',
  'requested',
  'enabled',
  'open',
  'allowed',
  'phase',
  'version',
  'scope',
  'path_kind',
  'http_status',
  'error_code',
  'business_error_hint',
  'mapping_version',
  'source_phase',
  'dedupe_key',
  'store_id',
  'credential_id',
  'real_preview',
  'real_sync',
  'backup_sha256',
  'backup_path',
];

const SENSITIVE_LABEL_PATTERNS = [
  /(^|[._-])token($|[._-])/i,
  /access[._-]?token/i,
  /refresh[._-]?token/i,
  /authorization/i,
  /(^|[._-])headers?($|[._-])/i,
  /signature/i,
  /bcrypt/i,
  /client[._-]?secret/i,
  /(^|[._-])secret($|[._-])/i,
  /password/i,
  /raw[._-]?response/i,
  /(^|[._-])raw[._-]?data($|[._-])/i,
  /request[._-]?body/i,
  /response[._-]?body/i,
  /channel[._-]?no/i,
  /product[._-]?order[._-]?id/i,
  /(^|[._-])order[._-]?id($|[._-])/i,
  /external[._-]?product[._-]?id/i,
  /buyer[._-]?name/i,
  /buyer[._-]?phone/i,
  /receiver[._-]?name/i,
  /receiver[._-]?phone/i,
  /(^|[._-])phone($|[._-])/i,
  /(^|[._-])address($|[._-])/i,
  /detailed[._-]?address/i,
  /zip[._-]?code/i,
];

const SENSITIVE_VALUE_PATTERNS = [
  /^bearer\s+[a-z0-9._~+/=-]+$/i,
  /^basic\s+[a-z0-9+/=-]+$/i,
  /^eyJ[a-z0-9_-]+\.[a-z0-9_-]+\.[a-z0-9_-]+$/i,
  /authorization\s*[:=]/i,
  /access[_-]?token\s*[:=]/i,
  /refresh[_-]?token\s*[:=]/i,
  /client[_-]?secret\s*[:=]/i,
  /signature\s*[:=]/i,
  /bcrypt\s*[:=]/i,
  /raw[_-]?response\s*[:=]/i,
  /^\+?\d[\d\s().-]{8,}\d$/,
];

function normalizeLabel(label) {
  return String(label || '').trim();
}

function isSafeLabel(label) {
  const normalized = normalizeLabel(label).toLowerCase();
  return SAFE_LABEL_HINTS.some((hint) => normalized.includes(hint));
}

function isSensitiveLabel(label) {
  const normalized = normalizeLabel(label);
  if (!normalized || isSafeLabel(normalized)) return false;
  return SENSITIVE_LABEL_PATTERNS.some((pattern) => pattern.test(normalized));
}

function isOpaqueSecretLike(value) {
  const text = String(value || '').trim();
  if (text.length < 48) return false;
  if (/\s/.test(text)) return false;
  return /^[A-Za-z0-9._~+/=-]+$/.test(text);
}

function isSensitiveValue(value) {
  if (typeof value !== 'string') return false;
  const text = value.trim();
  if (!text) return false;
  if (SENSITIVE_VALUE_PATTERNS.some((pattern) => pattern.test(text))) return true;
  if (isOpaqueSecretLike(text)) return true;
  return false;
}

function containsRedaction(value) {
  if (value === TECHNICAL_REDACTED_VALUE) return true;
  if (Array.isArray(value)) return value.some((item) => containsRedaction(item));
  if (value && typeof value === 'object') {
    return Object.values(value).some((item) => containsRedaction(item));
  }
  return false;
}

export function redactTechnicalValue(label, value, seen = new WeakSet()) {
  if (isSensitiveLabel(label)) return TECHNICAL_REDACTED_VALUE;
  if (isSensitiveValue(value)) return TECHNICAL_REDACTED_VALUE;
  if (Array.isArray(value)) {
    return value.map((item, index) => redactTechnicalValue(`${label}.${index}`, item, seen));
  }
  if (value && typeof value === 'object') {
    return redactTechnicalObject(value, seen);
  }
  return value;
}

export function redactTechnicalObject(value, seen = new WeakSet()) {
  if (!value || typeof value !== 'object') return redactTechnicalValue('', value, seen);
  if (seen.has(value)) return '[循环引用已隐藏]';
  seen.add(value);
  if (Array.isArray(value)) {
    return value.map((item, index) => redactTechnicalValue(String(index), item, seen));
  }
  return Object.entries(value).reduce((acc, [key, itemValue]) => {
    acc[key] = redactTechnicalValue(key, itemValue, seen);
    return acc;
  }, {});
}

function formatValue(value) {
  if (value === null || value === undefined) return '-';
  if (Array.isArray(value)) return value.length ? value.join(', ') : '-';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

export default function TechnicalDetails({ title = '查看技术详情', description, items = [], children, redactionMode = 'strict' }) {
  const safeItems = items
    .filter((item) => item && item.label)
    .map((item) => ({
      ...item,
      value: redactionMode === 'off' ? item.value : redactTechnicalValue(item.label, item.value),
    }));
  const redactedCount = safeItems.filter((item) => containsRedaction(item.value)).length;

  return (
    <details className="developer-details technical-details">
      <summary>{title}</summary>
      {description ? <p>{description}</p> : null}
      {redactedCount ? <p>部分高级字段因包含敏感信息已隐藏。</p> : null}
      {safeItems.length ? (
        <div className="sync-result-grid">
          {safeItems.map((item) => (
            <Fragment key={item.label}>
              <span>{item.label}</span>
              <strong>{formatValue(item.value)}</strong>
            </Fragment>
          ))}
        </div>
      ) : null}
      {children}
    </details>
  );
}
