# AI-native Query Patterns: Produktions-RAG mit pgvector

RAG-Systeme scheitern selten am ersten Demo-Prompt. Sie scheitern an Mandantenfiltern, veralteten Embeddings, unklarer Score-Semantik, kalten Indexen, fehlender Evaluierung und zu optimistischen Annahmen über Vektorsuche. Dieses Kapitel beschreibt AI-native Query Patterns auf Aurora PostgreSQL oder RDS PostgreSQL mit `pgvector`: von der Embedding-Pipeline über SQL-Retrieval bis zu Hybrid Search, Reranking und Multi-Tenant-Betrieb.

Der Fokus liegt auf produktionsfähigen Mustern, nicht auf Notebook-Minimalbeispielen. `pgvector` kann ein sehr guter Retrieval-Layer sein, wenn die Grenzen klar sind. Es ist aber keine native BM25-Fusion-Engine und ersetzt bei sehr großen, relevance-kritischen Suchprodukten nicht automatisch OpenSearch oder andere spezialisierte Search-Systeme.

## Referenzarchitektur: vom Dokument zum Retrieval Context

Eine belastbare Pipeline besteht aus mehreren Schritten:

1. Dokumente ingestieren und normalisieren.
2. Chunks erzeugen, inklusive stabiler IDs und Overlap-Strategie.
3. Embeddings mit einem Modell erzeugen, zum Beispiel Amazon Titan Text Embeddings V2.
4. Vektoren optional normalisieren, abhängig von Modell und Distanzmetrik.
5. Chunks, Metadaten und Embeddings per Batch Upsert speichern.
6. Indexe bauen oder inkrementell pflegen.
7. Retrieval evaluieren, reranken und in den Prompt-Kontext überführen.

Amazon Titan Text Embeddings V2 ist über Bedrock verfügbar und nutzt die Modell-ID `amazon.titan-embed-text-v2:0`. Das Modell unterstützt konfigurierbare Ausgabegrößen von 256, 512 und 1.024 Dimensionen [Amazon Titan Text Embeddings models](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html). Diese Optionen passen gut zu `pgvector`, weil 1.024 Dimensionen unter der Full-precision-Indexgrenze von `vector` liegen [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md).

## Embedding Pipeline

### Chunking ist ein Retrieval-Design, kein ETL-Nebeneffekt

Chunking bestimmt, was später gefunden werden kann. Zu kleine Chunks verlieren Kontext, zu große Chunks verschlechtern Präzision und füllen Prompt-Budgets. Für technische Dokumentation funktionieren oft Chunks entlang von Überschriften, Absätzen, Tabellen und Codeblöcken besser als starre Zeichenfenster. Overlap kann helfen, darf aber nicht unkontrolliert Storage und Trefferduplikate erhöhen.

Eine produktionsnahe Tabelle trennt Dokumentversion, Chunk und Embedding:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_chunks (
  tenant_id text NOT NULL,
  document_id uuid NOT NULL,
  document_version integer NOT NULL,
  chunk_id uuid NOT NULL,
  chunk_no integer NOT NULL,
  content text NOT NULL,
  content_hash text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  embedding vector(1024) NOT NULL,
  embedding_model text NOT NULL,
  embedded_at timestamptz NOT NULL DEFAULT now(),
  is_current boolean NOT NULL DEFAULT true,
  PRIMARY KEY (tenant_id, chunk_id),
  UNIQUE (tenant_id, document_id, document_version, chunk_no)
);

CREATE INDEX rag_chunks_current_idx
ON rag_chunks (tenant_id, document_id, is_current);

CREATE INDEX rag_chunks_metadata_gin_idx
ON rag_chunks USING gin (metadata);

CREATE INDEX rag_chunks_embedding_hnsw_idx
ON rag_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 256);
```

`content_hash` verhindert unnötige Re-Embeddings. `embedding_model` macht Modellwechsel auditierbar. `is_current` erlaubt versionierte Frische, ohne historische Chunks sofort zu löschen.

### Batch Upsert und Idempotenz

Embedding-Aufrufe kosten Geld und Zeit. Batch-Verarbeitung sollte daher idempotent sein. Ein typisches Upsert-Muster aktualisiert nur geänderte Chunks.

```sql
INSERT INTO rag_chunks (
  tenant_id,
  document_id,
  document_version,
  chunk_id,
  chunk_no,
  content,
  content_hash,
  metadata,
  embedding,
  embedding_model,
  embedded_at,
  is_current
)
VALUES (
  :tenant_id,
  :document_id,
  :document_version,
  :chunk_id,
  :chunk_no,
  :content,
  :content_hash,
  :metadata::jsonb,
  :embedding::vector,
  'amazon.titan-embed-text-v2:0',
  now(),
  true
)
ON CONFLICT (tenant_id, chunk_id)
DO UPDATE SET
  content = EXCLUDED.content,
  content_hash = EXCLUDED.content_hash,
  metadata = EXCLUDED.metadata,
  embedding = EXCLUDED.embedding,
  embedding_model = EXCLUDED.embedding_model,
  embedded_at = EXCLUDED.embedded_at,
  is_current = true
