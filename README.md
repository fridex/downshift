# DownShift

A bot that knows what to do when the shift feels down.

## Information

This is a simple application that can be deployed into your OpenShift project. It checks for pods (or services, jobs, ...) that fail to start due to image pull failures. If these images should be pulled from OpenShift internal registry, DownShift triggers build that is responsible for producing these images.

## Installation

Make sure you are logged in into your OpenShift cluster and you are in the correct namespace where you would like to have DownShift present and run:

```console
DOWNSHIFT_TEMPLATE_YAML='https://raw.githubusercontent.com/fridex/downshift/master/openshift/template.yaml'
oc process -f ${DOWNSHIFT_TEMPLATE_YAML} | oc apply -f -
```


## De-provisioning

Make sure you are logged in into your OpenShift cluster and you are in the correct namespace and run:

```console
oc delete all --selector 'app=downshift'
```
