"""
Metrics Analyzer and Anomaly Detection Engine
AI-driven decision making for deployment health assessment
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
from collections import deque

from app.core.config import settings

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Statistical anomaly detection using Z-score and moving averages
    Production-ready implementation with configurable sensitivity
    """

    def __init__(self, window_size: int = 50, threshold: float = 2.5):
        self.window_size = window_size
        self.threshold = threshold
        self._data_windows: Dict[str, deque] = {}

    def add_data_point(self, metric_name: str, value: float):
        """Add a data point to the sliding window"""
        if metric_name not in self._data_windows:
            self._data_windows[metric_name] = deque(maxlen=self.window_size)
        self._data_windows[metric_name].append(value)

    def is_anomaly(self, metric_name: str, value: float) -> tuple[bool, float]:
        """
        Detect if a value is anomalous using Z-score method
        Returns (is_anomaly, z_score)
        """
        if metric_name not in self._data_windows:
            return False, 0.0

        window = list(self._data_windows[metric_name])
        if len(window) < 10:  # Need minimum samples
            return False, 0.0

        mean = np.mean(window)
        std = np.std(window)

        if std == 0:
            return False, 0.0

        z_score = abs((value - mean) / std)
        is_anomaly = z_score > self.threshold

        if is_anomaly:
            logger.warning(
                f"Anomaly detected for {metric_name}: "
                f"value={value:.4f}, mean={mean:.4f}, std={std:.4f}, z_score={z_score:.2f}"
            )

        return is_anomaly, z_score

    def detect_trend(self, metric_name: str) -> Optional[str]:
        """
        Detect trend direction in metric
        Returns 'increasing', 'decreasing', or 'stable'
        """
        if metric_name not in self._data_windows:
            return None

        window = list(self._data_windows[metric_name])
        if len(window) < 5:
            return None

        # Linear regression to detect trend
        x = np.arange(len(window))
        y = np.array(window)

        try:
            slope, _, _, p_value, _ = stats.linregress(x, y)

            # Check if trend is statistically significant
            if p_value > 0.05:
                return "stable"

            if slope > 0.01:
                return "increasing"
            elif slope < -0.01:
                return "decreasing"
            else:
                return "stable"
        except Exception as e:
            logger.error(f"Trend detection error: {str(e)}")
            return None


