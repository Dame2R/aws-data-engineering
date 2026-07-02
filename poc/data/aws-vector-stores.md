# AWS Vector Store Options

AWS offers several ways to store and search vectors. Aurora PostgreSQL with pgvector is a good fit when the application wants SQL, transactions, relational filters, and vector search in the same database. It also works well with the RDS Data API in this proof of concept because the app avoids direct network database connectivity.

Amazon OpenSearch Service is often chosen when search is the center of the workload. It can combine lexical search, filtering, and vector search for larger search applications. Amazon S3 Vectors is a storage-oriented option for large vector datasets where durability and cost-efficient storage matter. Amazon DocumentDB supports vector search for document workloads, but it does not provide the same hybrid BM25 plus vector search capability that OpenSearch is known for.

The right store depends on query patterns. This project chooses pgvector because the corpus is small, SQL examples are useful for data engineers, and Aurora PostgreSQL keeps metadata filtering close to vector retrieval.
