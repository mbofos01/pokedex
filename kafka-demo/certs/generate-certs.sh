#!/usr/bin/env bash
# Generates a private CA plus per-service keystores/truststores (JKS, for the
# JVM-based broker/registry/UI) and a PEM client identity (for the Python
# producer/consumer) used to enable mutual TLS across the demo stack.
#
# Run via: docker compose run --rm cert-gen
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PASSWORD="${CERT_PASSWORD:-changeit}"
VALIDITY_DAYS=3650

echo "Cleaning up any previously generated certificates..."
rm -f ./*.jks ./*.pem ./*.csr ./*.srl

echo "Generating CA..."
openssl req -new -x509 -nodes -days "$VALIDITY_DAYS" \
  -subj "/CN=kafka-demo-ca/OU=kafka-demo/O=pokedex/C=US" \
  -keyout ca-key.pem -out ca-cert.pem

# Args: $1 keystore name  $2 CN  $3 SAN (e.g. "DNS:kafka,DNS:localhost")  $4 serial number
generate_keystore() {
  local name=$1 cn=$2 san=$3 serial=$4

  keytool -genkeypair -alias "$name" -keyalg RSA -keysize 2048 -validity "$VALIDITY_DAYS" \
    -keystore "$name.keystore.jks" -storepass "$PASSWORD" -keypass "$PASSWORD" \
    -dname "CN=$cn,OU=kafka-demo,O=pokedex,C=US" -ext "SAN=$san"

  keytool -certreq -alias "$name" -keystore "$name.keystore.jks" -storepass "$PASSWORD" \
    -file "$name.csr"

  openssl x509 -req -in "$name.csr" -CA ca-cert.pem -CAkey ca-key.pem -set_serial "$serial" \
    -out "$name-signed.pem" -days "$VALIDITY_DAYS" -extfile <(printf "subjectAltName=%s" "$san")

  keytool -importcert -alias CARoot -file ca-cert.pem -keystore "$name.keystore.jks" \
    -storepass "$PASSWORD" -noprompt
  keytool -importcert -alias "$name" -file "$name-signed.pem" -keystore "$name.keystore.jks" \
    -storepass "$PASSWORD" -noprompt

  keytool -importcert -alias CARoot -file ca-cert.pem -keystore "$name.truststore.jks" \
    -storepass "$PASSWORD" -noprompt

  rm -f "$name.csr" "$name-signed.pem"
}

echo "Generating broker keystore/truststore..."
generate_keystore kafka kafka "DNS:kafka,DNS:localhost" 1001

echo "Generating schema registry keystore/truststore..."
generate_keystore schema-registry schema-registry "DNS:schema-registry,DNS:localhost" 1002

echo "Generating kafka-ui keystore/truststore..."
generate_keystore kafka-ui kafka-ui "DNS:kafka-ui,DNS:localhost" 1003

echo "Generating Python client (producer/consumer) PEM identity..."
openssl genrsa -out client-key.pem 2048
openssl req -new -key client-key.pem -out client.csr \
  -subj "/CN=kafka-demo-client/OU=kafka-demo/O=pokedex/C=US"
openssl x509 -req -in client.csr -CA ca-cert.pem -CAkey ca-key.pem -set_serial 1004 \
  -out client-cert.pem -days "$VALIDITY_DAYS"
rm -f client.csr

echo "Done. Certificates written to $(pwd)"
