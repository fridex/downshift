#!/usr/bin/env python3
"""Start builds if a pod deployment fails due to image pull."""

__version__ = '0.0.1'
__author__ = 'Fridolin Pokorny <fridolin@redhat.com>; Vasek Pavlin <vasek@redhat.com>'

import os
import sys
import logging
from pathlib import Path

import daiquiri
import kubernetes
import openshift

daiquiri.setup(level=logging.DEBUG if bool(int(os.getenv('DEBUG_DOWNSHIFT', 0))) else logging.INFO)

# Load in-cluster configuration that is exposed by OpenShift/k8s configuration.
kubernetes.config.load_incluster_config()

_LOGGER = logging.getLogger('downshift')
_NAMESPACE = Path('/run/secrets/kubernetes.io/serviceaccount/namespace').read_text()
_K8S_API = kubernetes.client.CoreV1Api()
_OCP_BUILD = openshift.client.BuildOpenshiftIoV1Api(openshift.client.ApiClient())

# Payload sent to trigger build.
_PAYLOAD = {
    "kind": "BuildRequest",
    "apiVersion": "build.openshift.io/v1",
    "metadata": {
        "name": "XXX",
    },
    "triggeredBy": [{
        "message": "DownShift triggered"
    }],
    "dockerStrategyOptions": {},
    "sourceStrategyOptions": {}
}


def _trigger_build_request(build_name: str) -> None:
    """Trigger a build request in the given namespace."""
    # Reuse payload defined.
    _PAYLOAD['metadata']['name'] = build_name
    try:
        api_response = _OCP_BUILD.create_namespaced_build_config_instantiate(
            build_name,
            _NAMESPACE,
            _PAYLOAD
        )
        _LOGGER.debug("Response from server %r", api_response)
    except kubernetes.client.rest.ApiException as exc:
        _LOGGER.exception("Failed to start build %r: %s", build_name, exc.reason)


def _list_build_configs_images(image: str, only_running: bool = True) -> list:
    """Find build configs having the given image referenced."""
    result = []

    for item in _OCP_BUILD.list_namespaced_build_config(_NAMESPACE).items:
        image_to = item.spec.output.to.name.split(':', maxsplit=1)[0]
        if item.spec.output.to.kind == 'ImageStreamTag' and image == image_to:
            if only_running and item.status.to_dict().get('phase') == 'Running':
                _LOGGER.debug("Omitting build config %r as the build is already running", item.metadata.name)
                continue

            _LOGGER.debug("Build config %r produces %r", item.metadata.name, image)
            result.append(item.metadata.name)

    return result


def main():
    """Watch for builds that fail due to image pull and trigger builds for images."""
    watcher = kubernetes.watch.Watch()
    for event in watcher.stream(_K8S_API.list_namespaced_pod, namespace=_NAMESPACE):
        pod_name = event['object'].metadata.name
        _LOGGER.debug("Retrieved event %r for pod %r", event['type'], pod_name)

        for container_status in event['raw_object']['status'].get('containerStatuses', []):
            if 'waiting' not in container_status['state']:
                continue

            if container_status['state'].get('waiting', {}).get('reason') \
                    not in ('ErrImagePull', 'ImagePullBackOff'):
                continue

            _LOGGER.info("Checking build configs for image %r used in pod %r", container_status['name'], pod_name)
            build_configs = _list_build_configs_images(container_status['name'])

            if len(build_configs) == 0:
                _LOGGER.warning(
                    "No build config found to trigger build for %r, pod %r", container_status['name'], pod_name
                )
                continue

            if len(build_configs) > 1:
                _LOGGER.warning(
                    "Found multiple build configs for image %r (using only the first one): %r",
                    container_status['name'], build_configs
                )

            _LOGGER.info("Triggering build %r for %r", build_configs[0], pod_name)
            _trigger_build_request(build_configs[0])


if __name__ == '__main__':
    print("Running DownShift version", __version__)
    sys.exit(main())
