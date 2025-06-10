#!/usr/bin/env node

/**
 * StackOverflow MCP Server - NPX CLI Wrapper
 * 
 * This script provides npx compatibility for the Python-based StackOverflow MCP server.
 * It automatically handles Python environment detection, package installation, and 
 * working directory configuration.
 */

const { spawn } = require('child_process');
const { existsSync } = require('fs');
const path = require('path');
const os = require('os');

class StackOverflowMCPCLI {
    constructor() {
        this.pythonCommands = ['python3', 'python'];
        this.packageName = 'stackoverflow-mcp';
        this.verbose = process.argv.includes('--verbose') || process.argv.includes('-v');
    }

    log(message) {
        if (this.verbose) {
            console.log(`[stackoverflow-mcp] ${message}`);
        }
    }

    error(message) {
        console.error(`[stackoverflow-mcp] ERROR: ${message}`);
    }

    async findPython() {
        for (const cmd of this.pythonCommands) {
            try {
                const result = await this.runCommand(cmd, ['--version'], { stdio: 'pipe' });
                if (result.code === 0) {
                    const version = result.stdout.toString().trim();
                    this.log(`Found Python: ${cmd} (${version})`);
                    return cmd;
                }
            } catch (error) {
                this.log(`${cmd} not found: ${error.message}`);
            }
        }
        throw new Error('Python 3.12+ is required but not found. Please install Python from https://www.python.org/');
    }

    async runCommand(command, args = [], options = {}) {
        return new Promise((resolve, reject) => {
            const defaultOptions = {
                stdio: 'inherit',
                cwd: process.cwd(),
                env: process.env
            };
            
            const mergedOptions = { ...defaultOptions, ...options };
            
            this.log(`Running: ${command} ${args.join(' ')}`);
            
            const child = spawn(command, args, mergedOptions);
            
            let stdout = '';
            let stderr = '';
            
            if (child.stdout) {
                child.stdout.on('data', (data) => {
                    stdout += data.toString();
                });
            }
            
            if (child.stderr) {
                child.stderr.on('data', (data) => {
                    stderr += data.toString();
                });
            }
            
            child.on('close', (code) => {
                resolve({
                    code,
                    stdout,
                    stderr
                });
            });
            
            child.on('error', (error) => {
                reject(error);
            });
        });
    }

    async checkPackageInstalled(pythonCmd) {
        try {
            const result = await this.runCommand(pythonCmd, ['-c', `import ${this.packageName.replace('-', '_')}`], { stdio: 'pipe' });
            return result.code === 0;
        } catch (error) {
            return false;
        }
    }

    async installPackage(pythonCmd) {
        this.log(`Installing ${this.packageName} Python package...`);
        
        // If we're in a development environment, try local installation first
        if (existsSync('pyproject.toml') || existsSync('setup.py')) {
            try {
                this.log('Found development environment, installing locally...');
                const result = await this.runCommand(pythonCmd, ['-m', 'pip', 'install', '-e', '.']);
                if (result.code === 0) {
                    console.log(`✅ Successfully installed ${this.packageName} (development mode)`);
                    return true;
                }
            } catch (error) {
                this.log(`Local install failed: ${error.message}`);
            }
        }

        // Try uv first (modern Python package manager)
        try {
            this.log('Trying uv installation...');
            const result = await this.runCommand('uv', ['pip', 'install', this.packageName], { stdio: 'pipe' });
            if (result.code === 0) {
                console.log(`✅ Successfully installed ${this.packageName} (uv)`);
                return true;
            }
        } catch (error) {
            this.log(`uv not found or failed: ${error.message}`);
        }

        // Try pipx (isolated Python apps)
        try {
            this.log('Trying pipx installation...');
            const result = await this.runCommand('pipx', ['install', this.packageName], { stdio: 'pipe' });
            if (result.code === 0) {
                console.log(`✅ Successfully installed ${this.packageName} (pipx)`);
                return true;
            }
        } catch (error) {
            this.log(`pipx not found or failed: ${error.message}`);
        }

        // Try pip with user flag (safer for externally managed environments)
        try {
            this.log('Trying pip user installation...');
            const result = await this.runCommand(pythonCmd, ['-m', 'pip', 'install', '--user', this.packageName]);
            if (result.code === 0) {
                console.log(`✅ Successfully installed ${this.packageName} (pip --user)`);
                return true;
            }
        } catch (error) {
            this.log(`pip --user failed: ${error.message}`);
        }

        // Last resort: try pip with break system packages flag
        try {
            this.log('Trying pip with --break-system-packages (last resort)...');
            const result = await this.runCommand(pythonCmd, ['-m', 'pip', 'install', '--break-system-packages', this.packageName]);
            if (result.code === 0) {
                console.log(`⚠️  Successfully installed ${this.packageName} (--break-system-packages)`);
                console.log('⚠️  Warning: System packages flag used - consider using uv or pipx instead');
                return true;
            }
        } catch (error) {
            this.log(`--break-system-packages failed: ${error.message}`);
        }

        return false;
    }

