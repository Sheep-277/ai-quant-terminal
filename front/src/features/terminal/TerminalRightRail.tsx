import {
  ControlOutlined,
  LineChartOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Collapse, Tag } from 'antd';
import type { ReactNode } from 'react';
import { Panel, TerminalTableText } from './TerminalShared';
import type { TerminalPageKey } from './types';

type RightRailProfile = {
  primaryPanelId: string;
  primaryIcon: ReactNode;
  briefTitleId: string;
  briefBodyId: string;
  focusTagIds: string[];
  checklistTitleId?: string;
  checklistIds: string[];
  showTradingBoundary?: boolean;
};

const rightRailProfiles: Record<TerminalPageKey, RightRailProfile> = {
  dashboard: {
    primaryPanelId: 'terminal.panel.marketAiBrief',
    primaryIcon: <RobotOutlined />,
    briefTitleId: 'terminal.rightRail.dashboard.title',
    briefBodyId: 'terminal.rightRail.dashboard.body',
    focusTagIds: ['terminal.rightRail.focus.index', 'terminal.rightRail.focus.breadth', 'terminal.rightRail.focus.sector'],
    checklistIds: [],
  },
  'stock-research': {
    primaryPanelId: 'terminal.panel.stockResearchBrief',
    primaryIcon: <RobotOutlined />,
    briefTitleId: 'terminal.rightRail.stock.title',
    briefBodyId: 'terminal.rightRail.stock.body',
    focusTagIds: ['terminal.rightRail.focus.symbol', 'terminal.rightRail.focus.valuation', 'terminal.rightRail.focus.factor'],
    checklistTitleId: 'terminal.panel.researchChecklist',
    checklistIds: [
      'terminal.rightRail.checklist.price',
      'terminal.rightRail.checklist.fundamental',
      'terminal.rightRail.checklist.valuation',
      'terminal.rightRail.checklist.risk',
    ],
  },
  'ai-research': {
    primaryPanelId: 'terminal.panel.agentResearchTask',
    primaryIcon: <RobotOutlined />,
    briefTitleId: 'terminal.rightRail.ai.title',
    briefBodyId: 'terminal.rightRail.ai.body',
    focusTagIds: ['terminal.rightRail.focus.task', 'terminal.rightRail.focus.toolCall', 'terminal.rightRail.focus.evidence'],
    checklistIds: [],
  },
  'strategy-lab': {
    primaryPanelId: 'terminal.panel.strategyGuardrails',
    primaryIcon: <ControlOutlined />,
    briefTitleId: 'terminal.rightRail.strategy.title',
    briefBodyId: 'terminal.rightRail.strategy.body',
    focusTagIds: ['terminal.rightRail.focus.universe', 'terminal.rightRail.focus.entryExit', 'terminal.rightRail.focus.riskRule'],
    checklistTitleId: 'terminal.panel.strategyChecklist',
    checklistIds: [
      'terminal.rightRail.checklist.universe',
      'terminal.rightRail.checklist.entryExit',
      'terminal.rightRail.checklist.rebalance',
      'terminal.rightRail.checklist.riskLimit',
    ],
  },
  backtest: {
    primaryPanelId: 'terminal.panel.backtestQuality',
    primaryIcon: <LineChartOutlined />,
    briefTitleId: 'terminal.rightRail.backtest.title',
    briefBodyId: 'terminal.rightRail.backtest.body',
    focusTagIds: ['terminal.rightRail.focus.equityCurve', 'terminal.rightRail.focus.drawdown', 'terminal.rightRail.focus.benchmark'],
    checklistTitleId: 'terminal.panel.backtestChecklist',
    checklistIds: [
      'terminal.rightRail.checklist.noFutureData',
      'terminal.rightRail.checklist.feeSlippage',
      'terminal.rightRail.checklist.benchmark',
      'terminal.rightRail.checklist.sampleSplit',
    ],
  },
  portfolio: {
    primaryPanelId: 'terminal.panel.portfolioRiskBrief',
    primaryIcon: <SafetyCertificateOutlined />,
    briefTitleId: 'terminal.rightRail.portfolio.title',
    briefBodyId: 'terminal.rightRail.portfolio.body',
    focusTagIds: ['terminal.rightRail.focus.paperOrder', 'terminal.rightRail.focus.exposure', 'terminal.rightRail.focus.cash'],
    checklistTitleId: 'terminal.panel.portfolioChecklist',
    checklistIds: [
      'terminal.rightRail.checklist.paperOnly',
      'terminal.rightRail.checklist.cashWeight',
      'terminal.rightRail.checklist.exposure',
      'terminal.rightRail.checklist.preTradeRisk',
    ],
    showTradingBoundary: true,
  },
  monitor: {
    primaryPanelId: 'terminal.panel.streamHealthBrief',
    primaryIcon: <ControlOutlined />,
    briefTitleId: 'terminal.rightRail.monitor.title',
    briefBodyId: 'terminal.rightRail.monitor.body',
    focusTagIds: ['terminal.rightRail.focus.heartbeat', 'terminal.rightRail.focus.latency', 'terminal.rightRail.focus.signalEvidence'],
    checklistTitleId: 'terminal.panel.monitorChecklist',
    checklistIds: [
      'terminal.rightRail.checklist.heartbeat',
      'terminal.rightRail.checklist.latency',
      'terminal.rightRail.checklist.signalEvidence',
      'terminal.rightRail.checklist.reconnect',
    ],
  },
};

