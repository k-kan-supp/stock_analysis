import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Row, Col, Spin, Button, Tag, Statistic, Space, Typography, Segmented, Alert,
} from 'antd'
import { ArrowLeftOutlined, ArrowUpOutlined, ArrowDownOutlined, WarningOutlined } from '@ant-design/icons'
import {
  createChart, type IChartApi, type SeriesMarker, type Time,
} from 'lightweight-charts'
import { stocksApi } from '../api/client'
import type { TechnicalDaily } from '../types/stock'

const { Text } = Typography

const PERIOD_OPTIONS = [
  { label: '3ヶ月', value: 90 },
  { label: '6ヶ月', value: 180 },
  { label: '1年', value: 365 },
  { label: '3年', value: 1095 },
  { label: '5年', value: 1825 },
]

const MA_COLORS = {
  ma7:  '#FF6B35',
  ma49: '#9B59B6',
  ma98: '#27AE60',
}

// 3σ バンドの色 (MA と対応させる)
const SIGMA_COLORS = {
  band49: '#9B59B6',  // MA49 と同系色
  band98: '#27AE60',  // MA98 と同系色
}

interface CrossEvent {
  trade_date: string
  type: 'golden' | 'dead'
  pair: '7/49' | '49/98'
}

function detectCrosses(data: TechnicalDaily[]): CrossEvent[] {
  const events: CrossEvent[] = []
  for (let i = 1; i < data.length; i++) {
    const prev = data[i - 1]
    const curr = data[i]

    if (prev.ma7 != null && prev.ma49 != null && curr.ma7 != null && curr.ma49 != null) {
      if (prev.ma7 < prev.ma49 && curr.ma7 >= curr.ma49)
        events.push({ trade_date: curr.trade_date, type: 'golden', pair: '7/49' })
      else if (prev.ma7 > prev.ma49 && curr.ma7 <= curr.ma49)
        events.push({ trade_date: curr.trade_date, type: 'dead', pair: '7/49' })
    }

    if (prev.ma49 != null && prev.ma98 != null && curr.ma49 != null && curr.ma98 != null) {
      if (prev.ma49 < prev.ma98 && curr.ma49 >= curr.ma98)
        events.push({ trade_date: curr.trade_date, type: 'golden', pair: '49/98' })
      else if (prev.ma49 > prev.ma98 && curr.ma49 <= curr.ma98)
        events.push({ trade_date: curr.trade_date, type: 'dead', pair: '49/98' })
    }
  }
  return events
}

