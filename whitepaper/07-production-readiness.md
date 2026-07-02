# 07, Production Readiness für Aurora PostgreSQL `pgvector` und Bedrock

Ein RAG-PoC wird häufig an einer falschen Stelle unterschätzt: Nicht das erste Embedding ist schwierig, sondern der verlässliche Betrieb unter echten Daten-, Kosten-, Sicherheits- und Qualitätsbedingungen. Dieses Kapitel beschreibt die Mindestanforderungen, damit Aurora PostgreSQL Serverless v2 mit `pgvector` und Amazon Bedrock nicht nur als Demo, sondern als belastbarer Enterprise-Stack bewertet werden kann.

## Betriebsmodell und Skalierung

Aurora Serverless v2 skaliert über Aurora Capacity Units, kurz ACUs. Minimum und Maximum müssen bewusst gewählt werden, weil sie Kosten, Performance und Headroom bestimmen. AWS dokumentiert Aurora Serverless v2 als elastische Betriebsform, bei der Kapazität granular an Workload-Schwankungen angepasst wird (https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html). Für variable RAG-Lasten ist das attraktiv, weil Ingestion, Indexaufbau und interaktive Abfragen unterschiedliche Lastprofile haben.

Auto-pause beziehungsweise Scale-to-zero wurde für Aurora Serverless v2 in neueren Konfigurationen eingeführt und ist für nicht dauerhaft genutzte Umgebungen relevant. Für produktive Workloads ist es aber keine reine Kostenoptimierungsentscheidung. Kaltstartverhalten, Verbindungsaufbau, Data API Nutzung, SLOs und nächtliche Batchfenster müssen geprüft werden. In PROD ist ein kleines, dauerhaftes Minimum oft sinnvoller als aggressive Pause-Strategien.

Multi-AZ ist für Aurora kein optionales Luxusmerkmal, sondern Teil der Verfügbarkeitsstrategie. Für read-heavy Vector Search können Read Replicas sinnvoll sein, aber nur wenn Replikationsverzug und Indexzustand verstanden werden. Vektorsuche ist oft speicher- und CPU-lastig. Wenn Retrieval-Abfragen den Writer belasten, sollte mindestens eine Trennung von Write/Ingestion und Read/Retrieval geprüft werden.

## Connectivity, Data API oder VPC

AWS RDS Data API stellt einen HTTPS-basierten Zugriff auf Aurora bereit und kann für serverlose Anwendungen, administrative Workflows oder einfache Integrationen hilfreich sein (https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/data-api.html). Für latenzkritische, hochfrequente Retrieval-Pfade ist klassischer In-VPC Zugriff über PostgreSQL-Treiber, Connection Pooling und kontrollierte Netzwerkpfade meist besser geeignet.

Die Entscheidung ist operativ relevant:

| Pfad | Vorteil | Grenze | Empfehlung |
|---|---|---|---|
| RDS Data API | Kein dauerhafter DB-Connection-Pool, IAM-nahe Integration, gut für Lambda-nahe Muster | Zusätzlicher HTTP-Abstraktionslayer, nicht ideal für hohe Query-Frequenz | Gut für Admin, Backoffice, geringe Last |
| In-VPC PostgreSQL | Geringere Latenz, voller Treibersupport, besser für Pooling | VPC, Security Groups, Secrets und Pooling müssen sauber betrieben werden | Default für produktive Retrieval APIs |

Für beide Pfade gilt: keine Secrets im Code, kein lokales Credential-Sharing, keine pauschalen Admin-Rollen.

## Security Baseline

Die Security-Baseline muss vor dem ersten produktionsnahen Datensatz stehen. Dazu gehören:

- IAM Authentication oder Secrets Manager für Datenbankzugriff, abhängig vom Treiber- und Betriebsmodell.
- Least-privilege IAM Policy für Bedrock, etwa nur die benötigten `bedrock:InvokeModel` Rechte auf die freigegebenen Modell-ARNs.
- KMS-basierte Verschlüsselung at rest für Aurora und alle beteiligten Speicherorte.
- TLS in transit für Datenbankverbindungen und AWS Service Calls.
- VPC Isolation, Security Groups und private Subnetze für Datenbankpfade.
- Kein Secret in Code, Notebook, Prompt-Template, Markdown oder CI-Log.
- CloudTrail und CloudWatch für nachvollziehbare Modell- und Datenzugriffe.

Bedrock Modellzugriff muss pro Region aktiviert und governancefähig dokumentiert werden. AWS beschreibt, dass Modellzugriff in Bedrock explizit verwaltet werden muss (https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html). Das ist für Porsche/MHP-nahe Unternehmenskontexte wichtig, weil Region, Modellanbieter, Datenklassifikation und Freigabeprozess zusammengehören.

## Kostenmodell

Das Kostenmodell besteht aus mindestens vier Blöcken.

Erstens Aurora Serverless v2 ACU-hours: Minimum, Maximum und tatsächliche Skalierung bestimmen die Datenbankkosten. Vector Search kann CPU und Speicher intensiver nutzen als einfache OLTP-Abfragen. HNSW-Indizes brauchen RAM und Storage. Große Indexbuilds können kurzfristig hohe Kapazität auslösen.

Zweitens Bedrock Embedding-Kosten: Jeder Chunk, jede Query und jeder Re-Embedding-Lauf erzeugt Modellkosten. Chunk-Größe, Deduplizierung und Reindexierungsstrategie sind deshalb FinOps-Entscheidungen.

Drittens Bedrock Generation-Kosten: Antwortmodelle werden pro Input- und Output-Token abgerechnet. Schlechte Retrieval-Qualität erhöht Kosten, weil mehr Kontext eingefügt wird oder Nutzer mehrfach nachfragen.

