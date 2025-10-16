"""
Pydantic models for state management in DoPilot.
Defines all data structures used across the multi-agent workflow.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ===== ORIGINAL CORE CLASSES =====

class File(BaseModel):
    """File metadata for project planning."""
    path: str = Field(description="The path to the file to be created or modified")
    purpose: str = Field(description="The purpose of the file, e.g. 'main application logic', 'data processing module', etc.")


class Plan(BaseModel):
    """High-level project plan with name, description, features, and tech stack."""
    name: str = Field(description="The name of app to be built")
    description: str = Field(description="A oneline description of the app to be built, e.g. 'A web application for managing personal finances'")
    techstack: str = Field(description="The tech stack to be used for the app, e.g. 'python', 'javascript', 'react', 'flask', etc.")
    features: list[str] = Field(description="A list of features that the app should have, e.g. 'user authentication', 'data visualization', etc.")
    files: list[File] = Field(description="A list of files to be created, each with a 'path' and 'purpose'")
    dependencies: list[str] = Field(default_factory=list, description="List of dependencies/packages needed")


class ImplementationTask(BaseModel):
    """Single file implementation task."""
    filepath: str = Field(description="The path to the file to be modified")
    task_description: str = Field(description="A detailed description of the task to be performed on the file, e.g. 'add user authentication', 'implement data processing logic', etc.")


class TaskPlan(BaseModel):
    """Detailed file-by-file implementation plan."""
    implementation_steps: list[ImplementationTask] = Field(description="A list of steps to be taken to implement the task")


class CoderState(BaseModel):
    """State tracking for the coder agent."""
    task_plan: TaskPlan = Field(description="The plan for the task to be implemented")
    current_step_idx: int = Field(0, description="The index of the current step in the implementation steps")
    current_file_content: Optional[str] = Field(None, description="The content of the file currently being edited or created")
    retry_attempts: int = Field(0, description="Number of retry attempts for the current file")


# ===== PROMPT OPTIMIZER CLASSES =====

class Question(BaseModel):
    """A single clarifying question for the user."""
    question: str = Field(description="The clarifying question to ask the user")
    type: str = Field(description="Type of question: 'choice', 'multiple', or 'text'")
    options: list[str] = Field(default_factory=list, description="Available options for choice/multiple type questions")


class PromptOptimization(BaseModel):
    """Result of prompt optimizer agent."""
    questions: list[Question] = Field(description="List of clarifying questions to ask the user")
    optimized_prompt: Optional[str] = Field(None, description="The optimized prompt after receiving answers")


# ===== SECURITY VALIDATION CLASSES =====

class SecurityIssue(BaseModel):
    """A single security vulnerability found in code."""
    file: str = Field(description="File path where issue was found")
    line: int = Field(description="Line number of the issue")
    severity: str = Field(description="Severity level: 'high', 'medium', or 'low'")
    issue: str = Field(description="Description of the security issue")
    fix: str = Field(description="Recommended fix for the issue")


class SecurityValidation(BaseModel):
    """Result of security validation."""
    passed: bool = Field(description="Whether security scan passed")
    issues: list[SecurityIssue] = Field(default_factory=list, description="List of security issues found")
    recommendations: list[str] = Field(default_factory=list, description="General security recommendations")
