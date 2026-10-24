/**
 * Umi routes for AI Quant Terminal.
 * Keep Ant Design Pro layout infrastructure and expose the seven PRD top-level pages.
 */
export default [
  {
    path: '/user',
    layout: false,
    routes: [
      {
        path: '/user/login',
        name: 'login',
        component: './user/login',
      },
      {
        path: '/user',
        redirect: '/user/login',
      },
      {
        name: '404',
        component: './exception/404',
        path: '/user/*',
      },
    ],
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    icon: 'dashboard',
    component: './dashboard',
  },
  {
    path: '/stock-research',
    name: 'stock-research',
    icon: 'stock',
    component: './stock-research',
  },
  {
    path: '/ai-research',
    name: 'ai-research',
    icon: 'robot',
    component: './ai-research',
  },
  {
    path: '/strategy-lab',
    name: 'strategy-lab',
    icon: 'experiment',
    component: './strategy-lab',
  },
  {
    path: '/backtest',
    name: 'backtest',
    icon: 'lineChart',
    component: './backtest',
  },
  {
    path: '/portfolio',
    name: 'portfolio',
    icon: 'fundProjectionScreen',
    component: './portfolio',
  },
  {
    path: '/monitor',
    name: 'monitor',
    icon: 'monitor',
    component: './monitor',
  },
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    component: './exception/404',
    path: '/*',
  },
];
