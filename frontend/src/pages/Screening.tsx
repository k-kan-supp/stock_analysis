import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Card, Form, Row, Col, Select, InputNumber, Button, Table,
  Tag, Space,
} from 'antd'
import { FilterOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { stocksApi } from '../api/client'
import type { ScreeningParams, StockSummary } from '../types/stock'

const MARKET_OPTIONS = [
  { value: 'Prime', label: 'Prime' },
  { value: 'Standard', label: 'Standard' },
  { value: 'Growth', label: 'Growth' },
  { value: 'TOKYO_PRO', label: 'TOKYO PRO' },
]

const SORT_OPTIONS = [
  { value: 'market_cap_jpy', label: '時価総額' },
  { value: 'per_ttm', label: 'PER' },
  { value: 'pbr', label: 'PBR' },
  { value: 'dividend_yield', label: '配当利回り' },
  { value: 'roe', label: 'ROE' },
  { value: 'rsi_14', label: 'RSI' },
]

const fmtCap = (v: number | string | null) => {
  if (v == null) return '-'
  const n = Number(v)
  return n >= 1e12 ? `${(n / 1e12).toFixed(1)}兆` : `${(n / 1e8).toFixed(0)}億`
}

const fmtPct = (v: number | string | null) => (v == null ? '-' : `${(Number(v) * 100).toFixed(2)}%`)

export default function Screening() {
  const [form] = Form.useForm()
  const navigate = useNavigate()
  const [params, setParams] = useState<ScreeningParams>({ limit: 50, offset: 0 })
  const [page, setPage] = useState(1)

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['screening', params],
    queryFn: () => stocksApi.screening(params),
  })

  const handleFilter = (values: ScreeningParams) => {
    setPage(1)
    setParams({ ...values, limit: 50, offset: 0 })
  }

  const handleReset = () => {
    form.resetFields()
    setPage(1)
    setParams({ limit: 50, offset: 0 })
  }

  const columns = [
    {
      title: 'コード',
      dataIndex: 'stock_code',
      width: 80,
      render: (code: string) => (
        <a onClick={() => navigate(`/stocks/${code}`)}>{code}</a>
      ),
    },
    { title: '銘柄名', dataIndex: 'company_name_ja', ellipsis: true, width: 160 },
    {
      title: '市場',
      dataIndex: 'market_section',
      width: 90,
      render: (v: string | null) => v ? <Tag>{v}</Tag> : '-',
    },
    { title: '時価総額', dataIndex: 'market_cap_jpy', render: fmtCap, width: 100 },
    {
      title: '株価',
      dataIndex: 'price_latest',
      width: 90,
      render: (v: number | null) => v?.toLocaleString('ja-JP', { style: 'currency', currency: 'JPY' }) ?? '-',
    },
    { title: 'PER', dataIndex: 'per_ttm', render: (v: number | string | null) => v == null ? '-' : Number(v).toFixed(1), width: 70 },
    { title: 'PBR', dataIndex: 'pbr', render: (v: number | string | null) => v == null ? '-' : Number(v).toFixed(2), width: 70 },
    { title: '配当利回り', dataIndex: 'dividend_yield', render: fmtPct, width: 100 },
    { title: 'ROE', dataIndex: 'roe', render: fmtPct, width: 80 },
    {
      title: 'RSI(14)',
      dataIndex: 'rsi_14',
      width: 80,
      render: (v: number | string | null) => {
        if (v == null) return '-'
        const n = Number(v)
        const color = n >= 70 ? 'red' : n <= 30 ? 'blue' : 'default'
        return <Tag color={color}>{n.toFixed(1)}</Tag>
      },
    },
    {
      title: '',
      key: 'action',
      width: 60,
      render: (_: unknown, record: StockSummary) => (
        <Button size="small" onClick={() => navigate(`/stocks/${record.stock_code}/technical`)}>
          チャート
        </Button>
      ),
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card title={<><FilterOutlined /> スクリーニング条件</>}>
        <Form form={form} layout="vertical" onFinish={handleFilter}>
          <Row gutter={16}>
            <Col span={4}>
              <Form.Item name="market_section" label="市場区分">
                <Select options={MARKET_OPTIONS} placeholder="全市場" allowClear />
              </Form.Item>
            </Col>
            <Col span={3}>
              <Form.Item name="pbr_min" label="PBR 下限">
                <InputNumber min={0} max={100} step={0.1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={3}>
              <Form.Item name="pbr_max" label="PBR 上限">
                <InputNumber min={0} max={100} step={0.1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={3}>
              <Form.Item name="per_min" label="PER 下限">
                <InputNumber min={0} max={500} step={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={3}>
              <Form.Item name="per_max" label="PER 上限">
                <InputNumber min={0} max={500} step={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="dividend_yield_min" label="配当利回り下限 (%)">
                <InputNumber<number> min={0} max={20} step={0.5} style={{ width: '100%' }}
                  formatter={v => `${v}`} parser={(v): number => Number(v) / 100} />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="roe_min" label="ROE下限 (%)">
                <InputNumber<number> min={0} max={100} step={1} style={{ width: '100%' }}
                  formatter={v => `${v}`} parser={(v): number => Number(v) / 100} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={4}>
              <Form.Item name="rsi_min" label="RSI 下限">
                <InputNumber min={0} max={100} step={5} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="rsi_max" label="RSI 上限">
                <InputNumber min={0} max={100} step={5} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={5}>
              <Form.Item name="sort_by" label="ソート">
                <Select options={SORT_OPTIONS} defaultValue="market_cap_jpy" />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="sort_order" label="順序">
                <Select
                  options={[{ value: 'desc', label: '降順' }, { value: 'asc', label: '昇順' }]}
                  defaultValue="desc"
                />
              </Form.Item>
            </Col>
            <Col span={7} style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 24 }}>
              <Space>
                <Button type="primary" htmlType="submit" loading={isFetching}>検索</Button>
                <Button icon={<ReloadOutlined />} onClick={handleReset}>リセット</Button>
              </Space>
            </Col>
          </Row>
        </Form>
      </Card>

      <Card title={`検索結果: ${data?.total ?? 0} 銘柄`}>
        <Table
          dataSource={data?.items}
          columns={columns}
          rowKey="stock_code"
          loading={isLoading}
          size="small"
          scroll={{ x: 900 }}
          pagination={{
            current: page,
            pageSize: 50,
            total: data?.total ?? 0,
            onChange: (p) => {
              setPage(p)
              setParams(prev => ({ ...prev, offset: (p - 1) * 50 }))
            },
          }}
        />
      </Card>
    </div>
  )
}
