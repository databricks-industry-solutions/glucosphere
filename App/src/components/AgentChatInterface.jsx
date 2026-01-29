import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader, Bot, User, AlertCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { callMultiAgentSupervisor } from '../api/databricksAgent';

// Generate a unique conversation ID for this session
const generateConversationId = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

export default function AgentChatInterface() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '👋 Hi! I\'m your Device Troubleshooting Assistant powered by Databricks multi-agent supervisor. Ask me about device issues, sensor problems, or troubleshooting steps.',
      timestamp: new Date()
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [conversationId] = useState(() => generateConversationId());
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const isInitialMount = useRef(true);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    // Don't scroll on initial mount to prevent jumping to chat on page load
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    // Only scroll if there are user messages (not just the initial greeting)
    if (messages.length > 1) {
      scrollToBottom();
    }
  }, [messages]);

  const handleSend = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setError(null);

    // Add user message to chat
    const newUserMessage = {
      role: 'user',
      content: userMessage,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, newUserMessage]);
    setIsLoading(true);

    try {
      // Get conversation history (exclude timestamps and initial greeting for API)
      const conversationHistory = messages
        .filter(msg => msg.role !== 'assistant' || messages.indexOf(msg) > 0) // Exclude initial greeting
        .map(({ role, content }) => ({ role, content }));
      
      // Call the multi-agent supervisor with conversation ID
      const response = await callMultiAgentSupervisor(userMessage, conversationHistory, conversationId);
      
      // Add assistant response to chat
      // Handle different response formats from Databricks
      let assistantContent;
      if (response.choices && response.choices[0]?.message?.content) {
        assistantContent = response.choices[0].message.content;
      } else if (response.response) {
        assistantContent = response.response;
      } else if (response.content) {
        assistantContent = response.content;
      } else if (typeof response === 'string') {
        assistantContent = response;
      } else {
        assistantContent = 'I received your message but couldn\'t generate a response. Please try again.';
      }
      
      const assistantMessage = {
        role: 'assistant',
        content: assistantContent,
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      setError(err.message);
      
      // Add error message to chat
      const errorMessage = {
        role: 'assistant',
        content: `⚠️ I encountered an error: ${err.message}. This might be due to authentication or network issues. Please check your configuration.`,
        timestamp: new Date(),
        isError: true
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestedQueries = [
    'Sensor drift in cold temperatures',
    'Calibration error troubleshooting',
    'Adhesive failure solutions',
    'Battery drain issues'
  ];

  const handleSuggestedQuery = (query) => {
    setInputMessage(query);
    inputRef.current?.focus();
  };

  return (
    <div className="flex flex-col h-full">
      {/* Chat Header */}
      <div className="flex items-center gap-3 pb-4 border-b border-slate-800">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
          <Bot className="w-5 h-5 text-white" />
        </div>
        <div>
          <h3 className="text-sm font-medium text-slate-300">AI Device Support Assistant</h3>
          <p className="text-xs text-slate-500 font-mono">Powered by Databricks Multi-Agent Supervisor</p>
        </div>
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto py-4 space-y-4 min-h-[400px] max-h-[500px]">
        {messages.map((message, idx) => (
          <div
            key={idx}
            className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {message.role === 'assistant' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
                <Bot className="w-4 h-4 text-cyan-400" />
              </div>
            )}
            
            <div
              className={`max-w-[80%] rounded-lg px-4 py-3 ${
                message.role === 'user'
                  ? 'bg-cyan-500/20 border border-cyan-500/30 text-slate-100'
                  : message.isError
                  ? 'bg-rose-500/10 border border-rose-500/30 text-rose-300'
                  : 'bg-slate-800/50 border border-slate-700 text-slate-300'
              }`}
            >
              {message.role === 'assistant' && !message.isError ? (
                <div className="text-sm prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown
                    components={{
                      // Style headings
                      h1: ({node, ...props}) => <h1 className="text-base font-bold text-slate-200 mt-2 mb-1" {...props} />,
                      h2: ({node, ...props}) => <h2 className="text-sm font-semibold text-slate-200 mt-2 mb-1" {...props} />,
                      h3: ({node, ...props}) => <h3 className="text-sm font-medium text-slate-300 mt-1 mb-1" {...props} />,
                      // Style lists
                      ul: ({node, ...props}) => <ul className="list-disc list-inside my-1 space-y-0.5" {...props} />,
                      ol: ({node, ...props}) => <ol className="list-decimal list-inside my-1 space-y-0.5" {...props} />,
                      li: ({node, ...props}) => <li className="text-slate-300" {...props} />,
                      // Style paragraphs
                      p: ({node, ...props}) => <p className="my-1 text-slate-300" {...props} />,
                      // Style code
                      code: ({node, inline, ...props}) => 
                        inline 
                          ? <code className="bg-slate-900 px-1 py-0.5 rounded text-cyan-400 text-xs" {...props} />
                          : <code className="block bg-slate-900 p-2 rounded my-1 text-xs text-cyan-400" {...props} />,
                      // Style strong/bold
                      strong: ({node, ...props}) => <strong className="font-semibold text-slate-200" {...props} />,
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              )}
              <span className="text-xs text-slate-500 mt-2 block">
                {message.timestamp.toLocaleTimeString()}
              </span>
            </div>

            {message.role === 'user' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-slate-700 border border-slate-600 flex items-center justify-center">
                <User className="w-4 h-4 text-slate-300" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3 justify-start">
            <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
              <Bot className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg px-4 py-3">
              <div className="flex items-center gap-2">
                <Loader className="w-4 h-4 text-cyan-400 animate-spin" />
                <span className="text-sm text-slate-400">Agent is thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-rose-300">
            <p className="font-medium mb-1">Connection Error</p>
            <p>{error}</p>
          </div>
        </div>
      )}

      {/* Suggested Queries (shown when no messages or only initial message) */}
      {messages.length <= 1 && (
        <div className="mb-4 space-y-2">
          <p className="text-xs text-slate-500 font-mono">Try asking:</p>
          <div className="flex flex-wrap gap-2">
            {suggestedQueries.map((query, idx) => (
              <button
                key={idx}
                onClick={() => handleSuggestedQuery(query)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-full text-xs text-slate-400 transition-colors"
              >
                {query}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="relative">
        <textarea
          ref={inputRef}
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask about device issues, troubleshooting steps..."
          className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-4 pr-12 py-3 text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors resize-none"
          rows="3"
          disabled={isLoading}
        />
        <button
          onClick={handleSend}
          disabled={!inputMessage.trim() || isLoading}
          className="absolute right-2 bottom-2 p-2 bg-cyan-500 hover:bg-cyan-600 disabled:bg-slate-700 disabled:cursor-not-allowed rounded-lg transition-colors"
        >
          {isLoading ? (
            <Loader className="w-5 h-5 text-white animate-spin" />
          ) : (
            <Send className="w-5 h-5 text-white" />
          )}
        </button>
      </div>
    </div>
  );
}

