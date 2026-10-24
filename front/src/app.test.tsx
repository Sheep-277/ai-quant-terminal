import { cleanup, render, screen } from '@testing-library/react';
import { theme } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock all heavy dependencies before importing app
const mockReplace = vi.fn();
const mockHistory = {
  location: {
    pathname: '/welcome',
    search: '',
    hash: '',
  },
  replace: mockReplace,
};

const mockQueryCurrentUser = vi.fn();

vi.mock('@umijs/max', () => ({
  history: mockHistory,
  Link: ({ children }: any) => children,
}));

vi.mock('@/services/ant-design-pro/api', () => ({
  currentUser: mockQueryCurrentUser,
}));

vi.mock('@/components', () => ({
  AvatarDropdown: () => null,
  DocLink: () => null,
  ErrorBoundary: ({ children }: any) => children,
  Footer: () => null,
  LangDropdown: () => null,
  OfflineBanner: () => null,
  VersionDropdown: () => null,
}));

vi.mock('@ant-design/pro-components', () => ({
  SettingDrawer: () => null,
}));

vi.mock('@ant-design/icons', () => ({
  LinkOutlined: () => null,
}));

vi.mock('./requestErrorConfig', () => ({
  errorConfig: {},
}));

vi.mock('../config/defaultSettings', () => ({
  default: { navTheme: 'light' },
}));

vi.mock('@/features/terminal/GlobalTerminalBar', () => ({
  GlobalTerminalBar: () => {
    const { token } = theme.useToken();
    return <div data-testid="header-theme" data-background={token.colorBgContainer} data-text={token.colorText} />;
  },
}));

afterEach(cleanup);

describe('app runtime configuration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHistory.location = {
      pathname: '/welcome',
      search: '',
      hash: '',
    };
  });

  it('should fetch currentUser when not on login page', async () => {
    const { getInitialState } = await import('./app');
    mockQueryCurrentUser.mockResolvedValue({
      data: {
        name: 'Test User',
        access: 'admin',
      },
    });

    const state = await getInitialState();

    expect(mockQueryCurrentUser).toHaveBeenCalled();
    expect(state.currentUser).toEqual({
      name: 'Test User',
      access: 'admin',
    });
    expect(state.settingDrawerOpen).toBe(false);
    expect(state.fetchUserInfo).toBeDefined();
  });

  it('should fall back to the demo user when currentUser fetch fails', async () => {
    const { getInitialState } = await import('./app');
    mockQueryCurrentUser.mockRejectedValue(new Error('401 Unauthorized'));

    const state = await getInitialState();

    expect(mockReplace).not.toHaveBeenCalled();
    expect(state.currentUser).toMatchObject({
      userid: 'demo-quant-user',
      name: '量化研究员',
      access: 'admin',
    });
  });

  it('should not fetch currentUser on login page', async () => {
    const { getInitialState } = await import('./app');
    mockHistory.location = {
      pathname: '/user/login',
      search: '',
      hash: '',
    };

    const state = await getInitialState();

    expect(mockQueryCurrentUser).not.toHaveBeenCalled();
    expect(state.currentUser).toBeUndefined();
    expect(state.fetchUserInfo).toBeDefined();
  });

  it('should encode the full redirect path when layout detects no user', async () => {
    const { layout } = await import('./app');
    mockHistory.location = {
      pathname: '/admin/users',
      search: '?page=2',
      hash: '#section',
    };

    const layoutConfig = layout({
      initialState: {
        currentUser: undefined,
      },
      setInitialState: vi.fn(),
    } as never);
    layoutConfig.onPageChange?.();

    expect(mockReplace).toHaveBeenCalledWith(
      `/user/login?redirect=${encodeURIComponent('/admin/users?page=2#section')}`,
    );
  });

  it('should include default settings in initial state', async () => {
    const { getInitialState } = await import('./app');
    mockQueryCurrentUser.mockResolvedValue({
      data: { name: 'User' },
    });

    const state = await getInitialState();

    expect(state.settings).toEqual({ navTheme: 'light' });
  });

  it('fetchUserInfo should return user data on success', async () => {
    const { getInitialState } = await import('./app');
    mockQueryCurrentUser.mockResolvedValue({
      data: { name: 'Fetched User', access: 'user' },
    });

    const state = await getInitialState();

    const user = await state.fetchUserInfo?.();
    expect(user).toEqual({ name: 'Fetched User', access: 'user' });
  });

  it('keeps header and collapse button colors in sync when switching themes', async () => {
    const { layout } = await import('./app');
    const createLayout = (navTheme: 'light' | 'realDark') => layout({
      initialState: { settings: { navTheme } },
      setInitialState: vi.fn(),
    } as never);
    const lightLayout = createLayout('light');
    const darkLayout = createLayout('realDark');
    const lightActions = lightLayout.actionsRender;
    const darkActions = darkLayout.actionsRender;
    if (typeof lightActions !== 'function' || typeof darkActions !== 'function') {
      throw new Error('顶栏操作区未配置');
    }
    // 顶栏位于正文主题容器之外，单独渲染才能捕获主题遗漏。
    const view = render(lightActions({} as never));
    expect(screen.getByTestId('header-theme')).toHaveAttribute('data-background', '#FFFFFF');
    expect(screen.getByTestId('header-theme')).toHaveAttribute('data-text', '#111827');
    expect(lightLayout.token?.sider).toMatchObject({
      colorBgCollapsedButton: '#FFFFFF',
      colorTextCollapsedButton: '#667085',
      colorTextCollapsedButtonHover: '#111827',
    });

    view.rerender(darkActions({} as never));
    expect(screen.getByTestId('header-theme')).toHaveAttribute('data-background', '#111720');
    expect(screen.getByTestId('header-theme')).toHaveAttribute('data-text', '#E6EDF3');
    expect(darkLayout.token?.sider).toMatchObject({
      colorBgCollapsedButton: '#151C27',
      colorTextCollapsedButton: '#8B949E',
      colorTextCollapsedButtonHover: '#E6EDF3',
    });

    view.rerender(lightActions({} as never));
    expect(screen.getByTestId('header-theme')).toHaveAttribute('data-background', '#FFFFFF');
  });
});
