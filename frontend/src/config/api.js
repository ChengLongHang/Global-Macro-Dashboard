// Single source of truth for the backend base URL. Falls back to localhost
// for local dev if VITE_API_BASE_URL isn't set, but production builds
// should always set it via .env / .env.production.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
