import React, { useState } from 'react';

interface QuestionInputProps {
  onSubmit: (question: string) => void;
  disabled: boolean;
  placeholder?: string;
}

export const QuestionInput: React.FC<QuestionInputProps> = ({ onSubmit, disabled, placeholder }) => {
  const [inputValue, setInputValue] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || disabled) return;
    onSubmit(inputValue);
    setInputValue('');
  };

  return (
    <form onSubmit={handleSubmit} className="input-area">
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        disabled={disabled}
        placeholder={placeholder || "質問を入力..."}
        autoFocus
      />
      <button type="submit" disabled={disabled}>
        送信
      </button>
    </form>
  );
};