export default function Technical() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const [days, setDays] = useState(365)

  const candleRef = useRef<HTMLDivElement>(null)
  const rsiRef    = useRef<HTMLDivElement>(null)
  const macdRef   = useRef<HTMLDivElement>(null)
  const candleChartRef = useRef<IChartApi | null>(null)
  const rsiChartRef    = useRef<IChartApi | null>(null)
  const macdChartRef   = useRef<IChartApi | null>(null)

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
    if (!prices?.length || !technicals?.length) return

    candleChartRef.current?.remove()
    rsiChartRef.current?.remove()
    macdChartRef.current?.remove()

    const chartOpts = {
      layout: { background: { color: '#fff' }, textColor: '#333' },
      grid: { vertLines: { color: '#f0f0f0' }, horzLines: { color: '#f0f0f0' } },
      timeScale: { timeVisible: true },
    }

    // ── キャンドルチャート ────────────────────────────────
    const candleChart = createChart(candleRef.current, { ...chartOpts, height: 420 })

    const candleSeries = candleChart.addCandlestickSeries({
      upColor: '#e74c3c', downColor: '#3498db',
      borderUpColor: '#e74c3c', borderDownColor: '#3498db',
      wickUpColor: '#e74c3c', wickDownColor: '#3498db',
    })
    candleSeries.setData(
      prices.map(p => ({
        time: p.trade_date as Time,
        open: p.open, high: p.high, low: p.low, close: p.close,
      }))
    )

    // MA ライン描画ヘルパー
    const addLine = (key: keyof TechnicalDaily, color: string, width: 1 | 2 = 1, style = 0) => {
      const series = candleChart.addLineSeries({ color, lineWidth: width, lineStyle: style })
      series.setData(
        technicals
          .filter(t => t[key] != null)
          .map(t => ({ time: t.trade_date as Time, value: t[key] as number }))
      )
      return series
    }

    // MA 線
    addLine('ma7',  MA_COLORS.ma7,  2)
    addLine('ma49', MA_COLORS.ma49, 2)
    addLine('ma98', MA_COLORS.ma98, 2)

    // 3σ バンド (破線スタイル: lineStyle=1 は破線)
    addLine('sigma3_upper_49', SIGMA_COLORS.band49, 1, 1)
    addLine('sigma3_lower_49', SIGMA_COLORS.band49, 1, 1)
    addLine('sigma3_upper_98', SIGMA_COLORS.band98, 1, 1)
    addLine('sigma3_lower_98', SIGMA_COLORS.band98, 1, 1)

    // ── マーカー: クロス + 外れ値 ────────────────────────
    const crosses = detectCrosses(technicals)

    // クロスマーカー
    const crossMarkers: SeriesMarker<Time>[] = crosses.map(c => ({
      time: c.trade_date as Time,
      position: c.type === 'golden' ? ('belowBar' as const) : ('aboveBar' as const),
      color:    c.type === 'golden' ? '#FFD700' : '#4169E1',
      shape:    c.type === 'golden' ? ('arrowUp' as const) : ('arrowDown' as const),
      text:     `${c.type === 'golden' ? 'GC' : 'DC'}(${c.pair})`,
      size: 1,
    }))

    // 外れ値マーカー (3σ 突破)
    const outlierMarkers: SeriesMarker<Time>[] = []
    technicals.forEach(t => {
      // 同日に両方外れ値になる場合は 98日優先で表示
      const out49 = t.is_outlier_49 === true
      const out98 = t.is_outlier_98 === true
      if (!out49 && !out98) return

      // 上抜け・下抜けを終値 vs 上限で判定
      const latest = prices.find(p => p.trade_date === t.trade_date)
      if (!latest) return
      const isAbove =
        (out98 && t.sigma3_upper_98 != null && latest.close > t.sigma3_upper_98) ||
        (out49 && t.sigma3_upper_49 != null && latest.close > t.sigma3_upper_49)

      outlierMarkers.push({
        time:     t.trade_date as Time,
        position: isAbove ? ('aboveBar' as const) : ('belowBar' as const),
        color:    out98 ? '#FF4136' : '#FF851B',
        shape:    ('square' as const),
        text:     out98 ? '⚠98σ' : '⚠49σ',
        size:     1,
      })
    })

    // マーカーをまとめて時系列順にセット
    const allMarkers = [...crossMarkers, ...outlierMarkers]
      .sort((a, b) => ((a.time as string) < (b.time as string) ? -1 : 1))
    candleSeries.setMarkers(allMarkers)

    candleChart.timeScale().fitContent()
    candleChartRef.current = candleChart

    // ── RSI チャート ─────────────────────────────────────
    const rsiChart = createChart(rsiRef.current, { ...chartOpts, height: 140 })
    rsiChart.addLineSeries({ color: '#e67e22', lineWidth: 2 }).setData(
      technicals.filter(t => t.rsi_14 != null)
        .map(t => ({ time: t.trade_date as Time, value: t.rsi_14! }))
    )
    const refLine = (val: number, color: string) =>
      rsiChart.addLineSeries({ color, lineWidth: 1, lineStyle: 2 }).setData(
        prices.map(p => ({ time: p.trade_date as Time, value: val }))
      )
    refLine(70, '#e74c3c')
    refLine(30, '#3498db')
    rsiChart.timeScale().fitContent()
    rsiChartRef.current = rsiChart

    // ── MACD チャート ────────────────────────────────────
    const macdChart = createChart(macdRef.current, { ...chartOpts, height: 140 })
    macdChart.addLineSeries({ color: '#2980b9', lineWidth: 2 }).setData(
      technicals.filter(t => t.macd != null)
        .map(t => ({ time: t.trade_date as Time, value: t.macd! }))
    )
    macdChart.addLineSeries({ color: '#e74c3c', lineWidth: 1 }).setData(
      technicals.filter(t => t.macd_signal != null)
        .map(t => ({ time: t.trade_date as Time, value: t.macd_signal! }))
    )
    macdChart.addHistogramSeries({ color: '#2ecc71' }).setData(
      technicals.filter(t => t.macd_hist != null)
        .map(t => ({
          time: t.trade_date as Time,
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
  const crosses = technicals ? detectCrosses(technicals) : []
  const recentCrosses = [...crosses].reverse().slice(0, 5)

  const isOutlier49 = latestTech?.is_outlier_49 === true
  const isOutlier98 = latestTech?.is_outlier_98 === true

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Space>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>戻る</Button>
        <Button onClick={() => navigate(`/stocks/${code}`)}>銘柄詳細</Button>
      </Space>

      {/* ヘッダー */}
      <Card>
        <Row gutter={16} align="middle">
          <Col>
            <Text strong style={{ fontSize: 18 }}>
              {detail?.company_name_ja ?? code}
              <Tag style={{ marginLeft: 8 }}>{code}</Tag>
            </Text>
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

      {/* 外れ値アラートバナー */}
      {(isOutlier49 || isOutlier98) && (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          message={
            <Space>
              <Text strong>3σ 外れ値を検出</Text>
              {isOutlier98 && (
                <Tag color="red">98日 3σ 突破 (σ={latestTech?.std_98?.toFixed(0)})</Tag>
              )}
              {isOutlier49 && !isOutlier98 && (
                <Tag color="orange">49日 3σ 突破 (σ={latestTech?.std_49?.toFixed(0)})</Tag>
              )}
            </Space>
          }
          description={
            isOutlier98
              ? `98日バンド: ${latestTech?.sigma3_lower_98?.toFixed(0)} 〜 ${latestTech?.sigma3_upper_98?.toFixed(0)}`
              : `49日バンド: ${latestTech?.sigma3_lower_49?.toFixed(0)} 〜 ${latestTech?.sigma3_upper_49?.toFixed(0)}`
          }
        />
      )}

      {/* 指標カード */}
      {latestTech && (
        <>
          {/* MA / RSI / MACD */}
          <Row gutter={12}>
            {(
              [
                { key: 'ma7',    label: 'MA(7)',   color: MA_COLORS.ma7  },
                { key: 'ma49',   label: 'MA(49)',  color: MA_COLORS.ma49 },
                { key: 'ma98',   label: 'MA(98)',  color: MA_COLORS.ma98 },
                { key: 'rsi_14', label: 'RSI(14)', color: '#e67e22'      },
                { key: 'macd',   label: 'MACD',    color: '#2980b9'      },
              ] as { key: keyof TechnicalDaily; label: string; color: string }[]
            ).map(({ key, label, color }) => (
              <Col span={4} key={key}>
                <Card size="small" style={{ borderTop: `3px solid ${color}` }}>
                  <Statistic
                    title={<Text style={{ color, fontSize: 12 }}>{label}</Text>}
                    value={
                      (latestTech[key] as number | null)
                        ?.toFixed(key === 'rsi_14' || key === 'macd' ? 2 : 0) ?? '-'
                    }
                  />
                </Card>
              </Col>
            ))}
          </Row>

          {/* 3σ バンド */}
          <Row gutter={12}>
            {[
              {
                label: '49日 +3σ', value: latestTech.sigma3_upper_49?.toFixed(0) ?? '-',
                color: SIGMA_COLORS.band49, outlier: isOutlier49,
              },
              {
                label: '49日 MA', value: latestTech.ma49?.toFixed(0) ?? '-',
                color: SIGMA_COLORS.band49, outlier: false,
              },
              {
                label: '49日 -3σ', value: latestTech.sigma3_lower_49?.toFixed(0) ?? '-',
                color: SIGMA_COLORS.band49, outlier: isOutlier49,
              },
              {
                label: '49日 σ', value: latestTech.std_49?.toFixed(1) ?? '-',
                color: SIGMA_COLORS.band49, outlier: false,
              },
              {
                label: '98日 +3σ', value: latestTech.sigma3_upper_98?.toFixed(0) ?? '-',
                color: SIGMA_COLORS.band98, outlier: isOutlier98,
              },
              {
                label: '98日 MA', value: latestTech.ma98?.toFixed(0) ?? '-',
                color: SIGMA_COLORS.band98, outlier: false,
              },
              {
                label: '98日 -3σ', value: latestTech.sigma3_lower_98?.toFixed(0) ?? '-',
                color: SIGMA_COLORS.band98, outlier: isOutlier98,
              },
              {
                label: '98日 σ', value: latestTech.std_98?.toFixed(1) ?? '-',
                color: SIGMA_COLORS.band98, outlier: false,
              },
            ].map(item => (
              <Col span={3} key={item.label}>
                <Card
                  size="small"
                  style={{
                    borderTop: `3px solid ${item.color}`,
                    background: item.outlier ? '#fff7e6' : undefined,
                  }}
                >
                  <Statistic
                    title={
                      <Space size={4}>
                        <Text style={{ color: item.color, fontSize: 11 }}>{item.label}</Text>
                        {item.outlier && <WarningOutlined style={{ color: '#fa8c16' }} />}
                      </Space>
                    }
                    value={item.value}
                    valueStyle={item.outlier ? { color: '#fa8c16', fontWeight: 700 } : undefined}
                  />
                </Card>
              </Col>
            ))}
          </Row>
        </>
      )}

      {/* 直近クロス履歴 */}
      {recentCrosses.length > 0 && (
        <Card
          size="small"
          title="直近クロス履歴"
          style={{ borderLeft: '4px solid #FFD700' }}
        >
          <Space wrap>
            {recentCrosses.map((c, i) => (
              <Tag
                key={i}
                color={c.type === 'golden' ? 'gold' : 'blue'}
                icon={c.type === 'golden' ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              >
                {c.trade_date}&nbsp;
                {c.type === 'golden' ? 'ゴールデンクロス' : 'デッドクロス'}
                &nbsp;(MA{c.pair})
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      {/* チャート */}
      {isLoading ? (
        <Spin size="large" style={{ display: 'block', marginTop: 80 }} />
      ) : (
        <Card>
          {/* 凡例 */}
          <Space style={{ marginBottom: 8 }} wrap>
            {[
              { label: 'MA(7)',  color: MA_COLORS.ma7  },
              { label: 'MA(49)', color: MA_COLORS.ma49 },
              { label: 'MA(98)', color: MA_COLORS.ma98 },
            ].map(({ label, color }) => (
              <span key={label} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{
                  display: 'inline-block', width: 20, height: 3,
                  background: color, borderRadius: 2,
                }} />
                <Text style={{ color, fontSize: 12 }}>{label}</Text>
              </span>
            ))}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <span style={{
                display: 'inline-block', width: 20, height: 2,
                background: SIGMA_COLORS.band49, borderRadius: 2,
                borderTop: `2px dashed ${SIGMA_COLORS.band49}`,
              }} />
              <Text style={{ fontSize: 12, color: SIGMA_COLORS.band49 }}>49日 ±3σ</Text>
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <span style={{
                display: 'inline-block', width: 20, height: 2,
                background: SIGMA_COLORS.band98, borderRadius: 2,
                borderTop: `2px dashed ${SIGMA_COLORS.band98}`,
              }} />
              <Text style={{ fontSize: 12, color: SIGMA_COLORS.band98 }}>98日 ±3σ</Text>
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <ArrowUpOutlined style={{ color: '#FFD700' }} />
              <Text style={{ fontSize: 12, color: '#B8860B' }}>GC</Text>
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <ArrowDownOutlined style={{ color: '#4169E1' }} />
              <Text style={{ fontSize: 12, color: '#4169E1' }}>DC</Text>
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <WarningOutlined style={{ color: '#FF4136' }} />
              <Text style={{ fontSize: 12, color: '#FF4136' }}>3σ 外れ値</Text>
            </span>
          </Space>

          <div ref={candleRef} />

          <div style={{ marginTop: 8, borderTop: '1px solid #f0f0f0', paddingTop: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>RSI(14) — 赤点線:70 / 青点線:30</Text>
          </div>
          <div ref={rsiRef} />

          <div style={{ marginTop: 8, borderTop: '1px solid #f0f0f0', paddingTop: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>MACD(12,26,9) / Signal / Histogram</Text>
          </div>
          <div ref={macdRef} />
        </Card>
      )}
    </div>
  )
}
