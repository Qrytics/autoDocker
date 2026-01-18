# main.py
import argparse
import os
import sys
from core import WorkspaceManager, LLMArchitect, DockerBuilder

def cli_entry():
    parser = argparse.ArgumentParser(description="Auto-Docker CLI")
    parser.add_argument("source", help="Path to ZIP file OR GitHub URL")
    # ... other args ...
    args = parser.parse_args()
    
    # Logic to detect if source is a URL or a file
    if args.source.startswith("http"):
        # Handle GitHub logic
        pass 
    else:
        # Handle ZIP logic
        pass

def run_auto_docker(zip_path, model_name, tag, skip_test):
    print(f"\n{'='*50}")
    print(f"AUTO-DOCKER: {os.path.basename(zip_path)}")
    print(f"{'='*50}\n")
    
    if not os.path.exists(zip_path):
        print(f"Error: File '{zip_path}' not found.")
        return None
    
    # 1. Setup Workspace
    workspace = WorkspaceManager(zip_path)
    temp_path = workspace.setup()
    print(f"Unpacked to temporary directory: {temp_path}")
    
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
        
        print("Dockerfile generated and saved.")
        print("-" * 30)
        print(dockerfile_content)
        print("-" * 30)
        
    except Exception as e:
        print(f"Failed to generate Dockerfile: {e}")
        workspace.cleanup()
        return None
    
    # 5. Build the Image (with Self-Healing)
    builder = DockerBuilder()
    try:
        print(f"\nBuilding Docker image: {tag}")
        image = builder.build_image(temp_path, tag=tag)
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
            image = builder.build_image(temp_path, tag=tag)
            print(f"Healed! Image built successfully! ID: {image.id}")
        except Exception as retry_error:
            print(f"Healing failed. Manual intervention required: {retry_error}")
            print(f"Workspace preserved at: {temp_path}")
            return None
        # --- SELF-HEALING END ---
    
    # 6. Runtime Validation
    if not skip_test:
        try:
            print("\nRunning runtime validation tests...")
            success = builder.test_run(tag)
            if success:
                print("All checks passed! Your image is ready for production.")
        except Exception as runtime_err:
            print(f"Image builds, but fails to run: {runtime_err}")
            print(f"Workspace preserved at: {temp_path}")
            # Note: We could trigger a second 'Heal' loop here if we wanted!
            return None
    else:
        print("\nRuntime validation skipped (--skip-test flag used)")
    
    print(f"\nProject successfully containerized!")
    print(f"Docker Image: {tag}")
    print(f"Dockerfile Location: {temp_path}/Dockerfile")
    print(f"Workspace preserved at: {temp_path}")
    
    return image

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Auto-Docker: Intelligent Containerization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py my_project.zip
  python main.py my_project.zip --tag myapp:v1.0
  python main.py my_project.zip --model gemini/gemini-1.5-flash --skip-test
        """
    )
    
    parser.add_argument("zip", help="Path to the project ZIP file")
    parser.add_argument("--model", default="gemini/gemini-pro", 
                       help="LiteLLM model string (default: gemini/gemini-pro)")
    parser.add_argument("--tag", default="auto-docker-test:latest", 
                       help="Tag for the resulting Docker image (default: auto-docker-test:latest)")
    parser.add_argument("--skip-test", action="store_true", 
                       help="Skip the runtime stability test")
    
    args = parser.parse_args()
    
    result = run_auto_docker(args.zip, args.model, args.tag, args.skip_test)
    
    # Exit with appropriate code
    sys.exit(0 if result else 1)
