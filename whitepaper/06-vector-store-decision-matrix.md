# 06, AWS Vector Store Decision Matrix 2026

Die Vector-Store-Frage darf im Enterprise-Kontext nicht als Geschmacksentscheidung behandelt werden. Ein Vector Store entscheidet über Retrieval-Qualität, Kostenkurve, Betriebsmodell, Governance, Latenz, Datenmodell und spätere Erweiterbarkeit. AWS bietet 2026 mehrere legitime Optionen, aber sie sind nicht austauschbar. Die wichtigste Regel lautet: **Der beste Vector Store ist abhängig vom Datenmodell und vom Retrieval-Ziel, nicht vom neuesten Service-Namen.**

## Entscheidungsmatrix

| Store | Datenmodell | Max. Dimensionen | Hybrid BM25 + Vector | Filtering | Scale und Kostenprofil | Ops Overhead | Best-fit |
|---|---|---:|---|---|---|---|---|
| Aurora oder RDS PostgreSQL mit `pgvector` | Relationale Tabellen plus `vector`, ACID, SQL | Bis 2.000 indexierte Dimensionen, `halfvec` bis 4.000 | Nicht nativ als BM25-plus-vector Search Engine | Stark über SQL, Joins, RLS-nahe Muster, Metadatenfilter | Gut für kleine bis mittlere und relationale Workloads, Indexspeicher zählt | Mittel, PostgreSQL Betrieb plus Indexpflege | Vektoren neben relationalen Daten, transaktionale Konsistenz, PoC Default |
| Amazon S3 Vectors | Object Storage mit Vector Buckets | 1 bis 4.096 | Nicht als klassische Suchmaschine | Metadatenfilter | Sehr große, kostensensitive Embedding-Bestände, pay-per-query | Niedrig bis mittel | Milliarden-nahe Vektorbestände, Archiv plus Retrieval, Kostenoptimierung |
| Amazon OpenSearch Service oder Serverless | Search Engine, Dokumente, k-NN Indizes | Bis 10.000 | Ja, native hybride Suche mit BM25 und neuralen Verfahren über Pipelines | Stark, Search-DSL, Filter, Pipelines | Stark für Relevanz und Skalierung, aber separate Infrastruktur | Hoch, trotz Serverless bleibt Search Engineering | Enterprise Search, Hybrid RAG, Relevance Tuning, große Suchdomänen |
| Amazon DocumentDB 5.0+ und 8.0 | MongoDB-kompatible Dokumente | Bis 2.000 indexierte, bis 16.000 gespeicherte Dimensionen | Nein | Vector Search mit Filtern, 8.0 `$vectorSearch` Atlas-kompatibler | Gut bei vorhandener DocumentDB-Landschaft und moderater Skala | Mittel | Pure vector RAG auf dokumentorientierten Daten, wenn DocumentDB bereits gesetzt ist |
| Amazon MemoryDB oder ElastiCache Redis | In-memory Key-Value und Vektoren | Engine- und Modulabhängig | Nicht als Enterprise BM25-Hybrid-Search gedacht | In-memory Indexfilter je nach Engine | Niedrigste Latenz, hohe Kosten pro GB, flüchtiger Tier | Mittel | Hot cache, session-nahe Retrievals, sehr niedrige Latenz |
| Amazon Neptune Analytics | Graph plus Vektorähnlichkeit | Serviceabhängig, für GraphRAG ausgelegt | Nicht BM25-Hybrid, sondern Graph Traversal plus Vektor | Graphkanten, Properties, Traversals | Spezialisiert, analytischer Graphservice | Mittel | GraphRAG, Beziehungssuche, Kontext über Knoten und Kanten |
| Amazon Kendra | Managed Enterprise Search | Nicht als generischer Vector Store positioniert | Managed intelligente Suche | Konnektoren, ACLs, Facetten | Kosten für Managed Enterprise Search | Niedrig bis mittel | Unternehmenssuche mit Konnektoren und Rechtemodell |
| Bedrock Knowledge Bases | Managed RAG Orchestrator über Backends | Abhängig vom gewählten Backend | Abhängig vom Backend und Servicefunktion | Metadatenfilter und Backend-Fähigkeiten | Weniger eigener Code, Servicekosten plus Backend | Niedrig | Managed RAG, schneller Start, Standardisierung |

