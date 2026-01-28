import axios from 'axios';

const apiBase = import.meta.env.VITE_API_BASE_URL || '/api';

export const api = axios.create({
  baseURL: apiBase,
});

export interface Page<T> {
  results: T[];
  count: number;
  next?: string | null;
  previous?: string | null;
}

