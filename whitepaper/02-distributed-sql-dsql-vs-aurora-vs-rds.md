# Distributed SQL im Realitätscheck: Aurora DSQL vs. Aurora PostgreSQL vs. RDS PostgreSQL

Aurora DSQL ist kein „Aurora PostgreSQL mit Multi-Region-Schalter“ und auch kein neuer Vector Store. Es ist ein serverloses, aktiv-aktives, PostgreSQL-kompatibles OLTP-System für Anwendungen, die regionale Ausfälle und sehr geringe Betriebsreibung höher gewichten als vollständige PostgreSQL-Semantik. Für ein Data-Engineering-Handbuch ist diese Einordnung wichtig, weil der Name „PostgreSQL-kompatibel“ leicht zu falschen Architekturentscheidungen führt. DSQL spricht das PostgreSQL v3 wire protocol, unterstützt gängige Clients und ORMs, verzichtet aber bewusst auf viele Datenbankfeatures, die in Analytics, Data Quality, Geodaten, Volltextsuche oder Vektorarbeit selbstverständlich sind.

Dieses Kapitel ist deshalb ein Mythos-Buster: Aurora DSQL ist relevant für global verteilte OLTP-Kernprozesse. Aurora PostgreSQL und RDS PostgreSQL bleiben die richtigen Ziele für klassische PostgreSQL-Workloads, Erweiterungen, `pgvector`, Integritätsregeln und SQL-nahe Datenprodukte.

## Kurzfazit für Architekten

<table>
  <thead>
    <tr>
      <th>Frage</th>
      <th>Empfehlung</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Brauchen wir aktiv-aktive Multi-Region-Schreibbarkeit für OLTP?</td>
      <td>Aurora DSQL prüfen.</td>
    </tr>
    <tr>
      <td>Brauchen wir `pgvector`, PostGIS, `pg_trgm`, Trigger oder Foreign Keys?</td>
      <td>Nicht DSQL, sondern Aurora PostgreSQL oder RDS PostgreSQL.</td>
    </tr>
    <tr>
      <td>Wollen wir Vektoren direkt in SQL speichern und abfragen?</td>
      <td>Aurora PostgreSQL mit `pgvector`, alternativ RDS PostgreSQL.</td>
    </tr>
    <tr>
      <td>Ist die Anwendung stark transaktional, aber regional ausreichend?</td>
      <td>Aurora PostgreSQL oder RDS PostgreSQL bevorzugen.</td>
    </tr>
    <tr>
      <td>Ist Applikationslogik bereit für Commit-Konflikte und Retry-Schleifen?</td>
      <td>Voraussetzung für DSQL.</td>
    </tr>
  </tbody>
</table>

## Aurora DSQL: was es tatsächlich ist

