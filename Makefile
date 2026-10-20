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

schema: ## apply clickhouse/initdb/schema.sql to the running pod (idempotent, no restart)
	kubectl -n $(NS) exec -i clickhouse-0 -- sh -c 'clickhouse-client --password "$$CLICKHOUSE_PASSWORD" --multiquery' < clickhouse/initdb/schema.sql

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

kafka-read: ## print raw topic messages by partition:offset, e.g. make kafka-read AT="5:10295 0:78351"
	docker run --rm --env-file k8s/.env -e BROKER=$(KAFKA_BROKER) -e TOPIC=$(KAFKA_TOPIC) \
	  -v $(CURDIR)/clickhouse/tools:/tools:ro python:3.12-slim \
	  sh -c 'pip install -q confluent-kafka==2.6.1 2>/dev/null && python /tools/read_offsets.py $(AT)'

kafka-find: ## scan every retained topic message for a text, e.g. make kafka-find Q=0xc938d00a... or Q="2026-10-20 16:47"
	docker run --rm --env-file k8s/.env -e BROKER=$(KAFKA_BROKER) -e TOPIC=$(KAFKA_TOPIC) \
	  -v $(CURDIR)/clickhouse/tools:/tools:ro python:3.12-slim \
	  sh -c 'pip install -q confluent-kafka==2.6.1 2>/dev/null && python /tools/read_offsets.py --find "$(Q)"'

build: ## build the FastAPI image (shared with Docker Desktop Kubernetes)
	docker build -t shib-api:dev api/

restart-api: ## roll the API pods (pick up a freshly built image)
	kubectl -n $(NS) rollout restart deployment/api && kubectl -n $(NS) rollout status deployment/api

pf-api: ## port-forward the API to http://localhost:8080 (docs at /docs)
	kubectl -n $(NS) port-forward svc/api 8080:80

refresh-views: ## force the scheduled (refreshable) views to recompute now
	kubectl -n $(NS) exec clickhouse-0 -- sh -c 'clickhouse-client --password "$$CLICKHOUSE_PASSWORD" --multiquery -q "SYSTEM REFRESH VIEW shib.mv_funder_wallets; SYSTEM WAIT VIEW shib.mv_funder_wallets; SYSTEM REFRESH VIEW shib.mv_funder_stats; SYSTEM WAIT VIEW shib.mv_funder_stats; SELECT view, status, last_success_time, next_refresh_time, exception FROM system.view_refreshes FORMAT PrettyCompact"'

alert-check: ## run the SQD vs ClickHouse transfer-count check now and tail its log
	@name=alert-$$(date +%s); \
	kubectl -n $(NS) create job --from=cronjob/transfer-count-alert $$name && \
	kubectl -n $(NS) wait --for=condition=ready pod -l job-name=$$name --timeout=60s >/dev/null 2>&1; \
	kubectl -n $(NS) logs -f job/$$name

alerts: ## list transfer-count-alert jobs and any ALERT lines in their logs
	kubectl -n $(NS) get cronjob,jobs -l app=transfer-count-alert
	-kubectl -n $(NS) logs -l app=transfer-count-alert --tail=-1 --prefix | grep ALERT

# ---- single Ubuntu/Debian VM with k3s (see deploy/vm/deploy.sh) ----
vm-deploy: ## deploy to the VM: make vm-deploy VM=<ip> [SSH_USER=ubuntu] [API_HOST=api.example.com ACME_EMAIL=you@example.com]
	API_HOST="$(API_HOST)" ACME_EMAIL="$(ACME_EMAIL)" deploy/vm/deploy.sh $(VM) $(or $(SSH_USER),root)

vm-ssh: ## ssh into the VM: make vm-ssh VM=<ip>
	ssh $(or $(SSH_USER),root)@$(VM)

vm-status: ## pods, services, pvc on the VM: make vm-status VM=<ip>
	ssh $(or $(SSH_USER),root)@$(VM) 'sudo k3s kubectl -n $(NS) get pods,svc,pvc'

vm-logs: ## tail a pod on the VM: make vm-logs VM=<ip> POD=clickhouse-0
	ssh $(or $(SSH_USER),root)@$(VM) 'sudo k3s kubectl -n $(NS) logs -f $(POD)'

vm-delete: ## remove the app from the VM (keeps k3s and the data PVC): make vm-delete VM=<ip>
	ssh $(or $(SSH_USER),root)@$(VM) 'cd ~/bubblemaps-test && sudo k3s kubectl delete -k k8s/ --ignore-not-found'

vm-headlamp-token: ## print a 1-year login token for the Headlamp UI: make vm-headlamp-token VM=<ip>
	@ssh $(or $(SSH_USER),root)@$(VM) 'sudo k3s kubectl -n headlamp create token headlamp-admin --duration=8760h'

vm-wipe: ## uninstall k3s and all data on the VM, leaving a blank server: make vm-wipe VM=<ip>
	ssh $(or $(SSH_USER),root)@$(VM) 'sudo /usr/local/bin/k3s-uninstall.sh && rm -rf ~/bubblemaps-test /tmp/shib-api.tar'
