/**
 * API Client
 * Axios-based client for backend REST API
 */
import axios, { AxiosError, AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// API client instance
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle errors
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Unauthorized - clear token and redirect to login
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Types
export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
}

export interface DeploymentCreate {
  service_name: string;
  environment: 'development' | 'staging' | 'production';
  strategy: 'blue_green' | 'canary';
  target_version: string;
  namespace?: string;
  canary_steps?: number[];
  metrics_config?: MetricsConfig;
  metadata?: Record<string, any>;
}

export interface MetricsConfig {
  error_rate?: MetricThreshold;
  latency_p99?: MetricThreshold;
  latency_p95?: MetricThreshold;
  success_rate?: MetricThreshold;
}

export interface MetricThreshold {
  threshold: number;
  comparison: 'less_than' | 'greater_than' | 'equal' | 'not_equal';
  window?: number;
}

export interface Deployment {
  id: number;
  deployment_id: string;
  service_name: string;
  environment: string;
  strategy: string;
  status: string;
  current_version?: string;
  target_version: string;
  current_step: number;
  current_traffic_percentage: number;
  canary_steps: number[];
  active_slot?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  updated_at?: string;
  error_message?: string;
  rollback_reason?: string;
  created_by: string;
  metadata: Record<string, any>;
}

export interface DeploymentList {
  total: number;
  page: number;
  page_size: number;
  deployments: Deployment[];
}

export interface DeploymentControl {
  action: 'pause' | 'resume' | 'rollback' | 'promote' | 'switch';
  reason?: string;
}

export interface DeploymentEvent {
  id: number;
  deployment_id: number;
  event_type: string;
  severity: string;
  message: string;
  timestamp: string;
  actor?: string;
  details: Record<string, any>;
}

export interface MetricData {
  metric_name: string;
  metric_value: number;
  timestamp: string;
  labels: Record<string, string>;
}

// API functions
export const api = {
  // Authentication
  auth: {
    login: async (credentials: LoginRequest): Promise<TokenResponse> => {
      const response = await apiClient.post<TokenResponse>('/api/v1/auth/login', credentials);
      return response.data;
    },

    getCurrentUser: async (): Promise<User> => {
      const response = await apiClient.get<User>('/api/v1/auth/me');
      return response.data;
    },

    logout: async (): Promise<void> => {
      await apiClient.post('/api/v1/auth/logout');
      localStorage.removeItem('auth_token');
    },
  },

  // Deployments
  deployments: {
    list: async (params?: {
      service_name?: string;
      environment?: string;
      status?: string;
      page?: number;
      page_size?: number;
    }): Promise<DeploymentList> => {
      const response = await apiClient.get<DeploymentList>('/api/v1/deployments', { params });
      return response.data;
    },

    get: async (deploymentId: string): Promise<Deployment> => {
      const response = await apiClient.get<Deployment>(`/api/v1/deployments/${deploymentId}`);
      return response.data;
    },

    create: async (deployment: DeploymentCreate): Promise<Deployment> => {
      const response = await apiClient.post<Deployment>('/api/v1/deployments', deployment);
      return response.data;
    },

    start: async (deploymentId: string): Promise<Deployment> => {
      const response = await apiClient.post<Deployment>(
        `/api/v1/deployments/${deploymentId}/start`
      );
      return response.data;
    },

    control: async (deploymentId: string, control: DeploymentControl): Promise<Deployment> => {
      const response = await apiClient.post<Deployment>(
        `/api/v1/deployments/${deploymentId}/control`,
        control
      );
      return response.data;
    },

    getHistory: async (deploymentId: string): Promise<any[]> => {
      const response = await apiClient.get(`/api/v1/deployments/${deploymentId}/history`);
      return response.data;
    },

    getEvents: async (deploymentId: string, limit?: number): Promise<DeploymentEvent[]> => {
      const response = await apiClient.get<DeploymentEvent[]>(
        `/api/v1/deployments/${deploymentId}/events`,
        { params: { limit } }
      );
      return response.data;
    },

    getMetrics: async (deploymentId: string, metricNames?: string): Promise<any> => {
      const response = await apiClient.get(`/api/v1/deployments/${deploymentId}/metrics`, {
        params: { metric_names: metricNames },
      });
      return response.data;
    },

    delete: async (deploymentId: string): Promise<void> => {
      await apiClient.delete(`/api/v1/deployments/${deploymentId}`);
    },
  },

  // Health
  health: async (): Promise<any> => {
    const response = await apiClient.get('/health');
    return response.data;
  },
};

export default apiClient;
