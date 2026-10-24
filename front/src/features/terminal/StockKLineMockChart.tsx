import { ArrowLeftOutlined, ArrowRightOutlined, MinusOutlined, PlusOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Tooltip } from 'antd';
import { useMemo, useState } from 'react';
import { DataSourceBadge } from './DataSourceBadge';
import { formatDateTime, formatNumber } from './formatters';
import { GlossaryTerm } from './glossary';
import { terminalTheme } from './theme';
import type { KLinePoint, StockMarketDataSourceStatus } from './types';

const chartWidth = 720;
const chartHeight = 286;
const plotLeft = 14;
const plotRight = 646;
const priceTop = 24;
const priceBottom = 196;
const volumeTop = 218;
const volumeBottom = 254;
const minVisibleBars = 12;
const defaultVisibleBars = 36;

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const isValidKLineSeries = (bars: KLinePoint[]): boolean => bars.every((bar, index) => {
  const timestamp = Date.parse(bar.timestamp);
  // 不排序、补值或丢弃异常行情，防止图形与实际收到的数据不一致。
  return Number.isFinite(timestamp)
    && (index === 0 || timestamp > Date.parse(bars[index - 1].timestamp))
    && [bar.open, bar.high, bar.low, bar.close].every(value => Number.isFinite(value) && value > 0)
    && bar.low <= Math.min(bar.open, bar.close)
    && bar.high >= Math.max(bar.open, bar.close)
    && Number.isFinite(bar.volume) && bar.volume >= 0;
});

const buildChartGeometry = (bars: KLinePoint[]) => {
  if (bars.length === 0) return null;
  const prices = bars.flatMap((bar) => [bar.open, bar.high, bar.low, bar.close]);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const pricePadding = (maxPrice - minPrice || 1) * 0.08;
  const paddedMinPrice = minPrice - pricePadding;
  const paddedMaxPrice = maxPrice + pricePadding;
  const maxVolume = Math.max(...bars.map((bar) => bar.volume));
  const priceRange = paddedMaxPrice - paddedMinPrice || 1;
  const volumeRange = maxVolume || 1;
  const plotWidth = plotRight - plotLeft;
  const candleWidth = Math.max(5, Math.min(13, plotWidth / Math.max(bars.length, 1) / 2.4));

  const xAt = (index: number) => (bars.length <= 1 ? plotLeft + plotWidth / 2 : plotLeft + (index / (bars.length - 1)) * plotWidth);
  const yAtPrice = (price: number) => priceBottom - ((price - paddedMinPrice) / priceRange) * (priceBottom - priceTop);
  const yAtVolume = (volume: number) => volumeBottom - (volume / volumeRange) * (volumeBottom - volumeTop);
  const priceTicks = Array.from({ length: 5 }, (_, index) => {
    const ratio = index / 4;
    const value = paddedMaxPrice - (paddedMaxPrice - paddedMinPrice) * ratio;
    return {
      value,
      y: yAtPrice(value),
    };
  });

  return {
    candleWidth,
    maxVolume,
    priceTicks,
    xAt,
    yAtPrice,
    yAtVolume,
  };
};

