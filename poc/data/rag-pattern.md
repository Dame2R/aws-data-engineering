# Retrieval-Augmented Generation Pattern

Retrieval-augmented generation, or RAG, grounds a language model response in retrieved source material. The flow in this project has two phases. During ingestion, Markdown files are split into overlapping chunks, each chunk is embedded with Titan Text Embeddings V2, and the text plus embedding is upserted into the Aurora PostgreSQL documents table.

During query, the user question is embedded with the same model and dimensions. Aurora PostgreSQL ranks document chunks with pgvector cosine distance using the <=> operator. The best chunks are formatted into a context block with source numbers, and Claude on Amazon Bedrock receives a prompt that instructs it to answer only from that context.

This pattern keeps generation grounded and auditable. The query CLI prints the answer and the cited source chunks so a user can inspect whether the answer came from the sample corpus. If the retrieved context does not contain enough information, the model is instructed to say so instead of inventing details.
