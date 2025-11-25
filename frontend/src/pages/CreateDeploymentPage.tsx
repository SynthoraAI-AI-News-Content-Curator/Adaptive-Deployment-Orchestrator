/**
 * Create Deployment Page
 * Form for creating new deployments
 */
import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { api, DeploymentCreate } from '../services/api';
import { toast } from 'sonner';

export default function CreateDeploymentPage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<DeploymentCreate>({
    service_name: '',
    environment: 'staging',
    strategy: 'canary',
    target_version: '',
    namespace: 'default',
    canary_steps: [10, 25, 50, 100],
  });

  const createMutation = useMutation({
    mutationFn: (data: DeploymentCreate) => api.deployments.create(data),
    onSuccess: (data) => {
      toast.success('Deployment created successfully!');
      navigate(`/deployments/${data.deployment_id}`);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create deployment');
    },
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <button
        onClick={() => navigate('/deployments')}
        className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Deployments
      </button>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Create New Deployment</h1>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Service Name *
              </label>
              <input
                type="text"
                required
                value={formData.service_name}
                onChange={(e) => setFormData({ ...formData, service_name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="news-api"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Target Version *
              </label>
              <input
                type="text"
                required
                value={formData.target_version}
                onChange={(e) => setFormData({ ...formData, target_version: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="v2.0.0"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Environment *
              </label>
              <select
                required
                value={formData.environment}
                onChange={(e) => setFormData({ ...formData, environment: e.target.value as any })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="development">Development</option>
                <option value="staging">Staging</option>
                <option value="production">Production</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Strategy *
              </label>
              <select
                required
                value={formData.strategy}
                onChange={(e) => setFormData({ ...formData, strategy: e.target.value as any })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="canary">Canary</option>
                <option value="blue_green">Blue-Green</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Namespace
              </label>
              <input
                type="text"
                value={formData.namespace}
                onChange={(e) => setFormData({ ...formData, namespace: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="default"
              />
            </div>

            {formData.strategy === 'canary' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Canary Steps (%)
                </label>
                <input
                  type="text"
                  value={formData.canary_steps?.join(',')}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      canary_steps: e.target.value.split(',').map((s) => parseInt(s.trim())),
                    })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="10,25,50,100"
                />
              </div>
            )}
          </div>

          <div className="flex gap-4 pt-4">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {createMutation.isPending ? 'Creating...' : 'Create Deployment'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/deployments')}
              className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