WHERE rag_chunks.content_hash <> EXCLUDED.content_hash
   OR rag_chunks.embedding_model <> EXCLUDED.embedding_model;
```

Nach großen Loads sind `ANALYZE` und ein bewusstes Index-Build-Fenster Pflicht. Bei sehr großen HNSW-Indexen muss `maintenance_work_mem` geplant werden [Aurora PostgreSQL as a Vector Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html).

## Pattern 1: Top-k Similarity Search

Das Basismuster ist eine sortierte Vektorsuche. Bei Cosine Distance gilt: kleiner Abstand ist besser.

```sql
SET hnsw.ef_search = 80;

SELECT
  tenant_id,
  document_id,
  chunk_id,
  chunk_no,
  content,
  1 - (embedding <=> :query_embedding::vector) AS similarity
FROM rag_chunks
WHERE tenant_id = :tenant_id
  AND is_current = true
ORDER BY embedding <=> :query_embedding::vector
LIMIT 8;
```

Produktionshinweise: `LIMIT` muss begrenzt sein, typischerweise 5 bis 50 Kandidaten vor Reranking. Ein unbounded k ist Kosten- und Latenzfehler. `hnsw.ef_search` ist ein Recall-Latenz-Regler und sollte pro Query-Klasse oder Session gesetzt werden. Für einfache FAQ-RAG reichen oft niedrigere Werte. Für juristische, sicherheitsrelevante oder technische Entscheidungen braucht man höhere Recall-Ziele und Messdaten.

## Pattern 2: Metadata Pre-Filtering

Enterprise-RAG ist fast immer gefiltert: Mandant, Region, Sprache, Freigabestatus, Produktlinie, Dokumenttyp, Gültigkeitsdatum. Diese Filter dürfen nicht erst nach dem Prompt angewendet werden. Sie gehören in SQL.

```sql
SET hnsw.ef_search = 120;

SELECT
  document_id,
  chunk_id,
  content,
  metadata,
  1 - (embedding <=> :query_embedding::vector) AS similarity
FROM rag_chunks
WHERE tenant_id = :tenant_id
  AND is_current = true
  AND metadata @> '{"language":"de"}'::jsonb
  AND (metadata ->> 'classification') IN ('public', 'internal')
  AND (metadata ->> 'valid_from')::date <= current_date
ORDER BY embedding <=> :query_embedding::vector
LIMIT 12;
```

Das ist Pre-Filtering auf SQL-Ebene. Trotzdem kann der ANN-Index intern Kandidaten liefern, die Filter anschließend verwerfen. Bei selektiven Filtern sinkt Recall. `pgvector` 0.8 unterstützt iterative index scans, die in solchen Fällen zusätzliche Kandidaten nachziehen können [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md). Zusätzlich helfen klassische Indexe:

```sql
CREATE INDEX rag_chunks_tenant_current_language_idx
ON rag_chunks (tenant_id, is_current, ((metadata ->> 'language')));
```

Für sehr große Mandanten oder stabile Segmente können Partial HNSW Indexes sinnvoll sein:

```sql
CREATE INDEX rag_chunks_embedding_hnsw_tenant_porsche_idx
ON rag_chunks USING hnsw (embedding vector_cosine_ops)
WHERE tenant_id = 'porsche' AND is_current = true;
```

Der Trade-off ist klar: bessere Query-Latenz und potenziell besserer Recall für dieses Segment, aber mehr Storage, langsamere Writes und mehr Indexwartung.

## Pattern 3: Hybrid Search mit Full-Text und Vector Score

Viele reale Fragen enthalten Begriffe, IDs, Fehlercodes oder Produktnamen, die Vektorsuche allein schlechter behandelt als lexikalische Suche. PostgreSQL bietet Full-Text Search mit `tsvector` und `ts_rank`. `pgvector` bietet Vektordistanz. Die Fusion muss man selbst bauen. `pgvector` allein hat keine native BM25-Fusion und keine automatische Ranking-Normalisierung.

Eine einfache Struktur ergänzt eine generierte Suchspalte:

```sql
ALTER TABLE rag_chunks
ADD COLUMN search_vector tsvector
GENERATED ALWAYS AS (to_tsvector('german', content)) STORED;

