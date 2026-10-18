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

ch: ## open a clickhouse-client shell inside the pod
	kubectl -n $(NS) exec -it clickhouse-0 -- sh -c 'clickhouse-client --password "$$CLICKHOUSE_PASSWORD"'

schema: ## re-apply clickhouse/initdb/*.sql (idempotent) without restarting the pod
	kubectl -n $(NS) exec clickhouse-0 -- sh -c 'for f in /docker-entrypoint-initdb.d/*.sql; do echo "== $$f"; clickhouse-client --password "$$CLICKHOUSE_PASSWORD" --multiquery < "$$f"; done'

restart-ch: ## restart clickhouse (re-runs initdb scripts, keeps data)
	kubectl -n $(NS) rollout restart statefulset/clickhouse && kubectl -n $(NS) rollout status statefulset/clickhouse

pf-ch: ## port-forward ClickHouse HTTP to localhost:8123
	kubectl -n $(NS) port-forward svc/clickhouse 8123:8123
