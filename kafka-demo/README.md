# Kafka Demo (Avro + Schema Registry)

Standalone Kafka producer/consumer demo, isolated from the rest of the repo.
Broker, Schema Registry, Kafka UI, and both Python clients all speak **mutual TLS**
(mTLS) — everyone presents a client certificate signed by the same private CA.

## 1. Generate certificates (required, one-time)

```powershell
cd kafka-demo
docker compose run --rm cert-gen
```

This creates a private CA plus per-service keystores/truststores and a client
certificate under `certs/` (gitignored — regenerate any time by rerunning the command).
All services and both `.env` files already point at these generated files.

## 2. Run everything with Docker

```powershell
docker compose up -d kafka schema-registry kafka-ui
docker compose --profile run up --build producer consumer
```

Kafka UI is available at http://localhost:8090 (topics, messages, and registered schemas).

`docker-compose.yml` builds immutable production-style images (source is copied in
at build time). `docker-compose.override.yml` is auto-merged by `docker compose` and
adds read-only bind mounts for `producer.py`/`consumer.py`/`schemas/` purely for local
iteration — delete or ignore it for a production-like run.

## Run scripts locally against the dockerized broker

Each script reads config from its own `.env` file (`producer/.env`, `consumer/.env`),
so no manual env vars are needed for local runs.

`confluent-kafka` only ships prebuilt Windows wheels for supported Python versions
(currently up to 3.13). Use Python 3.11/3.12 for the local venv — newer versions
(e.g. 3.14) will try to build from source and fail on Windows.

```powershell
cd kafka-demo
docker compose up -d kafka schema-registry

py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r producer/requirements.txt
python producer/producer.py
```

Run `consumer/consumer.py` the same way in another terminal (`pip install -r consumer/requirements.txt`).

When running via `docker compose --profile run up`, the `environment:` overrides in
`docker-compose.yml` take precedence over the `.env` files and point the containers at
the in-network `kafka`/`schema-registry` hostnames instead of `localhost`.

## Mutual TLS

- `certs/generate-certs.sh` (run via the `cert-gen` service) creates a private CA,
  JKS keystores/truststores for the broker/Schema Registry/Kafka UI, and a PEM
  client identity for the Python producer/consumer.
- Kafka (`KAFKA_SSL_CLIENT_AUTH: required`) and Schema Registry
  (`SCHEMA_REGISTRY_SSL_CLIENT_AUTH: "true"`) both reject connections that don't
  present a certificate signed by the CA — there is no plaintext listener.
- Certificates are mounted read-only from `./certs` at runtime, never baked into an
  image, so they can be rotated by rerunning `cert-gen` and restarting the stack.
- The password protecting the generated keystores comes from `CERT_PASSWORD` in
  `kafka-demo/.env` (`changeit` by default) — replace it with a real secret before
  using this pattern anywhere beyond local development.

## Fail-proofing

- Producer: `acks=all`, idempotence enabled, retries with backoff, buffer-full handling.
- Producer stops after `MESSAGE_COUNT` messages (default `10`, set via `.env` or the environment) instead of running forever.
- Consumer: manual offset commits, only committed after successful processing.
- Messages are validated against the Avro schema (`schemas/message.avsc`) via Schema Registry on both produce and consume.

## Schema versions

The active schema is version 2 and adds the `schema_version` field with a default
value, preserving compatibility with version 1 consumers. The previous contract
is retained in `schemas/message.v1.avsc`.

## Where does the schema come from?

The schema itself lives in the **Schema Registry**, not on the Kafka broker or in a
local file:

- Each Avro-encoded message on the wire only carries a small schema ID; the actual
  schema is looked up from the registry.
- The **consumer** never reads `schemas/message.avsc` — `AvroDeserializer` fetches
  the writer's schema from the registry using the ID embedded in each message.
- The **producer** reads `schemas/message.avsc` and auto-registers it with the
  registry on first use (`auto.register.schemas`, on by default) — subsequent runs
  reuse the already-registered schema as long as the file is unchanged.