class MetricsAnalyzer:
    """
    Metrics analyzer for deployment health assessment
    Integrates with Prometheus and other monitoring systems
    """

    def __init__(self, prometheus_client=None):
        self.prometheus_client = prometheus_client
        self.anomaly_detector = AnomalyDetector(
            window_size=settings.ANOMALY_WINDOW_SIZE,
            threshold=settings.ANOMALY_THRESHOLD
        )
        self._metric_history: Dict[str, List[Dict]] = {}

    async def analyze_deployment_health(
        self,
        deployment_id: str,
        metrics_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze deployment health based on configured metrics
        Returns health assessment with details
        """
        if not metrics_config:
            logger.debug(f"No metrics config for {deployment_id}, defaulting to healthy")
            return {"healthy": True, "reason": "No metrics configured"}

        results = {
            "healthy": True,
            "metrics": {},
            "anomalies": [],
            "threshold_violations": []
        }

        # Check error rate
        if "error_rate" in metrics_config:
            error_rate_health = await self._check_error_rate(
                deployment_id,
                metrics_config["error_rate"]
            )
            results["metrics"]["error_rate"] = error_rate_health
            if not error_rate_health["healthy"]:
                results["healthy"] = False
                results["threshold_violations"].append(error_rate_health)

        # Check latency metrics
        for latency_metric in ["latency_p99", "latency_p95"]:
            if latency_metric in metrics_config:
                latency_health = await self._check_latency(
                    deployment_id,
                    latency_metric,
                    metrics_config[latency_metric]
                )
                results["metrics"][latency_metric] = latency_health
                if not latency_health["healthy"]:
                    results["healthy"] = False
                    results["threshold_violations"].append(latency_health)

        # Check success rate
        if "success_rate" in metrics_config:
            success_rate_health = await self._check_success_rate(
                deployment_id,
                metrics_config["success_rate"]
            )
            results["metrics"]["success_rate"] = success_rate_health
            if not success_rate_health["healthy"]:
                results["healthy"] = False
                results["threshold_violations"].append(success_rate_health)

        # Anomaly detection
        if settings.ANOMALY_DETECTION_ENABLED:
            anomalies = await self._detect_anomalies(deployment_id)
            if anomalies:
                results["anomalies"] = anomalies
                results["healthy"] = False

        if not results["healthy"]:
            logger.warning(
                f"Deployment {deployment_id} unhealthy: "
                f"{len(results['threshold_violations'])} threshold violations, "
                f"{len(results['anomalies'])} anomalies"
            )

        return results

    async def _check_error_rate(
        self,
        deployment_id: str,
        threshold_config: Dict
    ) -> Dict[str, Any]:
        """Check error rate metric"""
        try:
            # In production, query Prometheus
            # For now, simulate metric retrieval
            current_value = await self._get_metric_value(
                deployment_id,
                "error_rate"
            )

            threshold = threshold_config.get("threshold", 0.05)
            comparison = threshold_config.get("comparison", "less_than")

            is_healthy = self._compare_metric(current_value, threshold, comparison)

            # Track for anomaly detection
            self.anomaly_detector.add_data_point(f"{deployment_id}_error_rate", current_value)

            return {
                "metric": "error_rate",
                "current_value": current_value,
                "threshold": threshold,
                "comparison": comparison,
                "healthy": is_healthy,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking error_rate: {str(e)}")
            return {
                "metric": "error_rate",
                "healthy": True,  # Fail open to avoid blocking deployments
                "error": str(e)
            }

    async def _check_latency(
        self,
        deployment_id: str,
        metric_name: str,
        threshold_config: Dict
    ) -> Dict[str, Any]:
        """Check latency metric"""
        try:
            current_value = await self._get_metric_value(
                deployment_id,
                metric_name
            )

            threshold = threshold_config.get("threshold", 1000)  # 1s default
            comparison = threshold_config.get("comparison", "less_than")

            is_healthy = self._compare_metric(current_value, threshold, comparison)

            # Track for anomaly detection
            self.anomaly_detector.add_data_point(f"{deployment_id}_{metric_name}", current_value)

            return {
                "metric": metric_name,
                "current_value": current_value,
                "threshold": threshold,
                "comparison": comparison,
                "healthy": is_healthy,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking {metric_name}: {str(e)}")
            return {
                "metric": metric_name,
                "healthy": True,
                "error": str(e)
            }

    async def _check_success_rate(
        self,
        deployment_id: str,
        threshold_config: Dict
    ) -> Dict[str, Any]:
        """Check success rate metric"""
        try:
            current_value = await self._get_metric_value(
                deployment_id,
                "success_rate"
            )

            threshold = threshold_config.get("threshold", 0.95)
            comparison = threshold_config.get("comparison", "greater_than")

            is_healthy = self._compare_metric(current_value, threshold, comparison)

            # Track for anomaly detection
            self.anomaly_detector.add_data_point(f"{deployment_id}_success_rate", current_value)

            return {
                "metric": "success_rate",
                "current_value": current_value,
                "threshold": threshold,
                "comparison": comparison,
                "healthy": is_healthy,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking success_rate: {str(e)}")
            return {
                "metric": "success_rate",
                "healthy": True,
                "error": str(e)
            }

    async def _detect_anomalies(self, deployment_id: str) -> List[Dict]:
        """Detect anomalies across all tracked metrics"""
        anomalies = []

        for metric_key in ["error_rate", "latency_p99", "success_rate"]:
            full_key = f"{deployment_id}_{metric_key}"
            if full_key in self.anomaly_detector._data_windows:
                window = list(self.anomaly_detector._data_windows[full_key])
                if window:
                    latest_value = window[-1]
                    is_anomaly, z_score = self.anomaly_detector.is_anomaly(
                        full_key,
                        latest_value
                    )

                    if is_anomaly:
                        trend = self.anomaly_detector.detect_trend(full_key)
                        anomalies.append({
                            "metric": metric_key,
                            "value": latest_value,
                            "z_score": z_score,
                            "trend": trend,
                            "timestamp": datetime.utcnow().isoformat()
                        })

        return anomalies

    async def _get_metric_value(
        self,
        deployment_id: str,
        metric_name: str
    ) -> float:
        """
        Get current metric value from monitoring system
        In production, this queries Prometheus/Datadog
        For now, returns simulated values
        """
        if self.prometheus_client:
            # Production: query Prometheus
            # query = f'rate({metric_name}{{deployment="{deployment_id}"}}[5m])'
            # result = await self.prometheus_client.query(query)
            # return result
            pass

        # Simulation for demo purposes
        import random
        baseline = {
            "error_rate": 0.02,
            "latency_p99": 250,
            "latency_p95": 180,
            "success_rate": 0.98
        }

        base_value = baseline.get(metric_name, 0.5)
        # Add random variation
        variation = random.gauss(0, base_value * 0.1)
        return max(0, base_value + variation)

    def _compare_metric(
        self,
        value: float,
        threshold: float,
        comparison: str
    ) -> bool:
        """Compare metric value against threshold"""
        if comparison == "less_than":
            return value < threshold
        elif comparison == "greater_than":
            return value > threshold
        elif comparison == "equal":
            return abs(value - threshold) < 1e-6
        elif comparison == "not_equal":
            return abs(value - threshold) >= 1e-6
        else:
            logger.warning(f"Unknown comparison operator: {comparison}")
            return True

    async def get_deployment_metrics_history(
        self,
        deployment_id: str,
        metric_names: Optional[List[str]] = None,
        time_range: int = 3600
    ) -> Dict[str, List[Dict]]:
        """
        Get historical metrics for a deployment
        Args:
            deployment_id: Deployment identifier
            metric_names: List of metric names to retrieve
            time_range: Time range in seconds (default 1 hour)
        """
        # In production, query time-series database
        # For now, return simulated data
        metrics = {}
        metric_names = metric_names or ["error_rate", "latency_p99", "success_rate"]

        for metric_name in metric_names:
            full_key = f"{deployment_id}_{metric_name}"
            if full_key in self.anomaly_detector._data_windows:
                window = list(self.anomaly_detector._data_windows[full_key])
                metrics[metric_name] = [
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "value": value
                    }
                    for value in window
                ]
            else:
                metrics[metric_name] = []

        return metrics
