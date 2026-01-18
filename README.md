# autoDocker
A python script that uses active API to automatically containerize project files without human involvement. Use "distroless" / Alpine images to reduce the attack surface, multi-stage builds to keep the final image small, and an LLM API (like Gemini or OpenAI) to read the code and write the Dockerfile dynamically based on the actual logic it sees.