AWS dokumentiert Aurora PostgreSQL `pgvector` als Vektordatenbankoption (https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html). Amazon S3 Vectors wird als neuer S3 Bucket Type mit Vector Buckets, APIs wie `PutVectors`, `QueryVectors`, `GetVectors` und `DeleteVectors`, Metadatenfiltern und Integration in Bedrock Knowledge Bases und OpenSearch positioniert (https://aws.amazon.com/s3/features/vectors/). OpenSearch dokumentiert k-NN Vector Search und die Search-Engine-nahe Einbettung in Retrieval-Pipelines (https://docs.aws.amazon.com/opensearch-service/latest/developerguide/knn.html). DocumentDB Vector Search ist allgemein verfügbar und unterstützt HNSW sowie IVFFlat, aber AWS beschreibt keine native BM25-plus-vector Hybrid Search wie bei OpenSearch (https://docs.aws.amazon.com/documentdb/latest/devguide/vector-search.html, https://aws.amazon.com/blogs/aws/vector-search-for-amazon-documentdb-with-mongodb-compatibility-is-now-generally-available/). Neptune Analytics dokumentiert Vector Similarity Search innerhalb graphnaher Analysepfade (https://docs.aws.amazon.com/neptune-analytics/latest/userguide/vector-search.html).

## Aurora PostgreSQL mit `pgvector`

`pgvector` ist die richtige Wahl, wenn Vektoren **neben relationalen Fakten** liegen. Typische Beispiele sind Bauteile, Fahrzeuge, Werkstattberichte, Qualitätsereignisse, Ticketdaten oder technische Dokumentsegmente mit relationalen Attributen wie Baureihe, Region, Freigabestatus, Klassifikation oder Mandant. SQL kann diese Attribute direkt mit Vektorähnlichkeit kombinieren. Transaktionen, Constraints, Joins und Backups bleiben in einer vertrauten PostgreSQL-Welt.

Die Grenzen sind klar. `pgvector` ist keine vollständige Search Engine. HNSW und IVFFlat liefern Approximate Nearest Neighbor Search, aber keine native BM25-Hybrid-Relevanzpipeline. Volltextsuche in PostgreSQL kann helfen, ersetzt aber nicht OpenSearch, wenn Ranking, Analyzer, Synonyme, Cross-Encoder-Reranking, Sparse Retrieval oder multimodale Search Pipelines zentrale Anforderungen sind. Für den PoC bleibt `pgvector` trotzdem die beste Default-Wahl, weil Datenmodell und Betriebsaufwand kontrollierbar bleiben.

## Amazon S3 Vectors

S3 Vectors ist strategisch relevant, weil es die Kostenfrage bei sehr großen Embedding-Beständen adressiert. Vector Buckets bringen Vektoroperationen näher an Object Storage. Die dokumentierten APIs decken Schreiben, Abfragen, Lesen und Löschen von Vektoren ab. Unterstützt werden 1 bis 4.096 Dimensionen, Distanzmetriken wie cosine und euclidean sowie Metadatenfilter (https://aws.amazon.com/s3/features/vectors/).

Der Best-fit liegt bei riesigen, kostensensitiven Embedding Stores, bei denen Query-Latenz nicht zwingend auf In-memory- oder Search-Engine-Niveau liegen muss. Für Enterprise-Plattformen ist das attraktiv, wenn Vektoren eher Datenbestand als interaktiver Low-latency Index sind. S3 Vectors ist dagegen nicht automatisch die beste Wahl für hochinteraktive Assistenzsysteme mit komplexem Ranking.

## OpenSearch Service und OpenSearch Serverless

OpenSearch ist die stärkste AWS-Option, wenn **Suchrelevanz** das Hauptproblem ist. k-NN Vector Search, BM25, neural search, Suchpipelines, hybride Retrieval-Muster, Reranking und multimodale Suchmuster passen hier am besten zusammen (https://docs.aws.amazon.com/opensearch-service/latest/developerguide/knn.html). OpenSearch Serverless reduziert Infrastrukturarbeit, aber nicht die fachliche Komplexität von Search Engineering.

Diese Stärke hat Kosten. OpenSearch ist zusätzliche Infrastruktur, zusätzliche Datenhaltung, zusätzliche Indexierungslogik und zusätzlicher Betrieb. Für Teams ohne Search-Kompetenz kann OpenSearch schnell zu einer Plattform im Plattformprojekt werden. Es ist aber die richtige Wahl, wenn Nutzerqualität von Hybrid Search abhängt, etwa wenn exakte Begriffe, Teilenummern, Fehlermeldungen oder regulatorische Begriffe genauso wichtig sind wie semantische Nähe.

## DocumentDB, ehrliche Bewertung der Kollegenaussage

Die Aussage „Nehmt DocumentDB statt OpenSearch“ ist **keine defensible General Recommendation**. Sie ist nur in einem engen Korridor vertretbar:

- Das Team betreibt DocumentDB bereits produktiv.
- Die Daten sind dokumentorientiert und liegen dort ohnehin.
- Der Use Case braucht pure vector search, nicht BM25-plus-vector Hybrid Search.
- Die Skala ist moderat.
- Ops-Simplizität ist wichtiger als Suchrelevanz-Engineering.

DocumentDB unterstützt Vector Search mit HNSW und IVFFlat und kann Vektoren in Dokumentmodellen speichern. DocumentDB 8.0 ergänzt `$vectorSearch` mit Filter und Atlas-kompatiblerem Bedienmodell. Das ist nützlich. Es ersetzt aber nicht OpenSearch für den häufigsten Enterprise-RAG-Fall: **hybride Suche aus Keyword-Relevanz und semantischer Nähe**. DocumentDB bietet keine native BM25-plus-vector Hybrid Search, keine OpenSearch-ähnlichen Suchpipelines und keine vergleichbare Relevance-Toolbox. Eine pauschale Aussage „DocumentDB ersetzt OpenSearch“ ist daher ohne diese Einschränkung irreführend.

## MemoryDB und ElastiCache Redis

Redis-basierte Vektorsuche ist ein Latenzwerkzeug. Sie passt, wenn wenige Millisekunden zählen, etwa für session-nahe Empfehlungen, Hot-Context, Agent Memory Cache oder wiederholte Retrievals auf kleinen aktiven Datenmengen. Der Preis ist Speicher. In-memory ist selten der kostengünstige Primärspeicher für große Vektorkorpora. Deshalb ist Redis eher ein Beschleuniger oder Cache Layer, nicht der Default-Vector-Store für den Unternehmensbestand.

## Neptune Analytics

Neptune Analytics gehört in eine andere Kategorie. Der Wert liegt nicht in isolierter Vektorsuche, sondern in **Vektorähnlichkeit innerhalb von Graphkontext**. Für GraphRAG können semantisch ähnliche Knoten gefunden und anschließend über Beziehungen, Pfade, Nachbarschaften oder Eigenschaften erweitert werden (https://docs.aws.amazon.com/neptune-analytics/latest/userguide/vector-search.html). Das ist besonders relevant, wenn Wissenszusammenhänge wichtiger werden als Dokumentchunks allein, zum Beispiel Produktstruktur, Fehlerursachen, Lieferketten, Varianten, Abhängigkeiten oder technische Systembeziehungen.

## Kendra und Bedrock Knowledge Bases

Amazon Kendra ist weiterhin relevant, wenn Managed Enterprise Search mit Konnektoren, ACLs und Suchoberfläche gefragt ist. Es ist aber kein generischer Vector Store für datenplattformnahe Embedding-Architekturen. Bedrock Knowledge Bases ist ebenfalls kein einzelner Store, sondern ein Managed-RAG-Orchestrator über mehrere Backends. Die Entscheidung für Knowledge Bases beantwortet deshalb nicht automatisch die Backend-Frage. Sie entscheidet vor allem, wie viel Retrieval-Orchestrierung AWS übernehmen soll.

## Verdicts

Für diesen Zwischenstand gelten folgende Entscheidungen:

1. **Aurora PostgreSQL `pgvector`** ist der Default, wenn Vektoren neben transaktionalen oder relationalen Daten liegen und Hybrid Search optional ist.
2. **S3 Vectors** ist interessant für massive, kostensensitive Embedding-Bestände mit akzeptabler höherer Query-Latenz.
3. **OpenSearch** ist die richtige Wahl für hybrid, relevance-critical und große Suchdomänen.
4. **DocumentDB** ist nur in dem begrenzten Fall sinnvoll, in dem DocumentDB bereits gesetzt ist, pure vector RAG genügt und moderate Skala reicht.
5. **Neptune Analytics** ist der nächste relevante Forschungspfad für GraphRAG.
6. **Bedrock Knowledge Bases** ist eine Managed-RAG-Option, ersetzt aber nicht die fachliche Entscheidung über Datenmodell, Governance und Retrieval-Qualität.
