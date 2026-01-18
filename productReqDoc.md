Vision: A zero-config CLI tool that transforms any application source code (ZIP) into a production-hardened, multi-stage, distroless Docker image using LLM-driven intent recognition.

## 1. Core Objectives
Zero-Knowledge Requirement: The user should not need to know how to write a Dockerfile.

Security by Default: Every image must use Alpine or Distroless bases.

Optimization by Default: Every build must use multi-stage layering.

Self-Healing: If a build fails, the tool should attempt to fix the Dockerfile using the error logs.

## 2. Target Features (The "Ralph" Loop Roadmap)
Feature 1: The Analyzer & Architect. Unpacking the ZIP, scanning the file tree, and using an LLM to generate the optimized Dockerfile.

Feature 2: The Builder. Interfacing with the Docker Engine API to execute the build.

Feature 3: The Validator. Running the container locally to ensure it doesn't "crash-loop" and checking image size/security.

## 3. Technical Stack
Language: Python 3.10+

Orchestration: Docker SDK for Python.

Intelligence: OpenAI / Gemini API (for Dockerfile generation).

Processing: zipfile and tempfile for ephemeral workspace management.
