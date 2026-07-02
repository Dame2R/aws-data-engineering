# 08, Outlook, AgentCore als Consumption Layer und Neptune GraphRAG als nächster Datenbaustein

Dieses Kapitel trennt zwei Themen, die in AI-Diskussionen schnell vermischt werden: Agentenlaufzeit und Datenarchitektur. Amazon Bedrock AgentCore ist ein wichtiger Baustein für das Betreiben von AI Agents. Für ein AWS Data Engineering Go-to ist es aber **adjacent**, nicht der Kern des Datenfundaments. Der nächste fachlich passende Datenbaustein ist Neptune GraphRAG, weil dort die Vektorarbeit dieses Zwischenstands mit Graphmodellierung verbunden wird.

## Amazon Bedrock AgentCore, ehrlich eingeordnet

Amazon Bedrock AgentCore wurde laut AWS im Juli 2025 als Preview vorgestellt und am 13. Oktober 2025 allgemein verfügbar gemacht. AWS beschreibt AgentCore als Infrastruktur zum sicheren Bereitstellen und Betreiben von AI Agents in Enterprise-Umgebungen (https://aws.amazon.com/blogs/aws/introducing-amazon-bedrock-agentcore-securely-deploy-and-operate-ai-agents-at-any-scale/, https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html). Der Service ist framework- und modelloffen und adressiert Runtime, Tool-Zugriff, Identität, Memory, Observability und isolierte Ausführungsumgebungen.

Die Komponenten sind für agentische Anwendungen relevant:

| Komponente | Rolle |
|---|---|
| Runtime | Isolierte Ausführung von Agent Sessions, laut AWS mit MicroVM-Isolation pro Session |
| Memory | Persistenz von agentischem Kontext über Interaktionen hinweg |
| Gateway | Bereitstellung von Tools, unter anderem über MCP-nahe Muster |
| Identity | Authentifizierung und Autorisierung für Agenten und Tool-Zugriffe |
| Observability | Telemetrie, Tracing und Betriebseinblick für Agenten |
| Browser Tool | Kontrollierte Browserinteraktion für Agent Workflows |
| Code Interpreter | Ausführung von Code in kontrollierten Agentenszenarien |
| Policy und Evaluations | Laut Kontext GA seit März 2026, relevant für Kontrolle und Qualitätssicherung |

AgentCore ersetzt beziehungsweise beerbt Bedrock Agents Classic im Sinne der strategischen Agent-Infrastruktur, während Bedrock Agents Classic in den Wartungsmodus überführt wird. Die relevante Botschaft für dieses Whitepaper ist aber: AgentCore ist **keine Vector-Store-Entscheidung, keine Lakehouse-Architektur und kein Ersatz für Retrieval-Design**. Es ist eine Konsum- und Betriebschicht auf einer Datenplattform.

Die Kollegensuggestion „AgentCore betrachten“ ist daher berechtigt, aber nur mit korrekter Platzierung. In einem Data Engineering Handbook verdient AgentCore einen kompakten Abschnitt als Consumption Layer: Wie greifen Agents auf kuratierte Datenprodukte, RAG APIs, Knowledge Bases, Tools und Governance-konforme Services zu? Es sollte nicht als Kernbaustein des aktuellen Vector Store PoCs behandelt werden. Wer AgentCore ohne belastbare Datenbasis einführt, operationalisiert nur den Zugriff auf unzureichend modellierte Information.

## Bedrock Knowledge Bases und Bedrock Data Automation als angrenzende Bausteine

Bedrock Knowledge Bases bleibt der naheliegende Managed-RAG-Baustein. Es übernimmt Chunking, Embedding, Ingestion, Retrieval und optional `RetrieveAndGenerate` über mehrere Vector Backends (https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html). In einer Plattformstrategie kann Knowledge Bases entweder ein schneller Standardpfad für einfache Dokument-RAG Use Cases sein oder ein Vergleichspunkt für selbst gebaute Retrieval Services.

Bedrock Data Automation ist ein weiterer angrenzender Baustein für unstrukturierte Daten. AWS positioniert BDA als Service, der Inhalte aus Dokumenten, Bildern, Video und Audio in strukturierte Ausgaben transformiert (https://docs.aws.amazon.com/bedrock/latest/userguide/bda.html). Für Data Engineering ist das relevant, weil viele RAG-Probleme nicht bei der Vektorsuche beginnen, sondern bei Extraktion, Normalisierung und Strukturierung von unstrukturiertem Input. BDA ist damit eher ein ETL- und Enrichment-Baustein vor dem Retrieval als ein Vector Store.

## Warum Neptune GraphRAG der nächste logische Schritt ist

Der aktuelle Zwischenstand behandelt Vektoren primär als semantische Nachbarschaft von Chunks oder Datensätzen. Viele Enterprise-Fragen sind aber relationaler im semantischen Sinn: Welches Bauteil hängt mit welchem Fehlerbild zusammen? Welche Lieferkette betrifft welche Variante? Welche Softwarestände, Steuergeräte, Märkte und Qualitätsereignisse stehen in Beziehung? Solche Fragen profitieren von Graphstruktur.

Neptune Analytics unterstützt Vector Similarity Search in graphnahen Workflows (https://docs.aws.amazon.com/neptune-analytics/latest/userguide/vector-search.html). Der Graph kann semantisch ähnliche Startpunkte finden und anschließend über Kanten, Properties und Traversals erweitern. Das verändert RAG deutlich: Retrieval ist nicht mehr nur „top-k ähnliche Chunks“, sondern „semantisch relevante Knoten plus fachlich erklärbare Beziehungen“. Für technische Domänen ist das attraktiv, weil Erklärbarkeit und Pfadlogik oft genauso wichtig sind wie semantische Nähe.

Bedrock Knowledge Bases unterstützt Neptune Analytics als Backend im GraphRAG-Kontext. Dadurch entsteht ein Managed-Pfad, bei dem Graphdaten und generative Antworterzeugung näher zusammenrücken. Trotzdem bleibt Datenmodellierung der harte Teil. GraphRAG funktioniert nicht dadurch, dass man Dokumente blind in einen Graph lädt. Es braucht Entitäten, Kanten, Property-Standards, Quellen, Aktualisierungsregeln und Qualitätsmetriken.

## Wiederverwendung aus diesem Increment

Das nächste Quartal kann substanzielle Vorarbeit aus diesem Whitepaper wiederverwenden:

- Embedding-Modellwahl und Dimensionierung aus dem Bedrock-Teil.
- Governance-Regeln für Chunk, Quelle, Klassifikation und Zugriff.
- Recall- und Latenzmetriken aus der Production Readiness.
- Vector-Store-Vergleich, insbesondere Abgrenzung zu OpenSearch, S3 Vectors und `pgvector`.
- Bedrock Knowledge Bases Bewertung als Managed-RAG-Pfad.

Neu hinzukommen müssen Graph-spezifische Themen: Property Graph Modellierung, Entitätsextraktion, Kantenqualität, Graphaktualisierung, Traversal-Patterns, Pfaderklärbarkeit und Graphmetriken. Für Porsche/MHP-nahe Datenräume ist besonders wichtig, dass Graphen fachlich gepflegt werden. Ein unkuratierter Graph kann Retrieval sogar verschlechtern, weil er falsche Nähe mit scheinbarer Erklärbarkeit versieht.

## Empfehlung für den nächsten Zwischenstand

Für das nächste Quartal sollte ein eigenes Neptune GraphRAG Increment geplant werden. Ziel ist nicht, AgentCore tief zu erforschen, sondern GraphRAG als Datenarchitekturbaustein zu bewerten. AgentCore sollte dabei als möglicher Konsument betrachtet werden: Ein Agent ruft GraphRAG APIs, Knowledge Bases oder Tools auf, aber die Qualität entsteht im Datenmodell und Retrieval-Pfad darunter.

Das Zielbild lautet: **Data Platform zuerst, Retrieval Service danach, Agent Layer darüber**. Diese Reihenfolge schützt vor AI-Plattformtheater und hält das Go-to production-focused.
