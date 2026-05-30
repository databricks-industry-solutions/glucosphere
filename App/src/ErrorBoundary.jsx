import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ 
          padding: '40px', 
          backgroundColor: '#1e293b', 
          color: '#f1f5f9', 
          minHeight: '100vh',
          fontFamily: 'monospace'
        }}>
          <h1 style={{ color: '#ef4444', marginBottom: '20px' }}>⚠️ Something went wrong</h1>
          <div style={{ 
            backgroundColor: '#0f172a', 
            padding: '20px', 
            borderRadius: '8px',
            marginBottom: '20px',
            border: '1px solid #334155'
          }}>
            <h2 style={{ color: '#f59e0b', fontSize: '18px', marginBottom: '10px' }}>Error:</h2>
            <pre style={{ color: '#ef4444', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {this.state.error && this.state.error.toString()}
            </pre>
          </div>
          <div style={{ 
            backgroundColor: '#0f172a', 
            padding: '20px', 
            borderRadius: '8px',
            border: '1px solid #334155'
          }}>
            <h2 style={{ color: '#f59e0b', fontSize: '18px', marginBottom: '10px' }}>Stack Trace:</h2>
            <pre style={{ 
              color: '#94a3b8', 
              fontSize: '12px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              maxHeight: '400px',
              overflow: 'auto'
            }}>
              {this.state.errorInfo && this.state.errorInfo.componentStack}
            </pre>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