Viertens Operations- und Speicherfolgekosten: Backups, Replicas, Monitoring, Logs und Indexrebuilds gehören in die Betrachtung. Der oft genannte Vergleich zu Aurora DSQL DPUs ist für diesen Stack nur begrenzt hilfreich, weil DSQL für diesen Vektorfall nicht der Zielservice ist. Verglichen werden sollte stattdessen: Aurora PostgreSQL `pgvector`, OpenSearch, S3 Vectors und Managed Knowledge Bases im konkreten Retrieval-Profil.

## Indexbetrieb und Datenbankpflege

`pgvector` ist kein „create once, forget forever“-Baustein. HNSW und IVFFlat haben unterschiedliche Betriebsprofile. IVFFlat benötigt Training beziehungsweise geeignete Datenverteilung und profitiert von `ANALYZE`. HNSW bietet oft starke Query-Qualität, hat aber Speicher- und Build-Kosten. Bei großen Tabellen sind Indexbuilds planbare Betriebsereignisse.

Produktionsrelevante Punkte:

- `ANALYZE` nach größeren Lade- oder Re-Embedding-Läufen ausführen.
- `maintenance_work_mem` für Indexbuilds bewusst konfigurieren und nicht blind global erhöhen.
- Indexbuilds außerhalb kritischer Online-Fenster planen.
- Embedding-Versionen speichern, damit Re-Embedding kontrolliert möglich ist.
- Query-Pläne prüfen, insbesondere wenn Vektorfilter und relationale Filter kombiniert werden.
- Lösch- und Aktualisierungsstrategie definieren, weil veraltete Embeddings Retrieval-Qualität verschlechtern.

## Monitoring und SLOs

Ein produktiver RAG-Stack braucht technische und fachliche Metriken. Nur Datenbanklatenz reicht nicht.

Technische Metriken:

- Aurora ACU Nutzung, CPU, Speicher, Connections, I/O, Replikationsverzug.
- Query-Latenz für Vector Search, getrennt nach p50, p95 und p99.
- Bedrock Latenz, Fehlerquoten, Throttling, Tokenverbrauch.
- Indexgröße, Tabellenwachstum, Embedding-Durchsatz.

Fachliche Metriken:

- Recall@k auf kuratierten Testfragen.
- Anteil Antworten mit korrekten Quellen.
- Absturzrate in Fallback-Antworten.
- Nutzerfeedback nach Domäne.
- Halluzinations- und Policy-Verletzungen aus Evaluation Sets.

CloudWatch ist der technische Mindeststandard. Für RAG-Qualität braucht es zusätzlich ein Evaluation Harness mit festen Golden Questions, erwarteten Quellen und Regression Gates. Ohne solche Tests kann ein Modellwechsel oder Re-Embedding unbemerkt die Antwortqualität verschlechtern.

## Data Governance Touchpoints

RAG-Systeme verschieben Datenrisiken. Ein Dokument, das in einem normalen Portal korrekt berechtigt ist, kann im Retrieval-Kontext plötzlich in Prompt-Kontexten, Logs oder Antwortzitaten auftauchen. Deshalb müssen Governance-Regeln vor dem Indexieren greifen.

Mindestpunkte:

- Datenklassifikation am Dokument und am Chunk speichern.
- Mandant, Region, Projekt, Baureihe oder andere Zugriffsdimensionen als filterbare Metadaten modellieren.
- Retrieval Filter serverseitig erzwingen, nicht nur im Prompt erwähnen.
- Prompt- und Antwortlogs klassifizieren und retention-konform speichern.
- Re-Embedding bei Löschung, Korrektur oder Klassifikationswechsel planen.
- Quellenanzeige und Auditability als Feature behandeln, nicht als UI-Zusatz.

## Grenzen und Chancen

Die Chance des Stacks liegt in seiner Einfachheit: wenige Services, klare Verantwortung, relationaler Kontext und Bedrock als Modellplattform. Für einen PoC und viele domänennahe Assistenzsysteme ist das stark. Die Grenze liegt bei Suchrelevanz, sehr großen Vektorbeständen und graphnahen Beziehungen. Dann führen die Erweiterungspfade zu OpenSearch, S3 Vectors oder Neptune Analytics.

## Production Checklist

| Bereich | Check |
|---|---|
| Architektur | Aurora PostgreSQL Serverless v2 gewählt, Aurora DSQL bewusst ausgeschlossen |
| Skalierung | ACU min/max, Auto-pause, Read Replica Strategie dokumentiert |
| Netzwerk | In-VPC oder Data API Entscheidung begründet |
| Security | Secrets Manager oder IAM Auth, TLS, KMS, VPC Isolation, Least Privilege für Bedrock |
| Bedrock | Modellzugriff je Region aktiviert, Modell-IDs versioniert, Timeouts und Retries definiert |
| Datenmodell | Embedding-Dimension, Modellversion, Chunk-ID, Quelle und Security Metadaten gespeichert |
| Index | HNSW oder IVFFlat begründet, Buildfenster und `ANALYZE` geplant |
| SLOs | p95 Retrieval-Latenz, Recall@k und Antwortqualität definiert |
| Monitoring | CloudWatch, Bedrock Fehler, Tokenkosten und DB-Metriken beobachtet |
| Governance | Zugriffskontrolle vor Retrieval, Quellenpflicht, Log-Retention und Re-Embedding-Prozess definiert |
| Kosten | ACU-hours, Bedrock Tokens, Embedding Backfills und Indexspeicher kalkuliert |
| Betrieb | Runbook für Throttling, Indexrebuild, Modellfehler und Rollback vorhanden |
