"""
Prompt templates for DoPilot multi-agent system.
All LLM prompts are centralized here for easy maintenance and optimization.
"""

from agent.states import Plan


def prompt_optimizer_prompt(user_prompt: str, is_first_batch: bool = True) -> str:
    """Generate clarifying questions for the user prompt."""
    if is_first_batch:
        return f"""You are an AI assistant helping to clarify user requirements for code generation.

User's project idea:
{user_prompt}

Generate EXACTLY 10 core clarifying questions to understand the project better.
Focus on:
1. Application type (web app, mobile, desktop, CLI, etc.)
2. Target deployment platform
3. Technology stack preferences
4. Database requirements
5. Authentication needs
6. UI/UX preferences
7. Third-party API integrations
8. Performance requirements
9. Target audience
10. Unique constraints or requirements

For each question:
- type: "choice" for single-choice, "multiple" for multi-select, "text" for open-ended
- options: Array of choices (for choice/multiple types), or empty array for text
- Include "Skip" option for optional questions

Return EXACTLY 10 questions."""
    else:
        return f"""Based on the user's project idea and their previous answers, generate 8 follow-up questions to refine unclear aspects.

User's project idea:
{user_prompt}

Focus on:
- Missing technical details
- Unclear feature specifications
- Ambiguous requirements
- Implementation details that need clarification

Return EXACTLY 8 questions in the same format."""


def planner_prompt(user_prompt: str) -> str:
    """Convert user requirements into a structured project plan."""
    PLANNER_PROMPT = f"""
You are the PLANNER agent. Convert the user prompt into a COMPLETE engineering project plan.

User request:
{user_prompt}

Generate a comprehensive plan with:
1. name: Project name in snake_case or kebab-case (e.g., "todo_app" or "weather-dashboard")
2. description: Clear 2-3 sentence description
3. features: List 3-8 specific features to implement
4. techstack: Specific technologies (e.g., "React, Express.js, MongoDB" or "HTML, CSS, JavaScript")
5. files: List ALL files needed for the project. For each file provide:
   - path: Relative file path (e.g., "src/index.js", "public/style.css", "package.json")
   - purpose: Brief description of file's role (e.g., "main entry point", "styling for UI", "project dependencies")
   Include ALL necessary files: source code, config files, HTML, CSS, package.json, etc.
6. dependencies: List required packages/libraries (npm packages, Python packages, etc.)

CRITICAL: The files list must include EVERY file needed to build the complete working application.
For a web app, include: HTML files, JavaScript files, CSS files, package.json, config files, etc.
For a Python app, include: main script, helper modules, requirements.txt, config files, etc.

Make the plan specific, actionable, and production-ready.
    """
    return PLANNER_PROMPT


def architect_prompt(plan: Plan) -> str:
    """Convert Plan into detailed TaskPlan with file-by-file implementation steps."""
    # Convert Plan object to string representation for prompt
    files_str = "\n".join(f"- {file.path}: {file.purpose}" for file in plan.files)
    
    plan_str = f"""
Project: {plan.name}
Description: {plan.description}
Tech Stack: {plan.techstack}
Features:
{chr(10).join(f"- {f}" for f in plan.features)}
Files to Create:
{files_str}
Dependencies:
{chr(10).join(f"- {d}" for d in plan.dependencies)}
"""
    
    ARCHITECT_PROMPT = f"""
You are the ARCHITECT agent. Given this project plan, break it down into explicit engineering tasks.

CRITICAL RULE: You MUST create an implementation task for EVERY file listed in "Files to Create" section.

RULES:
- For EACH file in the "Files to Create" list, create EXACTLY ONE ImplementationTask
- In each task description:
    * Specify exactly what to implement in that specific file
    * Name the variables, functions, classes, and components to be defined
    * Mention how this file depends on or will be used by other files
    * Include integration details: imports, expected function signatures, data flow
- Order tasks so that dependencies are implemented first (e.g., package.json before code files)
- Each task must be SELF-CONTAINED with complete implementation details

Project Plan:
{plan_str}

Create a TaskPlan with implementation_steps array containing one task per file.
For each task:
1. filepath: EXACT path from the "Files to Create" list above
2. task_description: Detailed implementation instructions for this specific file

CRITICAL: The number of implementation_steps MUST EQUAL the number of files in the plan.
Do not skip any files. Do not combine multiple files into one task.
    """
    return ARCHITECT_PROMPT


def security_prompt(security_scan: dict, files_content: str) -> str:
    """Validate code security and provide fixes for vulnerabilities."""
    issues_text = "\n".join([
        f"- {issue['file']} (line {issue['line']}): [{issue['severity']}] {issue['issue']}"
        for issue in security_scan['issues'][:10]
    ])
    
    return f"""You are a security expert. Analyze the following code for security vulnerabilities.

Security scan found {security_scan['total_issues']} issues:
{issues_text}

Project files:
{files_content}

For each issue, provide:
1. file: Exact filepath
2. line: Line number
3. severity: "high", "medium", or "low"
4. issue: Clear description of the vulnerability
5. fix: Specific fix to apply

Focus on:
- Hardcoded credentials, API keys, secrets
- SQL injection vulnerabilities
- XSS vulnerabilities
- Insecure file operations
- Missing input validation

Return a SecurityValidation with:
- passed: false (since issues were found)
- issues: Array of SecurityIssue objects (maximum 5 most critical)
- recommendations: Array of general security best practices"""


def coder_system_prompt() -> str:
    """System prompt for the coder agent."""
    CODER_SYSTEM_PROMPT = """
You are the CODER agent.
You are implementing a specific engineering task.
You have access to tools to read and write files.

Always:
- Review all existing files to maintain compatibility.
- Implement the FULL file content, integrating with other modules.
- Maintain consistent naming of variables, functions, and imports.
- When a module is imported from another file, ensure it exists and is implemented as described.
    """
    return CODER_SYSTEM_PROMPT


def final_prompt_enhancer(user_prompt: str, answers: dict) -> str:
    """Enhance user prompt with AI analysis based on answered questions. MUST stay under 3000 characters."""
    answers_text = "\n".join([f"- {q}: {a}" for q, a in answers.items()])
    
    return f"""You are a technical specification expert. Enhance this project specification to be comprehensive and unambiguous.

Original idea:
{user_prompt}

User's clarifications:
{answers_text}

Create an enhanced specification that:
1. Clearly defines the application type and purpose
2. Specifies exact technology stack
3. Lists all features with implementation details
4. Defines data requirements and structure
5. Specifies authentication/authorization if needed
6. Clarifies UI/UX requirements
7. Notes any integrations or third-party services
8. Includes deployment target

CRITICAL: Your response MUST be under 3000 characters.
Be specific, technical, and actionable. Remove fluff and focus on concrete requirements.
Use bullet points for clarity."""
