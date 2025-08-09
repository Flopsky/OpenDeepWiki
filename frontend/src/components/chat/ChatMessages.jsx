import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FiUser, FiCpu, FiCopy, FiCheck, FiInfo, FiArrowDown, FiLoader } from 'react-icons/fi';

const ChatMessages = ({ messages, isLoading = false }) => {
  const [hoveredMessage, setHoveredMessage] = useState(null);
  const [copiedMessage, setCopiedMessage] = useState(null);
  const messagesEndRef = useRef(null);
  const containerRef = useRef(null);
  const [userScrolled, setUserScrolled] = useState(false);
  const prevMessagesLengthRef = useRef(messages.length);
  
  // Scroll to bottom when messages change
  useEffect(() => {
    // Only auto-scroll if new messages were added and user hasn't manually scrolled up
    if (messages.length > prevMessagesLengthRef.current && !userScrolled) {
      scrollToBottom();
    }
    prevMessagesLengthRef.current = messages.length;
  }, [messages, userScrolled]);

  // Ensure we keep the view pinned to bottom while loading
  useEffect(() => {
    if (isLoading && !userScrolled) {
      scrollToBottom();
    }
  }, [isLoading, userScrolled]);
  
  // Function to scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  
  // Handle scroll events to detect when user manually scrolls
  const handleScroll = (e) => {
    const container = e.target;
    const isScrolledUp = container.scrollHeight - container.scrollTop - container.clientHeight > 100;
    
    if (isScrolledUp) {
      setUserScrolled(true);
    } else {
      // If user scrolls back to bottom, reset the userScrolled flag
      setUserScrolled(false);
    }
  };
  
  const copyToClipboard = (text, index) => {
    // Create a temporary textarea element
    const textarea = document.createElement('textarea');
    textarea.value = text;
    
    // Make the textarea out of viewport
    textarea.style.position = 'fixed';
    textarea.style.left = '-999999px';
    textarea.style.top = '-999999px';
    
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    
    let success = false;
    try {
      // Execute the copy command
      success = document.execCommand('copy');
      if (success) {
        setCopiedMessage(index);
        setTimeout(() => setCopiedMessage(null), 2000);
      } else {
        console.error('Failed to copy text with execCommand');
        // Fallback to clipboard API
        navigator.clipboard.writeText(text).then(() => {
          setCopiedMessage(index);
          setTimeout(() => setCopiedMessage(null), 2000);
        }).catch(err => {
          console.error('Failed to copy text with clipboard API: ', err);
        });
      }
    } catch (err) {
      console.error('Failed to copy text: ', err);
      // Fallback to clipboard API
      navigator.clipboard.writeText(text).then(() => {
        setCopiedMessage(index);
        setTimeout(() => setCopiedMessage(null), 2000);
      }).catch(err => {
        console.error('Failed to copy text with clipboard API: ', err);
      });
    } finally {
      // Clean up
      document.body.removeChild(textarea);
    }
  };
  
  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="messages-container"
      role="log"
      aria-live="polite"
      aria-relevant="additions"
      style={{ position: 'relative' }}
    >
      {messages.map((message, index) => (
        <div 
          key={index}
          className={`message-row ${message.role} fade-in`}
          style={{ animationDelay: `${index * 0.1}s` }}
          onMouseEnter={() => setHoveredMessage(index)}
          onMouseLeave={() => setHoveredMessage(null)}
        >
          {message.role === 'system' ? (
            // System message (notification)
            <div className="message-container">
              <div className="message-content">
                <FiInfo size={16} style={{ marginRight: '8px', color: '#3b82f6', flexShrink: 0 }} />
                <span style={{ fontSize: '0.875rem', color: 'rgba(255, 255, 255, 0.8)' }}>
                  {message.content}
                </span>
              </div>
            </div>
          ) : (
            // Regular user or assistant message
            <>
              <div className="message-container">
                <div className={`message-avatar ${message.role}`}>
                  {message.role === 'user' ? <FiUser size={16} /> : <FiCpu size={16} />}
                </div>
                
                <div className="message-content">
                  <ReactMarkdown
                    components={{
                      code({node, inline, className, children, ...props}) {
                        const match = /language-(\w+)/.exec(className || '');
                        if (!inline && match) {
                          const language = match[1];
                          return (
                            <div style={{ margin: '1rem 0' }}>
                              <div className="code-header">
                                <span style={{ fontWeight: 600 }}>{language}</span>
                                <div className="code-actions">
                                  <button 
                                    className="code-action-button"
                                    onClick={() => copyToClipboard(String(children), `code-${index}`)}
                                  >
                                    {copiedMessage === `code-${index}` ? (
                                      <>
                                        <FiCheck size={12} />
                                        <span>Copied!</span>
                                      </>
                                    ) : (
                                      <>
                                        <FiCopy size={12} />
                                        <span>Copy</span>
                                      </>
                                    )}
                                  </button>
                                </div>
                              </div>
                              <SyntaxHighlighter
                                style={{
                                  ...vscDarkPlus,
                                  'pre[class*="language-"]': {
                                    ...vscDarkPlus['pre[class*="language-"]'],
                                    background: 'var(--bg-secondary)',
                                    margin: 0,
                                    padding: '1rem',
                                  },
                                  'code[class*="language-"]': {
                                    ...vscDarkPlus['code[class*="language-"]'],
                                    background: 'none',
                                    fontSize: '0.875rem',
                                    lineHeight: '1.6',
                                  }
                                }}
                                language={language}
                                PreTag="div"
                                customStyle={{
                                  margin: 0,
                                  padding: '1rem',
                                  background: 'var(--bg-secondary)',
                                  fontSize: '0.875rem',
                                  lineHeight: '1.6',
                                  borderRadius: '0 0 0.75rem 0.75rem',
                                }}
                                {...props}
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            </div>
                          );
                        }
                        return (
                          <code 
                            className={className} 
                            style={{
                              background: 'rgba(255, 255, 255, 0.05)',
                              color: '#10a37f',
                              padding: '0.125rem 0.375rem',
                              borderRadius: '0.375rem',
                              fontSize: '0.9em',
                              fontFamily: 'var(--font-mono)',
                              border: '1px solid rgba(255, 255, 255, 0.1)'
                            }}
                            {...props}
                          >
                            {children}
                          </code>
                        );
                      },
                      // Enhanced heading styles
                      h1: ({children}) => (
                        <h1 style={{ 
                          fontSize: '1.875rem', 
                          fontWeight: 700, 
                          marginBottom: '1rem',
                          color: 'rgba(255, 255, 255, 0.95)',
                          lineHeight: 1.2
                        }}>
                          {children}
                        </h1>
                      ),
                      h2: ({children}) => (
                        <h2 style={{ 
                          fontSize: '1.5rem', 
                          fontWeight: 600, 
                          marginBottom: '0.75rem',
                          color: 'rgba(255, 255, 255, 0.95)',
                          lineHeight: 1.3
                        }}>
                          {children}
                        </h2>
                      ),
                      h3: ({children}) => (
                        <h3 style={{ 
                          fontSize: '1.25rem', 
                          fontWeight: 600, 
                          marginBottom: '0.75rem',
                          color: 'rgba(255, 255, 255, 0.95)',
                          lineHeight: 1.4
                        }}>
                          {children}
                        </h3>
                      ),
                      // Enhanced paragraph styles
                      p: ({children}) => (
                        <p style={{ 
                          marginBottom: '1rem',
                          lineHeight: 1.7,
                          color: 'rgba(255, 255, 255, 0.95)'
                        }}>
                          {children}
                        </p>
                      ),
                      // Enhanced list styles
                      ul: ({children}) => (
                        <ul style={{ 
                          marginBottom: '1rem',
                          paddingLeft: '1.5rem',
                          listStyle: 'disc'
                        }}>
                          {children}
                        </ul>
                      ),
                      ol: ({children}) => (
                        <ol style={{ 
                          marginBottom: '1rem',
                          paddingLeft: '1.5rem',
                          listStyle: 'decimal'
                        }}>
                          {children}
                        </ol>
                      ),
                      li: ({children}) => (
                        <li style={{ 
                          marginBottom: '0.5rem',
                          lineHeight: 1.6,
                          color: 'rgba(255, 255, 255, 0.9)'
                        }}>
                          {children}
                        </li>
                      ),
                      // Enhanced link styles
                      a: ({href, children}) => (
                        <a 
                          href={href}
                          style={{ 
                            color: '#10a37f',
                            textDecoration: 'none',
                            borderBottom: '1px solid transparent',
                            transition: 'border-color 0.15s ease-out'
                          }}
                          onMouseEnter={(e) => {
                            e.target.style.borderBottomColor = '#10a37f';
                          }}
                          onMouseLeave={(e) => {
                            e.target.style.borderBottomColor = 'transparent';
                          }}
                        >
                          {children}
                        </a>
                      ),
                      // Enhanced blockquote styles
                      blockquote: ({children}) => (
                        <blockquote style={{
                          borderLeft: '3px solid #10a37f',
                          paddingLeft: '1rem',
                          margin: '1rem 0',
                          color: 'rgba(255, 255, 255, 0.7)',
                          fontStyle: 'italic',
                          background: 'rgba(255, 255, 255, 0.02)',
                          borderRadius: '0 0.5rem 0.5rem 0',
                          padding: '1rem 1rem 1rem 1.5rem'
                        }}>
                          {children}
                        </blockquote>
                      ),
                      // Enhanced table styles
                      table: ({children}) => (
                        <div style={{ 
                          margin: '1rem 0',
                          borderRadius: '0.75rem',
                          overflow: 'hidden',
                          border: '1px solid rgba(255, 255, 255, 0.1)'
                        }}>
                          <table style={{ 
                            width: '100%',
                            borderCollapse: 'collapse'
                          }}>
                            {children}
                          </table>
                        </div>
                      ),
                      th: ({children}) => (
                        <th style={{ 
                          padding: '0.75rem 1rem',
                          textAlign: 'left',
                          background: 'rgba(255, 255, 255, 0.05)',
                          fontWeight: 600,
                          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                          color: 'rgba(255, 255, 255, 0.95)'
                        }}>
                          {children}
                        </th>
                      ),
                      td: ({children}) => (
                        <td style={{ 
                          padding: '0.75rem 1rem',
                          borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                          color: 'rgba(255, 255, 255, 0.9)'
                        }}>
                          {children}
                        </td>
                      )
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
              </div>
              
              {message.role === 'assistant' && (
                <div className={`message-actions-container ${(hoveredMessage === index || copiedMessage === index) ? 'visible' : ''}`}>
                  <div className="message-actions">
                    <button 
                      className="message-action-button"
                      onClick={() => copyToClipboard(message.content, index)}
                      aria-label="Copy message"
                      title="Copy to clipboard"
                    >
                      {copiedMessage === index ? (
                        <>
                          <FiCheck size={12} />
                          <span>Copied!</span>
                        </>
                      ) : (
                        <>
                          <FiCopy size={12} />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      ))}

      {/* Typing indicator while loading */}
      {isLoading && (
        <div className="message-row assistant fade-in">
          <div className="message-container">
            <div className="message-avatar assistant">
              <FiCpu size={16} />
            </div>
            <div className="message-content" aria-label="Assistant is typing">
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', opacity: 0.9 }}>
                <FiLoader size={14} style={{ animation: 'spin 1s linear infinite' }} />
                <span>Thinking…</span>
              </div>
            </div>
          </div>
        </div>
      )}
      <div ref={messagesEndRef} style={{ height: '1px', width: '100%' }} />

      {/* Scroll to bottom button */}
      {userScrolled && (
        <button
          onClick={scrollToBottom}
          aria-label="Scroll to bottom"
          title="Scroll to bottom"
          style={{
            position: 'absolute',
            right: '24px',
            bottom: '24px',
            background: 'rgba(0, 0, 0, 0.4)',
            backdropFilter: 'blur(6px)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            color: 'white',
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
          }}
        >
          <FiArrowDown size={16} />
        </button>
      )}
    </div>
  );
};

export default ChatMessages;