#!/usr/bin/env python3
"""
Kubernetes service discovery for dynamic peer detection.

This module provides automatic discovery of temperature exporter pods
in a Kubernetes cluster, eliminating the need for static peer configuration.
"""
import logging
import os
from typing import List, Optional

logger = logging.getLogger("k8s_discovery")


def is_running_in_kubernetes() -> bool:
    """Check if running inside a Kubernetes pod.

    Returns:
        bool: True if running in Kubernetes, False otherwise
    """
    return os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token")


def discover_temp_exporter_pods(
    namespace: Optional[str] = None,
    label_selector: str = "app.kubernetes.io/name=sipeed-temp-exporter",
    port: int = 8080,
) -> List[str]:
    """Discover temperature exporter pods via Kubernetes API.

    Uses the Kubernetes service account to query the API for pods matching
    the label selector. Returns list of URLs to poll.

    Args:
        namespace: Kubernetes namespace (default: current pod's namespace)
        label_selector: Label selector for temp exporter pods
        port: Port number for temp exporter service

    Returns:
        List[str]: List of URLs (e.g., ['http://10.42.0.5:8080/temp', ...])
    """
    if not is_running_in_kubernetes():
        logger.debug("Not running in Kubernetes, skipping discovery")
        return []

    try:
        # Import kubernetes module (only when needed)
        from kubernetes import client, config

        # Load in-cluster config
        config.load_incluster_config()
        v1 = client.CoreV1Api()

        # Get current namespace if not provided
        if namespace is None:
            with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as f:
                namespace = f.read().strip()

        logger.info("Discovering temp exporter pods in namespace: %s", namespace)

        # List pods matching label selector
        pods = v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector,
        )

        urls = []
        for pod in pods.items:
            # Only include running pods
            if pod.status.phase != "Running":
                logger.debug(
                    "Skipping pod %s (phase: %s)", pod.metadata.name, pod.status.phase
                )
                continue

            # Get pod IP
            pod_ip = pod.status.pod_ip
            if not pod_ip:
                logger.debug("Skipping pod %s (no IP assigned)", pod.metadata.name)
                continue

            # Build URL
            url = f"http://{pod_ip}:{port}/temp"
            urls.append(url)
            logger.debug("Discovered pod: %s -> %s", pod.metadata.name, url)

        logger.info("Discovered %d temp exporter pods", len(urls))
        return urls

    except ImportError:
        logger.warning(
            "kubernetes Python module not available, install with: pip install kubernetes"
        )
        return []
    except Exception as e:
        logger.error("Failed to discover pods via Kubernetes API: %s", e)
        return []


def get_peers_with_discovery(
    static_peers: List[str],
    enable_k8s_discovery: bool = True,
    k8s_namespace: Optional[str] = None,
    k8s_label_selector: str = "app.kubernetes.io/name=sipeed-temp-exporter",
    k8s_port: int = 8080,
) -> List[str]:
    """Get peer list with optional Kubernetes auto-discovery.

    Combines static peer configuration with dynamic Kubernetes discovery.
    Kubernetes discovery only activates when running inside a K8s cluster.

    Args:
        static_peers: Static list of peer URLs/hostnames
        enable_k8s_discovery: Enable Kubernetes auto-discovery
        k8s_namespace: Kubernetes namespace for discovery
        k8s_label_selector: Label selector for pod discovery
        k8s_port: Port number for discovered pods

    Returns:
        List[str]: Combined list of peers (discovered + static)
    """
    peers = list(static_peers)  # Start with static peers

    # Add Kubernetes-discovered peers if enabled and running in K8s
    if enable_k8s_discovery and is_running_in_kubernetes():
        discovered = discover_temp_exporter_pods(
            namespace=k8s_namespace,
            label_selector=k8s_label_selector,
            port=k8s_port,
        )
        peers.extend(discovered)
        logger.info(
            "Total peers: %d static + %d discovered = %d",
            len(static_peers),
            len(discovered),
            len(peers),
        )

    return peers
