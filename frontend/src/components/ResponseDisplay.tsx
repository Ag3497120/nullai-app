import React from 'react';

// Message型を定義
export interface Message {
  id: string;
  type: 'question' | 'response' | 'error';
  content: string;
  confidence?: number;
  memoryAugmented?: boolean;
}

interface ResponseDisplayProps {
  messages: Message[];
  isLoading: boolean;
}

// 信頼度に応じた色を返す
const getConfidenceColor = (confidence: number): string => {
  if (confidence >= 0.8) return '#22c55e'; // green
  if (confidence >= 0.6) return '#eab308'; // yellow
  if (confidence >= 0.4) return '#f97316'; // orange
  return '#ef4444'; // red
};

// 信頼度のラベル
const getConfidenceLabel = (confidence: number): string => {
  if (confidence >= 0.8) return 'High';
  if (confidence >= 0.6) return 'Medium';
  if (confidence >= 0.4) return 'Low';
  return 'Very Low';
};

export const ResponseDisplay: React.FC<ResponseDisplayProps> = ({ messages, isLoading }) => {
  return (
    <div className="messages">
      {messages.map((msg) => (
        <div key={msg.id} className={`message ${msg.type}`}>
          <p>{msg.content}</p>

          {/* 回答メタ情報（responseタイプのみ） */}
          {msg.type === 'response' && (msg.confidence !== undefined || msg.memoryAugmented) && (
            <div className="response-meta">
              {msg.confidence !== undefined && (
                <span
                  className="confidence-badge"
                  style={{ backgroundColor: getConfidenceColor(msg.confidence) }}
                  title={`Confidence: ${(msg.confidence * 100).toFixed(0)}%`}
                >
                  {getConfidenceLabel(msg.confidence)} ({(msg.confidence * 100).toFixed(0)}%)
                </span>
              )}
              {msg.memoryAugmented && (
                <span className="memory-badge" title="Enhanced with memory context">
                  Memory Enhanced
                </span>
              )}
            </div>
          )}
        </div>
      ))}
      {isLoading && <div className="loading-indicator">回答を生成中...</div>}
    </div>
  );
};
