"""
============================================
RAG (Retrieval-Augmented Generation) ENGINE
VB-GRAMG Government Documents System
============================================

Handles:
- ChromaDB vector database management
- Nomic-embed-text embeddings via Ollama
- Semantic similarity search
- Document embedding & retrieval
- Ollama LLM integration for response generation
- Source document tracking & citation
"""

import os
import sys
import json
import logging
import requests
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

import chromadb
from chromadb.config import Settings

from config import Config
from answer_cleanup import collapse_repeats
import dose_conflicts
import lexical_rescue

# ============================================
# LOGGING
# ============================================

logger = logging.getLogger(__name__)

# ============================================
# NOMIC EMBEDDINGS WRAPPER
# ============================================

NOMIC_DOCUMENT_PREFIX = 'search_document: '
NOMIC_QUERY_PREFIX = 'search_query: '
SCHEME_PREFIXES = 'nomic-prefixes'
SCHEME_PLAIN = 'plain'


class NomicEmbeddings:
    """
    Wrapper for Ollama nomic-embed-text model
    
    Provides embeddings via local Ollama service
    - 768-dimensional vectors
    - Better semantic understanding than MiniLM
    - Offline capable (runs locally)
    """
    
    def __init__(self, ollama_url: str = 'http://localhost:11434'):
        """
        Initialize Nomic embeddings
        
        Args:
            ollama_url: URL of Ollama service
        """
        self.ollama_url = ollama_url
        self.model_name = 'nomic-embed-text'
        self.dimension = 768
        logger.info(f'📊 Nomic Embeddings initialized (dimension: {self.dimension})')
    
    def encode(self, texts, show_progress_bar=False, prefix=''):
        """
        Get embeddings from nomic-embed-text
        
        Args:
            texts: Single text (str) or list of texts
            show_progress_bar: Show progress (for compatibility)
        
        Returns:
            numpy array of embeddings
        """
        # Handle single string
        if isinstance(texts, str):
            texts = [texts]
        
        embeddings = []
        
        for i, text in enumerate(texts):
            try:
                if show_progress_bar and len(texts) > 1:
                    progress = (i + 1) / len(texts)
                    print(f'Encoding: [{progress:.0%}]', end='\r')
                
                # Call Ollama embeddings API
                response = requests.post(
                    f'{self.ollama_url}/api/embeddings',
                    json={
                        'model': self.model_name,
                        'prompt': prefix + text
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    embedding = response.json().get('embedding', [])
                    embeddings.append(embedding)
                else:
                    logger.error(f'❌ Nomic error: {response.text}')
                    # Fallback: zero vector
                    embeddings.append([0.0] * self.dimension)
            
            except requests.exceptions.Timeout:
                logger.error(f'❌ Nomic timeout for text: {text[:50]}...')
                embeddings.append([0.0] * self.dimension)
            except Exception as e:
                logger.error(f'❌ Embedding error: {str(e)}')
                embeddings.append([0.0] * self.dimension)
        
        # Return as numpy array
        result = np.array(embeddings, dtype=np.float32)
        
        # If single text, return 1D array for compatibility
        if len(embeddings) == 1:
            return result[0]
        
        return result

# ============================================
# RAG ENGINE CLASS
# ============================================

class RAGEngine:
    """
    Retrieval-Augmented Generation Engine
    
    Combines ChromaDB vector search with Ollama LLM
    for context-aware, document-grounded responses.
    
    Uses nomic-embed-text (768-dim) for embeddings.
    """

    def __init__(self):
        """Initialize RAG engine with ChromaDB and Nomic embeddings"""
        logger.info('🚀 Initializing RAG Engine...')
        
        # Configuration
        self.chunk_size = Config.CHUNK_SIZE
        self.chunk_overlap = Config.CHUNK_OVERLAP
        self.top_k = Config.TOP_K_DOCUMENTS
        self.temperature = Config.LLM_TEMPERATURE
        self.model_name = Config.OLLAMA_MODEL
        self.ollama_url = f'http://localhost:{Config.OLLAMA_PORT}'
        
        # ChromaDB client
        self.chroma_client = None
        self.collection = None
        
        # Embeddings model (Nomic via Ollama)
        self.embeddings_model = None
        
        # Document registry
        self.documents_registry = {}
        
        # Initialize components
        self._initialize_chroma()
        self._initialize_embeddings()
        self._load_registry()
        self._init_embedding_scheme()
        
        logger.info('✅ RAG Engine initialized successfully')

    # ========================================
    # INITIALIZATION
    # ========================================

    def _initialize_chroma(self):
        """Initialize ChromaDB client and collection"""
        try:
            logger.info('📦 Initializing ChromaDB...')
        
            # Ensure Chroma data directory exists
            chroma_path = Config.CHROMA_DATA_FOLDER
            Path(chroma_path).mkdir(parents=True, exist_ok=True)
            
            # Initialize Chroma client with persistent storage
            self.chroma_client = chromadb.PersistentClient(path=chroma_path)
            
            # Get or create collection
            # Note: ChromaDB auto-detects 768-dim vectors from Nomic
            self.collection = self.chroma_client.get_or_create_collection(
                name="vb_gramg_documents",
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info(f'✅ ChromaDB initialized (persist dir: {chroma_path})')
            logger.info(f'📚 Collection: {self.collection.name}')
            logger.info(f'📊 Documents in collection: {self.collection.count()}')
        
        except Exception as e:
            logger.error(f'❌ ChromaDB initialization failed: {str(e)}')
            raise

    def _initialize_embeddings(self):
        """Initialize Nomic embeddings via Ollama"""
        try:
            logger.info('🧠 Initializing embeddings model...')
            
            # Check Ollama connection first
            if not self._check_ollama_connection():
                raise Exception('Ollama service not available. Make sure ollama serve is running.')
            
            # Initialize Nomic embeddings
            self.embeddings_model = NomicEmbeddings(self.ollama_url)
            
            logger.info('✅ Embeddings model initialized: nomic-embed-text (768-dim)')
            logger.info('   Better semantic understanding than SentenceTransformer')
        
        except Exception as e:
            logger.error(f'❌ Embeddings initialization failed: {str(e)}')
            raise

    def _scheme_path(self):
        return os.path.join(Config.CHROMA_DATA_FOLDER, 'embedding_scheme.txt')

    def _init_embedding_scheme(self):
        """Decide whether documents and questions get the nomic prefixes.
        A database keeps the scheme it was built with: one without the marker file that already holds chunks was
        built without prefixes, and must be searched without them, or search quality drops."""
        scheme = None
        try:
            if os.path.exists(self._scheme_path()):
                with open(self._scheme_path(), 'r') as f:
                    scheme = f.read().strip()
        except Exception:
            scheme = None
        count = 0
        try:
            count = self.collection.count() if self.collection else 0
        except Exception:
            count = 0
        if scheme not in (SCHEME_PREFIXES, SCHEME_PLAIN):
            if count > 0:
                scheme = SCHEME_PLAIN
            else:
                scheme = SCHEME_PREFIXES if getattr(Config, 'USE_NOMIC_PREFIXES', True) else SCHEME_PLAIN
        self.embedding_scheme = scheme
        self.use_prefixes = scheme == SCHEME_PREFIXES
        if scheme == SCHEME_PLAIN and count > 0 and getattr(Config, 'USE_NOMIC_PREFIXES', True):
            logger.warning('⚠️ This database was built without the nomic prefixes. It still works; '
                           'rebuild it (python eval/reload_knowledge_base.py on an empty chroma_data) for better search.')
        logger.info(f'🔎 Embedding scheme: {scheme}')

    def _write_scheme_file(self):
        try:
            os.makedirs(Config.CHROMA_DATA_FOLDER, exist_ok=True)
            with open(self._scheme_path(), 'w') as f:
                f.write(self.embedding_scheme)
        except Exception as e:
            logger.warning(f'⚠️ Could not save the embedding scheme: {str(e)}')

    def _load_registry(self):
        """Load document registry from disk"""
        try:
            registry_path = os.path.join(Config.CHROMA_DATA_FOLDER, 'registry.json')
            
            if os.path.exists(registry_path):
                with open(registry_path, 'r') as f:
                    self.documents_registry = json.load(f)
                logger.info(f'📋 Loaded registry with {len(self.documents_registry)} documents')
            else:
                logger.info('📋 No existing registry found (starting fresh)')
        
        except Exception as e:
            logger.warning(f'⚠️ Failed to load registry: {str(e)}')
            self.documents_registry = {}

    def _save_registry(self):
        """Save document registry to disk"""
        try:
            registry_path = os.path.join(Config.CHROMA_DATA_FOLDER, 'registry.json')
            
            with open(registry_path, 'w') as f:
                json.dump(self.documents_registry, f, indent=2, default=str)
            
            logger.info(f'💾 Registry saved with {len(self.documents_registry)} documents')
        
        except Exception as e:
            logger.error(f'❌ Failed to save registry: {str(e)}')

    # ========================================
    # DOCUMENT MANAGEMENT
    # ========================================

    def add_document(self, doc_id: str, chunks: List[str], filepath: str = None) -> bool:
        """
        Add document chunks to the RAG system
        
        Args:
            doc_id: Unique document identifier
            chunks: List of text chunks
            filepath: Path to original document
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not chunks or len(chunks) == 0:
                logger.warning(f'⚠️ No chunks to add for document: {doc_id}')
                return False
            
            logger.info(f'📝 Adding document to RAG: {doc_id} ({len(chunks)} chunks)')
            
            # Generate embeddings for chunks using Nomic
            logger.info(f'🧮 Generating embeddings for {len(chunks)} chunks with Nomic...')
            embeddings = self.embeddings_model.encode(chunks, show_progress_bar=True,
                                                      prefix=NOMIC_DOCUMENT_PREFIX if self.use_prefixes else '')
            
            # Convert to list if numpy array
            embeddings_list = embeddings.tolist() if hasattr(embeddings, 'tolist') else list(embeddings)
            
            # A failed embedding request comes back as a vector of zeros. A chunk stored like that can never be found,
            # so refuse the whole document instead of storing it silently.
            empty = [i for i, v in enumerate(embeddings_list) if not any(v)]
            if empty:
                logger.error(f'❌ {len(empty)} of {len(chunks)} chunks could not be embedded (is Ollama running with nomic-embed-text?). Document not added.')
                return False
            
            # Prepare metadata
            metadatas = [
                {
                    'doc_id': doc_id,
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'added_at': datetime.now().isoformat()
                }
                for i in range(len(chunks))
            ]
            
            # Generate IDs for chunks
            ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
            
            # Add to ChromaDB
            logger.info(f'💾 Storing {len(chunks)} embeddings in ChromaDB...')
            self.collection.add(
                ids=ids,
                embeddings=embeddings_list,
                documents=chunks,
                metadatas=metadatas
            )
            
            # Update registry
            self.documents_registry[doc_id] = {
                'filename': doc_id,
                'filepath': filepath,
                'chunks_count': len(chunks),
                'added_at': datetime.now().isoformat(),
                'chunk_ids': ids
            }
            
            self._save_registry()
            self._write_scheme_file()
            
            logger.info(f'✅ Document added successfully: {doc_id}')
            logger.info(f'📊 Total documents in registry: {len(self.documents_registry)}')
            logger.info(f'📊 Total chunks in collection: {self.collection.count()}')
            
            return True
        
        except Exception as e:
            logger.error(f'❌ Failed to add document: {str(e)}')
            return False

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """
        Get all documents in the system
        
        Returns:
            List of document metadata
        """
        try:
            documents = []
            
            for doc_id, metadata in self.documents_registry.items():
                documents.append({
                    'id': doc_id,
                    'filename': metadata.get('filename'),
                    'chunks_count': metadata.get('chunks_count', 0),
                    'added_at': metadata.get('added_at'),
                    'filepath': metadata.get('filepath')
                })
            
            logger.info(f'📋 Retrieved {len(documents)} documents from registry')
            return documents
        
        except Exception as e:
            logger.error(f'❌ Failed to get documents: {str(e)}')
            return []

    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document and its chunks
        
        Args:
            doc_id: Document ID to delete
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if doc_id not in self.documents_registry:
                logger.warning(f'⚠️ Document not found: {doc_id}')
                return False
            
            logger.info(f'🗑️ Deleting document: {doc_id}')
            
            # Get chunk IDs for this document
            metadata = self.documents_registry[doc_id]
            chunk_ids = metadata.get('chunk_ids', [])
            
            # Delete from ChromaDB
            if chunk_ids:
                logger.info(f'🗑️ Deleting {len(chunk_ids)} chunks from ChromaDB...')
                self.collection.delete(ids=chunk_ids)
            
            # Remove from registry
            del self.documents_registry[doc_id]
            self._save_registry()
            
            logger.info(f'✅ Document deleted successfully: {doc_id}')
            logger.info(f'📊 Remaining documents: {len(self.documents_registry)}')
            
            return True
        
        except Exception as e:
            logger.error(f'❌ Failed to delete document: {str(e)}')
            return False

    def has_documents(self) -> bool:
        """Check if any documents are loaded"""
        count = self.collection.count() if self.collection else 0
        return count > 0

    def get_status(self) -> Dict[str, Any]:
        """Get RAG engine status"""
        return {
            'documents_loaded': len(self.documents_registry) > 0,
            'current_document': list(self.documents_registry.keys())[-1] if self.documents_registry else None,
            'chunks_count': self.collection.count() if self.collection else 0,
            'total_documents': len(self.documents_registry),
            'embedding_model': 'nomic-embed-text',
            'embedding_dimension': 768,
            'initialized': True,
            'timestamp': datetime.now().isoformat()
        }

    def initialize(self):
        """Initialize RAG system (load existing data)"""
        try:
            logger.info('🔄 Initializing RAG system...')
            
            # ChromaDB persists automatically
            count = self.collection.count() if self.collection else 0
            logger.info(f'✅ RAG system initialized with {count} chunks')
        
        except Exception as e:
            logger.warning(f'⚠️ RAG initialization issue: {str(e)}')

    # ========================================
    # SEMANTIC SEARCH & RETRIEVAL
    # ========================================

    def _lexical_index(self):
        """Keyword index over the stored passages; rebuilt when the number of passages changes."""
        count = self.collection.count()
        if getattr(self, '_lex', None) is None or getattr(self, '_lex_count', None) != count:
            data = self.collection.get(include=['documents', 'metadatas'])
            self._lex = lexical_rescue.Index(data.get('documents') or [], data.get('metadatas') or [])
            self._lex_count = count
        return self._lex

    def _retrieve_context(self, query: str, top_k: int = 5) -> Tuple[List[str], List[Dict], List[float]]:
        """
        Retrieve relevant document chunks for a query
        
        Args:
            query: User query
            top_k: Number of chunks to retrieve
        
        Returns:
            Tuple of (chunks, metadatas, similarities)
        """
        try:
            logger.info(f'🔍 Retrieving context for query: "{query[:50]}..."')
            
            if not self.has_documents():
                logger.warning('⚠️ No documents available for retrieval')
                return [], [], []
            
            # Generate query embedding using Nomic
            logger.info('🧮 Encoding query with Nomic...')
            query_embedding = self.embeddings_model.encode(query, prefix=NOMIC_QUERY_PREFIX if self.use_prefixes else '')
            
            # Search ChromaDB
            logger.info(f'🔎 Searching for top {top_k} similar chunks...')
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=min(top_k, self.collection.count())
            )
            
            # Extract chunks and metadata
            chunks = results.get('documents', [[]])[0]
            metadatas = results.get('metadatas', [[]])[0]
            distances = results.get('distances', [[]])[0]
            
            # The collection uses cosine distance (hnsw:space = cosine), so
            # cosine similarity = 1 - distance. (The old 1/(1+distance) could
            # never go below ~0.33, so the "not covered" guard never fired.)
            similarities = [1.0 - dist for dist in distances]

            # Keyword rescue: a passage with the question's rare words that the meaning-based search missed.
            # Added at the end with similarity 0.0, so the "is it covered" check still uses the embedding scores only.
            if getattr(Config, 'LEXICAL_RESCUE', False):
                try:
                    for text, meta, score, hits in self._lexical_index().rescue(
                            query, exclude=chunks, k=getattr(Config, 'LEXICAL_RESCUE_K', 1)):
                        chunks, metadatas, similarities = list(chunks) + [text], list(metadatas) + [meta or {}], list(similarities) + [0.0]
                        logger.info(f'🔤 Keyword rescue added a passage (score {score}, words {hits})')
                except Exception as e:
                    logger.error(f'Keyword rescue failed (ignored): {e}')

            logger.info(f'✅ Retrieved {len(chunks)} relevant chunks')
            
            for i, (chunk, similarity) in enumerate(zip(chunks, similarities)):
                logger.info(f'  [{i+1}] Relevance: {similarity:.2%} - "{chunk[:40]}..."')
            
            return chunks, metadatas, similarities
        
        except Exception as e:
            logger.error(f'❌ Retrieval failed: {str(e)}')
            return [], [], []

    # ========================================
    # LLM INTEGRATION (OLLAMA)
    # ========================================

    def _check_ollama_connection(self) -> bool:
        """Check if Ollama service is running"""
        try:
            logger.info('🔗 Checking Ollama connection...')
            response = requests.get(f'{self.ollama_url}/api/tags', timeout=5)
            
            if response.status_code == 200:
                logger.info('✅ Ollama is running')
                return True
            else:
                logger.error(f'❌ Ollama returned status {response.status_code}')
                return False
        
        except requests.exceptions.ConnectionError:
            logger.error('❌ Cannot connect to Ollama. Make sure it\'s running (ollama serve)')
            return False
        except requests.exceptions.Timeout:
            logger.error('❌ Ollama connection timeout')
            return False
        except Exception as e:
            logger.error(f'❌ Ollama connection check failed: {str(e)}')
            return False

    def _generate_response(self, context: str, question: str, answer_language: str = None) -> str:
        """
        Generate response using Ollama LLM
        
        Args:
            context: Retrieved context from documents
            question: User question
            answer_language: 'en' or 'hi' to force the answer language
                (None = detect from the question text)
        
        Returns:
            The generated answer text. (No confidence value is returned: the
            old hardcoded 0.85 measured nothing.)
        """
        try:
            # Check Ollama connection
            if not self._check_ollama_connection():
                raise Exception('Ollama service is not available')
            
            logger.info('🤖 Generating response with Ollama...')
            
            # Create prompt with context
            prompt = self._create_prompt(question, context, answer_language)
            
            logger.info('📤 Sending request to Ollama...')
            
            # Call Ollama API
            response = requests.post(
                f'{self.ollama_url}/api/generate',
                json={
                    'model': self.model_name,
                    'prompt': prompt,
                    'stream': False,
                    # Ollama reads sampling settings from "options"; top-level
                    # keys like 'temperature' were silently ignored.
                    'options': {
                        'temperature': self.temperature,
                        'top_k': 40,
                        'top_p': 0.9,
                        'num_predict': getattr(Config, 'LLM_MAX_TOKENS', 1024),
                        'num_ctx': getattr(Config, 'LLM_NUM_CTX', 4096)
                    }
                },
                timeout=Config.OLLAMA_TIMEOUT
            )
            
            if response.status_code != 200:
                logger.error(f'❌ Ollama returned status {response.status_code}')
                raise Exception(f'Ollama error: {response.text}')
            
            result = response.json()
            generated_text = collapse_repeats(result.get('response', '').strip())
            
            if not generated_text:
                raise Exception('Ollama returned empty response')
            
            logger.info(f'✅ Response generated ({len(generated_text)} chars)')
            
            return generated_text
        
        except requests.exceptions.Timeout:
            logger.error('❌ Ollama request timeout')
            raise Exception('LLM response timeout. Please try again.')
        except requests.exceptions.ConnectionError:
            logger.error('❌ Cannot connect to Ollama')
            raise Exception('LLM service unavailable. Please ensure Ollama is running.')
        except Exception as e:
            logger.error(f'❌ Response generation failed: {str(e)}')
            raise

    def _create_prompt(self, question: str, context: str, answer_language: str = None, background: str = None) -> str:
        # An explicit answer_language wins. Otherwise fall back to the old
        # behaviour: Devanagari in the question means answer in Hindi.
        if answer_language == 'hi':
            lang_instruction = "Respond in Hindi."
        elif answer_language == 'en':
            lang_instruction = "Respond in English."
        else:
            lang_instruction = "Respond in Hindi." if any("\u0900" <= c <= "\u097F" for c in question) else "Respond in English."
        
        background_block = ''
        if background:
            background_block = f"""
        BACKGROUND (about the farmer's photo; it is NOT part of the question):
        {background}
        Use the background only if the question refers to "this", "it" or "my plant". Never change the topic of the question.
"""

        return f"""You are a helpful assistant.
        
        {lang_instruction}
        
        CONTEXT:
        {context}
{background_block}
        USER QUESTION:
        {question}

        CRITICAL RULES:
        1. Answer only from the CONTEXT above. Do not use outside knowledge.
        2. NO META-COMMENTARY: Just provide the answer.
        3. STRICT RELEVANCE: If the answer is not in the context, reply "I don't have information about this."
        4. SAFETY: Never state a medicine, pesticide or chemical product name, dose, mixing ratio or schedule unless it appears in the CONTEXT. If it does, copy it exactly as written and name the Source it came from.
        
        ANSWER:"""

    # ========================================
    # MAIN QUERY METHOD
    # ========================================

    def query(self, question: str, top_k: int = None, answer_language: str = None,
              retrieval_query: str = None, background: str = None) -> Dict[str, Any]:
        # `question` is passed to the model exactly as asked. `retrieval_query` (optional) is only used to
        # search the documents; `background` is shown to the model as separate context, never as the question.
        try:
            if top_k is None:
                top_k = self.top_k
                
            chunks, metadatas, similarities = self._retrieve_context(retrieval_query or question, top_k)
            
            # Result fields: 'retrieval_score' is the best chunk's cosine
            # similarity (NOT answer confidence). 'grounded' says whether an
            # answer was generated from retrieved text or the system abstained.
            no_info = "I don't have information about this in the available documents."
            
            # Guardrail A: Zero chunks returned from an empty database
            if not chunks:
                return {
                    'response': no_info,
                    'source_documents': [],
                    'retrieval_score': None,
                    'grounded': False
                }
            
            best_score = float(max(similarities))
            logger.info(f'📏 Best retrieval score: {best_score:.3f} (min required {Config.MIN_COSINE_SIMILARITY})')
            
            # Guardrail B: best chunk must be similar enough to the question.
            if best_score < Config.MIN_COSINE_SIMILARITY:
                return {
                    'response': no_info,
                    'source_documents': [],
                    'retrieval_score': best_score,
                    'grounded': False
                }
            
            context = "\n\n---\n\n".join([f"Source {i+1}:\n{c}" for i, c in enumerate(chunks)])
            
            response = requests.post(
                f'{self.ollama_url}/api/generate',
                json={
                    'model': self.model_name,
                    'prompt': self._create_prompt(question, context, answer_language, background),
                    'stream': False,
                    'options': {'temperature': self.temperature, 'num_predict': getattr(Config, 'LLM_MAX_TOKENS', 1024),
                                'num_ctx': getattr(Config, 'LLM_NUM_CTX', 4096)}
                },
                timeout=Config.OLLAMA_TIMEOUT
            )
            
            generated_text = collapse_repeats(response.json().get('response', '').strip())
            
            # Guardrail C: Catch post-generation conversational drift
            refusal_keywords = [
                "don't have information", "don't have info", "not mentioned in the context", 
                "not provided in the context", "cannot answer", "not in the available documents",
                "provided context does not contain"
            ]
            
            if any(keyword in generated_text.lower() for keyword in refusal_keywords):
                return {
                    'response': no_info,
                    'source_documents': [],
                    'retrieval_score': best_score,
                    'grounded': False
                }
            
            # Where the guide gives two different amounts for the same spray, show both (fixed list, see dose_conflicts.py)
            try:
                note = dose_conflicts.note_for(question, generated_text, chunks,
                                               topic_extra=' '.join(x for x in (retrieval_query, background) if x))
            except Exception as e:
                logger.error(f'dose conflict note failed: {e}')
                note = ''
            if note:
                generated_text = generated_text.rstrip() + '\n\n' + note

            sources = list(set([m.get('doc_id', 'Unknown') for m in metadatas]))
            
            return {
                'response': generated_text,
                'source_documents': sources,
                'retrieval_score': best_score,
                'grounded': True
            }
        except Exception as e:
            logger.error(f'❌ Query failed: {str(e)}')
            return {
                'response': f'Error processing query: {str(e)}',
                'source_documents': [],
                'retrieval_score': None,
                'grounded': False
            }

    def _prepare_context(self, chunks: List[str], metadatas: List[Dict], 
                        similarities: List[float]) -> str:
        """
        Prepare formatted context for LLM
        
        Args:
            chunks: List of retrieved chunks
            metadatas: Metadata for each chunk
            similarities: Similarity scores
        
        Returns:
            Formatted context string
        """
        context_parts = []
        
        for i, (chunk, metadata, similarity) in enumerate(zip(chunks, metadatas, similarities)):
            context_parts.append(
                f"Source {i+1} (Relevance: {similarity:.0%}):\n{chunk}"
            )
        
        return "\n\n---\n\n".join(context_parts)

    def _extract_sources(self, chunks: List[str], metadatas: List[Dict]) -> List[str]:
        """
        Extract and format source document citations
        
        Args:
            chunks: Retrieved chunks
            metadatas: Metadata for each chunk
        
        Returns:
            List of source document references
        """
        sources = []
        seen_docs = set()
        
        for chunk, metadata in zip(chunks, metadatas):
            doc_id = metadata.get('doc_id')
            chunk_index = metadata.get('chunk_index', 0)
            total_chunks = metadata.get('total_chunks', 1)
            
            if doc_id and doc_id not in seen_docs:
                source_info = f"{doc_id} (Chunk {chunk_index + 1}/{total_chunks})"
                sources.append(source_info)
                seen_docs.add(doc_id)
        
        return sources

    # ========================================
    # UTILITY METHODS
    # ========================================

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        return {
            'total_chunks': self.collection.count() if self.collection else 0,
            'total_documents': len(self.documents_registry),
            'embedding_model': 'nomic-embed-text',
            'vector_dimension': 768,
            'embedding_source': 'Ollama (local)'
        }


# ============================================
# TESTING & DEBUGGING
# ============================================

if __name__ == '__main__':
    """Test RAG engine"""
    
    logging.basicConfig(level=logging.DEBUG)
    
    print('\n🚀 Testing RAG Engine with Nomic Embeddings...\n')
    
    try:
        # Initialize
        rag = RAGEngine()
        print(f'✅ RAG Engine initialized')
        
        # Check status
        status = rag.get_status()
        print(f'\n📊 Status:')
        print(json.dumps(status, indent=2))
        
        # Check connection
        connected = rag._check_ollama_connection()
        print(f'\n🔗 Ollama connection: {"✅ Connected" if connected else "❌ Not connected"}')
        
        # Get stats
        stats = rag.get_collection_stats()
        print(f'\n📈 Collection Stats:')
        print(json.dumps(stats, indent=2))
        
        print('\n✅ RAG Engine test completed\n')
    
    except Exception as e:
        print(f'\n❌ Test failed: {str(e)}\n')
        sys.exit(1)