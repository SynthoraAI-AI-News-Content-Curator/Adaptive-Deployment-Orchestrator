/**
 * Deployments List Page
 * Main dashboard view showing all deployments with real-time updates
 */
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Plus, RefreshCw, Filter, Activity, CheckCircle, XCircle, Pause, Clock } from 'lucide-react';
import { api, Deployment } from '../services/api';
import wsService from '../services/websocket';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';

export default function DeploymentsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [environmentFilter, setEnvironmentFilter] = useState<string>('all');

  // Fetch deployments
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['deployments', statusFilter, environmentFilter],
    queryFn: async () => {
      const params: any = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (environmentFilter !== 'all') params.environment = environmentFilter;
      return api.deployments.list(params);
    },
    refetchInterval: 10000, // Refetch every 10 seconds
  });

  // WebSocket real-time updates
  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) return;

    wsService.connect(token).catch((error) => {
      console.error('WebSocket connection failed:', error);
    });

    // Subscribe to deployment updates
    const unsubscribe = wsService.subscribe('deployment_update', (message) => {
      toast.info(`Deployment ${message.deployment_id} updated`);
      refetch();
    });

    const unsubscribeEvent = wsService.subscribe('event', (message) => {
      if (message.severity === 'error' || message.severity === 'critical') {
        toast.error(message.message || 'Deployment event');
      }
    });

    return () => {
      unsubscribe();
      unsubscribeEvent();
    };
  }, [refetch]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
      case 'rolled_back':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'in_progress':
        return <Activity className="w-5 h-5 text-blue-500 animate-pulse" />;
      case 'paused':
        return <Pause className="w-5 h-5 text-yellow-500" />;
      default:
        return <Clock className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
      case 'rolled_back':
        return 'bg-red-100 text-red-800';
      case 'in_progress':
        return 'bg-blue-100 text-blue-800';
      case 'paused':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">Failed to load deployments. Please try again.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Deployments</h1>
          <p className="text-gray-600 mt-1">
            Monitor and control your deployment rollouts
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <Link
            to="/deployments/new"
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Deployment
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-500" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Status</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="paused">Paused</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="rolled_back">Rolled Back</option>
          </select>
        </div>
        <select
          value={environmentFilter}
          onChange={(e) => setEnvironmentFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Environments</option>
          <option value="development">Development</option>
          <option value="staging">Staging</option>
          <option value="production">Production</option>
        </select>
      </div>

      {/* Deployments List */}
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      ) : data && data.deployments.length > 0 ? (
        <div className="space-y-4">
          {data.deployments.map((deployment: Deployment) => (
            <Link
              key={deployment.id}
              to={`/deployments/${deployment.deployment_id}`}
              className="block bg-white border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    {getStatusIcon(deployment.status)}
                    <h3 className="text-lg font-semibold text-gray-900">
                      {deployment.service_name}
                    </h3>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                        deployment.status
                      )}`}
                    >
                      {deployment.status.replace('_', ' ').toUpperCase()}
                    </span>
                    <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800">
                      {deployment.strategy.replace('_', '-').toUpperCase()}
                    </span>
                    <span className="px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-800">
                      {deployment.environment.toUpperCase()}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
                    <div>
                      <span className="text-gray-600">Target Version:</span>
                      <span className="ml-2 font-medium text-gray-900">
                        {deployment.target_version}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Traffic:</span>
                      <span className="ml-2 font-medium text-gray-900">
                        {deployment.current_traffic_percentage}%
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Created by:</span>
                      <span className="ml-2 font-medium text-gray-900">
                        {deployment.created_by}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Created:</span>
                      <span className="ml-2 font-medium text-gray-900">
                        {formatDistanceToNow(new Date(deployment.created_at), {
                          addSuffix: true,
                        })}
                      </span>
                    </div>
                  </div>

                  {deployment.strategy === 'canary' && (
                    <div className="mt-4">
                      <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                        <span>
                          Step {deployment.current_step + 1} of {deployment.canary_steps.length}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                          style={{
                            width: `${deployment.current_traffic_percentage}%`,
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {deployment.error_message && (
                    <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-800">
                      {deployment.error_message}
                    </div>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
          <Activity className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No deployments found</h3>
          <p className="text-gray-600 mb-4">
            Get started by creating your first deployment
          </p>
          <Link
            to="/deployments/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Deployment
          </Link>
        </div>
      )}
    </div>
  );
}
