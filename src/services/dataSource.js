const requestedSource = String(import.meta.env?.VITE_DATA_SOURCE || 'backend').trim().toLowerCase();

// Demo data must be an explicit opt-in. Unknown and missing values fail closed to Backend.
export const DATA_SOURCE = requestedSource === 'mock' ? 'mock' : 'backend';
export const isBackendSource = DATA_SOURCE === 'backend';
export const isMockSource = DATA_SOURCE === 'mock';
