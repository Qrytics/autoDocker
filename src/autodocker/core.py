import os
import zipfile
import tempfile
import shutil
import os
import docker
from git import Repo
from pathlib import Path
from litellm import completion

## Feature 1 / Task 1
class WorkspaceManager:
    def __init__(self, source_path):
        self.source_path = source_path # This can be a URL or a Path
        self.temp_dir = None
        self.file_map = []
        self.actual_files = []

    def setup(self):
        """Extracts zip to a temp directory and maps the structure."""
        self.temp_dir = tempfile.mkdtemp(prefix="auto_docker_")
        
        with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)
        
        self._build_file_map()
        return self.temp_dir

    def _build_file_map(self):
        """Scans the directory and creates a string representation of the project."""
        exclude_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'env'}
        
        lines = []
        self.actual_files = []
        
        for root, dirs, files in os.walk(self.temp_dir):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            level = os.path.relpath(root, self.temp_dir).count(os.sep)
            indent = ' ' * 4 * level
            folder_name = os.path.basename(root)
            
            if folder_name:
                lines.append(f"{indent}📂 {folder_name}/")
            
            sub_indent = ' ' * 4 * (level + 1)
            for f in files:
                lines.append(f"{sub_indent}📄 {f}")
                rel_path = os.path.relpath(os.path.join(root, f), self.temp_dir)
                self.actual_files.append(rel_path)
        
        self.file_map = "\n".join(lines)

    def get_context_for_llm(self):
        """Returns the file map and content of key manifest files."""
        context = f"Project Structure:\n{self.file_map}\n\n"

        context += "=== FILES THAT ACTUALLY EXIST ===\n"
        context += "\n".join(self.actual_files)
        context += "\n\n"
        
        # Identify key files that define the tech stack
        manifests = ['package.json', 'requirements.txt', 'go.mod', 'pom.xml', 'main.py', 
                     'app.py', 'index.js', 'pyproject.toml', 'setup.py']

        found_manifests = []
        missing_manifests = []
        
        context += "Key File Contents:\n"
        for root, _, files in os.walk(self.temp_dir):
            for f in files:
                if f in manifests:
                    found_manifests.append(f)
                    file_path = os.path.join(root, f)
                    with open(file_path, 'r', errors='ignore') as content:
                        context += f"--- {f} ---\n{content.read(1000)}\n" # Read first 1000 chars
        
        missing_manifests = [m for m in manifests if m not in found_manifests]
        if missing_manifests:
            context += "\n=== MISSING STANDARD FILES ===\n"
            context += f"The following common files do NOT exist: {', '.join(missing_manifests)}\n"
            context += "Do NOT attempt to COPY these files in the Dockerfile!\n\n"
        
        return context

    def cleanup(self):
        """Deletes the temporary workspace."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def setup_from_github(self, repo_url):
        """Clones a GitHub repo to a temp directory."""
        self.temp_dir = tempfile.mkdtemp(prefix="autodocker_git_")
        try:
            Repo.clone_from(repo_url, self.temp_dir)
            self._build_file_map() # Build the tree for the LLM
            return self.temp_dir
        except Exception as e:
            raise Exception(f"Git Clone Failed: {e}")

## Feature 1 / Task 2
class LLMArchitect:
    def __init__(self, model="groq/llama-3.3-70b-versatile"): # Defaulting to groq
        self.model = model

    def generate_dockerfile(self, project_context):
        """Sends project context to LLM and extracts the Dockerfile code."""
        
        system_prompt = (
            "You are an expert DevOps Engineer. Your task is to generate a Dockerfile based on a project structure.\n"
            "STRICT REQUIREMENTS:\n"
            "1. Use MULTI-STAGE builds to keep the image small.\n"
            "2. Use 'distroless' or 'alpine' as the final runtime base for security.\n"
            "3. Optimize for layer caching (copy requirements/package files first).\n"
            "4. Ensure the entry point is correctly identified from the file list.\n"
            "5. CRITICAL: Only COPY files that are listed in 'FILES THAT ACTUALLY EXIST' section.\n"
            "6. If requirements.txt is missing but pyproject.toml or setup.py exists, use 'pip install .' instead.\n"
            "7. Return ONLY the content of the Dockerfile. No markdown code blocks, no explanations."
        )

        user_prompt = f"Analyze this project and create the most optimized Dockerfile possible:\n\n{project_context}"

        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2 # Keep it deterministic
            )
            
            dockerfile_content = response.choices[0].message.content
            return self._clean_llm_output(dockerfile_content)
        except Exception as e:
            return f"Error generating Dockerfile: {str(e)}"

    def _clean_llm_output(self, text):
        """Removes markdown backticks if the LLM ignores instructions."""
        # Step 1: Remove markdown code blocks
        if "```dockerfile" in text:
            text = text.split("```dockerfile")[1].split("```")[0]
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                text = parts[1]
        
        # Step 2: Only keep lines that start with valid Docker instructions
        # This prevents "Error:" or "Here is the fix:" from being included
        valid_instructions = ("FROM", "RUN", "COPY", "WORKDIR", "CMD", "ENTRYPOINT", "EXPOSE", "ENV", "ARG", "LABEL", "USER", "VOLUME", "HEALTHCHECK", "#")
        lines = text.strip().split("\n")
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Keep lines that start with valid instructions OR continuation lines (indented)
            if stripped and (stripped.upper().startswith(valid_instructions) or line.startswith(" ") or line.startswith("\t")):
                cleaned_lines.append(line)
        
        result = "\n".join(cleaned_lines).strip()
        
        # Step 3: Validate we have at least a FROM instruction
        if not result or "FROM" not in result.upper():
            raise ValueError(f"LLM did not return a valid Dockerfile. Response was: {text[:200]}")
        
        return result

    def heal_dockerfile(self, project_context, faulty_dockerfile, error_log):
        """Asks the LLM to fix a Dockerfile that failed to build."""
        system_prompt = (
            "You are a Senior DevOps Engineer. A Dockerfile failed to build.\n"
            "CRITICAL RULES:\n"
            "1. Only COPY files that are explicitly listed in 'FILES THAT ACTUALLY EXIST' section.\n"
            "2. If a file like requirements.txt is missing, do NOT attempt to use it.\n"
            "3. Look for alternatives: pyproject.toml, setup.py, or use 'pip install .' for Python projects.\n"
            "4. If the error mentions a missing file, CHECK if it's in the 'MISSING STANDARD FILES' list.\n"
            "5. Return ONLY the fixed Dockerfile content. No explanations, no markdown."
        )

        user_prompt = (
            f"=== PROJECT CONTEXT (SOURCE OF TRUTH) ===\n{project_context}\n\n"
            f"=== FAULTY DOCKERFILE ===\n{faulty_dockerfile}\n\n"
            f"=== DOCKER BUILD ERROR ===\n{error_log}\n\n"
            "Analyze the error and fix the Dockerfile. Remember: only use files that ACTUALLY EXIST. "
            "Return ONLY valid Dockerfile code."
        )

        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1
            )
            return self._clean_llm_output(response.choices[0].message.content)
        except Exception as e:
            return f"Error healing Dockerfile: {str(e)}"

    def heal_runtime(self, project_context, current_dockerfile, runtime_error_log):
        """Asks the LLM to fix a Dockerfile that builds but fails at runtime."""
        
        system_prompt = (
            "You are a Senior DevOps Engineer. A Docker image BUILT successfully, but FAILED when running.\n"
            "CRITICAL ANALYSIS REQUIRED:\n"
            "1. Determine if this is a LIBRARY (like Flask, Bottle, Django libs) or an APPLICATION.\n"
            "2. For LIBRARIES: The CMD should be a simple validation like 'python -c \"import X; print(X.__version__)\"'\n"
            "3. For APPLICATIONS: Fix the entry point (e.g., correct the path to main.py, add ENTRYPOINT).\n"
            "4. Common runtime errors:\n"
            "   - 'executable file not found' → Use full command: CMD [\"python\", \"script.py\"] not CMD [\"script.py\"]\n"
            "   - 'No application entry point specified' → Library project, use import test\n"
            "   - 'ModuleNotFoundError' → Missing dependency or wrong WORKDIR\n"
            "   - 'Permission denied' → Add executable permissions or fix user\n"
            "5. Return ONLY the fixed Dockerfile content. No explanations, no markdown, no preamble."
        )

        user_prompt = (
            f"=== PROJECT CONTEXT ===\n{project_context}\n\n"
            f"=== CURRENT DOCKERFILE (builds successfully) ===\n{current_dockerfile}\n\n"
            f"=== RUNTIME ERROR LOG ===\n{runtime_error_log}\n\n"
            "The image builds fine but crashes when running. Fix the CMD/ENTRYPOINT to make it work. "
            "Return ONLY valid Dockerfile code."
        )

        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1
            )
            return self._clean_llm_output(response.choices[0].message.content)
        except Exception as e:
            return f"Error healing runtime: {str(e)}"

## Feature 2 / Task 1
class DockerBuilder:
    def __init__(self):
        try:
            self.client = docker.from_env()
            self.client.ping()
        except Exception as e:
            raise Exception("Docker is not running. Please start Docker Desktop.")

    def build_image(self, path, tag="auto-docker-app:latest"):
        """Builds a docker image from the provided directory path."""
        print(f"Building image: {tag}...")
        
        try:
            image, build_logs = self.client.images.build(
                path=path,
                tag=tag,
                rm=True,      # Remove intermediate containers
                forcerm=True  # Always remove intermediate containers
            )
            
            # Print build logs to show progress
            for line in build_logs:
                if 'stream' in line:
                    print(line['stream'].strip())
            
            return image
        except docker.errors.BuildError as e:
            print("Build Failed!")
            # This log is crucial for our 'Self-Healing' feature later
            error_log = "".join([str(log) for log in e.build_log])
            raise Exception(f"Build Error: {error_log}")

    def test_run(self, image_tag, timeout=10):
        """Starts the container briefly to ensure it doesn't crash on boot."""
        print(f"Testing container stability for {timeout} seconds...")
        container = None
        try:
            # Run the container in detached mode
            container = self.client.containers.run(image_tag, detach=True)
            
            # Wait to see if it stays 'running'
            import time
            time.sleep(timeout)
            
            container.reload() # Refresh container status
            if container.status == "running":
                print("Container is stable and running.")
                return True
            else:
                logs = container.logs().decode("utf-8")
                raise Exception(f"Container stopped with status {container.status}. Logs: {logs}")
                
        except Exception as e:
            print(f"Runtime Validation Failed: {e}")
            raise e
        finally:
            if container:
                container.stop()
                container.remove()
