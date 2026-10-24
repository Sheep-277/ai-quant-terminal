import { SearchOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { App, AutoComplete, Input } from 'antd';
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { formatDateTime } from './formatters';
import { useMarket } from './MarketContext';
import { TerminalTableText } from './TerminalShared';
import type { StockResearchSnapshot } from './types';

const useLocaleCode = () => {
  const intl = useIntl();
  return intl.locale?.startsWith('en') ? 'en-US' : 'zh-CN';
};

export type StockResearchTarget = Pick<StockResearchSnapshot, 'market' | 'symbol'> & {
  quoteTimestamp?: string | null;
  timezone?: string;
};

export const StockSymbolSelector = ({ researchTarget }: {
  researchTarget?: StockResearchTarget;
}) => {
  const intl = useIntl();
  const locale = useLocaleCode();
  const { market, selectedSymbol, setSelectedSymbol, snapshot } = useMarket();
  // 默认标的只用于展示；不把后端默认值自动保存成用户的主动选择。
  const currentSymbol = selectedSymbol ?? (researchTarget?.market === market ? researchTarget.symbol : undefined);
  // 比较已提交的请求身份，不把尚未提交的输入草稿当作请求标的。
  const targetMismatch = researchTarget && (researchTarget.market !== market
    || (selectedSymbol !== undefined && researchTarget.symbol !== selectedSymbol));
  const quoteTimestamp = researchTarget?.market === market && researchTarget.symbol === currentSymbol
    ? researchTarget.quoteTimestamp
    : undefined;
  const quoteTimeText = quoteTimestamp && Number.isFinite(Date.parse(quoteTimestamp))
    ? formatDateTime(quoteTimestamp, { timezone: researchTarget?.timezone ?? snapshot.timezone, locale })
    : intl.formatMessage({ id: 'terminal.footer.time.unavailable' });
  const { message } = App.useApp();
  const [symbolInput, setSymbolInput] = useState(currentSymbol ?? '');
  const [inputError, setInputError] = useState<'empty' | 'invalid' | null>(null);
  const feedbackId = useId();
  const userEditedInput = useRef(false);
  const previousTarget = useRef({ market, symbol: currentSymbol });
  const symbolOptions = useMemo(
    () =>
      snapshot.watchlist.map((item) => ({
        value: item.symbol,
        label: `${item.symbol} · ${intl.formatMessage({ id: item.nameId })}`,
      })),
    [intl, snapshot.watchlist],
  );
  const searchText = symbolInput.trim().toUpperCase();
  const filteredOptions = symbolOptions.filter(option => option.label.toUpperCase().includes(searchText));
  const hasNoMatch = Boolean(searchText && searchText !== currentSymbol && filteredOptions.length === 0);
  const feedbackKey = inputError ? `terminal.stockSelector.${inputError}`
    : hasNoMatch ? 'terminal.stockSelector.noCandidate' : undefined;

  useEffect(() => {
    // 首次默认标的到达前，用户可能已经开始输入；不要用响应覆盖这份草稿。
    const preserveInitialDraft = userEditedInput.current && selectedSymbol === undefined
      && previousTarget.current.market === market && previousTarget.current.symbol === undefined;
    if (!preserveInitialDraft) {
      setSymbolInput(currentSymbol ?? '');
      setInputError(null);
      userEditedInput.current = false;
    }
    previousTarget.current = { market, symbol: currentSymbol };
  }, [market, currentSymbol, selectedSymbol]);

  const selectSymbol = (symbol: string) => {
    const normalizedSymbol = symbol.trim().toUpperCase();
    if (!normalizedSymbol) {
      setInputError('empty');
      return;
    }
    // 与后端 StockResearchQuery 的字符与长度合同一致，不在前端猜测代码是否存在。
    if (normalizedSymbol.length > 32 || !/^[A-Z0-9.-]+$/.test(normalizedSymbol)) {
      setInputError('invalid');
      return;
    }

    setInputError(null);
    userEditedInput.current = false;
    setSelectedSymbol(normalizedSymbol);
    setSymbolInput(normalizedSymbol);
    void message.success(
      intl.formatMessage({ id: 'terminal.search.selectedSymbol' }, { symbol: normalizedSymbol }),
    );
  };

  return (
    <section className="terminal-stock-selector">
      <div className="terminal-stock-selector-copy">
        <TerminalTableText className="terminal-kicker">
          {intl.formatMessage({ id: 'terminal.stockSelector.kicker' })}
        </TerminalTableText>
        <TerminalTableText className="terminal-stock-selector-title">
          {currentSymbol
            ? intl.formatMessage({ id: 'terminal.stockSelector.title' }, { symbol: currentSymbol })
            : intl.formatMessage({ id: 'terminal.stockSelector.noSelection' })}
        </TerminalTableText>
      </div>
      <AutoComplete
        className="terminal-symbol-search"
        value={symbolInput}
        options={filteredOptions}
        status={inputError ? 'error' : undefined}
        onChange={(value) => { userEditedInput.current = true; setSymbolInput(value); setInputError(null); }}
        onSelect={selectSymbol}
      >
        <Input.Search
          size="small"
          prefix={<SearchOutlined />}
          placeholder={intl.formatMessage({ id: 'terminal.search.placeholder' }, { market })}
          allowClear
          status={inputError ? 'error' : undefined}
          aria-invalid={Boolean(inputError)}
          aria-describedby={feedbackKey ? feedbackId : undefined}
          enterButton={intl.formatMessage({ id: 'terminal.search.submit' })}
          onSearch={(value, _event, info) => {
            // 清除输入只是编辑操作，不提交空代码。
            if (info?.source === 'clear') { setInputError(null); return; }
            selectSymbol(value);
          }}
        />
      </AutoComplete>
      <TerminalTableText className="terminal-header-meta">
        {intl.formatMessage({ id: 'terminal.footer.time.quote' })}
        {' · '}
        <span>{quoteTimeText}</span>
      </TerminalTableText>
      {targetMismatch ? (
        <div className="terminal-stock-selector-feedback" role="status">
          {intl.formatMessage({ id: 'terminal.stockSelector.targetMismatch' }, {
            requestedMarket: market,
            requestedSymbol: selectedSymbol ?? intl.formatMessage({ id: 'terminal.stockSelector.defaultTarget' }),
            actualMarket: researchTarget.market,
            actualSymbol: researchTarget.symbol,
          })}
        </div>
      ) : null}
      {feedbackKey ? (
        <div id={feedbackId} className="terminal-stock-selector-feedback" role={inputError ? 'alert' : 'status'}>
          {intl.formatMessage({ id: feedbackKey })}
        </div>
      ) : null}
    </section>
  );
};