const RightRailChecklist = ({ itemIds }: { itemIds: string[] }) => {
  const intl = useIntl();

  return (
    <div className="terminal-right-checklist">
      {itemIds.map((itemId, index) => (
        <div className="terminal-right-checklist-row" key={itemId}>
          <span>{String(index + 1).padStart(2, '0')}</span>
          <TerminalTableText>{intl.formatMessage({ id: itemId })}</TerminalTableText>
        </div>
      ))}
    </div>
  );
};

export const StrategyGuardrails = () => {
  const intl = useIntl();
  const profile = rightRailProfiles['strategy-lab'];
  return (
    <Collapse
      className="terminal-strategy-guardrails"
      ghost
      size="small"
      items={[{
        key: 'guardrails',
        label: intl.formatMessage({ id: profile.primaryPanelId }),
        children: (
          <>
            <p className="terminal-muted">{intl.formatMessage({ id: profile.briefBodyId })}</p>
            <RightRailChecklist itemIds={profile.checklistIds} />
          </>
        ),
      }]}
    />
  );
};

export const TerminalRightRail = ({ pageKey }: { pageKey: TerminalPageKey }) => {
  const intl = useIntl();
  const profile = rightRailProfiles[pageKey];
  const aiBriefBody = intl.formatMessage({ id: profile.briefBodyId });

  return (
    <div className="terminal-right-rail">
      <Panel
        title={intl.formatMessage({ id: profile.primaryPanelId })}
        icon={profile.primaryIcon}
        className="terminal-right-summary"
      >
        <div className="terminal-ai-brief">
          <TerminalTableText>{intl.formatMessage({ id: profile.briefTitleId })}</TerminalTableText>
          <p title={aiBriefBody}>{aiBriefBody}</p>
          <div className="terminal-right-focus-tags">
            {profile.focusTagIds.map((tagId) => (
              <Tag key={tagId}>{intl.formatMessage({ id: tagId })}</Tag>
            ))}
          </div>
        </div>
        {profile.showTradingBoundary ? (
          <div className="terminal-right-boundary">
            <Tag color="gold" icon={<SafetyCertificateOutlined />}>
              {intl.formatMessage({ id: 'terminal.paperTradingOnly' })}
            </Tag>
          </div>
        ) : null}
        {/* 清单是阅读提示；实际评分、任务轨迹和风控结果由页面主体展示。 */}
        {profile.checklistTitleId && profile.checklistIds.length > 0 ? (
          <Collapse
            key={pageKey}
            className="terminal-right-details"
            ghost
            size="small"
            items={[
              {
                key: 'checklist',
                label: intl.formatMessage({ id: profile.checklistTitleId }),
                children: <RightRailChecklist itemIds={profile.checklistIds} />,
              },
            ]}
          />
        ) : null}
      </Panel>
    </div>
  );
};
