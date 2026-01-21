# main.py
import argparse
import os
import sys
import time
import colorama
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.syntax import Syntax
from rich_argparse import RichHelpFormatter
from .core import WorkspaceManager, LLMArchitect, DockerBuilder

console = Console()

def run_auto_docker(source, model_name, tag, skip_test):
    """Main containerization logic with rich output."""
    
    # Validate source exists
    if not source.startswith("http") and not os.path.exists(source):
        console.print(f"[bold red]Error:[/bold red] File '{source}' not found.")
        return None
    
    with console.status("[bold green]Working...") as status:
        
        # 1. Setup Workspace
        workspace = WorkspaceManager(source)
        if source.startswith("http"):
            status.update(f"[bold yellow]Cloning repository from GitHub...")
            temp_path = workspace.setup_from_github(source) # Call our new Git method
        else:
            status.update("[bold yellow]Unpacking local zip file...")
            temp_path = workspace.setup() # Call the original Zip method
            
        console.print(f"[green]Workspace ready at:[/green] [dim]{temp_path}[/dim]")
        
        try:
            # 2. Extract Context
            status.update("[bold yellow]Extracting project context...")
            context = workspace.get_context_for_llm()
            console.print("[green]Context extracted[/green] ")
            
            # 3. Consult the Architect (LLM)
            status.update(f"[bold blue]Architecting via {model_name}...")
            architect = LLMArchitect(model=model_name)
            dockerfile_content = architect.generate_dockerfile(context)

            if "RateLimitError" in dockerfile_content or "AuthenticationError" in dockerfile_content:
                console.print("[bold red]LLM Provider Error:[/bold red] You are being rate limited. Please wait 60 seconds.")
                return None

            if "AuthenticationError" in dockerfile_content or "API key not valid" in dockerfile_content:
                console.print("[bold red]LLM Auth Failed:[/bold red] Check your GROQ_API_KEY.")
                return None
            
            # 4. Write the Dockerfile
            dockerfile_path = os.path.join(temp_path, "Dockerfile")
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)
            
            console.print("[green]Dockerfile generated[/green]")
            
            # Display the Dockerfile with syntax highlighting
            console.print("\n[bold cyan]Generated Dockerfile:[/bold cyan]")
            syntax = Syntax(dockerfile_content, "dockerfile", theme="ansi_dark", line_numbers=True)
            console.print(syntax)
            
        except Exception as e:
            console.print(f"[bold red]Failed to generate Dockerfile:[/bold red] {e}")
            workspace.cleanup()
            return None
        
        # 5. Build the Image (with Self-Healing)
        builder = DockerBuilder()
        try:
            status.update(f"[bold magenta]Building Docker image: {tag} (this may take a minute)...")
            image = builder.build_image(temp_path, tag=tag)
            console.print(f"[green]Image built successfully![/green] [dim]ID: {image.id[:12]}[/dim]")
            
        except Exception as e:
            console.print(f"[yellow]Initial build failed. Attempting to self-heal...[/yellow]")
            
            # --- SELF-HEALING START ---
            status.update("[bold yellow]Self-healing Dockerfile...")
            error_log = str(e)
            
            with open(dockerfile_path, "r") as f:
                faulty_content = f.read()
                
            try:
                fixed_content = architect.heal_dockerfile(context, faulty_content, error_log)
                
                # Validate the fixed content
                if not fixed_content or "Error" in fixed_content[:50]:
                    console.print(f"[bold red]Healing produced invalid output:[/bold red] {fixed_content[:100]}")
                    console.print(f"[dim]Workspace preserved at: {temp_path}[/dim]")
                    return None
                
                with open(dockerfile_path, "w") as f:
                    f.write(fixed_content)
                
                console.print("[yellow]→[/yellow] Applied fix, retrying build...")
                
                status.update(f"[bold magenta]Rebuilding Docker image: {tag}...")
                image = builder.build_image(temp_path, tag=tag)
                console.print(f"[green]Healed![/green] Image built successfully! [dim]ID: {image.id[:12]}[/dim]")
                
            except Exception as retry_error:
                console.print(f"[bold red]Healing failed:[/bold red] {retry_error}")
                console.print(f"[dim]Workspace preserved at: {temp_path}[/dim]")
                return None
            # --- SELF-HEALING END ---
        
        # 6. Runtime Validation (w/ healing)
        if not skip_test:
            try:
                status.update("[bold cyan]Running runtime validation tests...")
                success = builder.test_run(tag)
                if success:
                    console.print("[green]All runtime checks passed![/green]")
            except Exception as runtime_err:
                runtime_log = str(runtime_err)
                console.print(f"[yellow]Runtime failed:[/yellow] {runtime_log[:150]}")
                console.print(f"[yellow]Attempting runtime healing...[/yellow]")
                
                status.update("[bold yellow]Healing runtime configuration...")
                
                with open(dockerfile_path, "r") as f:
                    current_dockerfile = f.read()

                try:
                    fixed_runtime_content = architect.heal_runtime(
                        context, 
                        current_dockerfile, 
                        runtime_log
                    )
                    
                    # Validate the fixed content
                    if not fixed_runtime_content or "Error" in fixed_runtime_content[:50]:
                        console.print(f"[bold red]Runtime healing produced invalid output:[/bold red] {fixed_runtime_content[:100]}")
                        console.print(f"[dim]Workspace preserved at: {temp_path}[/dim]")
                        return None
                    
                    # Write the fixed Dockerfile
                    with open(dockerfile_path, "w") as f:
                        f.write(fixed_runtime_content)
                    
                    console.print("[yellow]→[/yellow] Applied runtime fix, rebuilding...")
                    
                    # Show the fixed Dockerfile
                    console.print("\n[bold cyan]Fixed Dockerfile:[/bold cyan]")
                    syntax = Syntax(fixed_runtime_content, "dockerfile", theme="ansi_dark", line_numbers=True)
                    console.print(syntax)
                    
                    # Rebuild with the fixed Dockerfile
                    status.update(f"[bold magenta]Rebuilding with runtime fix: {tag}...")
                    image = builder.build_image(temp_path, tag=tag)
                    console.print(f"[green]Rebuilt successfully![/green] [dim]ID: {image.id[:12]}[/dim]")
                    
                    # Test again
                    status.update("[bold cyan]Retesting runtime...")
                    success = builder.test_run(tag)
                    if success:
                        console.print("[green]Runtime healing successful! Container is stable.[/green]")
                    else:
                        console.print("[yellow]Runtime still unstable after healing.[/yellow]")
                        console.print(f"[dim]Workspace preserved at: {temp_path}[/dim]")
                        return None
                        
                except Exception as final_error:
                    console.print(f"[bold red]Runtime healing failed:[/bold red] {final_error}")
                    console.print(f"[dim]Workspace preserved at: {temp_path}[/dim]")
                    return None
        else:
            console.print("[dim]Runtime validation skipped (--skip-test flag)[/dim]")
    
    workspace_name = os.path.basename(temp_path)
    
    # Success summary
    console.print("\n" + "="*60)
    console.print(Panel.fit(
        f"[bold green]Project Successfully Containerized![/bold green]\n\n"
        f"[cyan]Docker Image:[/cyan] {tag}\n"
        f"[cyan]Dockerfile:[/cyan] {workspace_name}/Dockerfile\n"
        f"[cyan]Workspace:[/cyan] {workspace_name}\n"
        f"[dim](Full path: {temp_path})[/dim]",
        border_style="green",
        title="Success"
    ))
    
    return image