CREATE INDEX rag_chunks_search_vector_idx
ON rag_chunks USING gin (search_vector);
```

Eine hybride Query kann Kandidaten aus beiden Welten holen und Scores normalisieren:

```sql
WITH vector_candidates AS (
  SELECT
    chunk_id,
    1 - (embedding <=> :query_embedding::vector) AS vector_score
  FROM rag_chunks
  WHERE tenant_id = :tenant_id
    AND is_current = true
  ORDER BY embedding <=> :query_embedding::vector
  LIMIT 50
), text_candidates AS (
  SELECT
    chunk_id,
    ts_rank(search_vector, websearch_to_tsquery('german', :query_text)) AS text_score
  FROM rag_chunks
  WHERE tenant_id = :tenant_id
    AND is_current = true
    AND search_vector @@ websearch_to_tsquery('german', :query_text)
  ORDER BY text_score DESC
  LIMIT 50
), merged AS (
  SELECT chunk_id FROM vector_candidates
  UNION
  SELECT chunk_id FROM text_candidates
)
SELECT
  c.document_id,
  c.chunk_id,
  c.content,
  COALESCE(v.vector_score, 0) AS vector_score,
  COALESCE(t.text_score, 0) AS text_score,
  (0.65 * COALESCE(v.vector_score, 0))
    + (0.35 * LEAST(COALESCE(t.text_score, 0), 1.0)) AS combined_score
FROM merged m
JOIN rag_chunks c ON c.chunk_id = m.chunk_id
LEFT JOIN vector_candidates v ON v.chunk_id = m.chunk_id
LEFT JOIN text_candidates t ON t.chunk_id = m.chunk_id
WHERE c.tenant_id = :tenant_id
ORDER BY combined_score DESC
LIMIT 12;
```

Dieses Beispiel ist bewusst transparent, aber nicht universell. `ts_rank` und Cosine Similarity sind nicht automatisch vergleichbar. Gewichtung, Clipping und Normalisierung müssen anhand eines Evaluierungssets kalibriert werden. Wenn Hybrid Search der Kern des Produkts ist, wenn BM25-Fusion, Synonyme, Analyzer, Facetten, Highlighting und hohe Query-Parallelität nötig sind, ist OpenSearch in AWS oft der bessere Hybrid Engine. PostgreSQL bleibt dann System of Record oder Metadatenquelle.

## Pattern 4: Reranking als zweite Stufe

ANN-Retrieval ist Kandidatensuche, nicht finales Ranking. Ein zweiter Reranking-Schritt kann Qualität deutlich verbessern. Das Muster: PostgreSQL liefert 30 bis 100 Kandidaten, ein Cross-Encoder oder Rerank-Modell bewertet Query-Chunk-Paare neu, danach gehen nur die besten Chunks in den LLM-Prompt. In AWS kann dieser Schritt über ein Bedrock Rerank-Modell oder Cohere Rerank angebunden werden, je nach freigegebener Modelllandschaft.

SQL-seitig braucht man dafür stabile Kandidaten mit Text und Metadaten:

```sql
SELECT
  document_id,
  chunk_id,
  chunk_no,
  content,
  metadata,
  1 - (embedding <=> :query_embedding::vector) AS initial_score
FROM rag_chunks
WHERE tenant_id = :tenant_id
  AND is_current = true
ORDER BY embedding <=> :query_embedding::vector
LIMIT 80;
```

Die Applikation ruft anschließend das Rerank-Modell auf und speichert optional Evaluierungsdaten:

```sql
CREATE TABLE rag_retrieval_audit (
  request_id uuid NOT NULL,
  tenant_id text NOT NULL,
  chunk_id uuid NOT NULL,
  initial_rank integer NOT NULL,
  initial_score double precision NOT NULL,
  rerank_score double precision,
  selected_for_prompt boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (request_id, chunk_id)
);
```

Audit-Daten sind kein Luxus. Sie beantworten später, warum eine Antwort einen bestimmten Kontext hatte, welche Chunks fehlten und ob Änderungen an `ef_search`, Chunking oder Modellversion die Qualität verbessert haben.

## Pattern 5: Multi-Tenant Isolation

Mandantenisolation darf nicht im Prompt passieren. Sie muss in Datenmodell, Query und idealerweise in Datenbankberechtigungen sichtbar sein. Das minimale SQL-Muster filtert immer auf `tenant_id`. Für stärkere Isolation kann PostgreSQL Row-Level Security genutzt werden.

```sql
ALTER TABLE rag_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY rag_chunks_tenant_policy
ON rag_chunks
USING (tenant_id = current_setting('app.tenant_id'));
```

Die Applikation setzt pro Transaktion den Tenant-Kontext:

```sql
BEGIN;
SET LOCAL app.tenant_id = :tenant_id;

