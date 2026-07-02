# AWS Data Engineering Go-to, AI-native Zwischenstand v0.1

Dieses Whitepaper ist ein Baustein des größeren Unternehmens-Go-to für AWS Data Engineering. Der aktuelle Zwischenstand fokussiert AI-native Datenmuster, Vector Stores, Retrieval-Augmented Generation und produktionsfähige Integration mit Amazon Bedrock. Klassische Lakehouse-, Streaming-, BI-, Governance- und OLTP-Themen werden eingeordnet, aber in späteren Increments vertieft.

## Scope

Dieser Increment beantwortet vor allem eine Architekturfrage: Wie sieht ein belastbarer AWS-Stack für RAG-nahe Datenprodukte aus, wenn Aurora DSQL korrekt als multi-region OLTP-Service abgegrenzt wird und Aurora PostgreSQL Serverless v2 mit `pgvector` und Bedrock den PoC-Kern bildet? Kapitel 02, 03 und 04 werden separat erstellt und sind hier nur im Inhaltsverzeichnis referenziert.

## Inhaltsverzeichnis

| Nr. | Datei | Beschreibung |
|---:|---|---|
| 01 | [01-executive-summary.md](01-executive-summary.md) | Executive Summary, korrigierte Kernentscheidung, Landscape Map und Scope des Increments. |
| 02 | [02-distributed-sql-dsql-vs-aurora-vs-rds.md](02-distributed-sql-dsql-vs-aurora-vs-rds.md) | Separat erstelltes Kapitel zu Distributed SQL, Aurora DSQL, Aurora und RDS. |
| 03 | [03-pgvector-on-aurora-postgresql.md](03-pgvector-on-aurora-postgresql.md) | Separat erstelltes Kapitel zu `pgvector` auf Aurora PostgreSQL und Datenmodell. |
| 04 | [04-ai-native-query-patterns.md](04-ai-native-query-patterns.md) | Separat erstelltes Kapitel zu AI-nativen Query Patterns und PoC-Struktur. |
| 05 | [05-bedrock-integration.md](05-bedrock-integration.md) | Vergleich der Bedrock-Integrationspfade: in-database inference, Application-layer RAG und Bedrock Knowledge Bases. |
| 06 | [06-vector-store-decision-matrix.md](06-vector-store-decision-matrix.md) | AWS Vector Store Decision Matrix 2026 mit klaren Verdicts zu `pgvector`, S3 Vectors, OpenSearch, DocumentDB und Neptune. |
| 07 | [07-production-readiness.md](07-production-readiness.md) | Produktionscheckliste für Aurora PostgreSQL `pgvector` plus Bedrock, inklusive Security, Kosten, Betrieb und Governance. |
| 08 | [08-outlook-agentcore-neptune.md](08-outlook-agentcore-neptune.md) | Outlook zu AgentCore als angrenzendem Consumption Layer und Neptune GraphRAG als nächstem Datenarchitektur-Increment. |
| 09 | [09-sources.md](09-sources.md) | Konsolidierte, de-duplizierte Quellenliste mit AWS-Dokumentation und Zugriffsdatum. |
