-- Increase recall for HNSW queries in the current session. Higher values can add latency.
SET hnsw.ef_search = 100;

-- (a) Top-k cosine similarity search. Replace the placeholder vector with a real embedding.
SELECT
  source,
  chunk_index,
  content,
  1 - (embedding <=> CAST('[0.1,0.2,0.3]' AS vector)) AS cosine_similarity
FROM documents
ORDER BY embedding <=> CAST('[0.1,0.2,0.3]' AS vector)
LIMIT 5;

-- (b) Metadata-filtered similarity search.
SELECT
  source,
  chunk_index,
  content,
  metadata,
  1 - (embedding <=> CAST('[0.1,0.2,0.3]' AS vector)) AS cosine_similarity
FROM documents
WHERE metadata->>'topic' = 'pgvector-basics'
ORDER BY embedding <=> CAST('[0.1,0.2,0.3]' AS vector)
LIMIT 5;

-- (c) Optional advanced alternative: in-database Bedrock embedding with Aurora ML.
-- This requires the aws_ml extension, aws_bedrock access, and an Aurora cluster IAM role.
-- The CDK stack must grant the database permission to invoke the model.
-- Keep app-layer embeddings with boto3 bedrock-runtime unless you explicitly enable Aurora ML.
-- Example shape only, adjust payload parsing and permissions for your Aurora PostgreSQL version:
-- SELECT aws_bedrock.invoke_model(
--   model_id => 'amazon.titan-embed-text-v2:0',
--   content_type => 'application/json',
--   accept_type => 'application/json',
--   model_input => json_build_object('inputText', 'question text', 'dimensions', 1024, 'normalize', true)::text
-- );
