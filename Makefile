.DEFAULT_GOAL := help
NS := bubblemaps-test
SCHEMA := clickhouse/initdb/schema.sql
KAFKA_BROKER := $(shell sed -n "s/.*kafka_broker_list *= *'\([^']*\)'.*/\1/p" $(SCHEMA))
KAFKA_TOPIC  := $(shell sed -n "s/.*kafka_topic_list *= *'\([^']*\)'.*/\1/p" $(SCHEMA))
KAFKA_GROUP  := $(shell sed -n "s/.*kafka_group_name *= *'\([^']*\)'.*/\1/p" $(SCHEMA))

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

reset-offsets: ## re-read the topic from the earliest retained offset (detach consumer, reset group on Kafka, re-attach)
	kubectl -n $(NS) exec clickhouse-0 -- sh -c 'clickhouse-client --password "$$CLICKHOUSE_PASSWORD" -q "DETACH TABLE shib.kafka_transfers"'
	-docker run --rm --env-file k8s/.env -e BROKER=$(KAFKA_BROKER) -e TOPIC=$(KAFKA_TOPIC) -e GROUP=$(KAFKA_GROUP) \
	  -v $(CURDIR)/clickhouse/tools:/tools:ro python:3.12-slim \
	  sh -c 'pip install -q confluent-kafka==2.6.1 && python /tools/reset_offsets.py'
	kubectl -n $(NS) exec clickhouse-0 -- sh -c 'clickhouse-client --password "$$CLICKHOUSE_PASSWORD" -q "ATTACH TABLE shib.kafka_transfers"'
