import os
import zipfile
import tempfile
import shutil
import os
import docker
from pathlib import Path
from litellm import completion

## Feature 1 / Task 1
class WorkspaceManager:
    def __init__(self, zip_path):
        self.zip_path = zip_path
        self.temp_dir = None
        self.file_map = []

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
        
        self.file_map = "\n".join(lines)

    def get_context_for_llm(self):
        """Returns the file map and content of key manifest files."""
        context = f"Project Structure:\n{self.file_map}\n\n"
        
        # Identify key files that define the tech stack
        manifests = ['package.json', 'requirements.txt', 'go.mod', 'pom.xml', 'main.py', 'app.py', 'index.js']
        
        context += "Key File Contents:\n"
        for root, _, files in os.walk(self.temp_dir):
            for f in files:
                if f in manifests:
                    file_path = os.path.join(root, f)
                    with open(file_path, 'r', errors='ignore') as content:
                        context += f"--- {f} ---\n{content.read(1000)}\n" # Read first 1000 chars
        
        return context

    def cleanup(self):
        """Deletes the temporary workspace."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

## Feature 1 / Task 2
class LLMArchitect:
    def __init__(self, model="gemini/gemini-pro"): # Defaulting to Gemini, but LiteLLM handles any
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
            "5. Return ONLY the content of the Dockerfile. No markdown code blocks, no explanations."
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
        return text.replace("```dockerfile", "").replace("```", "").strip()

## Feature 2 / Task 1
class DockerBuilder:
    def __init__(self):
        try:
            self.client = docker.from_env()
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
