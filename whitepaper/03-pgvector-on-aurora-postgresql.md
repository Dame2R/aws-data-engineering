# pgvector auf Amazon Aurora PostgreSQL und RDS PostgreSQL

Wenn Vektoren direkt in SQL gespeichert werden sollen, ist Aurora PostgreSQL mit `pgvector` der natürliche Startpunkt im AWS-PostgreSQL-Portfolio. Nicht Aurora DSQL, nicht automatisch eine separate Vector Database. Für viele Enterprise-RAG- und semantische Suchmuster reicht PostgreSQL aus, wenn Datenmodell, Indexgrenzen, Recall-Ziele und Betriebsparameter sauber verstanden werden. Der Vorteil ist einfach: Embeddings, Metadaten, Mandantenfilter, Berechtigungen, Transaktionen und klassische SQL-Abfragen bleiben in einem konsistenten Datenbanksystem.

Dieses Kapitel beschreibt den Stand Juli 2026 für Aurora PostgreSQL und RDS PostgreSQL, die wichtigsten Datentypen und Indexarten von `pgvector`, typische Produktionsfallen und ein vollständiges SQL-Beispiel für 1.024-dimensionale Embeddings.

## Versionen und Erwartungsmanagement

AWS liefert `pgvector` als PostgreSQL Extension in Aurora PostgreSQL und RDS PostgreSQL. Der Versionsstand ist nicht immer identisch mit dem Community-Projekt. Für Juli 2026 gilt laut vorliegendem Recherchestand: Aurora PostgreSQL 18.3 und 17.9 enthalten `pgvector` 0.8.1, RDS PostgreSQL 18.4 enthält `pgvector` 0.8.2, während Upstream bereits bei 0.8.4 liegt. Praktisch bedeutet das: AWS ist in der Regel produktionsstabil, aber ein bis zwei Patchstände hinter Community.

Die AWS-Dokumentation beschreibt Aurora PostgreSQL als Vector Database mit `pgvector` und verweist auf unterstützte Versionen und Betriebsaspekte [Aurora PostgreSQL as a Vector Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html). Die Extension-Matrix der Aurora PostgreSQL Release Notes bleibt die verbindliche Quelle für konkrete Versionen pro Engine-Version [Aurora PostgreSQL extensions](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Extensions.html). Für Featuredetails, Operatoren und Indexparameter ist zusätzlich das Upstream-README relevant [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md).

Installation ist bewusst einfach:

```sql
CREATE EXTENSION vector;
```

In produktiven Umgebungen gehört diese Anweisung dennoch in Migrationen und Freigabeprozesse. Sie ist Schemaänderung und Betriebsentscheidung, nicht ein Notebook-Experiment.

## Datentypen: nicht jedes Embedding ist gleich

`pgvector` bietet mehrere Typen, die unterschiedliche Speicher-, Genauigkeits- und Indexprofile haben.

<table>
  <thead>
    <tr>
      <th>Typ</th>
      <th>Zweck</th>
      <th>Indexierbare Dimensionen</th>
      <th>Hinweise</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>`vector`</td>
      <td>Full-precision Float32</td>
      <td>Bis 2.000</td>
      <td>Standardtyp, größere Dimensionen können gespeichert werden, aber nicht voll indexiert.</td>
    </tr>
    <tr>
      <td>`halfvec`</td>
      <td>Float16</td>
      <td>Bis 4.000</td>
      <td>Halbiert Speicher grob, nützlich für 1.024 bis 4.000 Dimensionen.</td>
    </tr>
    <tr>
      <td>`bit`</td>
      <td>Binary Vector</td>
      <td>Bis 64.000</td>
      <td>Für Hamming und Jaccard, oft mit `binary_quantize()`.</td>
    </tr>
    <tr>
      <td>`sparsevec`</td>
      <td>Sparse Vector</td>
      <td>Bis 1.000 non-zero Elemente</td>
      <td>Nur HNSW, nützlich bei sparse Repräsentationen.</td>
    </tr>
  </tbody>
</table>

Der Full-precision-Typ `vector` hat eine relevante Grenze: bis 2.000 Dimensionen sind indexierbar. Größere Vektoren können je nach Typ gespeichert werden, aber nicht mit denselben Indexmöglichkeiten. Für Modelle mit 3.072 oder 4.096 Dimensionen muss man also früh entscheiden: dimensionality reduction, `halfvec`, anderes Modell oder andere Sucharchitektur.

Für Amazon Titan Text Embeddings V2 ist die Lage günstig, weil das Modell 256, 512 oder 1.024 Dimensionen konfigurieren kann. 1.024 passt sauber in `vector(1024)` und HNSW. Für viele Enterprise-Szenarien ist das eine gute Balance aus Qualität, Kosten und Indexgröße.

## Distanzoperatoren und Operator Classes

`pgvector` nutzt Operatoren, die im SQL direkt sichtbar sind:

<table>
  <thead>
    <tr>
      <th>Operator</th>
      <th>Bedeutung</th>
      <th>Typischer Einsatz</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>`&lt;-&gt;`</td>
      <td>L2 distance</td>
      <td>Geometrische Distanz, Embeddings ohne Cosine-Normierung.</td>
    </tr>
    <tr>
      <td>`&lt;#&gt;`</td>
      <td>Negative inner product</td>
      <td>Maximum Inner Product Search, wegen PostgreSQL-Indexsortierung als negativer Wert.</td>
    </tr>
    <tr>
      <td>`&lt;=&gt;`</td>
      <td>Cosine distance</td>
      <td>Häufiger Standard für Text-Embeddings.</td>
    </tr>
  </tbody>
</table>

Dazu gehören Operator Classes wie `vector_l2_ops`, `vector_cosine_ops` und `vector_ip_ops`. Die Operator Class im Index muss zur Abfrage passen. Ein HNSW-Index mit `vector_cosine_ops` beschleunigt also Abfragen, die mit `embedding <=> :query_embedding` sortieren.

## Indexarten: HNSW als Default, IVFFlat mit Vorsicht

`pgvector` unterstützt HNSW und IVFFlat. Beide sind Approximate-Nearest-Neighbor-Indexe, aber mit anderem Betriebsprofil.

<table>
  <thead>
    <tr>
      <th>Kriterium</th>
      <th>HNSW</th>
      <th>IVFFlat</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Default-Empfehlung</td>
      <td>Ja, meistens</td>
      <td>Nur wenn passend getunt</td>
    </tr>
    <tr>
      <td>Build auf leerer Tabelle</td>
      <td>Ja</td>
      <td>Nein, braucht Trainingsdaten</td>
    </tr>
    <tr>
      <td>Recall und Geschwindigkeit</td>
      <td>Meist besser</td>
      <td>Stark abhängig von `lists` und `probes`</td>
    </tr>
    <tr>
      <td>Build-Kosten</td>
      <td>Höher, mehr Memory</td>
      <td>Geringer, schneller</td>
    </tr>
    <tr>
      <td>Tuning</td>
      <td>`m`, `ef_construction`, `hnsw.ef_search`</td>
      <td>`lists`, `probes`</td>
    </tr>
  </tbody>
</table>

HNSW ist in der Praxis der robustere Ausgangspunkt. `m` ist standardmäßig 16, `ef_construction` 64. AWS empfiehlt für parallele Builds häufig höhere Werte wie 256, weil Recall und Graph-Qualität steigen können, während Build-Zeit und Memory-Bedarf ebenfalls steigen [Aurora PostgreSQL as a Vector Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html). Zur Laufzeit steuert `hnsw.ef_search` die Anzahl der betrachteten Kandidaten, Default ist 40. Höhere Werte verbessern Recall, erhöhen aber Latenz.

IVFFlat kann sinnvoll sein, wenn Build-Zeit wichtiger ist oder wenn Datenverteilung und Abfrageprofil gut verstanden sind. Die Faustregeln aus dem `pgvector`-README: `lists` ungefähr `rows / 1000` unter einer Million Zeilen, darüber etwa `sqrt(rows)`. `probes` bestimmt, wie viele Listen pro Query durchsucht werden. Höhere `probes` verbessern Recall und verschlechtern Latenz [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md).

## Quantisierung und neuere pgvector-Funktionen

Seit `pgvector` 0.7 gibt es eine Quantization Suite mit `halfvec`, `binary_quantize()` sowie scalar und binary quantization. Das ist produktionsrelevant, weil Vektorindizes schnell zu den größten Objekten im System werden. Wer 50 Millionen Dokument-Chunks mit 1.024 Float32-Werten speichert, muss nicht nur Query-Latenz, sondern auch Storage, Cache-Hit-Rate, Backup-Zeit und Reindexing-Fenster betrachten.

`halfvec` ist oft der erste pragmatische Schritt: weniger Speicher, höhere maximal indexierbare Dimensionen, dafür geringere numerische Genauigkeit. Binary Quantization kann extreme Speicherreduktion bringen, eignet sich aber nicht blind für jede Relevanzanforderung. Sie muss gegen Ground-Truth-Queries gemessen werden.

`pgvector` 0.8 brachte iterative index scans, die gefilterte Abfragen verbessern können. Das ist besonders wichtig, wenn ein ANN-Index zunächst Kandidaten findet und Filter anschließend viele davon verwerfen. Iterative Scans können mehr Kandidaten nachziehen und damit Recall bei Filtern erhöhen [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md).

## Worked Example: Dokumente mit 1.024-dimensionalem Embedding

Das folgende Beispiel ist bewusst einfach, aber produktionsnah. Es nutzt `jsonb` für Metadaten, Tenant-Isolation als explizite Spalte und Cosine Distance für Text-Embeddings.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  document_id uuid PRIMARY KEY,
  tenant_id text NOT NULL,
  source_uri text NOT NULL,
  chunk_no integer NOT NULL,
  content text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  embedding vector(1024) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, source_uri, chunk_no)
);

CREATE INDEX documents_tenant_source_idx
ON documents (tenant_id, source_uri);

CREATE INDEX documents_metadata_gin_idx
ON documents USING gin (metadata);

