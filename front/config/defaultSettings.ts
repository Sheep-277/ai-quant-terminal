import type { ProLayoutProps } from '@ant-design/pro-components';

/**
 * @name
 */
const Settings: ProLayoutProps & {
  logo?: string;
} = {
  navTheme: 'realDark',
  colorPrimary: '#4da3ff',
  layout: 'mix',
  contentWidth: 'Fluid',
  fixedHeader: true,
  fixSiderbar: true,
  colorWeak: false,
  title: 'AI Quant Terminal',
  logo: '/logo.svg',
  iconfontUrl: '',
  token: {
    bgLayout: '#07090D',
    header: {
      colorBgHeader: '#0D1117',
      colorHeaderTitle: '#E6EDF3',
      colorTextMenu: '#8B949E',
      colorTextMenuSelected: '#E6EDF3',
      colorBgMenuItemSelected: '#151C27',
      colorBgMenuItemHover: '#111720',
    },
    sider: {
      colorMenuBackground: '#0D1117',
      colorTextMenu: '#8B949E',
      colorTextMenuSelected: '#E6EDF3',
      colorBgMenuItemSelected: '#151C27',
      colorBgMenuItemHover: '#111720',
    },
  },
};

export default Settings;
