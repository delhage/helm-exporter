#!/usr/bin/env python

from __future__ import print_function
from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY, Metric
import os
import sys
import time
import itertools
import operator
import re
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
    def __init__(self, name, chart_name, namespace, status, version, app_version, revision, app_name):
        self.name = name
        self.chart_name = chart_name
        self.namespace = namespace
        self.status = status
        self.version = version
        self.app_version = app_version
        self.revision = revision
        self.app_name = app_name

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

    def get_unique(self, deployed_releases_raw, failed_releases_raw):
        unique = []
        unique_failed_releases = self.get_unique_releases(failed_releases_raw)
        deployed_releases = self.to_releases(deployed_releases_raw)
        for deployed_release in deployed_releases:
            isFailedRelease = False
            for failed_release in unique_failed_releases:
                if deployed_release.name == failed_release.name and failed_release.revision > deployed_release.revision:
                    isFailedRelease = True
                    unique.append(failed_release)
                    break

            if not isFailedRelease:
                unique.append(deployed_release)
        
        return self.patch_releases(unique)

    def patch_releases(self, releases):
        for release in releases:
            try:
                content = self.tiller.get_release_content(release.name, release.revision)
                pattern = re.escape('\nimage: ')+"(.*?)"+re.escape('\n')
                matches = re.findall(pattern, str(content.release.config.raw))
                if len(matches) != 0:
                        image = matches[0]
                        splitted = image.rsplit(":", 1)
                        image_name = splitted[0]
                        image_version = splitted[1]
                        atg_app_name = image_name.rsplit("/", 1)[1]
                        release.app_version = image_version
                        release.app_name = atg_app_name
            except Exception as e:
                print(e)
        
        return releases

    def to_releases(self, releases_raw):
        releases = []
        for release_raw in releases_raw:
            name = release_raw.name
            chart_name = release_raw.chart.metadata.name
            namespace = release_raw.namespace
            status = hapi_dot_release_dot_status__pb2._STATUS_CODE.values_by_number[release_raw.info.status.code].name
            version = release_raw.chart.metadata.version
            app_version = release_raw.chart.metadata.appVersion
            revision = release_raw.version

            release = Release(name, chart_name, namespace, status, version, app_version, revision, "")
            releases.append(release)
        return releases

    def get_unique_releases(self, raw_releases):
        unique = []
        releases = self.to_releases(raw_releases)
        get_attr = operator.attrgetter('name')

        new_list = [list(g) for k, g in itertools.groupby(sorted(releases, key=get_attr), get_attr)]

        for release_group in new_list:
            latest_release = max(release_group, key=operator.attrgetter('revision'))
            unique.append(latest_release)
        return unique

    def collect(self):
        while True:
            try:
                all_deployed_releases_raw = self.tiller.list_releases("DEPLOYED")
                all_failed_releases_raw = self.tiller.list_releases("FAILED")
                all_releases = self.get_unique(all_deployed_releases_raw, all_failed_releases_raw)
                break
            except Exception as e:
                print(e)
                continue
        metric = Metric('helm_chart_info', 'Helm chart information', 'gauge')
        chart_count = Counter([(release.name, release.chart_name, release.version, release.app_version, release.namespace, release.status, release.revision, tiller_namespace, release.app_name) for release in all_releases])
        for chart in chart_count:
            metric.add_sample(
                    'helm_chart_info', 
                    value=chart_count[chart], 
                    labels={"name": chart[0], "chart_name": chart[1], "version": chart[2], "app_version":  chart[3],"namespace": chart[4], "status": chart[5], "revision": str(chart[6]), "tiller_namespace": chart[7], "app_name": chart[8]}
             )
        yield metric


if __name__ == "__main__":
    start_http_server(9484)
    REGISTRY.register(CustomCollector())
    print('Serving metrics on http://localhost:9484')
    while True:
        time.sleep(30)
