# 05, Bedrock Integration, Abfrage und Inferenz nahe an der Datenbank

Dieses Kapitel beschreibt drei Wege, wie Amazon Bedrock in einen produktionsnahen Aurora PostgreSQL `pgvector` Stack integriert werden kann. Die zentrale Frage ist nicht, ob Bedrock aufgerufen werden kann, sondern **wo** der Modellaufruf hingehört: in die Datenbank, in die Anwendung oder in einen Managed RAG Service. Für den PoC ist die empfohlene Default-Variante Application-layer RAG. Die beiden anderen Varianten bleiben wichtig, weil sie für engere Datenbanknähe oder weniger Implementierungsaufwand legitim sind.

## Option 1, In-database inference mit Aurora Machine Learning

Aurora PostgreSQL kann über Aurora Machine Learning externe ML-Services integrieren. Die Erweiterung `aws_ml` stellt unter anderem `aws_bedrock.invoke_model(...)` bereit, sodass SQL direkt Amazon Bedrock aufrufen kann (https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/postgresql-ml.html). Voraussetzung ist ein Aurora PostgreSQL Cluster mit passender IAM-Rolle, Bedrock-Berechtigungen und installierter Extension. Für Vektor-Workloads ist dies besonders naheliegend, wenn Embeddings direkt beim Schreiben oder Nachpflegen von Datensätzen erzeugt werden sollen.

Vereinfachtes SQL-Muster für ein Embedding mit Titan Text Embeddings V2:

```sql
CREATE EXTENSION IF NOT EXISTS aws_ml CASCADE;
CREATE EXTENSION IF NOT EXISTS vector;

WITH model_response AS (
  SELECT aws_bedrock.invoke_model(
    model_id => 'amazon.titan-embed-text-v2:0',
    content_type => 'application/json',
    accept_type => 'application/json',
    model_input => json_build_object(
      'inputText', 'Predictive maintenance report for battery module A12',
      'dimensions', 1024,
      'normalize', true
    )::text
  ) AS response
)
SELECT response
FROM model_response;
```

In einer produktiven Implementierung wird das JSON-Ergebnis modellabhängig ausgelesen, in einen `vector`-Wert transformiert und zusammen mit fachlichen Metadaten gespeichert. Titan Text Embeddings V2 unterstützt laut AWS variable Embedding-Dimensionen und ist für Text-Embedding-Anwendungsfälle in Bedrock vorgesehen (https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html).

Der Vorteil ist die Datenlokalität. ETL-nahe Jobs, Backfills oder einfache Trigger-gesteuerte Muster können direkt aus SQL heraus arbeiten. Das reduziert bewegliche Teile und kann für kleine Workloads elegant sein. Der Nachteil ist die Kopplung: Datenbanktransaktion, Netzwerklatenz, Modellverfügbarkeit, IAM-Berechtigung und Modellkosten treffen sich in einem SQL-Pfad. Pro-Zeile-Aufrufe können teuer und langsam werden. Außerdem wird Testbarkeit schwieriger, weil ein SQL-Statement plötzlich einen externen AI-Service aufruft.

Diese Option ist deshalb geeignet für:

- kleine bis mittlere Batch- oder Backfill-Prozesse,
- einfache in-SQL Embedding-Erzeugung,
- Prototyping nahe an bestehenden SQL Workflows,
- kontrollierte administrative Jobs, nicht für hochfrequente Online-Pfade.

Sie ist nicht geeignet als Default für High-throughput Retrieval, interaktive Chat-Anwendungen oder stark beobachtbare Enterprise-RAG-Flows.

## Option 2, Application-layer RAG als empfohlener PoC-Default

Beim Application-layer RAG ruft die Anwendung Bedrock direkt auf, typischerweise über `boto3`, AWS SDK for Java oder eine interne Plattformbibliothek. Die Anwendung erzeugt Embeddings, schreibt sie in Aurora PostgreSQL `pgvector`, führt Similarity Search aus und ruft anschließend ein generatives Modell auf Bedrock auf, zum Beispiel Anthropic Claude auf Amazon Bedrock. Aurora PostgreSQL bleibt dabei Datenbank und Vektorindex, nicht Orchestrator der Modelllogik.

Typischer Ablauf:

1. Dokument oder Datensatz wird fachlich normalisiert.
2. Anwendung chunked den Text nach domänenspezifischen Regeln.
3. Bedrock Titan Text Embeddings V2 erzeugt Embeddings.
4. Aurora PostgreSQL speichert Chunk, Metadaten, Security Attribute und `vector`.
5. Query wird eingebettet.
6. `pgvector` sucht Kandidaten, optional mit relationalen Filtern.
7. Anwendung baut Prompt-Kontext, erzwingt Guardrails, ruft das Generierungsmodell auf.
8. Antwort, Quellen und Metriken werden protokolliert.

