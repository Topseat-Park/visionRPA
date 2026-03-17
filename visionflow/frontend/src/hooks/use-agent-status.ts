import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { AgentStatus } from '@/types/agent';

export function useAgentStatus() {
  return useQuery({
    queryKey: ['agent', 'status'],
    queryFn: () => api.get<AgentStatus>('/agent/status'),
    refetchInterval: 2000,
  });
}