Aurora DSQL wurde zur re:Invent 2024 als Public Preview angekündigt und am 27. Mai 2025 allgemein verfügbar gemacht. Die Release Notes dokumentieren außerdem spätere Erweiterungen, unter anderem Sequenzen und `GENERATED AS IDENTITY` ab 2026-02-13, allerdings mit nicht standardkonformer Cache-Semantik (`CACHE 1` oder Werte ab `65536`) [Aurora DSQL release notes](https://docs.aws.amazon.com/aurora-dsql/latest/userguide/release-notes.html).

Technisch ist DSQL ein serverloses, disaggregiertes Distributed-SQL-System. In einer Single-Region-Konfiguration verteilt AWS die Schichten über drei Availability Zones. In der Multi-Region-Variante gibt es zwei aktive regionale Endpunkte und eine Witness Region. Die dokumentierte Verfügbarkeit liegt bei 99,99 Prozent für Single-Region und 99,999 Prozent für Multi-Region. Cross-continent Multi-Region wird nicht unterstützt [What is Aurora DSQL](https://docs.aws.amazon.com/aurora-dsql/latest/userguide/what-is-aurora-dsql.html).

Die Kompatibilität ist bewusst auf das Wire-Protokoll und eine Teilmenge von PostgreSQL fokussiert. Clients wie `psql`, `pgjdbc`, `psycopg` und viele ORMs können kommunizieren, aber daraus folgt nicht, dass Datenbankobjekte, Erweiterungen und Semantik identisch sind. Genau diese Unterscheidung muss in Architekturentscheidungen explizit gemacht werden.

## PostgreSQL-kompatibel heißt nicht PostgreSQL-vollständig

DSQL unterstützt ausgewählte SQL-Features und Datentypen, aber keine PostgreSQL-Erweiterungen. Das ist für Data Engineering entscheidend, weil viele produktive PostgreSQL-Architekturen nicht aus „Core SQL“ bestehen, sondern aus Erweiterungen und serverseitiger Logik. Laut AWS-Dokumentation gibt es kein `CREATE EXTENSION`. Damit fehlen `pgvector`, PostGIS, `pg_trgm`, TimescaleDB-artige Erweiterungen und alle anderen Extension-basierten Funktionen [Supported SQL features](https://docs.aws.amazon.com/aurora-dsql/latest/userguide/working-with-postgresql-compatibility-supported-sql-features.html), [Supported data types](https://docs.aws.amazon.com/aurora-dsql/latest/userguide/working-with-postgresql-compatibility-supported-data-types.html).

Weitere Einschränkungen sind für produktive Designs noch einschneidender:

<table>
  <thead>
    <tr>
      <th>Feature</th>
      <th>Aurora DSQL Status</th>
      <th>Architekturfolge</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>`CREATE EXTENSION`</td>
      <td>Nicht unterstützt</td>
      <td>Keine `pgvector`, PostGIS, `pg_trgm`.</td>
    </tr>
    <tr>
      <td>Vector-Datentyp</td>
      <td>Nicht unterstützt</td>
      <td>Kein nativer RAG- oder Embedding-Store.</td>
    </tr>
    <tr>
      <td>`CREATE TYPE`</td>
      <td>Nicht unterstützt</td>
      <td>Keine eigenen Enum- oder Composite-Typen.</td>
    </tr>
    <tr>
      <td>PL/pgSQL</td>
      <td>Nicht unterstützt</td>
      <td>Nur `LANGUAGE SQL` Functions.</td>
    </tr>
    <tr>
      <td>Trigger</td>
      <td>Nicht unterstützt</td>
      <td>Audit, Derived State und Validierung müssen anders gelöst werden.</td>
    </tr>
    <tr>
      <td>Foreign Key Constraints</td>
      <td>Nicht unterstützt</td>
      <td>Referenzielle Integrität liegt bei Applikation oder Prozess.</td>
    </tr>
    <tr>
      <td>Temporary Tables</td>
      <td>Nicht unterstützt</td>
      <td>ETL-nahe Zwischenzustände passen nicht gut.</td>
    </tr>
    <tr>
      <td>Materialized Views</td>
      <td>Nicht unterstützt</td>
      <td>Kein SQL-nativer Precompute-Layer.</td>
    </tr>
    <tr>
      <td>`TRUNCATE`</td>
      <td>Nicht unterstützt</td>
      <td>Batch-Reset-Muster müssen geändert werden.</td>
    </tr>
    <tr>
      <td>Views</td>
      <td>Unterstützt</td>
      <td>Nützlich für Projektion, aber kein Ersatz für fehlende Materialisierung.</td>
    </tr>
  </tbody>
</table>

Diese Liste disqualifiziert DSQL nicht. Sie grenzt seinen Einsatzbereich ab. Ein globales Bestellsystem, das Warenkorbzustände und Auftragsstatus aktiv-aktiv schreiben muss, ist ein plausibler Kandidat. Ein semantischer Suchindex, ein Geodaten-Service oder ein Data Mart sind es nicht.

## Nebenläufigkeit: OCC statt Locks

Aurora DSQL verwendet Optimistic Concurrency Control. Es gibt keine Row Locks, Konflikte werden erst beim Commit sichtbar. Bei Konflikten liefert DSQL SQLSTATE `40001`, unter anderem mit Fehlercodes wie `OC000` oder `OC001`. Anwendungen müssen diese Transaktionen erkennen und sicher wiederholen [Concurrency control](https://docs.aws.amazon.com/aurora-dsql/latest/userguide/working-with-concurrency-control.html).

Das Isolationsniveau ist fest auf Repeatable Read gesetzt. Das vereinfacht die Plattform, reduziert aber Wahlfreiheit. Wer bisher mit expliziten Locks, `SELECT FOR UPDATE`, Foreign Keys und Triggern Konsistenz erzwungen hat, muss das Modell neu entwerfen. In DSQL gehört Retry-Logik nicht in einen „späteren Hardening-Sprint“, sondern in die erste Version des Transaktionsdesigns.

Ein minimales Anwendungsmuster sieht konzeptionell so aus:

```sql
/* Pseudocode für eine idempotente Transaktion */
BEGIN;

UPDATE account_balance
SET amount = amount - :delta,
    version = version + 1
WHERE account_id = :source_account
  AND version = :expected_version;

INSERT INTO ledger_entry (entry_id, account_id, delta, idempotency_key)
VALUES (:entry_id, :source_account, -:delta, :idempotency_key);

COMMIT;
```

Die Applikation muss bei `SQLSTATE 40001` mit Backoff neu lesen und erneut schreiben. Zusätzlich braucht sie Idempotency Keys, damit Wiederholungen keine fachlichen Duplikate erzeugen. Genau hier unterscheidet sich DSQL von einem klassischen PostgreSQL-Betrieb, in dem Pessimistic Locking und Constraints viele Fehlerklassen bereits in der Datenbank abfangen.

## Harte Limits, die man vor dem Design kennen muss

Die Quotas sind nicht nur Betriebslimits, sondern Modellierungsgrenzen. AWS dokumentiert unter anderem: maximal 3.000 Zeilen pro Transaktion, 10 MiB maximale Write-Transaktion, fünf Minuten Transaktionsdauer, maximal ein DDL-Statement pro Transaktion, 255 Spalten pro Tabelle, 24 Indexes pro Tabelle, 1 KiB für Primary Key beziehungsweise Index Key, 2 MiB pro Zeile, 128 MiB Query Memory, 10 Schemas, 1.000 Tabellen, eine Datenbank pro Cluster mit dem Namen `postgres`, 60 Minuten maximale Verbindungsdauer, 10.000 Connections als Quote und 100 neue Connections pro Sekunde mit Burst bis 1.000 [Aurora DSQL quotas](https://docs.aws.amazon.com/aurora-dsql/latest/userguide/CHAP_quotas.html).

Authentifizierung erfolgt ausschließlich über IAM Token. Benutzername und Passwort sind nicht vorgesehen. Zeitzone und Collation sind ebenfalls eng: UTC und `C` Collation. Für globale Unternehmensanwendungen kann das akzeptabel sein, wenn Sortierung, Lokalisierung und Identity ohnehin in der Applikation oder in vorgelagerten Services behandelt werden. Für SQL-zentrierte Workloads ist es eine relevante Einschränkung.

## OLTP, nicht OLAP

Aurora DSQL ist für Online-Transaktionen positioniert, nicht für analytische Abfragen. Es gibt keine columnar storage, keine parallele Query-Ausführung und nur eingeschränkte Window-Function-Unterstützung über `RANK` hinaus. `COUNT(*)` auf großen Tabellen wird nicht als Standardmuster empfohlen, stattdessen sollen Systemkataloge genutzt werden. Diese Hinweise sind wichtig, weil Distributed SQL manchmal reflexartig mit analytischer Skalierung verwechselt wird.

Für Data Engineering heißt das: DSQL kann ein transaktionaler Quellstore sein, aus dem Events oder CDC-nahe Muster in Lakehouse, Stream Processing oder Warehouse fließen. Es ist aber nicht der Ort, an dem aggregierende Exploration, Feature Engineering, Backfills oder Vektor-Retrieval stattfinden sollten.

## Kostenmodell und Serverless-Verhalten

Aurora DSQL rechnet über Distributed Processing Units ab. Für `us-east-1` nennt AWS 8 US-Dollar pro Million DPU, 0,33 US-Dollar pro GB-Monat Storage, ein dauerhaftes Free Tier von 100.000 DPU und 1 GB sowie Scale-to-zero [Aurora DSQL pricing](https://aws.amazon.com/rds/aurora/dsql/pricing/). Scale-to-zero ist ein deutlicher Unterschied zu Aurora Serverless v2, das mit ACU arbeitet und einen Mindest-Floor ab 0,5 ACU hat.

Das Kostenargument darf aber nicht isoliert betrachtet werden. DSQL kann Betriebskosten senken, wenn eine transaktionale Multi-Region-Anwendung sonst selbst Replikation, Failover, Konfliktlösung und Kapazitätsplanung bauen müsste. DSQL kann Kosten erhöhen, wenn man versucht, fehlende Datenbankfeatures durch komplexe Applikationslogik, Nebenindizes und Kompensationsprozesse zu ersetzen.

## „AI Integration“ ist kein Vector Feature

Die DSQL Release Notes enthalten Einträge zu AI Integration, etwa MCP Server für AI Coding Assistants oder Kiro Powers und Skills. Diese Einträge beziehen sich auf Developer Tooling. Sie bedeuten nicht, dass DSQL einen Vector-Datentyp, RAG-Retrieval, Embedding-Indexe oder `pgvector` unterstützt [Aurora DSQL release notes](https://docs.aws.amazon.com/aurora-dsql/latest/userguide/release-notes.html). In Architekturreviews sollte dieser Punkt explizit ausgesprochen werden, weil „AI“ in Release Notes sonst leicht als Datenbankfähigkeit missverstanden wird.

## Positionierung im AWS-PostgreSQL-Portfolio

<table>
  <thead>
    <tr>
      <th>Kriterium</th>
      <th>Aurora DSQL</th>
      <th>Aurora PostgreSQL</th>
      <th>RDS PostgreSQL</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Primärer Zweck</td>
      <td>Aktiv-aktives Multi-Region-OLTP</td>
      <td>Skalierbares managed PostgreSQL mit Aurora-Storage</td>
      <td>Klassisches managed PostgreSQL</td>
    </tr>
    <tr>
      <td>Schreibmodell</td>
      <td>Serverless, verteilt, OCC</td>
      <td>Single Primary, Read Replicas</td>
      <td>Single Instance oder Multi-AZ</td>
    </tr>
    <tr>
      <td>Extensions</td>
      <td>Keine</td>
      <td>Viele, inklusive `pgvector` je Version</td>
      <td>Viele, inklusive `pgvector` je Version</td>
    </tr>
    <tr>
      <td>Vektoren</td>
      <td>Nein</td>
      <td>Ja, produktionsrelevant</td>
      <td>Ja, klassisch managed</td>
    </tr>
    <tr>
      <td>Constraints</td>
      <td>Keine Foreign Keys</td>
      <td>PostgreSQL-üblich</td>
      <td>PostgreSQL-üblich</td>
    </tr>
    <tr>
      <td>Trigger und PL/pgSQL</td>
      <td>Nein</td>
      <td>Ja</td>
      <td>Ja</td>
    </tr>
    <tr>
      <td>Multi-Region aktiv-aktiv</td>
      <td>Ja, innerhalb dokumentierter Grenzen</td>
      <td>Nicht als identisches Schreibmodell</td>
      <td>Nein</td>
    </tr>
    <tr>
      <td>Serverless</td>
      <td>Ja, Scale-to-zero</td>
      <td>Aurora Serverless v2, ACU Floor</td>
      <td>Nein, klassisch provisioniert</td>
    </tr>
    <tr>
      <td>Operative Kontrolle</td>
      <td>Stark abstrahiert</td>
      <td>Mittel</td>
      <td>Am meisten innerhalb RDS</td>
    </tr>
    <tr>
      <td>Gute Passung</td>
      <td>Globale OLTP-Kernprozesse</td>
      <td>Vector Workhorse, App-DB, SQL-nahe Services</td>
      <td>Kontrollierte PostgreSQL-Workloads, Legacy, Kompatibilität</td>
    </tr>
  </tbody>
</table>

## Entscheidungshilfe

### Aurora DSQL wählen, wenn

Aurora DSQL passt, wenn das Hauptproblem hochverfügbare, aktiv-aktive OLTP-Schreibbarkeit über zwei Regionen ist und das Datenmodell klein genug bleibt, um die dokumentierten Transaktions- und Objektlimits einzuhalten. Teams müssen bereit sein, referenzielle Integrität, Retry-Logik, Idempotenz, Schemaänderungen und fachliche Validierung bewusst in Applikation und Delivery-Prozess zu tragen. DSQL ist besonders attraktiv, wenn Last stark schwankt und Scale-to-zero wirtschaftlich relevant ist.

### Aurora PostgreSQL wählen, wenn

Aurora PostgreSQL ist die Standardempfehlung für viele neue AWS-PostgreSQL-Workloads: volle PostgreSQL-Semantik, Erweiterungen, Read Scaling, Serverless-v2-Option und gute Integration in AWS-Betrieb. Für Vektoren ist es der wichtigste Kandidat, weil `pgvector` direkt in derselben relationalen Datenbank laufen kann wie Metadaten, Mandantenfilter und Berechtigungslogik. Wenn ein Data Product SQL, JSONB, Constraints, Trigger, Volltextsuche und Embeddings kombiniert, ist Aurora PostgreSQL in der Regel näher an der Zielarchitektur als DSQL.

### RDS PostgreSQL wählen, wenn

RDS PostgreSQL passt, wenn klassische PostgreSQL-Kompatibilität, vorhersehbare Instanzgrößen, Erweiterungskontrolle und Betriebsgewohnheiten wichtiger sind als Aurora-spezifische Storage- und Skalierungsfeatures. Für Migrationen aus bestehendem PostgreSQL, für Workloads mit konservativer Betriebsfreigabe oder für Teams, die möglichst nah am bekannten PostgreSQL-Betriebsmodell bleiben wollen, ist RDS PostgreSQL weiterhin legitim.

## Produktionsregel

Die wichtigste Regel lautet: DSQL ist kein Ersatz für PostgreSQL als Feature-Plattform. Es ist eine neue Option für ein enges, aber wichtiges Problem, nämlich verteiltes OLTP mit aktiv-aktiver Verfügbarkeit. Sobald ein Design `pgvector`, PostGIS, serverseitige Procedural Logic, Foreign Keys, Materialized Views, temporäre Tabellen oder analytische Abfragen braucht, ist DSQL die falsche Grundlage. Für das AWS Data-Engineering-Go-to ist diese Grenze produktionskritisch, weil sie teure Fehlstarts verhindert.

## Quellen

- AWS, Aurora DSQL Release Notes: https://docs.aws.amazon.com/aurora-dsql/latest/userguide/release-notes.html
- AWS, What is Amazon Aurora DSQL: https://docs.aws.amazon.com/aurora-dsql/latest/userguide/what-is-aurora-dsql.html
- AWS, Supported SQL features: https://docs.aws.amazon.com/aurora-dsql/latest/userguide/working-with-postgresql-compatibility-supported-sql-features.html
- AWS, Supported data types: https://docs.aws.amazon.com/aurora-dsql/latest/userguide/working-with-postgresql-compatibility-supported-data-types.html
- AWS, Aurora DSQL quotas: https://docs.aws.amazon.com/aurora-dsql/latest/userguide/CHAP_quotas.html
- AWS, Concurrency control: https://docs.aws.amazon.com/aurora-dsql/latest/userguide/working-with-concurrency-control.html
- AWS, Aurora DSQL pricing: https://aws.amazon.com/rds/aurora/dsql/pricing/
