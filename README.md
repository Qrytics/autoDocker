# autoDocker

An LLM-powered tool that automatically containerizes your project files without human involvement. It uses an LLM API to read your code, generate an optimized Dockerfile with multi-stage builds and Alpine/slim base images, and then builds and validates the Docker image — all from a single command.

## How It Works

autoDocker is a smart build wrapper that:

1. **Extracts project intent** — reads your source files to understand the project structure (`WorkspaceManager`)
2. **Drafts an optimized Dockerfile** — uses an LLM to generate a secure, minimal Dockerfile (`LLMArchitect`)
3. **Builds the Docker image** — communicates with Docker on your machine (`DockerBuilder`)
4. **Self-heals on errors** — if the build fails, it automatically asks the LLM to fix the Dockerfile and retries
5. **Validates the result** — runs the container briefly to confirm it starts correctly (`Validator`)

## Prerequisites

- **Python 3.10+**
- **Docker** — [install Docker Desktop](https://www.docker.com/products/docker-desktop/) and make sure it is running
- **A Groq API key** — free tier available at <https://console.groq.com>

## Installation

```bash
# Clone the repository
git clone https://github.com/Qrytics/autoDocker.git
cd autoDocker

# Install the package (creates the `autodocker` CLI command)
pip install -e .
```

## Configuration

Export your API key before running:

```bash
export GROQ_API_KEY='your_key_here'
```

> **Using a different LLM provider?** autoDocker uses [LiteLLM](https://docs.litellm.ai/docs/) under the hood, so any provider it supports works. For example, to use Gemini set `GEMINI_API_KEY` and pass `--model gemini/gemini-1.5-flash`.

## Quick Start — Hello World

This example containerizes a simple "Hello, World!" Python script in under a minute.

**1. Create a sample project zip:**

```bash
mkdir hello_world
echo 'print("Hello, World!")' > hello_world/main.py
zip -r hello_world.zip hello_world/
```

**2. Run autoDocker:**

```bash
autodocker hello_world.zip --tag hello-world:v1
```

You should see autoDocker unpack the project, generate a Dockerfile, build the image, and confirm it runs successfully.

**3. Run your container manually (optional):**

```bash
docker run --rm hello-world:v1
# Hello, World!
```

## Usage

```
autodocker <source> [options]
```

| Argument | Description |
|---|---|
| `source` | Path to a `.zip` file **or** a public GitHub URL |
| `--tag TAG` | Docker image tag (default: `auto-docker-test:latest`) |
| `--model MODEL` | LiteLLM model string (default: `groq/llama-3.1-8b-instant`) |
| `--skip-test` | Skip the runtime stability check after building |

### Examples

```bash
# Basic usage with a zip file
autodocker my_project.zip

# Set a custom image tag
autodocker my_project.zip --tag myapp:v1.0

# Containerize a public GitHub repository
autodocker https://github.com/user/repo --tag myrepo:latest

# Use a different LLM model and skip the runtime test
autodocker my_project.zip --model gemini/gemini-1.5-flash --skip-test

# Show all options
autodocker --help
```
