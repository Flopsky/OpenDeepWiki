

# 🚀 OpenDeepWiki: AI-Powered Multi-Repository Documentation & Chat

**OpenDeepWiki** is an advanced AI-powered tool that helps you understand and interact with multiple codebases simultaneously. It automatically analyzes repositories, generates comprehensive documentation, and provides an intelligent chat interface where you can ask questions about your code across multiple projects.

[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue)](https://github.com/Flopsky/OpenDeepWiki)

## ✨ Key Features

### 🔄 **Multi-Repository Support**
- **Multiple Repository Management**: Load and manage multiple repositories simultaneously
- **Unified Chat Interface**: Ask questions across all your repositories in a single conversation
- **Optimized Pipeline**: Efficient processing with individual context retrieval but unified AI response generation
- **Repository Session Management**: Thread-safe handling of multiple repository sessions
- **Smart Repository Toggling**: Activate/deactivate repositories for targeted queries

### 🎨 **Modern UI Experience**
- **Glass-morphism Design**: Beautiful modern interface with backdrop blur effects
- **Animated Interactions**: Smooth hover effects, transitions, and loading animations
- **Smart Status System**: Context-aware status messages with emoji indicators
- **Professional Repository Cards**: Modern card design with gradient borders and hover effects
- **Intuitive Repository Manager**: Easy-to-use interface for adding, removing, and managing repositories

### 🧠 **Advanced AI Capabilities**
- **🔍 Intelligent Code Analysis**: Automatically classifies and analyzes code files, documentation, and configuration files
- **💬 Multi-Repository AI Chat**: Ask questions about your codebase and get contextual answers from AI models that understand your specific code across multiple projects
- **📚 Cross-Repository Documentation**: Extracts and processes docstrings, README files, and documentation from all loaded repositories
- **🤖 Dynamic Model Selection**: Type any model name from any provider - supports Gemini, Claude, and OpenAI models with automatic routing
- **⚡ Optimized Context Caching**: Gemini Context Caching with 30-minute TTL for cost-effective AI responses
- **🎯 Universal Model Support**: Use cutting-edge models like `gpt-4.1`, `claude-4-sonnet`, `o3`, `gemini-2.5-pro` and more

### 🔧 **Technical Excellence**
- **🌐 Modern Web UI**: Clean, responsive React interface with conversation history, markdown rendering, and syntax highlighting
- **🔗 Flexible Input**: Supports both GitHub repositories (via URL) and local repositories (via ZIP upload)
- **🐋 Containerized**: Fully containerized with Docker for easy deployment
- **📊 Advanced Conversation Management**: Save, load, and manage multiple conversation threads with repository context


<img width="1799" alt="exemple_1" src="https://github.com/user-attachments/assets/3ad1eef6-cff5-4c12-bcb3-550cd168cd23" />


## 🏗️ Architecture

OpenDeepWiki uses an optimized microservice architecture designed for multi-repository processing:

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

### Optimized Multi-Repository Pipeline

The architecture implements an efficient multi-repository processing pipeline:

1. **Individual Repository Processing**: Each repository runs through steps 1-8 (query rewriting, context caching, retrieval) independently
2. **Unified Response Generation**: All retrieved contexts are combined for a single call to the Final Response Generator
3. **Cost Optimization**: Reduces AI API calls while maintaining comprehensive multi-repository awareness
4. **Session Management**: Thread-safe handling of multiple repository sessions with conflict resolution

### Services

- **Frontend (React + Vite)**: Modern web interface with TypeScript support and glass-morphism design
- **Controller (Flask)**: Enhanced API gateway with multi-repository session management
- **Indexer Service (FastAPI)**: Analyzes and classifies repository files, extracts documentation with conflict resolution
- **Repo Chat Service (FastAPI)**: Provides AI-powered responses using multi-repository context aggregation

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

### Managing Multiple Repositories

1. **Adding Repositories**:
   - **GitHub Repository**: Click "Add Repository", paste the GitHub URL (e.g., `https://github.com/username/repo`)
   - **Local Repository**: Click "Upload ZIP" and select your zipped repository

2. **Repository Management**:
   - **View All Repositories**: See all loaded repositories in the modern repository manager
   - **Toggle Active/Inactive**: Use the toggle button to activate/deactivate repositories for queries
   - **Remove Repositories**: Hover over repository cards to reveal the delete button
   - **Status Monitoring**: Visual indicators show repository status (Ready, Loading, Error)

### Dynamic AI Model Selection

1. **Choose Any Model**: Type any model name directly in the model selector
   - **OpenAI**: `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`, `o1-preview`, `o1-mini`, `o3-mini`
   - **Anthropic**: `claude-3.5-sonnet-20241022`, `claude-3-haiku-20240307`, `claude-3-opus-20240229`
   - **Google**: `gemini-2.5-pro-preview-03-25`, `gemini-1.5-flash-8b-001`, `gemini-1.5-pro-002`

2. **Smart Auto-Complete**: Get suggestions for popular models while typing

3. **Automatic Routing**: The system automatically detects which provider to use based on model name

4. **API Key Management**: Configure API keys for each provider in the settings

### Multi-Repository Chat Experience

1. **Repository Selection**: 
   - Activate the repositories you want to query by toggling them "on"
   - The active repository count is displayed in the header
   - Blue indicators show which repositories are active for queries

2. **Cross-Repository Queries**:
   - Ask questions that span multiple repositories: "Compare the authentication systems in my projects"
   - Get unified responses that understand relationships between different codebases
   - Responses automatically indicate which repositories contributed to the answer

3. **Smart Context Management**:
   - Each repository maintains its own optimized context cache
   - Queries intelligently combine context from all active repositories
   - Single AI call processes all repository contexts for cost efficiency

### Example Multi-Repository Queries

- "How do the authentication systems differ between my frontend and backend repositories?"
- "What are the common patterns used across all my projects?"
- "Show me how to integrate the API from repo A with the frontend from repo B"
- "Compare the database schemas in my different microservices"
- "What dependencies are shared across my repositories?"

### Managing Conversations

- **New Chat**: Click "New Chat" to start a fresh conversation
- **Switch Conversations**: Click on any saved conversation in the sidebar
- **Delete Conversations**: Use the trash icon next to conversations
- **Repository Context**: Conversations remember which repositories were active
- **Persistent History**: All conversations are automatically saved with repository context

## 🤖 Universal AI Model Support

OpenDeepWiki features **Dynamic Model Selection** that automatically routes requests to the appropriate AI provider based on the model name you type. This revolutionary approach means you can use any model from any supported provider without changing settings or configurations.

### How It Works

1. **Type Any Model Name**: Simply enter the model name in the model selector
2. **Automatic Detection**: The system detects the provider based on naming patterns
3. **Smart Routing**: Your request is automatically routed to the correct API
4. **Seamless Experience**: All models work identically through the same interface

### Supported Models

| Provider | Model Examples | Naming Pattern |
|----------|---------------|----------------|
| **OpenAI** | `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`, `o1-preview`, `o1-mini`, `o3-mini` | Contains `gpt` or starts with `o` |
| **Anthropic** | `claude-3.5-sonnet-20241022`, `claude-3-haiku-20240307`, `claude-3-opus-20240229` | Contains `claude` |
| **Google** | `gemini-2.5-pro-preview-03-25`, `gemini-1.5-flash-8b-001`, `gemini-1.5-pro-002` | Starts with `gemini-` |

### Key Benefits

- **🎯 Zero Configuration**: No need to change settings when switching models
- **🚀 Future-Proof**: New models work automatically if they follow naming conventions
- **💡 Intelligent**: Case-insensitive detection with smart fallbacks
- **⚡ Unified Interface**: All models provide the same rich experience
- **🔄 Easy Switching**: Try different models instantly to compare results

## 🧠 Advanced Gemini Context Caching Technology

OpenDeepWiki leverages **Gemini Context Caching** with an optimized multi-repository architecture to provide efficient and cost-effective AI responses across multiple codebases.

### Multi-Repository Context Caching

1. **Individual Repository Analysis**: Each repository gets its own:
   - Comprehensive documentation extraction and analysis
   - Unique cached context with repository-specific display names
   - Conflict resolution for duplicate repository names
   - Independent cache lifecycle management

2. **Optimized Cache Strategy**: 
   - **Unique Display Names**: Repositories get unique identifiers using timestamps and content hashes
   - **Cache Reuse**: Identical repositories automatically reuse existing caches
   - **Cleanup Management**: Maintains 2 most recent caches per repository
   - **Conflict Resolution**: Handles multiple repositories with similar names gracefully

3. **Unified Query Processing**:
   - **Individual Processing**: Steps 1-8 (query rewriting, context retrieval) run separately for each active repository
   - **Combined Context**: All repository contexts are aggregated for final response generation
   - **Single AI Call**: Only one call to Final Response Generator, reducing costs while maintaining comprehensive awareness
   - **Attribution**: Responses indicate which repositories contributed to the answer

### Technical Implementation

```python
# Multi-repository pipeline optimization
def run_multi_repo_pipeline(query, repositories):
    contexts = []
    
    # Process each repository individually (steps 1-8)
    for repo in repositories:
        context = run_pipeline_up_to_context_retrieval(query, repo)
        contexts.append(context)
    
    # Single unified response generation (step 9)
    return generate_final_response(query, combined_contexts=contexts)

# Enhanced cache creation with unique naming
cache = caching.CachedContent.create(
    model=CONTEXT_CACHING_RETRIVER,
    display_name=f"{repo_name}_{timestamp}_{hash}",
    contents=documentation_json,
    system_instruction=system_prompt,
    ttl=datetime.timedelta(minutes=30)
)
```

### Benefits for Multi-Repository Workflows

- **⚡ Scalable Performance**: Parallel processing of repositories with optimized caching
- **💰 Cost Efficiency**: Single AI call for final response while maintaining full multi-repo context
- **🎯 Comprehensive Understanding**: AI has complete awareness of all active repository structures
- **🔄 Smart Reuse**: Automatic cache detection and reuse across sessions
- **📊 Advanced Management**: Sophisticated cache lifecycle with conflict resolution
- **🔗 Cross-Repository Intelligence**: Understands relationships and patterns across multiple codebases

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

### Testing Multi-Repository Features

```bash
# Test multi-repository API endpoints
curl -X POST http://localhost:5050/api/add_repo \
  -H "Content-Type: application/json" \
  -d '{"repo_link": "https://github.com/user/repo1"}'

curl -X GET http://localhost:5050/api/list_repos

# Test multi-repository chat
curl -X POST http://localhost:8001/multi_repo_score \
  -H "Content-Type: application/json" \
  -d '{"repositories": [...]}'
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
- **Modern CSS** with glass-morphism effects
- **React Router** for navigation
- **React Markdown** for rendering
- **React Syntax Highlighter** for code display
- **Advanced Animations** with CSS keyframes

### Backend
- **FastAPI** for microservices (Indexer, Repo Chat)
- **Flask** for API gateway (Controller) with session management
- **Pydantic** for data validation
- **Python 3.12** runtime
- **Thread-safe** multi-repository handling

### AI & APIs
- **Google Gemini** with context caching (gemini-*, automatic API routing)
- **Anthropic Claude** (claude-*, automatic API routing)
- **OpenAI GPT & Reasoning Models** (gpt-*, o*, automatic API routing)
- **Dynamic Model Selection** with intelligent provider detection
- **Langfuse** (optional tracing)
- **Optimized Pipeline** for multi-repository processing

### Infrastructure
- **Docker** for containerization
- **Supervisord** for process management
- **Nginx** for static file serving (in container)

## 📁 Project Structure

```
OpenDeepWiki/
├── frontend/               # React frontend application
│   ├── src/
│   │   ├── controler.py   # Flask API gateway with multi-repo support
│   │   ├── components/
│   │   │   └── RepositoryManager.jsx  # Multi-repository management
│   │   ├── services/
│   │   │   └── api.js     # Enhanced API with multi-repo endpoints
│   │   ├── styles/
│   │   │   └── opendeepwiki-theme.css # Modern UI styles
│   │   └── ...            # React components and pages
│   ├── package.json
│   └── vite.config.js
├── indexer/               # File classification service
│   ├── server.py         # FastAPI server
│   ├── service.py        # Classification logic
│   └── schema.py         # Data models
├── repo_chat/            # AI chat service
│   ├── server.py         # FastAPI server with multi-repo endpoints
│   ├── service.py        # Enhanced chat logic with multi-repo pipeline
│   └── schema.py         # Data models
├── src/                  # Core utilities and shared code
│   ├── core/            # Core functionality with cache management
│   ├── utils/           # Utility functions
│   └── schemas/         # Shared data models
├── MULTI_REPO_ARCHITECTURE.md  # Detailed architecture documentation
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
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key (required for gemini-* models) |
| `ANTHROPIC_API_KEY` | ❌ No | Anthropic Claude API key (required for claude-* models) |
| `OPENAI_API_KEY` | ❌ No | OpenAI API key (required for gpt-* and o* models) |
| `LANGFUSE_PUBLIC_KEY` | ❌ No | Langfuse public key for tracing |
| `LANGFUSE_SECRET_KEY` | ❌ No | Langfuse secret key for tracing |
| `LANGFUSE_HOST` | ❌ No | Langfuse host URL |

### Supported Model Patterns

The system automatically routes to the correct provider based on model name:

- **Gemini Models**: Any model starting with `gemini-` (e.g., `gemini-2.5-pro-preview-03-25`)
- **OpenAI Models**: Any model containing `gpt` or starting with `o` (e.g., `gpt-4o`, `o1-preview`)
- **Claude Models**: Any model containing `claude` (e.g., `claude-3.5-sonnet-20241022`)
- **Fallback**: Unknown models default to Gemini for backward compatibility

### Ports

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 7860 | Main web interface |
| Controller | 5050 | API gateway with multi-repo support |
| Repo Chat | 8001 | AI chat service with multi-repo endpoints |
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
- Maintain backward compatibility when possible
- Add tests for new features
- Update documentation as needed
- Consider multi-repository implications for new features

## 📋 Roadmap

- [x] ✅ Basic repository analysis and indexing
- [x] ✅ AI-powered chat interface
- [x] ✅ Multiple LLM support (Gemini, Claude, OpenAI)
- [x] ✅ Dynamic model selection with automatic provider routing
- [x] ✅ Universal model support (gpt-4o, claude-3.5-sonnet, o1-preview, etc.)
- [x] ✅ Conversation history management
- [x] ✅ Local repository upload via ZIP
- [x] ✅ Modern React UI with TypeScript
- [x] ✅ Docker containerization
- [x] ✅ Multi-repository support with optimized pipeline
- [x] ✅ Modern glass-morphism UI with animations
- [x] ✅ Enhanced Gemini Context Caching with conflict resolution
- [x] ✅ Thread-safe session management
- [ ] 🔄 Add support for anthropic extended context caching
- [ ] 🔄 Even more Advanced RAG techniques for better cross-repository context
- [ ] 🔄 File browser for multi-repository exploration
- [ ] 🔄 Code generation and modification capabilities across repositories
- [ ] 🔄 Integration with IDEs and editors
- [ ] 🔄 Team collaboration features with shared repository collections
- [ ] 🔄 Repository dependency analysis and visualization
- [ ] 🔄 Advanced repository comparison and diff features

## 🐛 Troubleshooting

### Common Issues

1. **Services not starting**: Check that all required ports are available
2. **API errors**: Verify your API keys are correctly set in `.env`
3. **Repository analysis fails**: Ensure the repository URL is accessible
4. **Docker build fails**: Make sure you have sufficient disk space
5. **Multi-repository conflicts**: Check repository manager for status indicators
6. **Context caching errors**: Verify Gemini API key and check cache management

### Model-Specific Issues

1. **"API key required" errors**: 
   - For `gpt-*` or `o*` models: Configure `OPENAI_API_KEY`
   - For `claude-*` models: Configure `ANTHROPIC_API_KEY`
   - For `gemini-*` models: Configure `GEMINI_API_KEY`

2. **Model not recognized**: 
   - Check the model name spelling
   - Verify the model follows supported naming patterns
   - Unknown models automatically default to Gemini

3. **Model switching not working**: 
   - Clear your browser cache
   - Check the model selector shows your typed value
   - Verify the correct API key is configured for the model type

### Multi-Repository Specific Issues

1. **Repository not appearing**: Check the repository manager status and error messages
2. **Queries not working across repositories**: Ensure repositories are toggled "active"
3. **Cache conflicts**: Repository names are automatically made unique with timestamps
4. **Performance issues**: Consider reducing the number of active repositories for large queries

### Getting Help

- Check the [Issues](https://github.com/Flopsky/OpenDeepWiki/issues) page
- Review the logs: `make logs`
- Test services: `python test_services.py`
- Review the detailed `MULTI_REPO_ARCHITECTURE.md` for technical details

## 📄 License

This project is licensed under the terms specified in the `license` file.

## 🙏 Acknowledgments

- Built with ❤️ using modern web technologies and advanced AI capabilities
- Powered by Google Gemini Context Caching for optimal performance
- Inspired by the need for better multi-repository code documentation and understanding
- Special thanks to the open-source community for the amazing tools and frameworks

---

**Happy Multi-Repository Coding!** 🚀

Transform your development workflow with OpenDeepWiki's powerful multi-repository AI assistance. Whether you're working on microservices, multiple projects, or complex codebases, OpenDeepWiki helps you understand and navigate your code like never before.

For questions, issues, or contributions, please visit our [GitHub repository](https://github.com/Flopsky/OpenDeepWiki).
