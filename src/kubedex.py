#!/usr/bin/env python

from __future__ import print_function
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY, Metric
import os
import sys
import time
from lib import tiller
from collections import Counter
from hapi.release import status_pb2 as hapi_dot_release_dot_status__pb2


tiller_namespace = 'kube-system'

if 'ENV' in os.environ:
    if os.environ['ENV'] == 'dev':
        tiller_endpoint = '127.0.0.1'
else:
    if 'TILLER_NAMESPACE' in os.environ:
        tiller_namespace = os.environ['TILLER_NAMESPACE']
    tiller_endpoint = "tiller-deploy.%s" % tiller_namespace


class Release:
    def __init__(self, name, chart_name, namespace, status, version, app_version):
        self.name = name
        self.chart_name = chart_name
        self.namespace = namespace
        self.status = status
        self.version = version
        self.app_version = app_version

class CustomCollector(object):
    def __init__(self):
        max_retries = 5
        for i in range(max_retries):
            try:
                self.tiller = tiller.Tiller(host=tiller_endpoint)
            except Exception as e:
                print(e)
                continue
            else:
                break
        else:
            print("Failed to connect to tiller on %s" % tiller_endpoint)
            sys.exit(1)

    def collect(self):
        while True:
            try:
                all_releases_raw = self.tiller.list_releases()
                all_releases = []
                for release_raw in all_releases_raw:
                    
                    release = Release(release_raw.name,
                                    release_raw.chart.metadata.name,
                                    release_raw.namespace,
                                    hapi_dot_release_dot_status__pb2._STATUS_CODE.values_by_number[release_raw.info.status.code].name,
                                    release_raw.chart.metadata.version,
                                    release_raw.chart.metadata.appVersion)
                    all_releases.append(release)
                self.tiller.get_release_content(all_releases[0].name, all_releases[0].version)
                break
            except Exception as e:
                print(e)
                continue
        metric = Metric('helm_chart_info', 'Helm chart information', 'gauge')
        chart_count = Counter([(release.name, release.chart_name, release.version, release.app_version, release.namespace, release.status, tiller_namespace) for release in all_releases])
        for chart in chart_count:
            metric.add_sample(
                    'helm_chart_info', 
                    value=chart_count[chart], 
                    labels={"name": chart[0], "chart_name": chart[1], "version": chart[2], "app_version":  chart[3],"namespace": chart[4], "status": chart[5], "tiller_namespace": chart[6]}
             )
        yield metric


if __name__ == "__main__":
    start_http_server(9484)
    REGISTRY.register(CustomCollector())
    print('Serving metrics on http://localhost:9484')
    while True:
        time.sleep(30)
