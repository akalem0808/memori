# Memori: Audio Memory System

Memori is an advanced audio memory system that helps users store, process, analyze, and explore their audio memories. The system transcribes audio, extracts meaningful insights, identifies emotions, and makes audio memories searchable and explorable.

## Project Overview

The Memori system consists of two main components:

1. **Backend (Python)**: Handles audio processing, transcription, analysis, and storage
2. **Frontend (React)**: Provides a user-friendly interface for uploading, exploring, and analyzing memories

## Key Features

- **Audio Transcription**: Converts spoken audio to text using Whisper
- **Emotion Analysis**: Identifies emotions in audio content
- **Topic Modeling**: Automatically categorizes memories by topic using BERTopic
- **Vector Search**: Find semantically similar memories
- **Real-time Processing**: Process audio streams in real-time
- **Comprehensive Insights**: Get deeper understanding of your memories
- **User Authentication**: Secure access to memory data

## Technical Stack

### Backend
- Python with FastAPI for the REST API
- Whisper for audio transcription
- SentenceTransformer for embeddings
- BERTopic for topic modeling
- ChromaDB for vector storage
- SQLite for metadata storage

### Frontend
- React with modern hooks and context
- Tailwind CSS for styling
- Responsive design for mobile and desktop
- Real-time updates for memory processing

## Getting Started

### Prerequisites
- Python 3.9+ for backend
- Node.js 14+ for frontend
- Docker (optional)

### Installation

#### Backend
```bash
# Clone the repository
git clone https://github.com/akalem0808/memori.git
cd memori

# Set up Python environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
cd backend
pip install -r requirements.txt

# Run the server
uvicorn memory_api:app --reload
```

#### Frontend
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Project Structure

- `backend/`: Contains all Python backend code
  - `audio_memory_assistant.py`: Core audio processing logic
  - `memory_api.py`: FastAPI endpoints
  - `memory_utils.py`: Utility functions
  - `advanced_features.py`: Real-time processing
  - `memory_insights.py`: Insights engine

- `frontend/`: Contains all React frontend code
  - `src/components/`: React components
  - `src/services/`: API communication
  - `src/`: App configuration and entry point

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
