# About Voltaic

Voltaic is an AI-powered competitive intelligence and knowledge assistant. It
reads documents, app reviews, news and web content, stores them as vectors in a
Postgres + pgvector database, and answers questions with citations using a
retrieval-augmented generation (RAG) pipeline.

## How retrieval works

Voltaic uses hybrid retrieval. For each question it runs a keyword (BM25) search
and a semantic vector search in parallel, fuses the two ranked lists with
Reciprocal Rank Fusion, and then re-ranks the best passages with a cross-encoder
model before sending them to the language model. This makes it strong on both
exact terms (product names, error codes) and meaning.

## Adding your own knowledge

Drop PDF, Markdown or plain-text files into the knowledge_base folder and run the
ingestion command. Voltaic chunks them, embeds them locally, and stores them so
the assistant can answer questions from your documents, with citations.

## Supported AI providers

Voltaic works with Anthropic Claude, OpenAI, or any OpenAI-compatible API such as
DeepSeek or Groq. Embeddings run locally with the bge-small model and require no
API key, so the only credential you need is one language-model key.
