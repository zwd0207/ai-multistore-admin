export const BUSINESS_TIME_ZONE = 'Asia/Seoul';
export const BUSINESS_TIME_LABEL = 'KST';

const DATE_PARTS_FORMATTER = new Intl.DateTimeFormat('en-CA', {
  timeZone: BUSINESS_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

const DATE_TIME_PARTS_FORMATTER = new Intl.DateTimeFormat('en-CA', {
  timeZone: BUSINESS_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

const LOCAL_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const LOCAL_DATE_TIME_RE = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/;
const HAS_EXPLICIT_ZONE_RE = /(?:z|[+-]\d{2}:?\d{2})$/i;

function partsToMap(parts) {
  return Object.fromEntries(parts.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]));
}

function formatDateParts(date) {
  const parts = partsToMap(DATE_PARTS_FORMATTER.formatToParts(date));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function formatDateTimeParts(date) {
  const parts = partsToMap(DATE_TIME_PARTS_FORMATTER.formatToParts(date));
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
}

function localTextParts(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed || HAS_EXPLICIT_ZONE_RE.test(trimmed)) return null;
  const match = trimmed.match(LOCAL_DATE_TIME_RE);
  if (!match) return null;
  return {
    date: `${match[1]}-${match[2]}-${match[3]}`,
    time: match[4] && match[5] ? `${match[4]}:${match[5]}` : null,
  };
}

function parseDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatKstDate(value) {
  if (!value) return '-';
  if (typeof value === 'string' && value.trim().endsWith(` ${BUSINESS_TIME_LABEL}`)) return value.trim();
  const local = localTextParts(value);
  if (local) return `${local.date} ${BUSINESS_TIME_LABEL}`;
  const date = parseDate(value);
  return date ? `${formatDateParts(date)} ${BUSINESS_TIME_LABEL}` : '-';
}

export function formatKstDateTime(value) {
  if (!value) return '-';
  if (typeof value === 'string' && value.trim().endsWith(` ${BUSINESS_TIME_LABEL}`)) {
    return value.trim().slice(0, -BUSINESS_TIME_LABEL.length).trim();
  }
  const local = localTextParts(value);
  if (local) return `${local.date} ${local.time || '00:00'}`;
  const date = parseDate(value);
  return date ? formatDateTimeParts(date) : '-';
}

export function formatKstDateTimeWithLabel(value) {
  if (typeof value === 'string' && value.trim().endsWith(` ${BUSINESS_TIME_LABEL}`)) return value.trim();
  const formatted = formatKstDateTime(value);
  return formatted === '-' ? formatted : `${formatted} ${BUSINESS_TIME_LABEL}`;
}

export function getKstTodayString() {
  return formatDateParts(new Date());
}

export function getKstDateOffsetString(daysOffset = 0) {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + Number(daysOffset || 0));
  return formatDateParts(date);
}

export function getKstNowText() {
  return formatKstDateTime(new Date());
}

export function toKstDisplayDate(value) {
  const local = typeof value === 'string' ? value.trim().match(LOCAL_DATE_RE) : null;
  if (local) return `${local[1]}-${local[2]}-${local[3]} ${BUSINESS_TIME_LABEL}`;
  return formatKstDate(value);
}
