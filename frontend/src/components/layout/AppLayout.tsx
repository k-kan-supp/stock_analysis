import { Layout, Menu, Input, Typography } from 'antd'
import {
  DashboardOutlined, FilterOutlined, SearchOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'

const { Header, Sider, Content } = Layout
const { Text } = Typography

const NAV_ITEMS = [
  { key: '/', icon: <DashboardOutlined />, label: 'ダッシュボード' },
  { key: '/screening', icon: <FilterOutlined />, label: 'スクリーニング' },
]

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  const handleSearch = (value: string) => {
    if (value.trim()) navigate(`/stocks/${value.trim()}`)
  }

  const selectedKey = NAV_ITEMS.find(item => location.pathname === item.key)?.key ?? '/screening'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={200} theme="dark">
        <div style={{ padding: '16px', borderBottom: '1px solid #303030' }}>
          <Text strong style={{ color: '#fff', fontSize: 16 }}>株式分析</Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={NAV_ITEMS}
          onClick={({ key }) => navigate(key)}
          style={{ marginTop: 8 }}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <Input.Search
            placeholder="銘柄コード (例: 7203)"
            prefix={<SearchOutlined />}
            onSearch={handleSearch}
            style={{ width: 280 }}
            allowClear
          />
        </Header>
        <Content style={{ margin: 24, minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
