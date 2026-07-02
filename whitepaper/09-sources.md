# 09, Quellen, konsolidiert

Zugriffsdatum für alle Quellen: **2026-07-02**.

## Aurora, PostgreSQL und Datenbankintegration

- https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html, AWS Dokumentation zu Aurora PostgreSQL als Vector Database mit `pgvector`, genutzt für Architekturentscheidung und Vector-Store-Bewertung.
- https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/postgresql-ml.html, AWS Dokumentation zu Aurora Machine Learning und `aws_ml`, genutzt für in-database inference mit `aws_bedrock.invoke_model(...)`.
- https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html, AWS Dokumentation zu Aurora Serverless v2, genutzt für Skalierung, ACU-Modell und Produktionsbetrieb.
- https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/data-api.html, AWS Dokumentation zur RDS Data API, genutzt für Connectivity-Entscheidung zwischen HTTPS Data API und In-VPC PostgreSQL.
- https://docs.aws.amazon.com/aurora-dsql/latest/userguide/what-is-aurora-dsql.html, AWS Dokumentation zu Aurora DSQL als serverlosem distributed OLTP-Service, genutzt zur Abgrenzung von Aurora DSQL gegenüber `pgvector`-RAG-Workloads.

## Amazon Bedrock, RAG und Modelle

- https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html, AWS Dokumentation zu Amazon Bedrock Knowledge Bases, genutzt für Managed-RAG-Option, Backends und `RetrieveAndGenerate`-Einordnung.
- https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html, AWS Dokumentation zu Titan Text Embeddings, genutzt für Embedding-Modellwahl und Dimensionshinweise.
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html, AWS Dokumentation zu Bedrock Model Access, genutzt für regionale Modellfreigabe und Produktionscheckliste.
- https://docs.aws.amazon.com/bedrock/latest/userguide/bda.html, AWS Dokumentation zu Bedrock Data Automation, genutzt für die Einordnung von unstructured-data ETL als angrenzenden Baustein.

## Vector Stores und Search

- https://aws.amazon.com/s3/features/vectors/, AWS Produktseite zu Amazon S3 Vectors, genutzt für Vector Buckets, APIs, Dimensionen, Distanzmetriken, Metadatenfilter und Kostenprofil.
- https://docs.aws.amazon.com/opensearch-service/latest/developerguide/knn.html, AWS Dokumentation zu k-NN in Amazon OpenSearch Service, genutzt für OpenSearch Vector Search und Hybrid-Search-Einordnung.
- https://docs.aws.amazon.com/documentdb/latest/devguide/vector-search.html, AWS Dokumentation zu Vector Search in Amazon DocumentDB, genutzt für Dimensionen, HNSW/IVFFlat und Filterbewertung.
- https://aws.amazon.com/blogs/aws/vector-search-for-amazon-documentdb-with-mongodb-compatibility-is-now-generally-available/, AWS News Blog zur General Availability von DocumentDB Vector Search, genutzt für Produktstatus und Fähigkeiten.
- https://docs.aws.amazon.com/neptune-analytics/latest/userguide/vector-search.html, AWS Dokumentation zu Vector Search in Neptune Analytics, genutzt für GraphRAG-Ausblick und Vector Search innerhalb graphnaher Workflows.

## Agentic AI und Consumption Layer

- https://aws.amazon.com/blogs/aws/introducing-amazon-bedrock-agentcore-securely-deploy-and-operate-ai-agents-at-any-scale/, AWS News Blog zur Einführung von Amazon Bedrock AgentCore, genutzt für Preview-/GA-Kontext und Komponentenüberblick.
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html, AWS Dokumentation zu Amazon Bedrock AgentCore, genutzt für Einordnung als Agent-Application-Infrastruktur und nicht als Data-Engineering-Kernbaustein.
