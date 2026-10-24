import { LinkOutlined } from '@ant-design/icons';
import type { ProLayoutProps, SettingDrawerProps } from '@ant-design/pro-components';
import { SettingDrawer } from '@ant-design/pro-components';
import type { RequestConfig, RunTimeLayoutConfig } from '@umijs/max';
import { history, Link } from '@umijs/max';
import { ConfigProvider, theme as antdTheme } from 'antd';
import type { ThemeConfig } from 'antd';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';
import relativeTime from 'dayjs/plugin/relativeTime';
import React from 'react';

// Initialize dayjs plugins globally
dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

import {
  AvatarDropdown,
  ErrorBoundary,
  OfflineBanner,
} from '@/components';
import { GlobalTerminalBar } from '@/features/terminal/GlobalTerminalBar';
import { MarketProvider } from '@/features/terminal/MarketContext';
import { currentUser as queryCurrentUser } from '@/services/ant-design-pro/api';
import defaultSettings from '../config/defaultSettings';
import { errorConfig } from './requestErrorConfig';

type TerminalLayoutSettings = Partial<ProLayoutProps>;

const isDev = process.env.NODE_ENV === 'development';
const loginPath = '/user/login';
const darkLayoutToken = {
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
    colorBgCollapsedButton: '#151C27',
    colorTextCollapsedButton: '#8B949E',
    colorTextCollapsedButtonHover: '#E6EDF3',
    colorTextMenu: '#8B949E',
    colorTextMenuSelected: '#E6EDF3',
    colorBgMenuItemSelected: '#151C27',
    colorBgMenuItemHover: '#111720',
  },
};
const lightLayoutToken = {
  bgLayout: '#F3F5F8',
  header: {
    colorBgHeader: '#FFFFFF',
    colorHeaderTitle: '#1F2937',
    colorTextMenu: '#4B5563',
    colorTextMenuSelected: '#111827',
    colorBgMenuItemSelected: '#EAF2FF',
    colorBgMenuItemHover: '#F3F6FA',
  },
  sider: {
    colorMenuBackground: '#FFFFFF',
    colorBgCollapsedButton: '#FFFFFF',
    colorTextCollapsedButton: '#667085',
    colorTextCollapsedButtonHover: '#111827',
    colorTextMenu: '#4B5563',
    colorTextMenuSelected: '#111827',
    colorBgMenuItemSelected: '#EAF2FF',
    colorBgMenuItemHover: '#F3F6FA',
  },
};
const darkAntdTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
  token: {
    colorBgBase: '#07090D',
    colorBgContainer: '#111720',
    colorBgElevated: '#151C27',
    colorBorder: '#252B36',
    colorBorderSecondary: '#1C2430',
    colorFillQuaternary: '#151C27',
    colorPrimary: '#4DA3FF',
    colorSuccess: '#F25F5C',
    colorError: '#45C46A',
    colorWarning: '#D6A84F',
    colorText: '#E6EDF3',
    colorTextSecondary: '#8B949E',
    colorTextTertiary: '#6E7681',
    borderRadius: 3,
    fontFamily: 'AlibabaSans, sans-serif',
    fontSize: 12,
    controlHeight: 28,
    controlHeightSM: 24,
  },
  components: {
    Card: {
      borderRadiusLG: 3,
      paddingLG: 12,
    },
    Table: {
      cellPaddingBlockSM: 4,
      cellPaddingInlineSM: 8,
      headerBg: '#151C27',
      headerColor: '#8B949E',
      rowHoverBg: '#151C27',
    },
    Tabs: {
      cardBg: '#111720',
      horizontalMargin: '0 0 8px 0',
    },
  },
};
const lightAntdTheme: ThemeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    colorBgBase: '#F3F5F8',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBorder: '#D8DEE8',
    colorBorderSecondary: '#E5E9F0',
    colorFillQuaternary: '#F7F9FC',
    colorPrimary: '#1668DC',
    colorSuccess: '#D92D20',
    colorError: '#16A34A',
    colorWarning: '#B7791F',
    colorText: '#111827',
    colorTextSecondary: '#667085',
    colorTextTertiary: '#8A94A6',
    borderRadius: 3,
    fontFamily: 'AlibabaSans, sans-serif',
    fontSize: 12,
    controlHeight: 28,
    controlHeightSM: 24,
  },
  components: {
    Card: {
      borderRadiusLG: 3,
      paddingLG: 12,
    },
    Table: {
      cellPaddingBlockSM: 4,
      cellPaddingInlineSM: 8,
      headerBg: '#F7F9FC',
      headerColor: '#667085',
      rowHoverBg: '#F3F6FA',
    },
    Tabs: {
      cardBg: '#FFFFFF',
      horizontalMargin: '0 0 8px 0',
    },
  },
};
const demoUser: API.CurrentUser = {
  name: '量化研究员',
  avatar: '/logo.svg',
  userid: 'demo-quant-user',
  email: 'research@ai-quant-terminal.local',
  title: '模拟交易工作区',
  group: 'AI Quant Terminal',
  access: 'admin',
};

const getTerminalThemeMode = (settings?: TerminalLayoutSettings) =>
  settings?.navTheme === 'light' ? 'light' : 'dark';

