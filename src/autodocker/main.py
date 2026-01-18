# main.py
import argparse
import os
import sys
import colorama
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.syntax import Syntax
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
        status.update("[bold yellow]Unpacking source...")
        workspace = WorkspaceManager(source)
        temp_path = workspace.setup()
        console.print(f"[green]Unpacked to:[/green] [dim]{temp_path}[/dim]")
        
        try:
            # 2. Extract Context
            status.update("[bold yellow]Extracting project context...")
            context = workspace.get_context_for_llm()
            console.print("[green]Context extracted[/green] ")
            
            # 3. Consult the Architect (LLM)
            status.update(f"[bold blue]Architecting via {model_name}...")
            architect = LLMArchitect(model=model_name)
            dockerfile_content = architect.generate_dockerfile(context)
            
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
                
            fixed_content = architect.heal_dockerfile(context, faulty_content, error_log)
            
            with open(dockerfile_path, "w") as f:
                f.write(fixed_content)
            
            console.print("[yellow]→[/yellow] Applied fix, retrying build...")
            
            try:
                status.update(f"[bold magenta]Rebuilding Docker image: {tag}...")
                image = builder.build_image(temp_path, tag=tag)
                console.print(f"[green]Healed![/green] Image built successfully! [dim]ID: {image.id[:12]}[/dim]")
            except Exception as retry_error:
                console.print(f"[bold red]Healing failed:[/bold red] {retry_error}")
                console.print(f"[dim]Workspace preserved at: {temp_path}[/dim]")
                return None
            # --- SELF-HEALING END ---
        
        # 6. Runtime Validation
        if not skip_test:
            try:
                status.update("[bold cyan]Running runtime validation tests...")
                success = builder.test_run(tag)
                if success:
                    console.print("[green]All runtime checks passed![/green]")
            except Exception as runtime_err:
                console.print(f"[yellow]Image builds, but fails to run:[/yellow] {runtime_err}")
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
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Positional argument
    parser.add_argument("source", help="Path to a .zip file or a public GitHub URL")

    # Configuration options group
    group = parser.add_argument_group("Configuration Options")
    group.add_argument("--model", default="gemini/gemini-pro", 
                      help="LiteLLM model (default: gemini/gemini-pro)")
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