CREATE INDEX documents_embedding_hnsw_idx
ON documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 256);
```

Eine einfache Top-k-Suche sortiert nach Cosine Distance. Niedriger ist besser. Wer einen Score ausgeben will, kann `1 - distance` verwenden, solange alle Beteiligten verstehen, dass dies keine kalibrierte Wahrscheinlichkeit ist.

```sql
SET hnsw.ef_search = 80;

SELECT
  document_id,
  source_uri,
  chunk_no,
  content,
  1 - (embedding <=> :query_embedding::vector) AS similarity
FROM documents
WHERE tenant_id = :tenant_id
ORDER BY embedding <=> :query_embedding::vector
LIMIT 10;
```

Metadatenfilter können ergänzt werden. Wichtig ist die Abfragereihenfolge: Der Planner entscheidet, ob Filter und Vektorindex sinnvoll kombiniert werden. Bei stark selektiven Filtern können zusätzliche B-Tree-, GIN- oder Partial-Indexe entscheidend sein.

```sql
SET hnsw.ef_search = 120;

SELECT
  document_id,
  source_uri,
  chunk_no,
  content,
  metadata,
  1 - (embedding <=> :query_embedding::vector) AS similarity
FROM documents
WHERE tenant_id = :tenant_id
  AND metadata @> '{"language":"de"}'::jsonb
  AND metadata ->> 'classification' IN ('public', 'internal')
ORDER BY embedding <=> :query_embedding::vector
LIMIT 20;
```

Für große Mandanten kann ein Partial HNSW Index helfen. Das ist aber nur sinnvoll, wenn Mandanten oder Kategorien stabil und groß genug sind, weil jeder zusätzliche HNSW-Index Speicher, Build-Zeit und Write-Kosten erzeugt.

```sql
CREATE INDEX documents_embedding_hnsw_tenant_acme_idx
ON documents USING hnsw (embedding vector_cosine_ops)
WHERE tenant_id = 'acme';
```

## Produktionsfallen

### HNSW Build Time und `maintenance_work_mem`

HNSW baut einen Graphen. Wenn der Graph nicht in `maintenance_work_mem` passt, wird der Build deutlich langsamer. Für große Tabellen müssen Build-Fenster, Parallelität, Parameter und Instanzgröße geplant werden. Aurora Optimized Reads können helfen, wenn große Indexe und temporäre Arbeitsmengen I/O-intensiv werden [Aurora PostgreSQL as a Vector Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html).

### Recall und Latenz sind ein Budget

`hnsw.ef_search` ist kein magischer Qualitätsregler. Höhere Werte bedeuten mehr Kandidaten, mehr CPU, mehr Speicherzugriff und meist bessere Trefferqualität. Für ein produktives RAG-System sollte man Offline-Evaluierung mit typischen Fragen, erwarteten Dokumenten und Latenzbudgets durchführen. Ohne Messset wird Recall zum Bauchgefühl.

### Filter können Recall zerstören

Ein häufiger Fehler ist naive Post-Filterung: Der Vektorindex findet die nächsten Kandidaten global, danach verwirft der Filter fast alle wegen `tenant_id`, Sprache, Berechtigung oder Dokumenttyp. Ergebnis: wenig oder falscher Kontext. Gegenmittel sind Pre-Filter über selektive Spalten, Partial Indexes, iterative scans und, bei sehr hohen Anforderungen, eine Sucharchitektur mit spezialisierten Retrieval-Stufen.

### `ANALYZE` bleibt Pflicht

PostgreSQL braucht Statistiken. Nach großen Loads, Backfills oder Reindexing sollte `ANALYZE` eingeplant werden. Ohne aktuelle Statistiken kann der Planner schlechte Entscheidungen treffen, gerade wenn Metadatenfilter und Vektorsortierung kombiniert werden.

## Betriebsentscheidung: separate Vector DB oder nicht?

Für viele Enterprise Use Cases ist eine separate Vector Database nicht nötig. Wenn Retrieval eng an relationale Metadaten, Mandantenrechte, Dokumentzustände und Transaktionen gekoppelt ist, reduziert `pgvector` Architekturkomplexität. Weniger Systeme bedeuten weniger Replikationspfade, weniger Konsistenzfragen und einfacheres Incident Debugging.

Eine separate Such- oder Vector-Plattform kann trotzdem richtig sein, wenn Milliarden Vektoren, sehr spezielle ANN-Algorithmen, harte Hybrid-Search-Anforderungen, sehr niedrige p99-Latenzen oder organisatorisch getrennte Suchteams vorliegen. Die ehrliche Empfehlung lautet daher nicht „immer PostgreSQL“, sondern: Starte mit Aurora PostgreSQL oder RDS PostgreSQL, wenn die Anforderungen innerhalb der dokumentierten Grenzen liegen. Eskaliere erst, wenn Messdaten zeigen, dass Recall, Latenz, Indexgröße oder Hybrid-Ranking nicht mehr passen.

## Quellen

- pgvector README: https://github.com/pgvector/pgvector/blob/master/README.md
- AWS, Aurora PostgreSQL as a Vector Database: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html
- AWS, Aurora PostgreSQL extensions: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Extensions.html
