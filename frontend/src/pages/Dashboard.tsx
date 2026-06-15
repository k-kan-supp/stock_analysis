import { useQuery } from '@tanstack/react-query'
import { Row, Col, Card, Statistic, Table, Spin } from 'antd'
import { Column, Bar } from '@ant-design/plots'
import { useNavigate } from 'react-router-dom'
import { dashboardApi } from '../api/client'
import type { IndustrySummary } from '../types/stock'

const fmtCap = (v: number | null) =>
  v == null ? '-' : `${(v / 1e12).toFixed(2)}兆円`

const fmtPct = (v: number | null) =>
  v == null ? '-' : `${(v * 100).toFixed(2)}%`

const stockColumns = (navigate: ReturnType<typeof useNavigate>) => [
  {
    title: 'コード',
    dataIndex: 'stock_code',
    render: (code: string) => (
      <a onClick={() => navigate(`/stocks/${code}`)}>{code}</a>
    ),
  },
  { title: '銘柄名', dataIndex: 'company_name_ja', ellipsis: true },
  { title: '時価総額', dataIndex: 'market_cap_jpy', render: fmtCap },
  { title: 'PBR', dataIndex: 'pbr', render: (v: number | null) => v?.toFixed(2) ?? '-' },
  { title: '配当利回り', dataIndex: 'dividend_yield', render: fmtPct },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.summary,
  })

  if (isLoading) return <Spin size="large" style={{ display: 'block', marginTop: 100 }} />

  const byMarketData = (data?.by_market ?? []).map(d => ({
    market: d.market_section ?? 'その他',
    count: d.count,
  }))

  const byIndustryData = (data?.by_industry ?? []).slice(0, 10).map((d: IndustrySummary) => ({
    industry: d.industry_name_ja,
    cap: d.total_market_cap_jpy ? d.total_market_cap_jpy / 1e12 : 0,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic title="上場銘柄数" value={data?.total_stocks} suffix="銘柄" />
          </Card>
        </Col>
        {(data?.by_market ?? []).map(m => (
          <Col span={6} key={m.market_section}>
            <Card>
              <Statistic title={m.market_section} value={m.count} suffix="銘柄" />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        <Col span={10}>
          <Card title="市場区分別銘柄数">
            <Column
              data={byMarketData}
              xField="market"
              yField="count"
              label={{ position: 'top' }}
              height={220}
            />
          </Card>
        </Col>
        <Col span={14}>
          <Card title="業種別時価総額 TOP10 (兆円)">
            <Bar
              data={byIndustryData}
              xField="cap"
              yField="industry"
              height={220}
              label={{ position: 'right', formatter: (d: { cap: number }) => `${d.cap.toFixed(1)}兆` }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={8}>
          <Card title="高配当ランキング">
            <Table
              dataSource={data?.high_dividend}
              columns={stockColumns(navigate)}
              rowKey="stock_code"
              size="small"
              pagination={false}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="52週高値比 上位">
            <Table
              dataSource={data?.top_gainers}
              columns={stockColumns(navigate)}
              rowKey="stock_code"
              size="small"
              pagination={false}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="52週高値比 下位">
            <Table
              dataSource={data?.top_losers}
              columns={stockColumns(navigate)}
              rowKey="stock_code"
              size="small"
              pagination={false}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
