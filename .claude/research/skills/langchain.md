---
title: LangChain
type: skill
verdict: strong
---
## Evidence
- [[ekantik]] — capstone of a deliberate topic-by-topic self-study curriculum (loaders → splitters → embeddings → vector stores → retrievers → chains → agents); production use of HuggingFaceEmbeddings wrapper, Chroma wrapper, PromptTemplate, RecursiveCharacterTextSplitter (`FastAPI/ekantiks_api.py:35-71`), live at ekantik.marutsut.me.
- [[bluparrot]] — Smart Query Assistant uses langchain-mcp-adapters, ChromaDB/FAISS stores; DGQA uses PyPDFLoader + `.with_structured_output()`.

## Resume verdict
Yes — LOCKED_SKILL_SET and resume. Phrase as "LangChain RAG pipelines (chunking, embeddings, retrievers, grounded prompting)" backed by a live deployed system.

## Interview readiness
Can walk the whole RAG stack from ingestion to grounded generation with real numbers (1200/250 chunks, danda-aware separators, k=7). Caveat from dossier: some deprecated LangChain wrappers in ekantik if probed on code quality.
