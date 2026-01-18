# main.py
import os
from core import WorkspaceManager, LLMArchitect, DockerBuilder

def run_auto_docker(zip_path, model_name="gemini/gemini-pro"):
    print(f"Starting Auto-Docker for: {zip_path}")
    
    # 1. Setup Workspace
    workspace = WorkspaceManager(zip_path)
    temp_path = workspace.setup()
    print(f"📂 Unpacked to temporary directory: {temp_path}")
    
    try:
        # 2. Extract Context
        context = workspace.get_context_for_llm()
        
        # 3. Consult the Architect (LLM)
        architect = LLMArchitect(model=model_name)
        print("Analyzing project structure and generating Dockerfile...")
        dockerfile_content = architect.generate_dockerfile(context)
        
        # 4. Write the Dockerfile to the temp directory
        dockerfile_path = os.path.join(temp_path, "Dockerfile")
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content)
        
        print("Success! Dockerfile generated and saved.")
        print("-" * 30)
        print(dockerfile_content)
        print("-" * 30)
        
    except Exception as e:
        print(f"Failed to generate Dockerfile: {e}")
        workspace.cleanup()
        return None
    
    # 5. Build the Image
    try:
        builder = DockerBuilder()
        image = builder.build_image(temp_path, tag="auto-docker-test:latest")
        print(f"Image built successfully! ID: {image.id}")
        
        # 6. Cleanup (Optional: keep if you want to inspect files)
        # workspace.cleanup() 
        
        return image
    except Exception as e:
        print(f"Build process failed: {e}")
        # Note: We'll use this error in Feature 3 for self-healing
        return None

if __name__ == "__main__":
    # Example usage (ensure you have your API key set in environment variables)
    # os.environ["GEMINI_API_KEY"] = "your-key-here"
    path = "my_project.zip" 
    if os.path.exists(path):
        run_auto_docker(path)
    else:
        print(f"File {path} not found. Please provide a valid zip.")
