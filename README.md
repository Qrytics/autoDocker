# autoDocker
A python script that uses active API to automatically containerize project files without human involvement. Use "distroless" / Alpine images to reduce the attack surface, multi-stage builds to keep the final image small, and an LLM API (like Gemini or OpenAI) to read the code and write the Dockerfile dynamically based on the actual logic it sees.

## Smart Build Wrapper that:
1. Extracts project intent (WorkspaceManager)
2. Drafts optimized code (LLMArchitect)
3. Communicates with OS-level virtualization (DockerBuilder)
4. Corrects its own errors (Self-Healer)
5. Performs Quality Assurance (Validator)

## How to Use:
**Install dependencies:** `pip install litellm docker`

**Set your API Key:** `export GEMINI_API_KEY='your_key_here'`

**Run it:** `python main.py my_code.zip --tag my-web-app:v1`

**Basic usage**: `python main.py my_project.zip`

**Custom tag**: `python main.py my_project.zip --tag myapp:v1.0`

**Different model + skip tests**: `python main.py my_project.zip --model gemini/gemini-1.5-flash --skip-test`

**_See help_**: `python main.py --help`
