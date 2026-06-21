import React, { Component, type ErrorInfo, type ReactNode } from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './index.css';

// ── Error Boundary: 防止任何组件崩溃导致全页白屏 ──
class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] Caught:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '60vh', color: 'var(--text-secondary)', gap: 12
        }}>
          <div style={{ fontSize: 48 }}>⚠️</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>页面发生错误</div>
          <div style={{ fontSize: 14, color: 'var(--text-muted)', maxWidth: 400, textAlign: 'center' }}>
            {this.state.error?.message || '未知错误'}
          </div>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
            style={{
              marginTop: 16, padding: '8px 24px', border: 'none', borderRadius: 8,
              background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 14
            }}
          >
            重新加载
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,  // 30分钟回收，避免永久缓旧数据
      retry: 1,
    },
  },
});

// 预加载股池快照：先显示本地副本保证秒出，再异步从 API 刷新确保数据最新
async function init() {
  try {
    const res = await fetch('/data/turtle_pool.json');
    if (res.ok) {
      const pool = await res.json();
      queryClient.setQueryData(['stockPool', 'turtle'], pool);
      // 立即标记为过期，触发后台刷新，确保不展示旧数据
      queryClient.invalidateQueries({ queryKey: ['stockPool', 'turtle'] });
    }
  } catch {
    // 预加载失败不影响正常流程，useQuery 会自行请求 API
  }

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </QueryClientProvider>
    </React.StrictMode>,
  );
}

init();
