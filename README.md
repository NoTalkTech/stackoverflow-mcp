# StackOverflow MCP Server

[![npm version](https://badge.fury.io/js/@notalk-tech%2Fstackoverflow-mcp.svg)](https://badge.fury.io/js/@notalk-tech%2Fstackoverflow-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server that provides seamless access to StackOverflow's programming Q&A database using the FastMCP framework. This package serves as an NPX-compatible wrapper for the Python-based StackOverflow MCP server.

## Quick Start

### Using NPX (Recommended)

```bash
# Run directly with npx (no installation required)
npx @notalk-tech/stackoverflow-mcp

# Skip installation prompts (useful for automation)
npx -y @notalk-tech/stackoverflow-mcp

# Or install globally
npm install -g @notalk-tech/stackoverflow-mcp
stackoverflow-mcp
```

### Using Python Module Directly

```bash
# If you have the Python package installed
python -m stackoverflow_mcp

# Using uv (recommended for Python development)
uv run python -m stackoverflow_mcp
```

### Integrating with Cursor

To add StackOverflow MCP as a Model Context Protocol server in Cursor, add the following configuration to your Cursor settings:

```json
{
  "mcp_servers": {
    "stackoverflow": {
      "command": "npx",
      "args": [
        "-y",
        "@notalk-tech/stackoverflow-mcp",
        "--api-key", "your_stackoverflow_api_key",
      ]
    }
  }
}
```

## 📋 Prerequisites

- **Node.js** 14.0.0 or higher
- **Python** 3.12 or higher
- **uv** (recommended) or **pip** (Python package manager)

The NPX wrapper will automatically:
- Detect your Python installation
- Install the required Python package (`stackoverflow-fastmcp`)
- Handle environment setup and configuration

## Installation

### Option 1: NPX (No Installation)
```bash
npx @notalk-tech/stackoverflow-mcp --help
```

### Option 2: Global NPM Installation
```bash
npm install -g @notalk-tech/stackoverflow-mcp
stackoverflow-mcp --help
```

### Option 3: Local Development
```bash
git clone https://github.com/NoTalkTech/stackoverflow-mcp.git
cd stackoverflow-mcp
npm install
node cli.js --help
```

## 🎯 Features

- **🔍 Question Search**: Search StackOverflow questions by keywords
- **📖 Question Details**: Get detailed question content, answers, and metadata
- **🏷️ Tag-based Search**: Find questions by programming language tags
- **⚡ Rate Limit Management**: Automatic detection and handling of API limits
- **🔐 API Authentication**: Support for StackOverflow API keys
- **🚀 Auto-deployment**: NPX-compatible with automatic Python environment setup
- **📁 Smart Configuration**: Auto-discovery of config files and working directories
- **🔧 Development Mode**: Enhanced logging and debugging features
- **⚡ FastMCP Implementation**: Simplified, elegant server using FastMCP framework

## About MCP Mode

This server is specifically designed to operate in **Model Context Protocol (MCP) mode**, which means:

- Communication occurs through standard input/output (stdio) rather than HTTP
- The server integrates seamlessly with AI assistants supporting the MCP standard
- No traditional server ports or network connections are used
- The server provides a consistent, structured interface for querying StackOverflow

MCP mode makes this tool ideal for integration with AI models, allowing them to search and retrieve programming knowledge programmatically.

## Usage

### Basic Usage

```bash
# Start the MCP server with default settings
npx @notalk-tech/stackoverflow-mcp

# Auto-confirm installation (useful for scripts/CI)
npx -y @notalk-tech/stackoverflow-mcp

# Provide an API key directly
npx @notalk-tech/stackoverflow-mcp --api-key your_stackoverflow_api_key

# Specify a working directory
npx @notalk-tech/stackoverflow-mcp --working-dir /path/to/your/project
```

### Python Development with uv

For Python development, we recommend using uv for faster dependency management:

```bash
# Install dependencies with uv
uv sync

# Run the server with uv
uv run python -m stackoverflow_mcp

# Run with API key
uv run python -m stackoverflow_mcp --api-key your_stackoverflow_api_key
```

**FastMCP Benefits:**
- 🔥 **Simplified Code**: Clean, maintainable implementation
- 🎯 **Decorator-based**: Clean tool registration with `@mcp.tool()`
- 🚀 **Auto-schema**: Type hints automatically generate schemas  
- 🛡️ **Built-in Error Handling**: Consistent error responses
- 📦 **Better Separation**: Clean architecture with focused responsibilities

### Getting Your API Key

To use this MCP server with higher rate limits, you'll need a StackOverflow API key:

#### Quick Steps

1. **Register Your Application**
   - Visit https://stackapps.com/apps/oauth/register
   - Log in with your Stack Exchange account
   - Fill in basic information:
     - Application Name (e.g., "My MCP Server")
     - Description (brief description of your use case)
     - OAuth Domain (can use `localhost` for local development)
     - Application Website (optional)
   - Submit the registration

2. **Generate Your API Key**
   - After registration, go to your application management page
   - Click **"Generate a new API key"** button
   - Copy the generated key (this is your API key)
   - Keep this key secure and don't share it publicly

3. **Configure the Server**
   - Add the key to your configuration file (see Configuration section below)
   - Or pass it via command line: `--api-key your_key_here`

#### Rate Limits

- **Without API key**: 300 requests/day per IP
- **With API key**: 10,000 requests/day
- **With OAuth**: 10,000 requests/day + write access (not needed for read-only queries)

For read-only operations (searching and retrieving questions/answers), a simple API key is sufficient. You don't need OAuth authentication unless you want to post questions, answers, or perform write operations.

**Learn more**: https://api.stackexchange.com/docs/authentication

### Configuration

Create a `.stackoverflow-mcp.json` file in your project directory:

```json
{
  "stackoverflow_api_key": "your_api_key_here",
  "log_level": "CRITICAL"
}
```

### Command Line Options

```
Options:
  --working-dir DIRECTORY         Working directory (auto-detect if not specified)
  --api-key TEXT                  StackOverflow API key
  --version                       Show the version and exit.
  --help                          Show this message and exit.
```

## 🔧 Configuration Files

The server automatically discovers configuration files in the following order:

1. `.stackoverflow-mcp.json`
2. `stackoverflow-mcp.config.json`
3. `config/stackoverflow-mcp.json`
4. `.config/stackoverflow-mcp.json`

## 🌐 API Endpoints

Once running, the MCP server provides the following tools:

- `search_questions`: Search StackOverflow questions by keywords
- `search_by_tags`: Find questions filtered by programming language tags
- `get_question`: Get detailed information about a specific question
- `get_question_with_answers`: Get comprehensive question details including answers
- `get_rate_limit_status`: Get current rate limiting status and quotas
- `get_authentication_status`: Get current API authentication status
- `get_queue_status`: Get current request queue status and statistics

## 🧪 Testing

```bash
# Test the npm package
npm test

# Test npm packaging
npm run test:npm

# Test global installation
npm run test:install

# Test Python module directly
python -m pytest tests/ -v
```

## 🚀 Development

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/NoTalkTech/stackoverflow-mcp.git
cd stackoverflow-mcp

# Install Node.js dependencies
npm install

# Install Python dependencies
pip install -e .

# Run in development mode
npm start
```

### Project Structure

```
@notalk/stackoverflow-mcp/
├── cli.js                          # NPX wrapper (Node.js)
├── package.json                    # NPM package configuration
├── src/stackoverflow_mcp/          # Python MCP server
│   ├── __main__.py                 # Python module entry point
│   ├── main.py                     # CLI and server management
│   ├── server.py                   # MCP server implementation
│   └── stackoverflow_client.py     # StackOverflow API client
├── tests/                          # Test files
└── README.md                       # This file
```

## 📦 Publishing

### Semantic Versioning

This package follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Current Versions

- **Python Package**: `stackoverflow-fastmcp` v0.2.6
- **NPM Package**: `@notalk-tech/stackoverflow-mcp` v1.2.5

### Version Synchronization

When publishing new versions, it's important to keep version numbers synchronized:

1. **Python Package Version**: Defined in `src/stackoverflow_mcp/__init__.py` and `pyproject.toml`
2. **NPM Package Version**: Defined in `package.json`
3. **CLI Version Reference**: Defined in `cli.js` (expectedVersion variable)

All three should be updated together when making a release to ensure consistency.

### Release Process

This project provides a unified publishing script to simultaneously release both NPM and Python packages.

```bash
# Option 1: Using the publish script (recommended)
./publish.sh             # Publish both NPM and Python packages
./publish.sh --npm-only  # Publish only the NPM package
./publish.sh --pypi-only # Publish only the Python package
./publish.sh --dry-run   # Test the publishing process without actual uploads

# Option 2: Manual process
# Update version
npm version patch|minor|major

# Publish to npm
npm publish

# Create GitHub release
git push --tags
```

#### Prerequisites for Publishing

- PyPI API token (environment variable `PYPI_API_TOKEN` or configured in `~/.pypirc`)
- NPM authentication (`npm login` or using automation tokens)
- Git credentials for pushing tags

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/NoTalkTech/stackoverflow-mcp/issues)
- **Documentation**: [GitHub Wiki](https://github.com/NoTalkTech/stackoverflow-mcp/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/NoTalkTech/stackoverflow-mcp/discussions)

## 🙏 Acknowledgments

- [Model Context Protocol](https://github.com/modelcontextprotocol) for the MCP specification
- [StackOverflow](https://stackapps.com/applications/register) for providing the API
- The open-source community for inspiration and contributions

---

**Made with ❤️ for the developer community**
