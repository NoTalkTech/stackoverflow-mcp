# StackOverflow MCP Server

[![npm version](https://badge.fury.io/js/@notalk-tech%2Fstackoverflow-mcp.svg)](https://badge.fury.io/js/@notalk-tech%2Fstackoverflow-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server that provides seamless access to StackOverflow's programming Q&A database using the FastMCP framework.

## Quick Start

### Using with Cursor (Recommended)

Add this configuration to your Cursor MCP settings:

```json
{
  "mcp_servers": {
    "stackoverflow": {
      "command": "npx",
      "args": [
        "-y",
        "@notalk-tech/stackoverflow-mcp",
        "--api-key", "your_stackoverflow_api_key"
      ]
    }
  }
}
```

### Using NPX

```bash
# Run directly (no installation required)
npx @notalk-tech/stackoverflow-mcp

# With API key
npx @notalk-tech/stackoverflow-mcp --api-key your_key

# Skip installation prompts
npx -y @notalk-tech/stackoverflow-mcp
```

### Using Python Module

```bash
# Direct execution
python -m stackoverflow_mcp

# With uv (recommended)
uv run python -m stackoverflow_mcp --api-key your_key
```

## 🎯 Features

- **🔍 Question Search**: Search StackOverflow questions by keywords
- **📖 Question Details**: Get detailed question content, answers, and metadata
- **🏷️ Tag-based Search**: Find questions by programming language tags
- **⚡ Rate Limit Management**: Automatic detection and handling of API limits
- **🔐 API Authentication**: Support for StackOverflow API keys
- **🚀 Auto-deployment**: NPX-compatible with automatic Python environment setup

## 🔑 Getting Your API Key

To use this MCP server with higher rate limits, you'll need a StackOverflow API key:

### Steps

1. **Register Your Application**
   - Visit https://stackapps.com/applications/register
   - Log in with your Stack Exchange account
   - Fill in application details (name, description, OAuth domain)
   - Submit the registration

2. **Generate Your API Key**
   - Go to your application management page
   - Click **"Generate a new API key"**
   - Copy and save the generated key securely

### Rate Limits

- **Without API key**: 300 requests/day per IP
- **With API key**: 10,000 requests/day

For read-only operations (searching and retrieving Q&A), a simple API key is sufficient. OAuth is only needed for write operations.

**Learn more**: https://api.stackexchange.com/docs/authentication

## ⚙️ Configuration

Create a `.stackoverflow-mcp.json` file in your working directory:

```json
{
  "stackoverflow_api_key": "your_api_key_here",
  "log_level": "CRITICAL"
}
```

The server auto-discovers config files in this order:
1. `.stackoverflow-mcp.json`
2. `stackoverflow-mcp.config.json`
3. `config/stackoverflow-mcp.json`
4. `.config/stackoverflow-mcp.json`

### Command Line Options

```
--working-dir DIRECTORY    Working directory (auto-detect if not specified)
--api-key TEXT             StackOverflow API key
--version                  Show version and exit
--help                     Show help message
```

## 🌐 Available Tools

Once running, the MCP server provides these tools:

- `search_questions`: Search StackOverflow questions by keywords
- `search_by_tags`: Find questions filtered by programming language tags
- `get_question`: Get detailed information about a specific question
- `get_question_with_answers`: Get comprehensive question details including answers
- `get_rate_limit_status`: Check current rate limiting status and quotas
- `get_authentication_status`: Check current API authentication status
- `get_queue_status`: Check current request queue status and statistics

## 📋 Prerequisites

- **Node.js** 14.0.0 or higher
- **Python** 3.12 or higher
- **uv** (recommended) or **pip**

The NPX wrapper automatically handles Python package installation and environment setup.

## 🚀 Development

### Local Setup

```bash
git clone https://github.com/NoTalkTech/stackoverflow-mcp.git
cd stackoverflow-mcp

# Install dependencies
npm install
pip install -e .

# Run in development mode
npm start
```

### Project Structure

```
stackoverflow-mcp/
├── cli.js                          # NPX wrapper (Node.js)
├── package.json                    # NPM package configuration
├── pyproject.toml                  # Python package configuration
├── src/stackoverflow_mcp/          # Python MCP server
│   ├── __main__.py                 # Python module entry point
│   ├── main.py                     # CLI and server management
│   ├── server.py                   # MCP server implementation
│   └── stackoverflow_client.py     # StackOverflow API client
└── tests/                          # Test files
```

### Testing

```bash
# Test npm package
npm test

# Test Python module
python -m pytest tests/ -v
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/NoTalkTech/stackoverflow-mcp/issues)
- **Documentation**: [GitHub README](https://github.com/NoTalkTech/stackoverflow-mcp#readme)

## 🙏 Acknowledgments

- [Model Context Protocol](https://github.com/modelcontextprotocol) for the MCP specification
- [StackOverflow](https://stackoverflow.com/) for providing the API
- The open-source community for inspiration and contributions

---

**Made with ❤️ for the developer community**
