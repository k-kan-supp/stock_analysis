import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Row, Col, Select, Spin, Button, Tag, Statistic,
  Space, Typography, Segmented,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import {
  createChart, CandlestickSeries, LineSeries,
  HistogramSeries, type IChartApi,
} from 'lightweight-charts'
import { stocksApi } from '../api/client'

const { Title } = Typography

const PERIOD_OPTIONS = [
  { label: '3ヶ月', value: 90 },
  { label: '6ヶ月', value: 180 },
  { label: '1年', value: 365 },
  { label: '3年', value: 1095 },
  { label: '5年', value: 1825 },
]

export default function Technical() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const [days, setDays] = useState(365)

  const candleRef = useRef<HTMLDivElement>(null)
  const rsiRef = useRef<HTMLDivElement>(null)
  const macdRef = useRef<HTMLDivElement>(null)
  const candleChartRef = useRef<IChartApi | null>(null)
  const rsiChartRef = useRef<IChartApi | null>(null)
  const macdChartRef = useRef<IChartApi | null>(null)

  const { data: prices, isLoading: pricesLoading } = useQuery({
    queryKey: ['prices', code, days],
    queryFn: () => stocksApi.getPrices(code!, days),
    enabled: !!code,
  })

  const { data: technicals, isLoading: techLoading } = useQuery({
    queryKey: ['technicals', code, days],
    queryFn: () => stocksApi.getTechnicals(code!, days),
    enabled: !!code,
  })

  const { data: detail } = useQuery({
    queryKey: ['stock', code],
    queryFn: () => stocksApi.getDetail(code!),
    enabled: !!code,
  })

  useEffect(() => {
    if (!candleRef.current || !rsiRef.current || !macdRef.current) return
    if (!prices || !technicals) return

    candleChartRef.current?.remove()
    rsiChartRef.current?.remove()
    macdChartRef.current?.remove()

    const chartOpts = {
      layout: { background: { color: '#fff' }, textColor: '#333' },
      grid: { vertLines: { color: '#f0f0f0' }, horzLines: { color: '#f0f0f0' } },
      timeScale: { timeVisible: true },
    }

    // キャンドルチャート
    const candleChart = createChart(candleRef.current, { ...chartOpts, height: 360 })
    const candleSeries = candleChart.addSeries(CandlestickSeries, {
      upColor: '#e74c3c', downColor: '#3498db',
      borderUpColor: '#e74c3c', borderDownColor: '#3498db',
      wickUpColor: '#e74c3c', wickDownColor: '#3498db',
    })
    candleSeries.setData(
      prices.map(p => ({
        time: p.trade_date as `${number}-${number}-${number}`,
        open: p.open, high: p.high, low: p.low, close: p.close,
      }))
    )

    // MA
    const maData = (key: 'ma25' | 'ma75' | 'ma200', color: string) =>
      technicals
        .filter(t => t[key] != null)
        .map(t => ({ time: t.trade_date as `${number}-${number}-${number}`, value: t[key]! }))

    candleChart.addSeries(LineSeries, { color: '#f39c12', lineWidth: 1 }).setData(maData('ma25', '#f39c12'))
    candleChart.addSeries(LineSeries, { color: '#9b59b6', lineWidth: 1 }).setData(maData('ma75', '#9b59b6'))
    candleChart.addSeries(LineSeries, { color: '#1abc9c', lineWidth: 1 }).setData(maData('ma200', '#1abc9c'))
    candleChart.timeScale().fitContent()
    candleChartRef.current = candleChart

    // RSIチャート
    const rsiChart = createChart(rsiRef.current, { ...chartOpts, height: 140 })
    const rsiSeries = rsiChart.addSeries(LineSeries, { color: '#e67e22', lineWidth: 2 })
    rsiSeries.setData(
      technicals
        .filter(t => t.rsi_14 != null)
        .map(t => ({ time: t.trade_date as `${number}-${number}-${number}`, value: t.rsi_14! }))
    )
    rsiChart.addSeries(LineSeries, { color: '#e74c3c', lineWidth: 1, lineStyle: 2 })
      .setData(prices.map(p => ({ time: p.trade_date as `${number}-${number}-${number}`, value: 70 })))
    rsiChart.addSeries(LineSeries, { color: '#3498db', lineWidth: 1, lineStyle: 2 })
      .setData(prices.map(p => ({ time: p.trade_date as `${number}-${number}-${number}`, value: 30 })))
    rsiChart.timeScale().fitContent()
    rsiChartRef.current = rsiChart

    // MACDチャート
    const macdChart = createChart(macdRef.current, { ...chartOpts, height: 140 })
    macdChart.addSeries(LineSeries, { color: '#2980b9', lineWidth: 2 }).setData(
      technicals.filter(t => t.macd != null)
        .map(t => ({ time: t.trade_date as `${number}-${number}-${number}`, value: t.macd! }))
    )
    macdChart.addSeries(LineSeries, { color: '#e74c3c', lineWidth: 1 }).setData(
      technicals.filter(t => t.macd_signal != null)
        .map(t => ({ time: t.trade_date as `${number}-${number}-${number}`, value: t.macd_signal! }))
    )
    macdChart.addSeries(HistogramSeries, { color: '#2ecc71' }).setData(
      technicals.filter(t => t.macd_hist != null)
        .map(t => ({
          time: t.trade_date as `${number}-${number}-${number}`,
          value: t.macd_hist!,
          color: t.macd_hist! >= 0 ? '#e74c3c' : '#3498db',
        }))
    )
    macdChart.timeScale().fitContent()
    macdChartRef.current = macdChart

    return () => {
      candleChart.remove()
      rsiChart.remove()
      macdChart.remove()
    }
  }, [prices, technicals])

  const isLoading = pricesLoading || techLoading
  const latestTech = technicals?.[technicals.length - 1]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Space>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>戻る</Button>
        <Button onClick={() => navigate(`/stocks/${code}`)}>銘柄詳細</Button>
      </Space>

      <Card>
        <Row gutter={16} align="middle">
          <Col>
            <Title level={4} style={{ margin: 0 }}>
              {detail?.company_name_ja ?? code}
              <Tag style={{ marginLeft: 8 }}>{code}</Tag>
            </Title>
          </Col>
          <Col flex="auto" />
          <Col>
            <Segmented
              options={PERIOD_OPTIONS.map(o => ({ label: o.label, value: o.value }))}
              value={days}
              onChange={v => setDays(v as number)}
            />
          </Col>
        </Row>
      </Card>

      {latestTech && (
        <Row gutter={16}>
          {[
            { title: 'RSI (14)', value: latestTech.rsi_14?.toFixed(1) ?? '-' },
            { title: 'MACD', value: latestTech.macd?.toFixed(2) ?? '-' },
            { title: 'BB上限', value: latestTech.bb_upper?.toFixed(0) ?? '-' },
            { title: 'BB中央', value: latestTech.bb_mid?.toFixed(0) ?? '-' },
            { title: 'BB下限', value: latestTech.bb_lower?.toFixed(0) ?? '-' },
            { title: 'MA25', value: latestTech.ma25?.toFixed(0) ?? '-' },
            { title: 'MA75', value: latestTech.ma75?.toFixed(0) ?? '-' },
            { title: 'MA200', value: latestTech.ma200?.toFixed(0) ?? '-' },
          ].map(item => (
            <Col span={3} key={item.title}>
              <Card size="small">
                <Statistic title={item.title} value={item.value} />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {isLoading ? (
        <Spin size="large" style={{ display: 'block', marginTop: 80 }} />
      ) : (
        <Card>
          <div style={{ marginBottom: 4 }}>
            <Tag color="orange">MA25</Tag>
            <Tag color="purple">MA75</Tag>
            <Tag color="cyan">MA200</Tag>
          </div>
          <div ref={candleRef} />
          <div style={{ marginTop: 8, borderTop: '1px solid #f0f0f0', paddingTop: 4 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>RSI(14)</Typography.Text>
          </div>
          <div ref={rsiRef} />
          <div style={{ marginTop: 8, borderTop: '1px solid #f0f0f0', paddingTop: 4 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>MACD / Signal / Histogram</Typography.Text>
          </div>
          <div ref={macdRef} />
        </Card>
      )}
    </div>
  )
}