    async detectWorkingDirectory() {
        const cwd = process.cwd();
        const indicators = [
            'pyproject.toml',
            'package.json',
            '.git',
            '.stackoverflow-mcp.json',
            'stackoverflow-mcp.config.json'
        ];

        // Check current directory
        for (const indicator of indicators) {
            if (existsSync(path.join(cwd, indicator))) {
                this.log(`Detected project directory from ${indicator}: ${cwd}`);
                return cwd;
            }
        }

        // Check parent directories
        let current = cwd;
        while (current !== path.dirname(current)) {
            current = path.dirname(current);
            for (const indicator of indicators) {
                if (existsSync(path.join(current, indicator))) {
                    this.log(`Found project directory: ${current}`);
                    return current;
                }
            }
        }

        this.log(`Using current working directory: ${cwd}`);
        return cwd;
    }

    filterCliArgs(args) {
        // Filter out Node.js specific arguments and pass through relevant ones
        const filteredArgs = args.filter(arg => {
            return !arg.startsWith('--inspect') && 
                   !arg.startsWith('--debug') &&
                   arg !== '--verbose' &&  // Handle this in Node.js wrapper
                   arg !== '-v';
        });

        // Add verbose flag for Python if enabled
        if (this.verbose && !filteredArgs.includes('--log-level')) {
            filteredArgs.push('--log-level', 'DEBUG');
        }

        return filteredArgs;
    }

    async main() {
        try {
            console.log('🔧 StackOverflow MCP Server (npx wrapper)');
            console.log('');

            // 1. Find Python
            const pythonCmd = await this.findPython();

            // 2. Detect working directory
            const workingDir = await this.detectWorkingDirectory();
            this.log(`Detected working directory: ${workingDir}`);
            
            try {
                process.chdir(workingDir);
                this.log(`Changed to working directory: ${process.cwd()}`);
            } catch (error) {
                this.error(`Failed to change to working directory ${workingDir}: ${error.message}`);
                // Continue with current directory
            }

            // 3. Check if package is installed
            const isInstalled = await this.checkPackageInstalled(pythonCmd);
            
            if (!isInstalled) {
                console.log(`📦 ${this.packageName} not found, installing...`);
                const installSuccess = await this.installPackage(pythonCmd);
                
                if (!installSuccess) {
                    this.error('Failed to install the Python package');
                    this.error('Please try one of these methods:');
                    this.error('');
                    this.error('Recommended (pipx):');
                    this.error('  brew install pipx');
                    this.error(`  pipx install ${this.packageName}`);
                    this.error('');
                    this.error('Alternative (uv):');
                    this.error('  brew install uv');
                    this.error(`  uv pip install ${this.packageName}`);
                    this.error('');
                    this.error('Fallback (pip):');
                    this.error(`  pip install --user ${this.packageName}`);
                    this.error('');
                    process.exit(1);
                }
            } else {
                this.log('Python package already installed');
            }

            // 4. Filter and prepare CLI arguments
            const cliArgs = process.argv.slice(2);
            const filteredArgs = this.filterCliArgs(cliArgs);
            
            // Add working directory argument if not already specified
            if (!filteredArgs.includes('--working-dir') && !filteredArgs.includes('--working-directory')) {
                filteredArgs.push('--working-dir', workingDir);
            }

            // 5. Run the Python CLI
            console.log('🚀 Starting StackOverflow MCP Server...');
            console.log('');

            const result = await this.runCommand(pythonCmd, ['-m', this.packageName.replace('-', '_'), ...filteredArgs]);
            process.exit(result.code);

        } catch (error) {
            this.error(error.message);
            console.log('');
            console.log('💡 Troubleshooting:');
            console.log('  1. Ensure Python 3.12+ is installed and in PATH');
            console.log('  2. Install a Python package manager:');
            console.log('     brew install pipx   (recommended)');
            console.log('     brew install uv     (alternative)');
            console.log('  3. Check network connectivity for package installation');
            console.log('  4. Try running with --verbose for more details');
            console.log('');
            console.log('For more help, visit: https://github.com/NoTalkTech/stackoverflow-mcp');
            process.exit(1);
        }
    }
}

// Handle CLI execution
if (require.main === module) {
    const cli = new StackOverflowMCPCLI();
    cli.main().catch((error) => {
        console.error('Unexpected error:', error);
        process.exit(1);
    });
}

module.exports = StackOverflowMCPCLI; 