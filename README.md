# AWS Data Engineering Go-to

A company-wide, incrementally built reference handbook for modern AWS data engineering: what services to use, in which architecture, with honest limits and opportunities ("Grenzen und Chancen"). Each quarter adds a self-contained building block (whitepaper chapter + optional proof-of-concept) that accumulates into the full go-to.

> Note on language: the whitepaper chapters are written in German (target audience: internal colleagues). Code, configuration, and repository documentation are in English.

## Current increment: AI-native Vector & RAG patterns

Focus of this increment: production-ready AI-native data patterns on AWS. Core corrected finding: **Amazon Aurora DSQL does not support pgvector** (no extensions, no vector type, multi-region OLTP only). The correct vector stack is **Amazon Aurora PostgreSQL Serverless v2 + pgvector + Amazon Bedrock**. Aurora DSQL is covered as a contrast (distributed OLTP), not as a vector store.

Deliverables:
- `whitepaper/` — Whitepaper v0.1 (interim), 9 chapters, German, cited against AWS docs.
- `poc/` — Deploy-ready proof-of-concept: AWS CDK (TypeScript) infrastructure + Python RAG application (Bedrock Titan embeddings + Aurora pgvector via RDS Data API + Bedrock Claude generation).

## Repository structure

```
aws-data-engineering-go-to/
  whitepaper/   # v0.1 chapters (01..09) + index (German)
  poc/
    cdk/        # AWS CDK v2 (TypeScript) infrastructure
    app/        # Python RAG application (boto3, RDS Data API)
    sql/        # schema + example queries (pgvector, HNSW)
    data/       # small sample corpus for the demo
    README.md   # PoC runbook (deploy, seed, query, teardown)
```

## How to use

1. Read `whitepaper/README.md` for the chapter index and start at `01-executive-summary.md`.
2. To try the demo, follow `poc/README.md`. The PoC is scaffolded but not deployed; you deploy and run it yourself (review IAM and cost first).

## Roadmap

- This quarter: AI-native vector/RAG deep-dive (this increment).
- Next quarter: Amazon Neptune graph modeling + vector embeddings for RAG (GraphRAG). Strong content overlap with the vector work here is intentional and reused.
- Future increments: lakehouse (S3 Tables/Iceberg, SageMaker Lakehouse + Unified Studio), ingestion/streaming (Glue, Kinesis, MSK, Firehose, Zero-ETL), warehousing/analytics (Redshift, Athena, EMR), and governance (Lake Formation, Glue Data Catalog).

## Status

Whitepaper: v0.1 (interim). PoC: scaffolded, not yet deployed.
