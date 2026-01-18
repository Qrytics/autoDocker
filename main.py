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
    
    # 5. Build the Image (Updated with Healing)
    image_tag = "auto-docker-test:latest"
    try:
        builder = DockerBuilder()
        image = builder.build_image(temp_path, tag=image_tag)
        print(f"Image built successfully! ID: {image.id}")
        
    except Exception as e:
        print(f"Initial build failed. Attempting to self-heal...")
        
        # --- SELF-HEALING START ---
        error_log = str(e)
        # Re-read the faulty dockerfile to send to LLM
        with open(dockerfile_path, "r") as f:
            faulty_content = f.read()
            
        fixed_content = architect.heal_dockerfile(context, faulty_content, error_log)
        
        print("Applying fix and retrying build...")
        with open(dockerfile_path, "w") as f:
            f.write(fixed_content)
            
        try:
            image = builder.build_image(temp_path, tag=image_tag)
            print(f"Healed! Image built successfully! ID: {image.id}")
        except Exception as retry_error:
            print(f"Healing failed. Manual intervention required: {retry_error}")
            return None
        # --- SELF-HEALING END ---
    
    # 6. Runtime Validation
    try:
        print("Running runtime validation tests...")
        success = builder.test_run(image_tag)
        if success:
            print("All checks passed! Your image is ready for production.")
            return image
    except Exception as runtime_err:
        print(f"Image builds, but fails to run: {runtime_err}")
        # Note: We could trigger a second 'Heal' loop here if we wanted!
        return None

if __name__ == "__main__":
    # Example usage (ensure you have your API key set in environment variables)
    # os.environ["GEMINI_API_KEY"] = "your-key-here"
    path = "my_project.zip" 
    if os.path.exists(path):
        run_auto_docker(path)
    else:
        print(f"File {path} not found. Please provide a valid zip.")
