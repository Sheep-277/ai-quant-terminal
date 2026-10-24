import { RobotOutlined, StarOutlined } from '@ant-design/icons';
import { getIntl, getLocale } from '@umijs/max';
import { App, Button, Segmented, Tag, Tooltip } from 'antd';
import { formatDateTime } from './formatters';
import { useMarket } from './MarketContext';
import type { MarketCode } from './types';

export const GlobalTerminalBar = () => {
  const intl = getIntl();
  const { market, setMarket, snapshot } = useMarket();
  const { message } = App.useApp();
  const locale = getLocale().startsWith('en') ? 'en-US' : 'zh-CN';

  const showPrototypeMessage = () => {
    void message.info(intl.formatMessage({ id: 'terminal.prototypeOnly' }));
  };
  const marketOptions = [
    { label: intl.formatMessage({ id: 'terminal.marketSwitcher.us' }), value: 'US' },
    { label: intl.formatMessage({ id: 'terminal.marketSwitcher.hk' }), value: 'HK' },
    { label: intl.formatMessage({ id: 'terminal.marketSwitcher.cn' }), value: 'CN' },
  ];

  return (
    <div className="terminal-global-bar">
      <Segmented
        size="small"
        value={market}
        options={marketOptions}
        onChange={(value) => setMarket(value as MarketCode)}
      />
      {/* 全局上下文仍是预置快照，不把样例状态和日期当作实时行情。 */}
      <Tooltip
        trigger={['hover', 'focus']}
        title={
          <>
            {intl.formatMessage({ id: 'terminal.globalBar.sampleNotice' })}
            <br />
            {formatDateTime(snapshot.updatedAt, { timezone: snapshot.timezone, locale })}
            {' · '}{snapshot.timezone}
          </>
        }
      >
        <Tag className="terminal-status-tag" tabIndex={0}>
          {intl.formatMessage({ id: 'terminal.leftRail.source.mock' })}
          {' · '}
          {intl.formatMessage({ id: `terminal.marketStatus.${snapshot.status}` })}
        </Tag>
      </Tooltip>
      <Tooltip title={intl.formatMessage({ id: 'terminal.panel.watchlist' })}>
        <Button size="small" type="text" icon={<StarOutlined />} onClick={showPrototypeMessage} />
      </Tooltip>
      <Tooltip title={intl.formatMessage({ id: 'terminal.aiCopilot' })}>
        <Button size="small" type="text" icon={<RobotOutlined />} onClick={showPrototypeMessage} />
      </Tooltip>
    </div>
  );
};
