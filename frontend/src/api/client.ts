import axios from 'axios'
import type {
  StockDetail, DailyPrice, TechnicalDaily,
  ScreeningParams, ScreeningResponse,
  IndustrySummary, DashboardSummary,
} from '../types/stock'

const api = axios.create({ baseURL: '/api/v1' })

export const stocksApi = {
  screening: (params: ScreeningParams) =>
    api.get<ScreeningResponse>('/stocks/screening', { params }).then(r => r.data),

  getDetail: (code: string) =>
    api.get<StockDetail>(`/stocks/${code}`).then(r => r.data),

  getPrices: (code: string, days = 365) =>
    api.get<DailyPrice[]>(`/stocks/${code}/prices`, { params: { days } }).then(r => r.data),

  getTechnicals: (code: string, days = 365) =>
    api.get<TechnicalDaily[]>(`/stocks/${code}/technicals`, { params: { days } }).then(r => r.data),
}

export const industriesApi = {
  list: () =>
    api.get<IndustrySummary[]>('/industries/').then(r => r.data),
}

export const dashboardApi = {
  summary: () =>
    api.get<DashboardSummary>('/dashboard/summary').then(r => r.data),
}
