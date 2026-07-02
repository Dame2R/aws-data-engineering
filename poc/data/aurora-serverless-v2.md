# Aurora Serverless v2 for the RAG PoC

Amazon Aurora PostgreSQL Serverless v2 is the relational database layer for this proof of concept. It provides PostgreSQL compatibility while scaling capacity in Aurora Capacity Units, usually called ACUs. The workload can grow from a small demo ingest to larger retrieval tests without the application changing its database access pattern.

For this project, the important design choice is access through the RDS Data API. The Python application sends SQL statements through HTTPS using boto3 rds-data, so it does not need an in-VPC connection string, a bastion host, or a PostgreSQL network driver such as psycopg. Credentials are resolved through Secrets Manager using DB_SECRET_ARN, and the cluster is identified with DB_CLUSTER_ARN.

Aurora Serverless v2 can be configured with a low minimum capacity. On supported engine versions and configurations, it can scale down to zero ACUs when idle and resume when work arrives. That behavior is useful for a proof of concept because it can reduce idle cost while keeping the same PostgreSQL and pgvector programming model.
