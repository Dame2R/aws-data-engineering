# 01, Executive Summary, Zwischenstand v0.1

## Kernaussage

Dieser Zwischenstand korrigiert die wichtigste Architekturannahme für den aktuellen AWS Data Engineering Go-to: **Amazon Aurora DSQL ist nicht der Zielservice für `pgvector` und RAG-nahe Vektorsuche**. Aurora DSQL unterstützt `pgvector` nicht und ist ein serverloser, verteilter relationaler Datenbankservice für stark verfügbare OLTP-Workloads mit Single-Region- und Multi-Region-Clustern, optimiert für transaktionale Anwendungen, nicht für PostgreSQL-Erweiterungen als Vektor-Backend. Die aktuelle AWS-Dokumentation positioniert Aurora DSQL entsprechend als distributed OLTP-Service mit PostgreSQL-kompatiblen Treibern und SQL-Funktionen, nicht als vollständige Aurora-PostgreSQL-Extension-Plattform (https://docs.aws.amazon.com/aurora-dsql/latest/userguide/what-is-aurora-dsql.html).

Für den PoC und als produktionsfähige Referenzarchitektur ist deshalb die präzisere Zielkombination:

**Amazon Aurora PostgreSQL Serverless v2 + `pgvector` + Amazon Bedrock**

Diese Kombination trennt die Rollen sauber: Aurora PostgreSQL verwaltet relationale Daten, Transaktionen und Vektoren in einem konsistenten Datenmodell, `pgvector` liefert Ähnlichkeitssuche mit HNSW oder IVFFlat, Amazon Bedrock liefert Embeddings und generative Modelle. AWS beschreibt Aurora PostgreSQL explizit als Vector Database Option mit `pgvector` (https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html), während Aurora Serverless v2 die elastische Betriebsform für variable Lastprofile liefert (https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html).

## Einordnung in den größeren AWS Data Engineering Go-to

Dieses Whitepaper ist **kein vollständiges AWS Data Engineering Handbuch**. Es ist ein Baustein dieses Quartals innerhalb eines größeren Unternehmens-Go-to. Der aktuelle Scope liegt auf AI-nativen Datenmustern, Vektorsuche, RAG und produktionsnaher Integration mit Amazon Bedrock. Klassische Lakehouse-, Streaming-, BI-, Batch- und Governance-Themen werden bewusst nur gerahmt, nicht vollständig ausgearbeitet.

### Landscape Map, Zielbild des gesamten Stacks

| Layer | Relevante AWS Services | Status in diesem Increment | Künftige Increments |
|---|---|---|---|
| Storage und Lakehouse | Amazon S3, S3 Tables mit Apache Iceberg, S3 Vectors, SageMaker Lakehouse, SageMaker Unified Studio, Lake Formation, AWS Glue Data Catalog | Nur referenziert, S3 Vectors als Vector Store bewertet | Lakehouse-Standards, Tabellenformate, Objektlayout, Catalog-Strategie, Datenzonen |
| Ingestion und Streaming | AWS Glue, Amazon Kinesis, Amazon MSK, Amazon Data Firehose, AWS DMS, Zero-ETL Integrationen | Nicht vertieft | Streaming Patterns, CDC, Schema Evolution, Replay, Landing Zones |
| Processing und Serving | Amazon Redshift Serverless, Amazon Athena, Amazon EMR, Amazon QuickSight | Nicht vertieft | Serving-Layer-Design, SQL Federation, BI, Performance- und Kostenmuster |
| OLTP und operative Stores | Amazon Aurora, Aurora DSQL, DynamoDB, Amazon DocumentDB | Aurora PostgreSQL als Vector Store vertieft, Aurora DSQL abgegrenzt, DocumentDB bewertet | Operative Datenarchitekturen, Multi-Region OLTP, NoSQL-Pattern |
| AI und Vector Layer | Amazon Bedrock, Bedrock Knowledge Bases, Aurora PostgreSQL `pgvector`, OpenSearch, S3 Vectors, Neptune Analytics, DocumentDB Vector Search | **Hauptscope dieses Increments** | GraphRAG mit Neptune, Agentic Consumption, multimodale Retrieval-Pipelines |
| Governance, Security und Operations | IAM, KMS, Secrets Manager, VPC, CloudWatch, CloudTrail, Lake Formation, Data Quality, lineage-nahe Kontrollen | Produktionscheckliste für AI/vector Stack | Unternehmensweite Governance, Plattformbetriebsmodell, FinOps, Datenprodukt-Standards |

Diese Map ist bewusst breit. Sie verhindert, dass der aktuelle AI-Fokus fälschlich als Gesamtarchitektur gelesen wird. Der Wert dieses Zwischenstands liegt darin, für AI-native Retrieval-Workloads eine belastbare AWS-Position zu schaffen, ohne die noch offenen Plattformfragen zu verdecken.

## Architekturposition für diesen Zwischenstand

Der empfohlene Default für den PoC ist **Application-layer RAG mit Amazon Bedrock und Aurora PostgreSQL `pgvector`**. Die Anwendung ruft Bedrock Embedding-Modelle auf, zum Beispiel Titan Text Embeddings V2, speichert Vektoren in `pgvector`, führt Similarity Search in PostgreSQL aus und ruft anschließend ein Generierungsmodell auf Bedrock auf. Dieser Pfad ist testbar, portabel und betrieblich verständlich. Bedrock Knowledge Bases bleibt eine attraktive Managed-Alternative, wenn Chunking, Ingestion, Retrieval und `RetrieveAndGenerate` stärker als Service konsumiert werden sollen (https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html).

In-database inference über Aurora Machine Learning und `aws_ml` ist technisch relevant, aber nicht der Default. SQL kann über `aws_bedrock.invoke_model(...)` Bedrock direkt aufrufen (https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/postgresql-ml.html). Das ist für einfache Embedding-Erzeugung nahe an den Daten interessant, koppelt aber Datenbanktransaktionen, Modellaufrufe, Latenz und Kosten enger zusammen. Für High-throughput Retrieval, saubere Tests und flexible Modellwechsel ist die Anwendungsschicht meist robuster.

## Chancen

Der Stack bietet für MHP/Porsche-nahe Enterprise-Kontexte mehrere Chancen. Erstens bleiben relationale Fakten, Berechtigungsattribute und Embeddings in einem konsistenten Transaktionsraum, solange `pgvector` auf Aurora PostgreSQL genügt. Zweitens kann die Plattform klein starten: Aurora Serverless v2, Bedrock und klar geschnittene Applikationslogik reichen für einen ernsthaften PoC. Drittens bleibt der Ausbaupfad offen: OpenSearch für anspruchsvolle hybride Suche, S3 Vectors für große kostensensitive Embedding-Bestände, Neptune Analytics für GraphRAG, Bedrock Knowledge Bases für Managed RAG.

## Grenzen

Die Grenzen sind ebenso wichtig. `pgvector` ersetzt keine vollwertige Enterprise Search Engine. Native BM25-plus-vector Hybrid Search, Re-Ranking Pipelines und Suchrelevanz-Engineering sprechen eher für OpenSearch. Aurora PostgreSQL ist kein kostenloser Vektor-Cache: HNSW-Indizes brauchen Speicher, Indexaufbau muss geplant werden, Recall und Latenz brauchen SLOs. Bedrock ist kein lokaler Funktionsaufruf: Modellzugriff muss pro Region aktiviert werden, Kosten entstehen pro Embedding, Token und Generation, und Fehlerbilder gehören in Retry-, Timeout- und Observability-Design.

## Zwischenstand

Die belastbare Entscheidung lautet deshalb nicht „eine Datenbank für alles“, sondern **ein kleiner, korrekt positionierter Kern mit klaren Erweiterungspfaden**. Für dieses Quartal ist Aurora PostgreSQL Serverless v2 mit `pgvector` und Bedrock der Go-to-Kern. Aurora DSQL bleibt im Zielbild wichtig, aber als multi-region OLTP-Baustein, nicht als Vektor-Backend für diesen RAG-PoC. Nächstes Quartal sollte die Arbeit an Neptune GraphRAG anschließen, weil dort Vektorähnlichkeit, Graphstruktur und Retrieval-Qualität zusammengeführt werden.
