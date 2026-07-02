# Bedrock Titan Text Embeddings V2

Amazon Titan Text Embeddings V2 on Amazon Bedrock converts text into numeric vectors that can be stored in pgvector. The model ID used by this PoC is amazon.titan-embed-text-v2:0 unless EMBED_MODEL_ID overrides it. The application calls Bedrock Runtime InvokeModel through boto3 and sends a JSON body with inputText, dimensions, and normalize.

Titan Text Embeddings V2 supports configurable output dimensions. This project defaults VECTOR_DIM to 1024, which matches the schema file and provides the largest standard vector size for the model. The application also validates the supported Titan V2 dimensions 1024, 512, and 256. If a smaller dimension is used, the database vector column must use the same dimension.

The normalize flag is set to true so cosine distance behaves predictably for semantic retrieval. The ingest command embeds each Markdown chunk, while the query command embeds the user question and searches for nearby chunks in Aurora PostgreSQL.
