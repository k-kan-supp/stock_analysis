import { useQuery } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Descriptions, Row, Col, Tag, Spin, Button,
  Statistic, Tabs, Typography, Space, Divider,
} from 'antd'
import { LineChartOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import { stocksApi } from '../api/client'

const { Title, Link } = Typography

const fmtPct = (v: number | null) => (v == null ? '-' : `${(v * 100).toFixed(2)}%`)
const fmtB = (v: number | null) =>
  v == null ? '-' : v >= 1e12 ? `${(v / 1e12).toFixed(2)}兆円` : `${(v / 1e8).toFixed(1)}億円`
const fmt = (v: number | null, digits = 2) => (v == null ? '-' : v.toFixed(digits))

export default function StockDetail() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['stock', code],
    queryFn: () => stocksApi.getDetail(code!),
    enabled: !!code,
  })

  if (isLoading) return <Spin size="large" style={{ display: 'block', marginTop: 100 }} />
  if (!data) return <div>銘柄が見つかりません</div>

  const tabItems = [
    {
      key: 'valuation',
      label: 'バリュエーション',
      children: (
        <Row gutter={16}>
          {[
            { title: 'PER (実績)', value: fmt(data.per_ttm) },
            { title: 'PER (予想)', value: fmt(data.per_fwd) },
            { title: 'PBR', value: fmt(data.pbr, 3) },
            { title: 'PSR', value: fmt(data.psr, 3) },
            { title: 'EV/EBITDA', value: fmt(data.ev_ebitda) },
            { title: 'BPS', value: fmt(data.book_value_per_share) },
          ].map(item => (
            <Col span={4} key={item.title}>
              <Card size="small">
                <Statistic title={item.title} value={item.value} />
              </Card>
            </Col>
          ))}
        </Row>
      ),
    },
    {
      key: 'profitability',
      label: '収益性',
      children: (
        <Row gutter={16}>
          {[
            { title: '売上高 (TTM)', value: fmtB(data.revenue_ttm_jpy) },
            { title: '営業利益', value: fmtB(data.operating_income_jpy) },
            { title: '純利益', value: fmtB(data.net_income_jpy) },
            { title: '売上総利益率', value: fmtPct(data.gross_margin) },
            { title: '営業利益率', value: fmtPct(data.operating_margin) },
            { title: '純利益率', value: fmtPct(data.net_margin) },
            { title: 'ROE', value: fmtPct(data.roe) },
            { title: 'ROA', value: fmtPct(data.roa) },
            { title: 'ROIC', value: fmtPct(data.roic) },
          ].map(item => (
            <Col span={4} key={item.title}>
              <Card size="small">
                <Statistic title={item.title} value={item.value} />
              </Card>
            </Col>
          ))}
        </Row>
      ),
    },
    {
      key: 'dividend',
      label: '配当・株主還元',
      children: (
        <Row gutter={16}>
          {[
            { title: '1株配当', value: data.dividend_per_share ? `${data.dividend_per_share}円` : '-' },
            { title: '配当利回り', value: fmtPct(data.dividend_yield) },
            { title: '配当性向', value: fmtPct(data.payout_ratio) },
            { title: '連続増配年数', value: data.consecutive_div_years ? `${data.consecutive_div_years}年` : '-' },
            { title: '総還元利回り', value: fmtPct(data.total_shareholder_yield) },
          ].map(item => (
            <Col span={4} key={item.title}>
              <Card size="small">
                <Statistic title={item.title} value={item.value} />
              </Card>
            </Col>
          ))}
        </Row>
      ),
    },
    {
      key: 'financial_health',
      label: '財務健全性',
      children: (
        <Row gutter={16}>
          {[
            { title: '自己資本比率', value: fmtPct(data.equity_ratio) },
            { title: 'D/Eレシオ', value: fmt(data.debt_to_equity, 3) },
            { title: '流動比率', value: fmt(data.current_ratio, 3) },
            { title: 'Altman Zスコア', value: fmt(data.altman_z_score, 3) },
          ].map(item => (
            <Col span={4} key={item.title}>
              <Card size="small">
                <Statistic title={item.title} value={item.value} />
              </Card>
            </Col>
          ))}
        </Row>
      ),
    },
    {
      key: 'technical',
      label: 'テクニカル',
      children: (
        <Row gutter={16}>
          {[
            { title: '現在株価', value: data.price_latest ? `¥${data.price_latest.toLocaleString()}` : '-' },
            { title: '52週高値', value: data.price_52w_high ? `¥${data.price_52w_high.toLocaleString()}` : '-' },
            { title: '52週安値', value: data.price_52w_low ? `¥${data.price_52w_low.toLocaleString()}` : '-' },
            { title: '52週高値比', value: fmtPct(data.price_vs_52w_high) },
            { title: '25日MA', value: fmt(data.ma25) },
            { title: '75日MA', value: fmt(data.ma75) },
            { title: '200日MA', value: fmt(data.ma200) },
            { title: 'RSI(14)', value: fmt(data.rsi_14) },
            { title: 'ベータ(1年)', value: fmt(data.beta_1y, 3) },
          ].map(item => (
            <Col span={4} key={item.title}>
              <Card size="small">
                <Statistic title={item.title} value={item.value} />
              </Card>
            </Col>
          ))}
        </Row>
      ),
    },
    {
      key: 'esg',
      label: 'ESG・株主',
      children: (
        <Row gutter={16}>
          {[
            { title: 'ESGスコア', value: fmt(data.esg_score) },
            { title: '外国人持株比率', value: fmtPct(data.foreign_ownership_ratio) },
            { title: '機関投資家比率', value: fmtPct(data.institutional_ownership) },
          ].map(item => (
            <Col span={4} key={item.title}>
              <Card size="small">
                <Statistic title={item.title} value={item.value} />
              </Card>
            </Col>
          ))}
        </Row>
      ),
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Space>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>戻る</Button>
        <Button
          type="primary"
          icon={<LineChartOutlined />}
          onClick={() => navigate(`/stocks/${code}/technical`)}
        >
          テクニカルチャート
        </Button>
      </Space>

      <Card>
        <Row gutter={24} align="middle">
          <Col>
            <Title level={3} style={{ margin: 0 }}>
              {data.company_name_ja}
              <Tag style={{ marginLeft: 8 }}>{data.stock_code}</Tag>
              {data.market_section && <Tag color="blue">{data.market_section}</Tag>}
            </Title>
            {data.company_name_en && (
              <Typography.Text type="secondary">{data.company_name_en}</Typography.Text>
            )}
          </Col>
          <Col flex="auto" />
          <Col>
            <Statistic
              title="現在株価"
              value={data.price_latest ?? '-'}
              prefix="¥"
              precision={0}
            />
          </Col>
          <Col>
            <Statistic title="時価総額" value={fmtB(data.market_cap_jpy)} />
          </Col>
        </Row>

        {data.custom_theme_tags && data.custom_theme_tags.length > 0 && (
          <div style={{ marginTop: 12 }}>
            {data.custom_theme_tags.map(tag => (
              <Tag key={tag} color="geekblue">{tag}</Tag>
            ))}
          </div>
        )}

        <Divider />

        <Descriptions size="small" column={4}>
          <Descriptions.Item label="決算月">{data.fiscal_year_end ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="従業員数">{data.employee_count?.toLocaleString() ?? '-'}名</Descriptions.Item>
          <Descriptions.Item label="上場日">{data.listing_date ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="IRサイト">
            {data.website_url
              ? <Link href={data.website_url} target="_blank">リンク</Link>
              : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  )
}