Der entscheidende Vorteil ist Entkopplung. Modellwahl, Prompting, Retry-Strategie, Rate Limits, Caching, Evaluation, A/B Tests und Observability liegen in Anwendung oder Plattformservice. Das passt besser zu CI/CD, Unit Tests, Integration Tests und Sicherheitsreviews. Auch ein späterer Wechsel von Aurora `pgvector` zu OpenSearch oder S3 Vectors ist einfacher, weil die Datenbank nicht selbst Modellaufrufe orchestriert.

Produktionsnah muss diese Variante trotzdem sauber gebaut werden. Embedding-Dimensionen gehören als Konfiguration versioniert. Modell-IDs, Region, Timeout und Retry-Budgets müssen explizit sein. Security Filter dürfen nicht erst im Prompt passieren, sondern müssen vor dem Retrieval oder im Retrieval-Query angewendet werden. Prompt-Kontext muss Quellen, Zeitstempel, Klassifikation und Zugriffskontext enthalten. Halluzinationsschutz entsteht nicht durch Bedrock allein, sondern durch Retrieval-Qualität, Zitierung, Evaluation und klare Antwortgrenzen.

Diese Option ist geeignet für:

- den empfohlenen PoC,
- Teams mit eigener Anwendungsschicht,
- produktionsnahe Tests und Modellwechsel,
- Domänenlogik, Security Filtering und Observability,
- Architekturen, die später mehrere Vector Stores unterstützen sollen.

Ihr Nachteil ist mehr eigener Code. Chunking, Ingestion, Fehlerbehandlung, Reindexierung und Evaluation müssen gebaut oder als interne Plattformkomponenten standardisiert werden.

## Option 3, Fully managed RAG mit Bedrock Knowledge Bases

Amazon Bedrock Knowledge Bases ist der Managed-RAG-Pfad. Der Service übernimmt Datenquellenanbindung, Chunking, Embedding, Ingestion, Retrieval und optional die Generierung über `RetrieveAndGenerate` (https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html). Als Vector Stores unterstützt Bedrock Knowledge Bases mehrere Backends, darunter Amazon Aurora PostgreSQL, Amazon OpenSearch Serverless, Amazon S3 Vectors, Neptune Analytics, Pinecone und MongoDB-kompatible Optionen. AWS dokumentiert Aurora PostgreSQL als unterstützte Vektordatenbank für Knowledge Bases (https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html).

Der Vorteil ist Geschwindigkeit. Ein Team muss weniger Ingestion- und Retrieval-Code schreiben und kann stärker serviceorientiert arbeiten. Das ist besonders attraktiv für frühe Enterprise Use Cases mit überschaubarer Domänenlogik, klaren Dokumentquellen und dem Wunsch nach schneller Standardisierung.

Der Trade-off ist Kontrolle. Chunking, Metadatenmodell, Retrieval-Tuning, Evaluationshooks, mehrstufige Reranking-Strategien und kundenspezifische Guardrails sind weniger frei gestaltbar als in einer eigenen Anwendungsschicht. Außerdem entsteht eine stärkere Abhängigkeit von Knowledge-Bases-spezifischen APIs und Servicegrenzen. Für Teams, die ihr Retrieval-Verhalten genau messen, erklären und optimieren müssen, kann das einschränkend sein.

Diese Option ist geeignet für:

- schnelle Managed-RAG-Prototypen,
- dokumentengetriebene Assistenzsysteme,
- Teams mit wenig eigener Plattformkapazität,
- standardisierte Ingestion in bekannten AWS-Grenzen,
- Use Cases, bei denen weniger Code wichtiger ist als maximale Kontrolle.

Sie ist weniger geeignet, wenn Retrieval selbst ein differenzierender Kern des Produkts ist oder wenn sehr spezifische Ranking-, Compliance- oder Erklärbarkeitsanforderungen bestehen.

## Vergleich und Empfehlung

| Kriterium | In-database inference | Application-layer RAG | Bedrock Knowledge Bases |
|---|---|---|---|
| Hauptidee | SQL ruft Bedrock direkt auf | Anwendung orchestriert Embedding, Retrieval und Generation | AWS Managed Service orchestriert RAG |
| Kontrollgrad | Mittel, aber stark DB-gekoppelt | Hoch | Mittel bis niedrig |
| Implementierungsaufwand | Niedrig für einfache Fälle | Mittel | Niedrig |
| Testbarkeit | Eingeschränkt | Hoch | Mittel |
| Betriebliches Risiko | Per-row Latenz und Kosten in DB-Pfad | Verteilte Komponenten, aber beobachtbar | Servicegrenzen und geringere Transparenz |
| Best-fit | Backfills, einfache SQL-nahe Embeddings | PoC Default und produktionsnahe App | Managed RAG mit wenig Custom Logic |

Die PoC-Empfehlung ist klar: **Application-layer RAG**. Dieser Pfad ist robust genug für Enterprise Engineering, vermeidet eine Überkopplung der Datenbank an Modellaufrufe und lässt spätere Vector-Store-Entscheidungen offen. In-database inference ist ein nützliches Spezialwerkzeug. Bedrock Knowledge Bases ist ein ernstzunehmender Managed-Pfad, wenn Geschwindigkeit und Standardisierung wichtiger sind als volle Retrieval-Kontrolle.
