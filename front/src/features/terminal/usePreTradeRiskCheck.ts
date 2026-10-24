import { useMutation } from '@tanstack/react-query';
import {
  preTradeRiskCheck,
  type PreTradeRiskCheckParams,
} from '@/services/terminal/risk';

export const preTradeRiskCheckMutationKey = ['terminal', 'risk', 'pre-trade-check'];

export const usePreTradeRiskCheck = () => {
  // 下单前风险检查是写式校验请求，用 mutation 承接提交状态和错误状态。
  return useMutation({
    mutationKey: preTradeRiskCheckMutationKey,
    mutationFn: (payload: PreTradeRiskCheckParams) => preTradeRiskCheck(payload),
  });
};
