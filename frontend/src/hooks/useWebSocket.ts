import { useState, useEffect, useCallback, useRef } from 'react';

const WS_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws');

export interface WSMessage {
  type: 'connected' | 'processing' | 'thinking' | 'response' | 'error' | 'pong';
  message?: string;
  session_id?: string;
  step?: string;
  question?: string;
  response?: string;
  status?: string;
  confidence?: number;
  memory_augmented?: boolean;
  error?: string;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  isProcessing: boolean;
  thinkingSteps: string[];
  lastResponse: WSMessage | null;
  error: string | null;
  connect: (sessionId: string) => void;
  disconnect: () => void;
  sendQuestion: (question: string, domainId?: string) => void;
}

export const useWebSocket = (): UseWebSocketReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [thinkingSteps, setThinkingSteps] = useState<string[]>([]);
  const [lastResponse, setLastResponse] = useState<WSMessage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string>('');

  const connect = useCallback((sessionId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    sessionIdRef.current = sessionId;
    setError(null);

    const token = localStorage.getItem('auth_token');
    const wsUrl = `${WS_BASE_URL}/api/questions/ws/${sessionId}${token ? `?token=${token}` : ''}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const data: WSMessage = JSON.parse(event.data);

        switch (data.type) {
          case 'connected':
            console.log('WS: Connected to session', data.session_id);
            break;

          case 'processing':
            setIsProcessing(true);
            setThinkingSteps([]);
            break;

          case 'thinking':
            if (data.step) {
              setThinkingSteps((prev) => [...prev, data.step!]);
            }
            break;

          case 'response':
            setIsProcessing(false);
            setLastResponse(data);
            break;

          case 'error':
            setIsProcessing(false);
            setError(data.error || 'Unknown error');
            break;

          case 'pong':
            // Keepalive response
            break;
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = (event) => {
      console.error('WebSocket error:', event);
      setError('WebSocket connection error');
      setIsConnected(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      setIsProcessing(false);
      console.log('WebSocket disconnected');
    };

    wsRef.current = ws;
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'close' }));
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
    setIsProcessing(false);
  }, []);

  const sendQuestion = useCallback((question: string, domainId: string = 'medical') => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket not connected');
      return;
    }

    const userId = localStorage.getItem('auth_user')
      ? JSON.parse(localStorage.getItem('auth_user')!).id
      : 'anonymous';

    wsRef.current.send(
      JSON.stringify({
        type: 'question',
        question,
        domain_id: domainId,
        user_id: userId,
      })
    );
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Keepalive ping
  useEffect(() => {
    if (!isConnected) return;

    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);

    return () => clearInterval(pingInterval);
  }, [isConnected]);

  return {
    isConnected,
    isProcessing,
    thinkingSteps,
    lastResponse,
    error,
    connect,
    disconnect,
    sendQuestion,
  };
};
