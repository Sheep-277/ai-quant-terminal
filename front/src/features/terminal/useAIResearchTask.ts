import { useMutation, useQuery } from '@tanstack/react-query';
import {
  checkAIResearchSearchConnection,
  checkAIResearchLLMConnection,
  createAIResearchTask,
  getAIResearchLLMStatus,
  getAIResearchSearchStatus,
  getAIResearchTaskById,
  getAIResearchTaskByPollUrl,
  getAIResearchTask,
  type CreateAIResearchTaskParams,
  type GetAIResearchTaskByIdParams,
  type GetAIResearchTaskByPollUrlParams,
  type GetAIResearchTaskParams,
} from '@/services/terminal/aiResearch';
import type { MarketCode } from './types';

type UseAIResearchTaskParams = GetAIResearchTaskParams & {
  enabled?: boolean;
};

type UseAIResearchTaskByIdParams = GetAIResearchTaskByIdParams & {
  enabled?: boolean;
};

type UseAIResearchTaskByPollUrlParams = GetAIResearchTaskByPollUrlParams & {
  enabled?: boolean;
};

export const aiResearchTaskQueryKey = (market: MarketCode) => [
  'terminal',
  'ai-research',
  market,
];

export const aiResearchTaskByIdQueryKey = (taskId: string) => [
  'terminal',
  'ai-research',
  'task',
  taskId,
];

export const aiResearchTaskByPollUrlQueryKey = (pollUrl: string) => [
  'terminal',
  'ai-research',
  'poll',
  pollUrl,
];

export const aiResearchTaskCreateMutationKey = ['terminal', 'ai-research', 'create'];

export const aiResearchLLMStatusQueryKey = ['terminal', 'ai-research', 'llm-status'];

export const aiResearchLLMCheckMutationKey = ['terminal', 'ai-research', 'llm-check'];

export const aiResearchSearchStatusQueryKey = ['terminal', 'ai-research', 'search-status'];

export const aiResearchSearchCheckMutationKey = ['terminal', 'ai-research', 'search-check'];

export const useCreateAIResearchTask = () => {
  // 当前只提交 Mock 任务创建请求，后续接页面表单时再决定是否刷新轮询任务。
  return useMutation({
    mutationKey: aiResearchTaskCreateMutationKey,
    mutationFn: (payload: CreateAIResearchTaskParams) => createAIResearchTask(payload),
  });
};

export const useAIResearchTask = ({
  market,
  enabled = true,
}: UseAIResearchTaskParams) => {
  // AI Research 当前展示 Mock 研究任务，后续接入真实 Agent 编排时保持页面调用稳定。
  return useQuery({
    queryKey: aiResearchTaskQueryKey(market),
    queryFn: () => getAIResearchTask({ market }),
    enabled,
    staleTime: 30_000,
    refetchInterval: enabled ? 60_000 : false,
  });
};

export const useAIResearchLLMStatus = (enabled = true) => {
  // 该状态只用于页面诊断，不触发真实 LLM 请求。
  return useQuery({
    queryKey: aiResearchLLMStatusQueryKey,
    queryFn: () => getAIResearchLLMStatus(),
    enabled,
    staleTime: 30_000,
    refetchInterval: enabled ? 60_000 : false,
  });
};

export const useCheckAIResearchLLMConnection = () => {
  // 手动触发真实 LLM ping 检查，避免页面自动消耗调用次数。
  return useMutation({
    mutationKey: aiResearchLLMCheckMutationKey,
    mutationFn: () => checkAIResearchLLMConnection(),
  });
};

export const useAIResearchSearchStatus = (enabled = true) => {
  // 该状态只用于页面诊断，不触发真实搜索请求。
  return useQuery({
    queryKey: aiResearchSearchStatusQueryKey,
    queryFn: () => getAIResearchSearchStatus(),
    enabled,
    staleTime: 30_000,
    refetchInterval: enabled ? 60_000 : false,
  });
};

export const useCheckAIResearchSearchConnection = () => {
  // 手动触发真实搜索源 ping 检查，避免页面自动消耗搜索额度。
  return useMutation({
    mutationKey: aiResearchSearchCheckMutationKey,
    mutationFn: () => checkAIResearchSearchConnection(),
  });
};

export const useAIResearchTaskById = ({
  taskId,
  enabled = true,
}: UseAIResearchTaskByIdParams) => {
  // 查询某一次 AI Research 任务结果，供创建任务后的结果轮询或详情展示使用。
  return useQuery({
    queryKey: aiResearchTaskByIdQueryKey(taskId),
    queryFn: () => getAIResearchTaskById({ taskId }),
    enabled: enabled && taskId.length > 0,
    retry: false,
    staleTime: 30_000,
    refetchInterval: enabled ? 30_000 : false,
  });
};

export const useAIResearchTaskByPollUrl = ({
  pollUrl,
  enabled = true,
}: UseAIResearchTaskByPollUrlParams) => {
  // 直接复用后端回执中的轮询地址，页面层无需拆解 API 路径。
  return useQuery({
    queryKey: aiResearchTaskByPollUrlQueryKey(pollUrl),
    queryFn: () => getAIResearchTaskByPollUrl({ pollUrl }),
    enabled: enabled && pollUrl.length > 0,
    retry: false,
    staleTime: 30_000,
    refetchInterval: enabled ? 30_000 : false,
  });
};
