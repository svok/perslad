#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "rag" --dbname "rag" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
EOSQL