SELECT chunk_id, content
FROM rag_chunks
WHERE is_current = true
ORDER BY embedding <=> :query_embedding::vector
LIMIT 10;

COMMIT;
```

RLS ersetzt keine Anwendungskontrolle, reduziert aber Blast Radius bei Query-Fehlern. In stark regulierten Umgebungen sollte zusätzlich geprüft werden, ob Mandanten physisch getrennte Cluster, Schemas oder Datenbanken benötigen. Diese Entscheidung ist weniger eine Vektorfrage als eine Governance-Frage.

## Freshness und Re-Embedding

Wissensstände ändern sich. RAG-Systeme brauchen Frischemechanismen: Upsert bei Dokumentänderung, Invalidierung alter Versionen, Backfill bei Modellwechsel und Reindexing bei großen Strukturänderungen.

Ein einfaches Muster markiert alte Versionen inaktiv:

```sql
UPDATE rag_chunks
SET is_current = false
WHERE tenant_id = :tenant_id
  AND document_id = :document_id
  AND document_version < :new_document_version;
```

Bei Modellwechseln sollte man nicht alle Chunks blind überschreiben, sondern parallelisieren und messbar migrieren. Ein Feld wie `embedding_model` erlaubt gemischten Betrieb während einer Migration. Queries können dann bewusst auf eine Modellgeneration begrenzt werden:

```sql
SELECT chunk_id, content
FROM rag_chunks
WHERE tenant_id = :tenant_id
  AND is_current = true
  AND embedding_model = 'amazon.titan-embed-text-v2:0'
ORDER BY embedding <=> :query_embedding::vector
LIMIT 10;
```

## Anti-Patterns und Limits

<table>
  <thead>
    <tr>
      <th>Anti-Pattern</th>
      <th>Problem</th>
      <th>Besseres Muster</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Sehr hohe Full-precision-Dimensionen</td>
      <td>`vector` ist nur bis 2.000 Dimensionen indexierbar.</td>
      <td>Titan V2 mit 1.024 Dimensionen, `halfvec`, Reduktion oder andere Architektur.</td>
    </tr>
    <tr>
      <td>Naive Post-Filterung</td>
      <td>Recall sinkt, weil Kandidaten nachträglich verworfen werden.</td>
      <td>Pre-Filter, Partial Indexes, iterative scans, höheres `ef_search`.</td>
    </tr>
    <tr>
      <td>Unbounded k</td>
      <td>Hohe Latenz, hohe Kosten, schlechter Prompt-Kontext.</td>
      <td>Begrenztes k, Reranking, Prompt-Budget.</td>
    </tr>
    <tr>
      <td>Fehlendes `ANALYZE`</td>
      <td>Schlechte Planner-Entscheidungen nach Loads.</td>
      <td>`ANALYZE` nach Bulk Ingest und regelmäßige Wartung.</td>
    </tr>
    <tr>
      <td>Kalter HNSW Cache</td>
      <td>p95 und p99 brechen nach Deployments oder Failover ein.</td>
      <td>Warmup-Queries, realistische Load Tests, passende Instanzgröße.</td>
    </tr>
    <tr>
      <td>Score als Wahrheit</td>
      <td>Similarity ist keine faktische Korrektheit.</td>
      <td>Ground Truth, Reranking, Quellenanzeige, Antwortvalidierung.</td>
    </tr>
  </tbody>
</table>

## Betriebsmetriken

Ein RAG-Retrieval-Layer braucht eigene SLOs. Sinnvolle Metriken sind Query-Latenz nach Stufe, Trefferanzahl vor und nach Filterung, Anteil leerer Retrievals, durchschnittliches `ef_search`, Rerank-Latenz, Prompt-Token pro Antwort, Cache-Hit-Rate und Retrieval-Recall auf einem kuratierten Testset. Kosten entstehen nicht nur im LLM, sondern auch bei Embedding-Erzeugung, Storage, HNSW-Wartung und Reranking.

Aurora PostgreSQL mit `pgvector` ist stark, wenn Retrieval und relationale Governance nah beieinander liegen. Die AWS-Dokumentation positioniert Aurora PostgreSQL explizit als Vector Database mit `pgvector` [Aurora PostgreSQL as a Vector Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html). Das ist aber kein Freibrief für beliebige Suchanforderungen. Für produktionskritische Relevanz muss jede Query-Klasse gemessen und nicht nur syntaktisch implementiert werden.

## Quellen

- pgvector README: https://github.com/pgvector/pgvector/blob/master/README.md
- AWS, Amazon Titan Text Embeddings models: https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html
- AWS, Aurora PostgreSQL as a Vector Database: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html
