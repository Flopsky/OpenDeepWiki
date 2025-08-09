import React, { useState, useRef, useEffect } from 'react';
import { FiArrowUp, FiLoader, FiPlus, FiPaperclip } from 'react-icons/fi';

const ChatInput = ({ onSendMessage, disabled, placeholder, isLoading, draftKey = 'chat_draft', inline = false }) => {
  const [message, setMessage] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const textareaRef = useRef(null);
  const formRef = useRef(null);
  
  // Restore draft per-conversation
  useEffect(() => {
    try {
      const saved = localStorage.getItem(draftKey);
      if (saved) setMessage(saved);
    } catch {}
  }, [draftKey]);
  
  // Persist draft per-conversation
  useEffect(() => {
    try {
      localStorage.setItem(draftKey, message);
    } catch {}
  }, [message, draftKey]);
  
  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [message]);
  
  const handleSubmit = (e) => {
    e.preventDefault();
    if (message.trim() && !disabled && !isLoading) {
      onSendMessage(message);
      setMessage('');
      try { localStorage.removeItem(draftKey); } catch {}
      
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };
  
  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };
  
  const handleFocus = () => {
    setIsFocused(true);
  };
  
  const handleBlur = () => {
    setIsFocused(false);
  };
  
  const isMessageValid = message.trim().length > 0;
  
  return (
    <div className={`input-container ${inline ? 'inline' : ''}`} role="form" aria-label="Chat input area">
      <div className="input-wrapper">
        <form ref={formRef} className="input-form" onSubmit={handleSubmit}>
          
          <textarea
            className="input-textarea"
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={handleFocus}
            onBlur={handleBlur}
            placeholder={placeholder}
            disabled={disabled || isLoading}
            rows={1}
            style={{
              borderRadius: '1rem',
              transition: 'all 0.15s ease-out',
            }}
            aria-label="Message opendeepwiki"
          />
          
          <button 
            className={`input-button send ${isMessageValid && !disabled && !isLoading ? 'active' : ''}`}
            type="submit" 
            disabled={!isMessageValid || disabled || isLoading}
            aria-label={isLoading ? "Sending..." : "Send message"}
            title={isLoading ? "Sending..." : "Send message"}
            style={{
              transform: isMessageValid && !disabled && !isLoading ? 'scale(1.05)' : 'scale(1)',
              transition: 'all 0.15s ease-out',
            }}
          >
            {isLoading ? (
              <FiLoader size={16} className="loading-icon" />
            ) : (
              <FiArrowUp size={16} />
            )}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatInput;