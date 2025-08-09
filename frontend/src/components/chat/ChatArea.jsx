import React from 'react';
import styled from 'styled-components';
import { FiMenu, FiInfo, FiFileText, FiGithub } from 'react-icons/fi';
import ChatMessages from './ChatMessages';
import ChatInput from './ChatInput';

const ChatContainer = styled.div`
  flex: 1;
  height: 100vh;
  display: flex;
  flex-direction: column;
  position: relative;
  margin-left: ${props => props.leftSidebarVisible ? 'var(--sidebar-width)' : '0'};
  margin-right: ${props => props.rightSidebarVisible ? 'var(--right-sidebar-width)' : '0'};
  width: ${props => {
    if (props.leftSidebarVisible && props.rightSidebarVisible) {
      return 'calc(100% - var(--sidebar-width) - var(--right-sidebar-width))';
    } else if (props.leftSidebarVisible) {
      return 'calc(100% - var(--sidebar-width))';
    } else if (props.rightSidebarVisible) {
      return 'calc(100% - var(--right-sidebar-width))';
    } else {
      return '100%';
    }
  }};
  transition: margin 0.3s ease, width 0.3s ease;
  background-color: ${props => props.theme === 'dark' ? 'var(--background-dark)' : 'var(--background-light)'};
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  height: var(--header-height);
  padding: 0 var(--spacing-md);
  border-bottom: 1px solid ${props => props.theme === 'dark' ? 'var(--border-dark)' : 'var(--border-light)'};
`;

const ToggleButton = styled.button`
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: ${props => props.theme === 'dark' ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)'};
  border: none;
  cursor: pointer;
  transition: background-color 0.2s ease;
  
  &:hover {
    background: ${props => props.theme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'};
  }
`;

const Title = styled.h1`
  font-size: 0.9rem;
  margin: 0 auto;
  text-align: center;
  font-weight: 500;
  color: ${props => props.theme === 'dark' ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)'};
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
`;

const RepoIcon = styled(FiGithub)`
  margin-right: var(--spacing-xs);
`;

const MessagesContainer = styled.div`
  flex: 1;
  overflow-y: auto;
  padding-bottom: 120px; /* Space for input */
`;

const EmptyState = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: var(--spacing-xl);
  text-align: center;
  color: ${props => props.theme === 'dark' ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)'};
`;

const EmptyStateTitle = styled.h2`
  font-size: 2rem;
  margin-bottom: var(--spacing-md);
  font-weight: 600;
`;

const EmptyStateText = styled.p`
  max-width: 600px;
  margin-bottom: var(--spacing-lg);
  font-size: 1.1rem;
  line-height: 1.5;
`;

const ChatArea = ({
  leftSidebarVisible,
  rightSidebarVisible,
  toggleLeftSidebar,
  toggleRightSidebar,
  chatHistory,
  onSendMessage,
  repoParams,
  isLoading
}) => {
  const isDarkMode = document.body.classList.contains('dark');
  const theme = isDarkMode ? 'dark' : 'light';
  
  const hasRepoInfo = repoParams && repoParams.repo_name;
  const hasMessages = chatHistory && chatHistory.length > 0;
  
  return (
    <ChatContainer 
      leftSidebarVisible={leftSidebarVisible} 
      rightSidebarVisible={rightSidebarVisible}
      theme={theme}
    >
      <Header theme={theme}>
        {!leftSidebarVisible && (
          <ToggleButton onClick={toggleLeftSidebar} theme={theme} aria-label="Toggle left sidebar">
            <FiMenu />
          </ToggleButton>
        )}
        
        <Title theme={theme}>
          {hasRepoInfo ? (
            <>
              <RepoIcon size={16} /> opendeepwiki - {repoParams.repo_name}
            </>
          ) : 'opendeepwiki'}
        </Title>
        
        <ToggleButton onClick={toggleRightSidebar} theme={theme} aria-label="Toggle right sidebar">
          <FiInfo />
        </ToggleButton>
      </Header>
      
      {hasMessages ? (
        <MessagesContainer>
          <ChatMessages messages={chatHistory} isLoading={isLoading} />
        </MessagesContainer>
      ) : (
        <EmptyState theme={theme}>
          <EmptyStateTitle>What can I help with?</EmptyStateTitle>
          <EmptyStateText>
            {hasRepoInfo 
              ? `Ask me anything about the ${repoParams.repo_name} repository. I can help you understand the code, documentation, and more.` 
              : 'Initialize a repository from the sidebar to get started. You can use a GitHub URL or upload a local repository.'}
          </EmptyStateText>
        </EmptyState>
      )}
      
      <ChatInput 
        onSendMessage={onSendMessage} 
        disabled={!hasRepoInfo || isLoading}
        isLoading={isLoading}
        placeholder={hasRepoInfo 
          ? isLoading ? "Thinking..." : "Message opendeepwiki..." 
          : "Initialize a repository to start chatting..."}
      />
    </ChatContainer>
  );
};

export default ChatArea;