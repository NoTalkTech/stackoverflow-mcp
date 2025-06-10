# StackOverflow MCP Server

[![npm version](https://badge.fury.io/js/@notalk-tech%2Fstackoverflow-mcp.svg)](https://badge.fury.io/js/@notalk-tech%2Fstackoverflow-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server providing StackOverflow Q&A access through FastMCP framework. NPX wrapper for Python-based server.

## Quick Start

```bash
# Run directly (recommended)
npx @notalk-tech/stackoverflow-mcp

# Auto-confirm installation  
npx -y @notalk-tech/stackoverflow-mcp

# Global install
npm install -g @notalk-tech/stackoverflow-mcp
```

## Prerequisites

- Node.js 14.0.0+
- Python 3.12+
- uv or pip

## Features

- 🔍 Search StackOverflow questions
- 📖 Get detailed question content and answers
- 🏷️ Tag-based filtering
- ⚡ Rate limit handling
- 🔐 API key support
- 🚀 Auto Python environment setup

## Usage

### Basic Commands

```bash
# Start server
npx @notalk-tech/stackoverflow-mcp

# Custom port
npx @notalk-tech/stackoverflow-mcp --port 8080

# Debug mode
npx @notalk-tech/stackoverflow-mcp --log-level DEBUG

# With config file
npx @notalk-tech/stackoverflow-mcp --config-file ./config.json
```

### Configuration

Create `.stackoverflow-mcp.json`:

```json
{
  "host": "localhost",
  "port": 3000,
  "log_level": "INFO",
  "stackoverflow_api_key": "optional_api_key"
}
```

### Command Options

```
--host TEXT                     Host to bind server
--port INTEGER                  Port number
--log-level [DEBUG|INFO|WARNING|ERROR]  Logging level
--config-file FILE              Configuration file path
--working-dir DIRECTORY         Working directory
--api-key TEXT                  StackOverflow API key
--version                       Show version
--help                          Show help
```

## MCP Tools

- `search_questions`: Search by keywords
- `get_question_details`: Get question details
- `search_by_tags`: Filter by programming tags
- `get_user_info`: Get user information

## Development

```bash
# Clone and setup
git clone https://github.com/NoTalkTech/stackoverflow-mcp.git
cd stackoverflow-mcp
npm install

# Test
npm test

# Run locally
node cli.js --help
```

## License

MIT License - see [LICENSE](LICENSE) file.

---

**Made with ❤️ for developers**
