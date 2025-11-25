/**
 * WebSocket Service
 * Real-time updates from backend
 */

export interface WSMessage {
  type: string;
  deployment_id?: string;
  data?: any;
  timestamp: string;
  message?: string;
  severity?: string;
  event_type?: string;
  metrics?: any;
  status?: string;
}

export type WSMessageHandler = (message: WSMessage) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private token: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private handlers: Map<string, Set<WSMessageHandler>> = new Map();
  private isConnecting = false;
  private shouldReconnect = true;

  constructor() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = import.meta.env.VITE_WS_URL || `${wsProtocol}//${window.location.host}`;
    this.url = `${wsHost}/ws`;
  }

  /**
   * Connect to WebSocket server
   */
  connect(token?: string, deploymentId?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      if (this.isConnecting) {
        reject(new Error('Connection already in progress'));
        return;
      }

      this.isConnecting = true;
      this.token = token || localStorage.getItem('auth_token');

      if (!this.token) {
        this.isConnecting = false;
        reject(new Error('No authentication token available'));
        return;
      }

      const wsUrl = deploymentId
        ? `${this.url}?token=${this.token}&deployment_id=${deploymentId}`
        : `${this.url}?token=${this.token}`;

      try {
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WSMessage = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.isConnecting = false;
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('WebSocket disconnected');
          this.isConnecting = false;
          this.ws = null;

          if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
            setTimeout(() => {
              this.reconnectAttempts++;
              console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
              this.connect(this.token || undefined, deploymentId);
            }, this.reconnectDelay * this.reconnectAttempts);
          }
        };
      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.shouldReconnect = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Subscribe to specific message types
   */
  subscribe(messageType: string, handler: WSMessageHandler): () => void {
    if (!this.handlers.has(messageType)) {
      this.handlers.set(messageType, new Set());
    }
    this.handlers.get(messageType)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.handlers.get(messageType);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.handlers.delete(messageType);
        }
      }
    };
  }

  /**
   * Send message to server
   */
  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }

  /**
   * Subscribe to deployment updates
   */
  subscribeToDeployment(deploymentId: string): void {
    this.send({
      type: 'subscribe',
      deployment_id: deploymentId,
    });
  }

  /**
   * Unsubscribe from deployment updates
   */
  unsubscribeFromDeployment(deploymentId: string): void {
    this.send({
      type: 'unsubscribe',
      deployment_id: deploymentId,
    });
  }

  /**
   * Request deployment status
   */
  requestDeploymentStatus(deploymentId: string): void {
    this.send({
      type: 'get_status',
      deployment_id: deploymentId,
    });
  }

  /**
   * Send ping
   */
  ping(): void {
    this.send({ type: 'ping' });
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Handle incoming message
   */
  private handleMessage(message: WSMessage): void {
    // Call handlers for specific message type
    const handlers = this.handlers.get(message.type);
    if (handlers) {
      handlers.forEach((handler) => handler(message));
    }

    // Call handlers for 'all' message type
    const allHandlers = this.handlers.get('all');
    if (allHandlers) {
      allHandlers.forEach((handler) => handler(message));
    }
  }
}

// Singleton instance
const wsService = new WebSocketService();

export default wsService;