export const StockKLineMockChart = ({
  bars: inputBars,
  dataSource,
  timezone,
}: {
  bars: KLinePoint[];
  dataSource: StockMarketDataSourceStatus;
  timezone: string;
}) => {
  const intl = useIntl();
  const invalidData = useMemo(() => !isValidKLineSeries(inputBars), [inputBars]);
  const bars = invalidData ? [] : inputBars;
  // 区分接口明确不可用与正常空序列，不把读取失败解释为没有历史行情。
  const emptyMessageId = invalidData ? 'terminal.chart.invalidData'
    : dataSource.dataStatus === 'unavailable' ? 'terminal.chart.emptyUnavailable'
      : 'terminal.chart.empty';
  const [visibleBars, setVisibleBars] = useState(defaultVisibleBars);
  // 未手动平移时跟随最新样本，首次加载为空也不会停留在历史起点。
  const [endIndex, setEndIndex] = useState<number | null>(null);
  const normalizedVisibleBars = clamp(visibleBars, Math.min(minVisibleBars, bars.length), bars.length);
  const normalizedEndIndex = clamp(endIndex ?? bars.length - 1, normalizedVisibleBars - 1, Math.max(bars.length - 1, 0));
  const startIndex = Math.max(0, normalizedEndIndex - normalizedVisibleBars + 1);
  const visibleData = bars.slice(startIndex, normalizedEndIndex + 1);
  const geometry = useMemo(() => buildChartGeometry(visibleData), [visibleData]);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const hoveredBar = hoverIndex === null ? null : visibleData[hoverIndex];
  const tickStep = Math.max(1, Math.floor(visibleData.length / 4));
  const xAxisTicks = visibleData
    .map((bar, index) => ({ bar, index }))
    .filter((_, index) => index % tickStep === 0 || index === visibleData.length - 1);

  const zoom = (direction: 'in' | 'out') => {
    if (!bars.length) return;
    setHoverIndex(null);
    const step = direction === 'in' ? -6 : 6;
    const nextVisibleBars = clamp(normalizedVisibleBars + step, Math.min(minVisibleBars, bars.length), bars.length);
    setVisibleBars(nextVisibleBars);
    setEndIndex((current) => current === null ? null : clamp(current, nextVisibleBars - 1, bars.length - 1));
  };

  const pan = (direction: 'left' | 'right') => {
    if (!bars.length) return;
    setHoverIndex(null);
    const step = Math.max(3, Math.floor(normalizedVisibleBars / 4));
    setEndIndex((current) =>
      clamp(
        (current ?? bars.length - 1) + (direction === 'left' ? -step : step),
        normalizedVisibleBars - 1,
        bars.length - 1,
      ),
    );
  };

  return (
    <section
      className="terminal-chart"
      aria-label={intl.formatMessage({ id: 'terminal.chart.aria' })}
      onWheel={(event) => {
        if (!bars.length) return;
        event.preventDefault();
        zoom(event.deltaY > 0 ? 'out' : 'in');
      }}
    >
      <div className="terminal-chart-toolbar">
        <div className="terminal-chart-title">
          <span>{intl.formatMessage({ id: 'terminal.chart.klineContainer' })}</span>
          <DataSourceBadge className="terminal-status-tag" labelId="terminal.dataSource.kline" source={dataSource} />
        </div>
        <div className="terminal-chart-actions">
          <Tooltip title={intl.formatMessage({ id: 'terminal.chart.panLeft' })} trigger={['hover', 'focus']}>
            <span>
              <button type="button" aria-label={intl.formatMessage({ id: 'terminal.chart.panLeft' })} onClick={() => pan('left')} disabled={startIndex === 0}>
                <ArrowLeftOutlined aria-hidden="true" />
              </button>
            </span>
          </Tooltip>
          <Tooltip title={intl.formatMessage({ id: 'terminal.chart.zoomIn' })} trigger={['hover', 'focus']}>
            <span>
              <button type="button" aria-label={intl.formatMessage({ id: 'terminal.chart.zoomIn' })} onClick={() => zoom('in')} disabled={normalizedVisibleBars <= minVisibleBars}>
                <PlusOutlined aria-hidden="true" />
              </button>
            </span>
          </Tooltip>
          <Tooltip title={intl.formatMessage({ id: 'terminal.chart.zoomOut' })} trigger={['hover', 'focus']}>
            <span>
              <button type="button" aria-label={intl.formatMessage({ id: 'terminal.chart.zoomOut' })} onClick={() => zoom('out')} disabled={normalizedVisibleBars >= bars.length}>
                <MinusOutlined aria-hidden="true" />
              </button>
            </span>
          </Tooltip>
          <Tooltip title={intl.formatMessage({ id: 'terminal.chart.panRight' })} trigger={['hover', 'focus']}>
            <span>
              <button type="button" aria-label={intl.formatMessage({ id: 'terminal.chart.panRight' })} onClick={() => pan('right')} disabled={normalizedEndIndex >= bars.length - 1}>
                <ArrowRightOutlined aria-hidden="true" />
              </button>
            </span>
          </Tooltip>
        </div>
      </div>
      {geometry ? <div className="terminal-chart-grid" /> : null}
      {geometry ? (
      <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img">
        <title>{intl.formatMessage({ id: 'terminal.chart.title' })}</title>
        <line x1={plotLeft} x2={plotRight} y1={priceBottom} y2={priceBottom} className="terminal-chart-axis-line" />
        <line x1={plotRight} x2={plotRight} y1={priceTop} y2={volumeBottom} className="terminal-chart-axis-line" />
        <line x1={plotLeft} x2={plotRight} y1={volumeTop} y2={volumeTop} className="terminal-chart-volume-divider" />
        <text x={plotLeft} y={volumeTop - 7} className="terminal-chart-axis-label">
          {intl.formatMessage({ id: 'terminal.chart.volume' })}
        </text>
        {geometry.priceTicks.map((tick) => (
          <g key={tick.value}>
            <line x1={plotLeft} x2={plotRight} y1={tick.y} y2={tick.y} className="terminal-chart-grid-line" />
            <text x={plotRight + 8} y={tick.y + 4} className="terminal-chart-axis-label">
              {formatNumber(tick.value, { maximumFractionDigits: 2 }, intl.locale)}
            </text>
          </g>
        ))}
        <text x={plotRight + 8} y={volumeBottom - 3} className="terminal-chart-axis-label">
          {formatNumber(geometry.maxVolume, { notation: 'compact', maximumFractionDigits: 1 }, intl.locale)}
        </text>
        {xAxisTicks.map(({ bar, index }) => (
          <text key={`${bar.timestamp}-${index}`} x={geometry.xAt(index)} y={chartHeight - 9} textAnchor="middle" className="terminal-chart-axis-label">
            {formatDateTime(bar.timestamp, { locale: intl.locale, timezone, pattern: 'MM/dd' })}
          </text>
        ))}
        {visibleData.map((bar, index) => {
          const x = geometry.xAt(index);
          const positive = bar.close >= bar.open;
          const color = positive ? terminalTheme.positiveColor : terminalTheme.negativeColor;
          const openY = geometry.yAtPrice(bar.open);
          const closeY = geometry.yAtPrice(bar.close);
          const highY = geometry.yAtPrice(bar.high);
          const lowY = geometry.yAtPrice(bar.low);
          const candleTop = Math.min(openY, closeY);
          const candleHeight = Math.max(Math.abs(closeY - openY), 2);
          const volumeY = geometry.yAtVolume(bar.volume);

          return (
            <g
              key={bar.timestamp}
              onMouseEnter={() => setHoverIndex(index)}
              onMouseLeave={() => setHoverIndex(null)}
            >
              <rect x={x - 9} y={priceTop} width={18} height={volumeBottom - priceTop} fill="transparent" />
              <line x1={x} x2={x} y1={highY} y2={lowY} stroke={color} strokeWidth="1" />
              <rect x={x - geometry.candleWidth / 2} y={candleTop} width={geometry.candleWidth} height={candleHeight} fill={color} opacity="0.92" />
              <rect x={x - geometry.candleWidth / 2} y={volumeY} width={geometry.candleWidth} height={volumeBottom - volumeY} fill={color} opacity="0.34" />
            </g>
          );
        })}
        {hoverIndex !== null && hoveredBar ? (
          <line x1={geometry.xAt(hoverIndex)} x2={geometry.xAt(hoverIndex)} y1={priceTop} y2={volumeBottom} className="terminal-chart-crosshair" />
        ) : null}
      </svg>
      ) : (
        <div className="terminal-chart-empty" role="status">
          {intl.formatMessage({ id: emptyMessageId })}
        </div>
      )}
      {bars.length > 0 && (dataSource.fallbackActive || dataSource.dataStatus === 'unavailable' || bars.length < minVisibleBars) ? (
        <div className="terminal-chart-notice" role="status">
          {intl.formatMessage({
            id: dataSource.fallbackActive ? 'terminal.chart.fallback'
              : dataSource.dataStatus === 'unavailable' ? 'terminal.chart.unavailable'
                : 'terminal.chart.limited',
          }, { count: formatNumber(bars.length, {}, intl.locale) })}
        </div>
      ) : null}
      <div className="terminal-chart-footer">
        <span>
          {bars.length > 0 ? intl.formatMessage(
            { id: 'terminal.chart.visibleRange' },
            {
              visible: formatNumber(visibleData.length, { maximumFractionDigits: 0 }, intl.locale),
              total: formatNumber(bars.length, { maximumFractionDigits: 0 }, intl.locale),
            },
          ) : null}
        </span>
        <span>
          <GlossaryTerm term="RSI" /> / <GlossaryTerm term="MACD" />
        </span>
      </div>
      {hoveredBar ? (
        <div className="terminal-chart-tooltip">
          <strong>{formatDateTime(hoveredBar.timestamp, { locale: intl.locale, timezone })}</strong>
          <span>{timezone}</span>
          <span>O {formatNumber(hoveredBar.open, {}, intl.locale)}</span>
          <span>H {formatNumber(hoveredBar.high, {}, intl.locale)}</span>
          <span>L {formatNumber(hoveredBar.low, {}, intl.locale)}</span>
          <span>C {formatNumber(hoveredBar.close, {}, intl.locale)}</span>
          <span>V {formatNumber(hoveredBar.volume, { notation: 'compact', maximumFractionDigits: 1 }, intl.locale)}</span>
        </div>
      ) : null}
    </section>
  );
};
