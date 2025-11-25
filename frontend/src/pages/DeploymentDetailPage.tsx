/**
 * Deployment Detail Page
 * Detailed view with real-time monitoring and control capabilities
 */
import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Play, Pause, RotateCcw, FastForward, Activity } from 'lucide-react';
import { api } from '../services/api';
import wsService from '../services/websocket';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';

export default function DeploymentDetailPage() {
  const { deploymentId } = useParams<{ deploymentId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Fetch deployment details
  const { data: deployment, isLoading } = useQuery({
    queryKey: ['deployment', deploymentId],
    queryFn: () => api.deployments.get(deploymentId!),
    enabled: !!deploymentId,
    refetchInterval: 5000,
  });

  // Fetch events
  const { data: events } = useQuery({
    queryKey: ['deployment-events', deploymentId],
    queryFn: () => api.deployments.getEvents(deploymentId!, 50),
    enabled: !!deploymentId,
    refetchInterval: 5000,
  });

  // Control mutations
  const controlMutation = useMutation({
    mutationFn: ({ action, reason }: { action: string; reason?: string }) =>
      api.deployments.control(deploymentId!, { action: action as any, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deployment', deploymentId] });
      toast.success('Action completed successfully');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Action failed');
    },
  });

  const startMutation = useMutation({
    mutationFn: () => api.deployments.start(deploymentId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deployment', deploymentId] });
      toast.success('Deployment started');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to start deployment');
    },
  });

  // WebSocket updates
  useEffect(() => {
    if (!deploymentId) return;

    const token = localStorage.getItem('auth_token');
    if (!token) return;

    wsService.connect(token, deploymentId).then(() => {
      wsService.subscribeToDeployment(deploymentId);
    });

    const unsubUpdate = wsService.subscribe('deployment_update', (message) => {
      if (message.deployment_id === deploymentId) {
        queryClient.invalidateQueries({ queryKey: ['deployment', deploymentId] });
      }
    });

    const unsubEvent = wsService.subscribe('event', (message) => {
      if (message.deployment_id === deploymentId) {
        queryClient.invalidateQueries({ queryKey: ['deployment-events', deploymentId] });

        if (message.severity === 'error' || message.severity === 'critical') {
          toast.error(message.message);
        } else if (message.severity === 'warning') {
          toast.warning(message.message);
        }
      }
    });

    return () => {
      unsubUpdate();
      unsubEvent();
      if (deploymentId) {
        wsService.unsubscribeFromDeployment(deploymentId);
      }
    };
  }, [deploymentId, queryClient]);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!deployment) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">Deployment not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/deployments')}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Deployments
        </button>

        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{deployment.service_name}</h1>
            <p className="text-gray-600 mt-1">{deployment.deployment_id}</p>
          </div>

          {/* Control Buttons */}
          <div className="flex gap-2">
            {deployment.status === 'pending' && (
              <button
                onClick={() => startMutation.mutate()}
                disabled={startMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                Start
              </button>
            )}

            {deployment.status === 'in_progress' && (
              <>
                <button
                  onClick={() => controlMutation.mutate({ action: 'pause' })}
                  disabled={controlMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50"
                >
                  <Pause className="w-4 h-4" />
                  Pause
                </button>
                <button
                  onClick={() => {
                    const reason = prompt('Rollback reason:');
                    if (reason) {
                      controlMutation.mutate({ action: 'rollback', reason });
                    }
                  }}
                  disabled={controlMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  <RotateCcw className="w-4 h-4" />
                  Rollback
                </button>
                {deployment.strategy === 'canary' && (
                  <button
                    onClick={() => controlMutation.mutate({ action: 'promote' })}
                    disabled={controlMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    <FastForward className="w-4 h-4" />
                    Promote to 100%
                  </button>
                )}
              </>
            )}

            {deployment.status === 'paused' && (
              <button
                onClick={() => controlMutation.mutate({ action: 'resume' })}
                disabled={controlMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                Resume
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Status</div>
          <div className="text-2xl font-bold text-gray-900 capitalize">
            {deployment.status.replace('_', ' ')}
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Strategy</div>
          <div className="text-2xl font-bold text-gray-900 capitalize">
            {deployment.strategy.replace('_', '-')}
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Traffic</div>
          <div className="text-2xl font-bold text-gray-900">
            {deployment.current_traffic_percentage}%
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Environment</div>
          <div className="text-2xl font-bold text-gray-900 capitalize">
            {deployment.environment}
          </div>
        </div>
      </div>

      {/* Progress */}
      {deployment.strategy === 'canary' && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Rollout Progress</h2>
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-600">
                Step {deployment.current_step + 1} of {deployment.canary_steps.length}
              </div>
              <div className="flex-1">
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className="bg-blue-600 h-4 rounded-full transition-all duration-500 flex items-center justify-end pr-2"
                    style={{ width: `${deployment.current_traffic_percentage}%` }}
                  >
                    <span className="text-xs text-white font-medium">
                      {deployment.current_traffic_percentage}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              {deployment.canary_steps.map((step: number, idx: number) => (
                <div
                  key={idx}
                  className={`flex-1 text-center p-2 rounded ${
                    idx <= deployment.current_step
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  <div className="text-xs font-medium">{step}%</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Events Log */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Activity className="w-5 h-5" />
          Events Log
        </h2>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {events && events.length > 0 ? (
            events.map((event) => (
              <div
                key={event.id}
                className={`p-3 rounded border-l-4 ${
                  event.severity === 'error' || event.severity === 'critical'
                    ? 'bg-red-50 border-red-500'
                    : event.severity === 'warning'
                    ? 'bg-yellow-50 border-yellow-500'
                    : 'bg-gray-50 border-gray-300'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-900">{event.message}</div>
                    <div className="text-xs text-gray-600 mt-1">
                      {event.event_type} • {event.actor || 'system'} •{' '}
                      {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                    </div>
                  </div>
                  <span
                    className={`px-2 py-1 rounded text-xs font-medium ${
                      event.severity === 'error' || event.severity === 'critical'
                        ? 'bg-red-100 text-red-800'
                        : event.severity === 'warning'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-blue-100 text-blue-800'
                    }`}
                  >
                    {event.severity}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="text-center text-gray-500 py-8">No events yet</div>
          )}
        </div>
      </div>
    </div>
  );
}
