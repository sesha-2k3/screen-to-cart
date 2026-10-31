import createClient from 'openapi-fetch';
import type { paths } from './api-types';

export const BACKEND_URL: string =
  import.meta.env.WXT_BACKEND_URL || 'http://localhost:8000';

export const api = createClient<paths>({ baseUrl: BACKEND_URL });
