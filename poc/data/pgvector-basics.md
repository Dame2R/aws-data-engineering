# pgvector Basics

pgvector adds vector similarity search to PostgreSQL. A table can store an embedding column with a fixed dimension, such as vector(1024), alongside ordinary relational fields like source, chunk_index, content, and metadata. This lets the RAG application keep vectors and document text in one transactional database.

The operator used in this PoC is <=>, the pgvector cosine distance operator. Smaller distance is better, so nearest-neighbor queries sort with ORDER BY embedding <=> query_embedding LIMIT k. If a similarity score is easier to read, it can be calculated as 1 - distance for normalized embeddings.

pgvector supports exact search without an index and approximate nearest-neighbor search with indexes. HNSW is a strong default for interactive retrieval because it does not require a training step and usually offers good recall and latency. IVFFlat can also be useful, but it needs lists and training data choices. For this project, an HNSW index with vector_cosine_ops is created for the documents table.
