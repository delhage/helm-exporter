build:
	docker build . -t waseemhassan/helm-release-exporter:1.0.3
	docker push waseemhassan/helm-release-exporter:1.0.3

deploy:
	helm del ks-kubedex --purge --tiller-namespace tiller
	helm del tiller-kubedex --purge --tiller-namespace tiller
	helm install helm-exporter --name ks-kubedex --set image.repository=waseemhassan/helm-release-exporter --set image.tag=1.0.3 --tiller-namespace tiller --namespace ocp-supporting-services
	helm install helm-exporter --name tiller-kubedex --set tillerNamespace=tiller --set image.repository=waseemhassan/helm-release-exporter --set image.tag=1.0.3 --tiller-namespace tiller --namespace ocp-supporting-services