# 🚀 OpenDeepWiki: AI-Powered Codebase Documentation & Chat

**OpenDeepWiki** is an AI-powered tool that helps you understand and interact with any codebase. It automatically analyzes repositories, generates comprehensive documentation, and provides an intelligent chat interface where you can ask questions about your code.

[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue)](https://github.com/Flopsky/OpenDeepWiki)

## ✨ Key Features

- **🔍 Intelligent Code Analysis**: Automatically classifies and analyzes code files, documentation, and configuration files
- **💬 AI-Powered Chat**: Ask questions about your codebase and get contextual answers from AI models that understand your specific code
- **📚 Documentation Generation**: Extracts and processes docstrings, README files, and other documentation
- **🌐 Modern Web UI**: Clean, responsive React interface with conversation history, markdown rendering, and syntax highlighting
- **🔗 Flexible Input**: Supports both GitHub repositories (via URL) and local repositories (via ZIP upload)
- **🤖 Multiple AI Models**: Choose from various Gemini, Claude, and OpenAI models
- **🐋 Containerized**: Fully containerized with Docker for easy deployment
- **📊 Conversation Management**: Save, load, and manage multiple conversation threads

## 🏗️ Architecture

OpenDeepWiki uses a microservice architecture with the following components:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Controller    │    │   Indexer       │
│   (React)       │◄──►│   (Flask)       │◄──►│   (FastAPI)     │
│   Port: 7860    │    │   Port: 5050    │    │   Port: 8002    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Repo Chat     │
                       │   (FastAPI)     │
                       │   Port: 8001    │
                       └─────────────────┘
```

### Services

- **Frontend (React + Vite)**: Modern web interface with TypeScript support
- **Controller (Flask)**: API gateway handling initialization, file uploads, and request routing
- **Indexer Service (FastAPI)**: Analyzes and classifies repository files, extracts documentation
- **Repo Chat Service (FastAPI)**: Provides AI-powered responses using repository context

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Git (for cloning repositories)

### 1. Clone the Repository

```bash
git clone https://github.com/Flopsky/OpenDeepWiki.git
cd OpenDeepWiki
```

### 2. Configure Environment

Create a `.env` file with your API keys:

```bash
# Copy the example environment file
make env

# Edit .env with your API keys
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here  # Optional
OPENAI_API_KEY=your_openai_api_key_here        # Optional

# Optional: Langfuse tracing
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. Build and Run

Using the Makefile (recommended):

```bash
# Setup everything (environment, build, and run)
make setup

# Or step by step:
make build  # Build Docker image
make run    # Run the container
```

Or using Docker directly:

```bash
# Build the Docker image
docker build -t opendeepwiki .

# Run the container
docker run -d --name opendeepwiki_app \
  -p 7860:7860 \
  -p 5050:5050 \
  -p 8001:8001 \
  -p 8002:8002 \
  --env-file .env \
  opendeepwiki
```

### 4. Access the Application

Open your browser and navigate to: **http://localhost:7860**

## 💡 How to Use

### Loading a Repository

1. **GitHub Repository**: 
   - Paste the GitHub URL (e.g., `https://github.com/username/repo`) in the sidebar
   - Click "Initialize" to clone and analyze the repository

2. **Local Repository**:
   - Create a ZIP file of your local repository
   - Use the "Upload Repository (.zip)" button in the sidebar

### Chatting with Your Code

1. Wait for the repository analysis to complete (status shown in sidebar)
2. Select "Custom Documentalist" from the model dropdown
3. Start asking questions about your codebase:
   - "How does the authentication system work?"
   - "What are the main components of this application?"
   - "Explain the database schema"
   - "Show me how to add a new feature"

### Managing Conversations

- **New Chat**: Click "New Chat" to start a fresh conversation
- **Switch Conversations**: Click on any saved conversation in the sidebar
- **Delete Conversations**: Use the trash icon next to conversations
- **Persistent History**: All conversations are automatically saved

## 🧠 Gemini Context Caching Technology

OpenDeepWiki leverages **Gemini Context Caching** to provide efficient and cost-effective AI responses about your codebase. This advanced technique is a core innovation that makes the system both fast and economical.

### How Context Caching Works

1. **Repository Analysis**: When you load a repository, the system:
   - Analyzes all code files, documentation, and configuration files
   - Extracts docstrings, comments, and structural information
   - Creates a comprehensive documentation JSON containing all relevant context

2. **Cache Creation**: The extracted documentation is stored in a **Gemini cached context** with:
   - **Display Name**: Repository identifier for easy management
   - **System Instruction**: Expert developer persona tailored to your specific repository
   - **Content**: Complete repository documentation and metadata
   - **TTL**: 30-minute time-to-live for optimal performance

3. **Intelligent Retrieval**: When you ask questions:
   - The system uses the cached context to understand your specific codebase
   - Queries are processed against the pre-loaded repository knowledge
   - Responses are generated with full awareness of your code structure and patterns

### Technical Implementation

```python
# Cache creation with repository documentation
cache = caching.CachedContent.create(
    model=CONTEXT_CACHING_RETRIVER,
    display_name=repository_name,
    contents=documentation_json,
    system_instruction=system_prompt,
    ttl=datetime.timedelta(minutes=30)
)

# Cached client for efficient queries
client_gemini = instructor.from_gemini(
    client=genai.GenerativeModel.from_cached_content(
        cached_content=cache,
        safety_settings=safety_config
    ),
    mode=instructor.Mode.GEMINI_JSON
)
```

### Benefits

- **⚡ Fast Response Times**: Pre-loaded context eliminates the need to re-process repository data for each query
- **💰 Cost Efficiency**: Reduces token usage by avoiding repetitive context loading
- **🎯 Accurate Responses**: AI has complete understanding of your specific codebase structure
- **🔄 Persistent Knowledge**: Cache persists across multiple conversation sessions
- **📊 Smart Management**: Automatic cache reuse for identical repositories

### Cache Lifecycle

1. **Creation**: Triggered when initializing a new repository
2. **Reuse**: Existing caches are automatically detected and reused for the same repository
3. **Refresh**: Cache is recreated if repository content changes significantly
4. **Cleanup**: Automatic expiration after 30 minutes for optimal resource management

This caching strategy ensures that OpenDeepWiki can provide instant, contextually-aware responses about your code while maintaining cost-effectiveness and system performance.

## 🛠️ Development

### Requirements

- Python 3.12+
- Node.js 18+
- Docker

### Local Development Setup

1. **Backend Services**:
   ```bash
   # Install Python dependencies
   pip install -r requirements.txt
   
   # Run indexer service
   python -m indexer.server
   
   # Run repo chat service
   python -m repo_chat.server
   
   # Run controller
   python frontend/src/controler.py
   ```

2. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Testing

```bash
# Test that all services are working
python test_services.py

# Run frontend tests
cd frontend && npm test
```

### Makefile Commands

```bash
make help           # Show available commands
make env            # Create .env from template
make build          # Build Docker image
make run            # Run container
make stop           # Stop container
make restart        # Restart container
make logs           # View container logs
make clean          # Remove container and image
make prune-all      # Full cleanup including unused Docker objects
```

## 🧩 Technology Stack

### Frontend
- **React 19** with TypeScript
- **Vite** for build tooling
- **Styled Components** for styling
- **React Router** for navigation
- **React Markdown** for rendering
- **React Syntax Highlighter** for code display

### Backend
- **FastAPI** for microservices (Indexer, Repo Chat)
- **Flask** for API gateway (Controller)
- **Pydantic** for data validation
- **Python 3.12** runtime

### AI & APIs
- **Google Gemini** (primary LLM)
- **Anthropic Claude** (optional)
- **OpenAI** (optional)
- **Langfuse** (optional tracing)

### Infrastructure
- **Docker** for containerization
- **Supervisord** for process management
- **Nginx** for static file serving (in container)

## 📁 Project Structure

```
OpenDeepWiki/
├── frontend/               # React frontend application
│   ├── src/
│   │   ├── controler.py   # Flask API gateway
│   │   └── ...            # React components and pages
│   ├── package.json
│   └── vite.config.js
├── indexer/               # File classification service
│   ├── server.py         # FastAPI server
│   ├── service.py        # Classification logic
│   └── schema.py         # Data models
├── repo_chat/            # AI chat service
│   ├── server.py         # FastAPI server
│   ├── service.py        # Chat logic
│   └── schema.py         # Data models
├── src/                  # Core utilities and shared code
│   ├── core/            # Core functionality
│   ├── utils/           # Utility functions
│   └── schemas/         # Shared data models
├── Dockerfile            # Container definition
├── supervisord.conf      # Process management
├── Makefile             # Build and deployment commands
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key for AI responses |
| `ANTHROPIC_API_KEY` | ❌ No | Anthropic Claude API key (optional) |
| `OPENAI_API_KEY` | ❌ No | OpenAI API key (optional) |
| `LANGFUSE_PUBLIC_KEY` | ❌ No | Langfuse public key for tracing |
| `LANGFUSE_SECRET_KEY` | ❌ No | Langfuse secret key for tracing |
| `LANGFUSE_HOST` | ❌ No | Langfuse host URL |

### Ports

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 7860 | Main web interface |
| Controller | 5050 | API gateway |
| Repo Chat | 8001 | AI chat service |
| Indexer | 8002 | File analysis service |

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Guidelines

- Follow Python PEP 8 style guidelines
- Use TypeScript for frontend development
- Add tests for new features
- Update documentation as needed

## 📋 Roadmap

- [x] ✅ Basic repository analysis and indexing
- [x] ✅ AI-powered chat interface
- [x] ✅ Multiple LLM support (Gemini, Claude, OpenAI)
- [x] ✅ Conversation history management
- [x] ✅ Local repository upload via ZIP
- [x] ✅ Modern React UI with TypeScript
- [x] ✅ Docker containerization
- [ ] 🔄 Advanced RAG techniques for better context
- [ ] 🔄 File browser for repository exploration
- [ ] 🔄 Code generation and modification capabilities
- [ ] 🔄 Integration with IDEs and editors
- [ ] 🔄 Team collaboration features

## 🐛 Troubleshooting

### Common Issues

1. **Services not starting**: Check that all required ports are available
2. **API errors**: Verify your API keys are correctly set in `.env`
3. **Repository analysis fails**: Ensure the repository URL is accessible
4. **Docker build fails**: Make sure you have sufficient disk space

### Getting Help

- Check the [Issues](https://github.com/Flopsky/OpenDeepWiki/issues) page
- Review the logs: `make logs`
- Test services: `python test_services.py`

## 📄 License

This project is licensed under the terms specified in the `license` file.

## 🙏 Acknowledgments

- Built with ❤️ using modern web technologies
- Powered by advanced AI language models
- Inspired by the need for better code documentation and understanding

---

**Happy Coding!** 🚀

For questions, issues, or contributions, please visit our [GitHub repository](https://github.com/Flopsky/OpenDeepWiki).
