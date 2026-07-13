const requestedSource = String(import.meta.env?.VITE_DATA_SOURCE || 'mock').toLowerCase();

export const DATA_SOURCE = requestedSource === 'backend' ? 'backend' : 'mock';
export const isBackendSource = DATA_SOURCE === 'backend';
