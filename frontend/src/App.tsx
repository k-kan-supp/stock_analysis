import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider, App as AntApp } from 'antd'
import jaJP from 'antd/locale/ja_JP'
import AppLayout from './components/layout/AppLayout'
import Dashboard from './pages/Dashboard'
import Screening from './pages/Screening'
import StockDetail from './pages/StockDetail'
import Technical from './pages/Technical'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5 * 60 * 1000, retry: 1 },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={jaJP}>
        <AntApp>
          <BrowserRouter>
            <Routes>
              <Route element={<AppLayout />}>
                <Route index element={<Dashboard />} />
                <Route path="/screening" element={<Screening />} />
                <Route path="/stocks/:code" element={<StockDetail />} />
                <Route path="/stocks/:code/technical" element={<Technical />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AntApp>
      </ConfigProvider>
    </QueryClientProvider>
  )
}
