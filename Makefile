.DEFAULT_GOAL := help
NS := bubblemaps-test

help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

render: ## render the kustomize manifests without applying (needs .env)
	kubectl kustomize k8s/

apply: ## create/update everything in the cluster
	kubectl apply -k k8s/

delete: ## remove everything (keeps PersistentVolumeClaims)
	kubectl delete -k k8s/ --ignore-not-found

status: ## pods, services, pvc in the namespace
	kubectl -n $(NS) get pods,svc,pvc

logs: ## tail logs of a pod: make logs POD=clickhouse-0
	kubectl -n $(NS) logs -f $(POD)