def cli_entry():
    """CLI entry point with enhanced argument parsing."""
    colorama.init()
    parser = argparse.ArgumentParser(
        prog="autodocker",
        description="[bold cyan]Auto-Docker[/bold cyan]: Intelligent Containerization",
        epilog="Example: autodocker ./my_project.zip --tag web-app:v1",
        formatter_class=RichHelpFormatter
    )
    
    # Positional argument
    parser.add_argument("source", help="Path to a .zip file or a public GitHub URL")

    # Configuration options group
    group = parser.add_argument_group("Configuration Options")
    group.add_argument("--model", default="groq/llama-3.1-8b-instant", 
                  help="LiteLLM model (default: groq/llama-3.1-8b-instant)")
    group.add_argument("--tag", default="auto-docker-test:latest", 
                      help="Docker image tag (default: auto-docker-test:latest)")
    group.add_argument("--skip-test", action="store_true", 
                      help="Skip runtime stability check")

    args = parser.parse_args()

    # Welcome header
    console.print(Panel.fit(
        "[bold green]Welcome to Auto-Docker[/bold green] v0.1.0\n"
        "[dim]Automatically architecting your containers...[/dim]",
        border_style="cyan"
    ))

    # Run the main logic
    result = run_auto_docker(args.source, args.model, args.tag, args.skip_test)
    
    # Exit with appropriate code
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    cli_entry()
