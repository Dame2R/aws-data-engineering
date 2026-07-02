# RDS Data API Access Pattern

The RDS Data API is the database access layer for this proof of concept. Instead of opening a TCP connection to PostgreSQL, the application calls the rds-data ExecuteStatement API with the cluster ARN, secret ARN, database name, SQL text, and named parameters. This is useful for demos, scripts, and serverless environments where direct VPC database connectivity is not desired.

Data API parameters are typed as scalar values such as stringValue, longValue, doubleValue, booleanValue, or isNull. It does not provide a native pgvector parameter type. The application therefore serializes embeddings as pgvector text literals, for example [0.1,0.2,0.3], and casts them in SQL with CAST(:embedding AS vector). The same pattern is used for inserts and similarity queries.

The application keeps SQL parameterized for ordinary values such as source, chunk_index, content, metadata, and limit. This makes the PoC easy to read while preserving the important boundary between application values and SQL syntax.