const getRuntimeSettings = (
  settings?: TerminalLayoutSettings,
): TerminalLayoutSettings => {
  const themeMode = getTerminalThemeMode(settings);

  return {
    ...defaultSettings,
    ...settings,
    navTheme: themeMode === 'dark' ? 'realDark' : 'light',
    token: themeMode === 'dark' ? darkLayoutToken : lightLayoutToken,
  };
};

const TerminalThemeProvider = ({
  settings,
  children,
}: {
  settings?: TerminalLayoutSettings;
  children: React.ReactNode;
}) => {
  const themeMode = getTerminalThemeMode(settings);

  React.useEffect(() => {
    document.documentElement.dataset.aqtTheme = themeMode;
  }, [themeMode]);

  return (
    <ConfigProvider theme={themeMode === 'dark' ? darkAntdTheme : lightAntdTheme}>
      {children}
    </ConfigProvider>
  );
};

/**
 * @see https://umijs.org/docs/api/runtime-config#getinitialstate
 * */
export async function getInitialState(): Promise<{
  settings?: TerminalLayoutSettings;
  currentUser?: API.CurrentUser;
  loading?: boolean;
  fetchUserInfo?: () => Promise<API.CurrentUser | undefined>;
  settingDrawerOpen?: boolean;
}> {
  const fetchUserInfo = async () => {
    try {
      const msg = await queryCurrentUser({
        skipErrorHandler: true,
      });
      return msg.data;
    } catch (_error) {
      return demoUser;
    }
  };
  // 如果不是登录页面，执行
  const { location } = history;
  if (
    ![loginPath, '/user/register', '/user/register-result'].includes(
      location.pathname,
    )
  ) {
    const currentUser = await fetchUserInfo();
    return {
      fetchUserInfo,
      currentUser,
      settings: defaultSettings as TerminalLayoutSettings,
      settingDrawerOpen: false,
    };
  }
  return {
    fetchUserInfo,
    settings: defaultSettings as TerminalLayoutSettings,
    settingDrawerOpen: false,
  };
}

// ProLayout 支持的api https://procomponents.ant.design/components/layout
export const layout: RunTimeLayoutConfig = ({
  initialState,
  setInitialState,
}) => {
  const runtimeSettings = getRuntimeSettings(initialState?.settings);

  return {
    menuItemRender: (item, dom) => {
      if (item.path) {
        return (
          <Link to={item.path} prefetch>
            {dom}
          </Link>
        );
      }
      return dom;
    },
    actionsRender: () => {
      // 顶栏不在 childrenRender 内，需同步注入正文使用的同一套主题。
      return [
        <ConfigProvider
          key="terminal-bar"
          theme={getTerminalThemeMode(runtimeSettings) === 'dark' ? darkAntdTheme : lightAntdTheme}
        >
          <GlobalTerminalBar />
        </ConfigProvider>,
      ];
    },
    avatarProps: {
      src: initialState?.currentUser?.avatar,
      title: initialState?.currentUser?.name,
      render: (_, avatarChildren) => (
        <AvatarDropdown>{avatarChildren}</AvatarDropdown>
      ),
    },
    // waterMarkProps: {
    //   content: initialState?.currentUser?.name,
    // },
    footerRender: false,
    onPageChange: () => {
      const { location } = history;
      // 如果没有登录，重定向到 login
      if (!initialState?.currentUser && location.pathname !== loginPath) {
        history.replace(
          `${loginPath}?redirect=${encodeURIComponent(location.pathname + location.search + location.hash)}`,
        );
      }
    },
    bgLayoutImgList: [],
    links: isDev
      ? [
          <Link key="openapi" to="/umi/plugin/openapi" target="_blank">
            <LinkOutlined />
            <span>OpenAPI 文档</span>
          </Link>,
        ]
      : [],
    // Replace ProLayout's default ErrorBoundary with our offline-aware version,
    // so chunk load errors show friendly messages instead of "Something went wrong."
    ErrorBoundary,
    menuHeaderRender: undefined,
    // 自定义 403 页面
    // unAccessible: <div>unAccessible</div>,
    // 增加一个 loading 的状态
    childrenRender: (children) => {
      // if (initialState?.loading) return <PageLoading />;
      return (
        <TerminalThemeProvider settings={runtimeSettings}>
          {children}
          <SettingDrawer
            disableUrlParams
            enableDarkTheme
            collapse={initialState?.settingDrawerOpen}
            onCollapseChange={(open) => {
              setInitialState((s) => ({
                ...s,
                settingDrawerOpen: open,
              }));
            }}
            settings={runtimeSettings as SettingDrawerProps['settings']}
            onSettingChange={(settings) => {
              setInitialState((s) => ({
                ...s,
                settings,
              }));
            }}
          />
        </TerminalThemeProvider>
      );
    },
    ...runtimeSettings,
  };
};

/**
 * @name request 配置，可以配置错误处理
 * 它基于 axios 提供了一套统一的网络请求和错误处理方案。
 * @doc https://umijs.org/docs/max/request#配置
 */
export const request: RequestConfig = {
  baseURL: isDev ? '' : 'https://pro-api.ant-design-demo.workers.dev',
  ...errorConfig,
};

export function rootContainer(container: React.ReactNode) {
  return (
    <MarketProvider>
      <OfflineBanner />
      <ErrorBoundary>{container}</ErrorBoundary>
    </MarketProvider>
  );
}
