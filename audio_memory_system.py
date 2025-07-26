import whisper
import chromadb
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from bertopic import BERTopic
from langchain.chains import ConversationalRetrievalChain
from langchain.llms import ChatOpenAI
from langchain.embeddings import SentenceTransformerEmbeddings
from langchain.vectorstores import Chroma
from langchain.memory import ConversationSummaryBufferMemory
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import sqlite3
from datetime import datetime, timedelta
import numpy as np
import json
import uuid
import time
import logging

class AudioMemoryAssistant:
    def __init__(self, db_path="./memory_db", openai_api_key=None):
        """Initialize the Audio Memory Assistant with all required models"""
        
        # Core models
        print("Loading Whisper model...")
        self.whisper_model = whisper.load_model("base")
        
        print("Loading text embeddings...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        print("Loading emotion analyzer...")
        self.emotion_analyzer = pipeline(
            "text-classification", 
            model="j-hartmann/emotion-english-distilroberta-base",
            device=0 if torch.cuda.is_available() else -1
        )
        
        print("Initializing BERTopic...")
        self.topic_model = BERTopic(
            embedding_model="all-MiniLM-L6-v2",
            min_topic_size=3,
            calculate_probabilities=True
        )
        
        # Vector database
        print("Setting up ChromaDB...")
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        try:
            self.collection = self.chroma_client.get_collection("audio_memories")
        except:
            self.collection = self.chroma_client.create_collection(
                name="audio_memories",
                metadata={"hnsw:space": "cosine"}
            )
        
        # SQL database for structured metadata
        self.db_path = f"{db_path}/metadata.db"
        self._init_sql_db()
        
        # LangChain setup
        if openai_api_key:
            print("Setting up LangChain...")
            self.llm = ChatOpenAI(
                model_name="gpt-3.5-turbo",
                temperature=0.1,
                openai_api_key=openai_api_key
            )
            
            # Create LangChain vector store wrapper
            self.langchain_vectorstore = Chroma(
                client=self.chroma_client,
                collection_name="audio_memories",
                embedding_function=SentenceTransformerEmbeddings(
                    model_name="all-MiniLM-L6-v2"
                )
            )
            
            # Memory for conversation context
            self.conversation_memory = ConversationSummaryBufferMemory(
                llm=self.llm,
                max_token_limit=1000,
                return_messages=True,
                memory_key="chat_history"
            )
            
            # RAG chain
            self.qa_chain = ConversationalRetrievalChain.from_llm(
                llm=self.llm,
                retriever=self.langchain_vectorstore.as_retriever(search_kwargs={"k": 5}),
                memory=self.conversation_memory,
                return_source_documents=True
            )
        else:
            print("No OpenAI API key provided - query functionality will be limited")
            self.llm = None
            self.qa_chain = None
        
        # Topics fitted flag
        self.topics_fitted = False
        
        print("Audio Memory Assistant initialized successfully!")
    
    def _init_sql_db(self):
        """Initialize SQLite database for metadata"""
        self.sql_conn = sqlite3.connect(self.db_path)
        self.sql_conn.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                timestamp REAL,
                duration REAL,
                text_content TEXT,
                emotion_label TEXT,
                emotion_score REAL,
                topic_ids TEXT,
                speaker_info TEXT,
                file_path TEXT,
                created_at TEXT
            )
        ''')
        self.sql_conn.commit()
    
    def process_audio_file(self, audio_file_path, metadata=None):
        """Process an audio file and store it in memory"""
        
        print(f"Processing audio file: {audio_file_path}")
        start_time = time.time()
        
        # 1. Transcribe audio
        print("Transcribing audio...")
        result = self.whisper_model.transcribe(audio_file_path)
        text = result["text"].strip()
        
        if not text:
            print("No speech detected in audio file")
            return None
        
        # 2. Analyze emotion
        print("Analyzing emotion...")
        emotion_result = self.emotion_analyzer(text)[0]
        emotion_label = emotion_result["label"]
        emotion_score = emotion_result["score"]
        
        # 3. Generate embedding
        print("Generating embedding...")
        embedding = self.embedder.encode(text)
        
        # 4. Extract topics (if we have enough data)
        topic_ids = []
        if self.collection.count() > 10 or not self.topics_fitted:
            try:
                # Get all existing texts for topic modeling
                all_results = self.collection.get()
                existing_texts = all_results["documents"] if all_results["documents"] else []
                
                if existing_texts:
                    all_texts = existing_texts + [text]
                    print("Updating topic model...")
                    topics, probs = self.topic_model.fit_transform(all_texts)
                    topic_ids = [int(topics[-1])]  # Topic for new text
                    self.topics_fitted = True
                else:
                    # First document
                    topics, probs = self.topic_model.fit_transform([text])
                    topic_ids = [int(topics[0])]
                    self.topics_fitted = True
            except Exception as e:
                print(f"Topic modeling failed: {e}")
                topic_ids = []
        
        # 5. Create unique ID
        memory_id = str(uuid.uuid4())
        timestamp = time.time()
        
        # 6. Store in vector database
        print("Storing in vector database...")
        self.collection.add(
            embeddings=[embedding.tolist()],
            documents=[text],
            metadatas=[{
                "id": memory_id,
                "timestamp": timestamp,
                "emotion": emotion_label,
                "emotion_score": emotion_score,
                "duration": result.get("duration", 0),
                "file_path": audio_file_path,
                "date": datetime.fromtimestamp(timestamp).isoformat(),
                "topic_ids": json.dumps(topic_ids)
            }],
            ids=[memory_id]
        )
        
        # 7. Store structured metadata in SQL
        print("Storing metadata...")
        self.sql_conn.execute('''
            INSERT INTO memories 
            (id, timestamp, duration, text_content, emotion_label, emotion_score, 
             topic_ids, speaker_info, file_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            memory_id, timestamp, result.get("duration", 0), text, 
            emotion_label, emotion_score, json.dumps(topic_ids),
            json.dumps(metadata) if metadata else None,
            audio_file_path, datetime.now().isoformat()
        ))
        self.sql_conn.commit()
        
        processing_time = time.time() - start_time
        print(f"Audio processed successfully in {processing_time:.2f}s")
        print(f"Emotion: {emotion_label} ({emotion_score:.3f})")
        print(f"Topics: {topic_ids}")
        print(f"Text preview: {text[:100]}...")
        
        return {
            "id": memory_id,
            "text": text,
            "emotion": emotion_label,
            "emotion_score": emotion_score,
            "topics": topic_ids,
            "timestamp": timestamp
        }
    
    def query_memories(self, query, time_filter=None, emotion_filter=None, limit=5):
        """Query memories using natural language"""
        
        if self.qa_chain is None:
            return self._simple_similarity_search(query, time_filter, emotion_filter, limit)
        
        # Build ChromaDB filter
        where_filter = {}
        if time_filter:
            if "since" in time_filter:
                since_timestamp = (datetime.now() - timedelta(days=time_filter["since"])).timestamp()
                where_filter["timestamp"] = {"$gte": since_timestamp}
        
        if emotion_filter:
            where_filter["emotion"] = {"$in": emotion_filter}
        
        # Update retriever with filters if needed
        if where_filter:
            self.qa_chain.retriever.search_kwargs.update({"filter": where_filter})
        
        # Query using RAG chain
        try:
            result = self.qa_chain({"question": query})
            return {
                "answer": result["answer"],
                "source_documents": [
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata
                    } for doc in result["source_documents"]
                ]
            }
        except Exception as e:
            print(f"RAG query failed: {e}")
            return self._simple_similarity_search(query, time_filter, emotion_filter, limit)
    
    def _simple_similarity_search(self, query, time_filter=None, emotion_filter=None, limit=5):
        """Fallback similarity search without LLM"""
        
        # Build filter
        where_filter = {}
        if time_filter and "since" in time_filter:
            since_timestamp = (datetime.now() - timedelta(days=time_filter["since"])).timestamp()
            where_filter["timestamp"] = {"$gte": since_timestamp}
        
        if emotion_filter:
            where_filter["emotion"] = {"$in": emotion_filter}
        
        # Search
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where=where_filter if where_filter else None
        )
        
        if not results["documents"][0]:
            return {"answer": "No memories found matching your query.", "source_documents": []}
        
        # Format results
        documents = []
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            documents.append({
                "content": doc,
                "metadata": metadata,
                "similarity": 1 - results["distances"][0][i]  # Convert distance to similarity
            })
        
        return {
            "answer": f"Found {len(documents)} relevant memories. Use a more specific query for better results.",
            "source_documents": documents
        }
    
    def get_memory_stats(self):
        """Get statistics about stored memories"""
        
        total_count = self.collection.count()
        
        # Get emotion distribution
        all_results = self.collection.get()
        emotions = [meta.get("emotion", "unknown") for meta in all_results["metadatas"]]
        emotion_counts = {}
        for emotion in emotions:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        # Get recent activity
        recent_timestamp = (datetime.now() - timedelta(days=7)).timestamp()
        recent_results = self.collection.query(
            query_texts=[""],
            n_results=total_count,
            where={"timestamp": {"$gte": recent_timestamp}}
        )
        recent_count = len(recent_results["documents"][0]) if recent_results["documents"][0] else 0
        
        # Topic information
        topic_info = {}
        if self.topics_fitted:
            try:
                topic_labels = self.topic_model.get_topic_info()
                topic_info = {
                    "total_topics": len(topic_labels),
                    "top_topics": topic_labels.head(5)["Representation"].tolist()
                }
            except:
                topic_info = {"total_topics": 0, "top_topics": []}
        
        return {
            "total_memories": total_count,
            "recent_memories_7days": recent_count,
            "emotion_distribution": emotion_counts,
            "topics": topic_info
        }
    
    def get_timeline(self, days=30):
        """Get memory timeline for visualization"""
        
        since_timestamp = (datetime.now() - timedelta(days=days)).timestamp()
        
        # Query recent memories
        results = self.collection.query(
            query_texts=[""],
            n_results=1000,  # Large number to get all
            where={"timestamp": {"$gte": since_timestamp}}
        )
        
        if not results["documents"][0]:
            return []
        
        # Format for timeline
        timeline = []
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            timeline.append({
                "id": metadata["id"],
                "timestamp": metadata["timestamp"],
                "date": metadata["date"],
                "emotion": metadata["emotion"],
                "text_preview": doc[:100] + "..." if len(doc) > 100 else doc,
                "duration": metadata.get("duration", 0)
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return timeline
    
    def delete_memory(self, memory_id):
        """Delete a specific memory"""
        
        try:
            # Delete from vector database
            self.collection.delete(ids=[memory_id])
            
            # Delete from SQL database
            self.sql_conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            self.sql_conn.commit()
            
            return True
        except Exception as e:
            print(f"Error deleting memory {memory_id}: {e}")
            return False
    
    def close(self):
        """Clean up resources"""
        if hasattr(self, 'sql_conn'):
            self.sql_conn.close()

# Example usage
if __name__ == "__main__":
    # Initialize (requires OpenAI API key for full functionality)
    assistant = AudioMemoryAssistant(openai_api_key="your-api-key-here")
    
    # Process an audio file
    result = assistant.process_audio_file("meeting_recording.wav")
    print(f"Processed: {result}")
    
    # Query memories
    response = assistant.query_memories("What did we discuss about the budget?")
    print(f"Query response: {response['answer']}")
    
    # Get statistics
    stats = assistant.get_memory_stats()
    print(f"Memory stats: {stats}")
    
    # Get timeline
    timeline = assistant.get_timeline(days=7)
    print(f"Recent memories: {len(timeline)}")
    
    # Clean up
    assistant.close()