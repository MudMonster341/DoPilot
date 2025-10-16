# DoPilot

AI-powered code generator that transforms natural language descriptions into production-ready applications using intelligent prompt enhancement and multi-agent code generation.

Hosted at : https://dopilot-9uemyzapfmyzq8posqqpnn.streamlit.app/ 
---

## Key Selling Feature: Intelligent Prompt Enhancement

DoPilot doesn't just generate code from your initial description. It enhances your prompt through an intelligent question-answer workflow:

1. **Initial Analysis**: Analyzes your project idea to identify missing information
2. **Targeted Questions**: Asks 10 core questions about technology stack, deployment target, database requirements, authentication, UI preferences, and more
3. **Context Building**: Synthesizes your answers into a comprehensive technical specification
4. **AI Enhancement**: Uses LLM to expand your requirements into a detailed, unambiguous project specification (max 3000 characters)
5. **User Control**: Allows you to review and edit the final enhanced prompt before generation

This ensures the generated code precisely matches your needs, reducing iteration cycles and improving first-time accuracy.

---

## Features

- **Prompt Enhancement System**: Transforms vague ideas into detailed technical specifications through guided questions
- **Multi-Agent Architecture**: Specialized agents for planning, architecture, coding, security, and verification
- **Security Validation**: Automatic detection and fixing of common vulnerabilities (hardcoded secrets, SQL injection, XSS)
- **Production-Ready Output**: Complete applications with proper structure, error handling, and best practices
- **Rate Limiting**: Built-in protection against API quota exhaustion
- **Token Management**: Optimized to minimize LLM API costs
- **ZIP Export**: Download complete projects with all files and documentation

---

## Architecture

DoPilot uses LangGraph to orchestrate a multi-agent workflow:

```
User Prompt → Prompt Optimizer → Enhanced Specification
                                         ↓
                                    Planner Agent
                                         ↓
                                  Architect Agent
                                         ↓
                                    Coder Agent (loops until all files done)
                                         ↓
                                  Security Agent
                                         ↓
                                 Security Fixer (if issues found)
                                         ↓
                              Final Verification Agent
                                         ↓
                                Complete Project + ZIP
```

### Tech Stack

- **LangGraph**: State machine orchestration for multi-agent workflows
- **LangChain**: LLM integration and prompt management
- **Google Gemini / Groq**: AI models for code generation and analysis
- **Streamlit**: Web interface
- **Pydantic**: Type-safe state management

---

## Quick Start

### 1. Prerequisites
- Python 3.11 or higher
- [uv package manager](https://docs.astral.sh/uv/getting-started/installation/)
- API key from either:
  - **Google Gemini** (Recommended): [Get API Key](https://aistudio.google.com/apikey)
  - **Groq**: [Get API Key](https://console.groq.com/keys)

### 2. Installation
```bash
# Install dependencies
uv sync

# Create environment file
copy .sample_env .env

# Add your API key to .env
# For Gemini:
MODEL_PROVIDER=gemini
GOOGLE_API_KEY=your_actual_api_key_here

# For Groq:
MODEL_PROVIDER=groq
GROQ_API_KEY=your_actual_api_key_here
```

### 3. Run Application

**Web Interface (Recommended)**
```bash
streamlit run app.py
```
Then open http://localhost:8501 in your browser.

**Command Line**
```bash
python main.py
```

## How to Use

1. Enter your application idea in natural language
2. Answer 10 core questions (application type, tech stack, database, authentication, UI preferences, etc.)
3. Review and edit the AI-enhanced specification (character limit: 3000)
4. Monitor real-time generation logs
5. Download complete project as ZIP

## Example Prompts

- "Create a to-do list application with local storage"
- "Build a weather dashboard that fetches data from OpenWeather API"
- "Make a blog with markdown support and syntax highlighting"
- "Create a calculator with scientific functions"
- "Build a portfolio website with contact form"

## Security Features

### Built-in Protection
- Environment variable validation for API keys
- Automatic security scanning for common vulnerabilities
- Detection of hardcoded credentials, API keys, and secrets
- SQL injection prevention checks
- XSS vulnerability detection
- Rate limiting to prevent API quota exhaustion
- Token usage optimization to minimize costs

### Rate Limiting Configuration
DoPilot implements multiple layers of rate limiting:
- Per-user request throttling
- API call batching where possible
- Automatic retry with exponential backoff
- Token counting to stay within model limits

### Generated Code Security
All generated code includes:
- Environment variable usage for sensitive data
- Input validation and sanitization
- Proper error handling
- No hardcoded credentials or secrets

## Model Comparison

| Feature | Google Gemini | Groq Llama |
|---------|--------------|------------|
| Code Quality | Excellent | Good |
| Speed | Fast | Very Fast |
| Context Size | 32K tokens | 8K tokens |
| Rate Limit | 10 req/min | 30 req/min |
| Best For | Production apps | Quick prototypes |

## Cost Optimization

- Prompt enhancement limited to 3000 characters to reduce token usage
- Simplified verification agent to minimize unnecessary LLM calls
- Efficient state management to avoid redundant API requests
- Strategic use of prompt caching where supported

---

**Important**: Always review generated code before deploying to production. While DoPilot generates production-ready code with security best practices, manual review is recommended.
