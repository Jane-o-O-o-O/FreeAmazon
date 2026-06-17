export type SourceSearchFilters = {
  max_price_cny?: number | null;
  max_moq?: number | null;
  factory_only: boolean;
  dropshipping: boolean;
  min_supplier_years?: number | null;
};

export type SourceSearchTask = {
  task_id: string;
  status: string;
  progress: number;
  message?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AmazonProduct = {
  asin: string;
  marketplace: string;
  url: string;
  title: string;
  brand?: string | null;
  category?: string | null;
  price?: number | null;
  currency?: string | null;
  rating?: number | null;
  review_count?: number | null;
  main_image_url: string;
  image_urls: string[];
};

export type RankedSourceItem = {
  source: string;
  item_id: string;
  title: string;
  url: string;
  image_url: string;
  price_min?: number | null;
  price_max?: number | null;
  moq?: number | null;
  monthly_sales?: number | null;
  supplier_name?: string | null;
  supplier_location?: string | null;
  supplier_years?: number | null;
  is_factory: boolean;
  supports_dropshipping: boolean;
  image_similarity: number;
  title_similarity: number;
  category_similarity: number;
  price_score: number;
  supplier_score: number;
  risk_penalty: number;
  final_score: number;
  match_label: string;
  explanation: string;
};

export type SourceSearchResult = {
  task_id: string;
  amazon_product: AmazonProduct;
  candidates: RankedSourceItem[];
  is_partial: boolean;
};

export type CopywritingRequest = {
  site: string;
  product_name: string;
  audience?: string | null;
  selling_points?: string | null;
  keywords?: string | null;
  tone: string;
  language: string;
};

export type CopywritingResult = {
  site: string;
  generation_source: string;
  model?: string | null;
  skill: string;
  title: string;
  short_title: string;
  bullet_points: string[];
  description: string;
  tags: string[];
  seo_keywords: string[];
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.PROD ? "" : "http://localhost:8000");
const authStorageKey = "amazon-agent-access-token";

export type LoginResult = {
  access_token: string;
  token_type: string;
  expires_in: number;
  username: string;
};

export type SessionResult = {
  authenticated: boolean;
  username: string;
};

export function getStoredAccessToken() {
  return window.localStorage.getItem(authStorageKey);
}

export function storeAccessToken(token: string) {
  window.localStorage.setItem(authStorageKey, token);
}

export function clearAccessToken() {
  window.localStorage.removeItem(authStorageKey);
}

function authHeaders() {
  const token = getStoredAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  Object.entries(authHeaders()).forEach(([key, value]) => headers.set(key, value));
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });
  if (response.status === 401) {
    clearAccessToken();
  }
  return response;
}

export async function login(input: { username: string; password: string }): Promise<LoginResult> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "登录失败");
  }

  const result = (await response.json()) as LoginResult;
  storeAccessToken(result.access_token);
  return result;
}

export async function getSession(): Promise<SessionResult> {
  const response = await apiFetch("/api/auth/session");

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "会话已失效");
  }

  return response.json();
}

export function proxiedImageUrl(url: string) {
  if (!url) return url;
  try {
    const parsed = new URL(url);
    const hostname = parsed.hostname.toLowerCase();
    if (hostname === "alicdn.com" || hostname.endsWith(".alicdn.com")) {
      const token = getStoredAccessToken();
      const tokenParam = token ? `&token=${encodeURIComponent(token)}` : "";
      return `${API_BASE_URL}/api/image-proxy?url=${encodeURIComponent(url)}${tokenParam}`;
    }
  } catch {
    return url;
  }
  return url;
}

export async function createSourceSearchTask(input: {
  amazon_url: string;
  marketplace?: string;
  filters: SourceSearchFilters;
}): Promise<SourceSearchTask> {
  const response = await apiFetch("/api/source-search/tasks", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to create task");
  }

  return response.json();
}

export async function getSourceSearchResult(taskId: string): Promise<SourceSearchResult | null> {
  const response = await apiFetch(`/api/source-search/tasks/${taskId}/results`);

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to fetch results");
  }

  return response.json();
}

export async function getSourceSearchTask(taskId: string): Promise<SourceSearchTask> {
  const response = await apiFetch(`/api/source-search/tasks/${taskId}`);

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to fetch task");
  }

  return response.json();
}

export async function generateCopywriting(input: CopywritingRequest): Promise<CopywritingResult> {
  const response = await apiFetch("/api/copywriting/generate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to generate copywriting");
  }

  return response.json();
}
