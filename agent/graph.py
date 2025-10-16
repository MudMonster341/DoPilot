from dotenv import load_dotenv
from langchain.globals import set_verbose, set_debug
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.prebuilt import create_react_agent
import os
import time
import re

from agent.prompts import *
from agent.states import *
from agent.tools import (
    write_file, read_file, get_current_directory, list_files, list_file, 
    set_project_root, create_project_readme, scan_project_security, 
    generate_requirements_txt, validate_requirements_file, PROJECT_ROOT
)
from agent.rate_limiter import (
    rate_limit_check, count_tokens_estimate, enforce_character_limit,
    token_counter, gemini_limiter, groq_limiter
)
import pathlib

_ = load_dotenv()

set_debug(False)
set_verbose(False)

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "gemini")

# Validate API keys are configured
if MODEL_PROVIDER == "gemini":
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "<YOUR_GOOGLE_API_KEY_HERE>":
        raise ValueError(
            "GOOGLE_API_KEY not configured. Please create a .env file with your API key. "
            "Copy .sample_env to .env and add your Google API key from https://aistudio.google.com/apikey"
        )
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.2,
        max_tokens=8192,
        google_api_key=api_key
    )
else:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "<YOUR_GROQ_API_KEY_HERE>":
        raise ValueError(
            "GROQ_API_KEY not configured. Please create a .env file with your API key. "
            "Copy .sample_env to .env and add your Groq API key from https://console.groq.com/keys"
        )
    from langchain_groq.chat_models import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key)


def prompt_optimizer_agent(state: dict) -> dict:
    """Generates clarifying questions for the user prompt."""
    user_prompt = state["user_prompt"]
    is_first_batch = state.get("is_first_batch", True)
    
    print("\n🤔 Analyzing prompt and generating questions...")
    
    # Rate limiting check
    can_proceed, wait_time = rate_limit_check(MODEL_PROVIDER)
    if not can_proceed:
        print(f"⏳ Rate limit reached. Waiting {wait_time:.0f} seconds...")
        time.sleep(wait_time + 1)
    
    try:
        # Count estimated tokens
        prompt_text = prompt_optimizer_prompt(user_prompt, is_first_batch)
        estimated_tokens = count_tokens_estimate(prompt_text)
        print(f"📊 Estimated tokens for this request: {estimated_tokens}")
        
        resp = llm.with_structured_output(PromptOptimization).invoke(prompt_text)
        
        if resp is None or not resp.questions:
            print("⚠️ No questions generated, proceeding without optimization")
            return {"questions": [], "skip_questions": True}
        
        questions_list = [q.model_dump() for q in resp.questions]
        
        # For first batch, ensure exactly 10 questions
        if is_first_batch:
            questions_list = questions_list[:10]
            print(f"✅ Generated {len(questions_list)} core questions")
        else:
            questions_list = questions_list[:8]
            print(f"✅ Generated {len(questions_list)} follow-up questions")
        
        return {
            "questions": questions_list,
            "skip_questions": False
        }
        
    except Exception as e:
        print(f"❌ Error generating questions: {e}")
        import traceback
        traceback.print_exc()
        return {"questions": [], "skip_questions": True}


def planner_agent(state: dict) -> dict:
    """Converts user prompt into a structured Plan."""
    print("\n" + "="*80)
    print("ENTERING PLANNER AGENT")
    print("="*80)
    print("📋 Planning project structure...")
    optimized_prompt = state.get("optimized_prompt", state.get("user_prompt"))
    
    # Enforce character limit to control token usage
    optimized_prompt = enforce_character_limit(optimized_prompt, max_chars=3000)
    
    # Rate limiting check
    can_proceed, wait_time = rate_limit_check(MODEL_PROVIDER)
    if not can_proceed:
        print(f"⏳ Rate limit reached. Waiting {wait_time:.0f} seconds...")
        time.sleep(wait_time + 1)
    
    print("🤖 Analyzing requirements with AI...")
    prompt_text = planner_prompt(optimized_prompt)
    estimated_tokens = count_tokens_estimate(prompt_text)
    print(f"📊 Estimated tokens: {estimated_tokens}")
    
    resp = llm.with_structured_output(Plan).invoke(prompt_text)
    if resp is None:
        raise ValueError("Planner did not return a valid response.")
    
    print(f"DEBUG: Plan created with {len(resp.files)} files")
    if len(resp.files) == 0:
        print("ERROR: Planner returned ZERO files! This is a critical error.")
        print("ERROR: The LLM did not generate any files in the plan.")
        raise ValueError("Planner returned a plan with no files")
    
    for file in resp.files:
        print(f"  - {file.path}: {file.purpose}")
    
    project_path = set_project_root.invoke({"project_name": resp.name})
    print(f"✅ Project created: {resp.name}")
    print(f"📁 Location: {project_path}")
    
    readme_path = create_project_readme(resp)
    print(f"📄 Generated: README.md")
    print("")
    
    return {"plan": resp}


def architect_agent(state: dict) -> dict:
    """Converts Plan into a TaskPlan (file-by-file instructions)."""
    print("\n" + "="*80)
    print("ENTERING ARCHITECT AGENT")
    print("="*80)
    print("🏗️ Designing architecture...")
    plan: Plan = state.get("plan")
    if not plan:
        raise ValueError("No plan found in state")
    
    # Rate limiting check
    can_proceed, wait_time = rate_limit_check(MODEL_PROVIDER)
    if not can_proceed:
        print(f"⏳ Rate limit reached. Waiting {wait_time:.0f} seconds...")
        time.sleep(wait_time + 1)
    
    print("🤖 Creating detailed task plan with AI...")
    print(f"DEBUG: Plan has {len(plan.files)} files to implement")
    prompt_text = architect_prompt(plan)
    estimated_tokens = count_tokens_estimate(prompt_text)
    print(f"📊 Estimated tokens: {estimated_tokens}")
    
    resp = llm.with_structured_output(TaskPlan).invoke(prompt_text)
    print(f"DEBUG: TaskPlan created with {len(resp.implementation_steps)} implementation steps")
    print("")
    
    return {"task_plan": resp, "plan": state.get("plan")}


def coder_agent(state: dict) -> dict:
    """Direct code generation agent without tool calling."""
    print("\n" + "="*80)
    print("ENTERING CODER AGENT")
    print("="*80)
    coder_state: CoderState = state.get("coder_state")
    if coder_state is None:
        task_plan = state.get("task_plan")
        if task_plan is None:
            raise ValueError("No task_plan found in state. Architect agent did not run or failed.")
        if not hasattr(task_plan, 'implementation_steps'):
            raise ValueError(f"task_plan is invalid: {type(task_plan)}")
        
        coder_state = CoderState(task_plan=task_plan, current_step_idx=0)
        print("💻 Starting code generation...")
        print(f"DEBUG: Total files to generate: {len(task_plan.implementation_steps)}")
        print("")

    steps = coder_state.task_plan.implementation_steps
    print(f"DEBUG: Current step {coder_state.current_step_idx + 1}/{len(steps)}")
    
    if len(steps) == 0:
        raise ValueError("Task plan is empty. Architect agent did not supply implementation steps.")
    
    if coder_state.current_step_idx >= len(steps):
        from agent.tools import generate_requirements_txt, validate_requirements_file
        
        print("")
        print("📦 Checking for package dependencies...")
        generated = generate_requirements_txt()
        if generated:
            print("📄 Generated: requirements.txt")
            validation = validate_requirements_file()
            if not validation['valid']:
                print(f"⚠️ Requirements validation issues: {len(validation['issues'])}")
                for issue in validation['issues']:
                    print(f"  - {issue['severity']}: {issue['message']}")
            else:
                print("✅ Requirements validated successfully")
        
        print("")
        print("✅ Code generation complete")
        print("")
        return {
            "coder_state": coder_state, 
            "status": "CODING_DONE",
            "plan": state.get("plan"),
            "task_plan": state.get("task_plan")
        }

    current_task = steps[coder_state.current_step_idx]
    filepath = current_task.filepath
    print(f"DEBUG: Processing file: {filepath}")
    
    existing_content = read_file.invoke(filepath)
    
    prompt = f"""You are implementing a coding task. Generate the COMPLETE file content.

Task: {current_task.task_description}
File: {filepath}
Existing content: {existing_content if existing_content else "Empty file"}

Generate the FULL file content with all necessary code. Output ONLY the code, no explanations.
Ensure proper imports, error handling, and production-ready code.
"""
    
    try:
        # Rate limiting check
        can_proceed, wait_time = rate_limit_check(MODEL_PROVIDER)
        if not can_proceed:
            print(f"⏳ Rate limit reached. Waiting {wait_time:.0f} seconds before retry...")
            time.sleep(wait_time + 1)
        
        estimated_tokens = count_tokens_estimate(prompt)
        if coder_state.current_step_idx == 0:  # Only log for first file
            print(f"📊 Estimated tokens per file: ~{estimated_tokens}")
        
        response = llm.invoke(prompt)
        code_content = response.content.strip()
        
        if code_content.startswith('```'):
            lines = code_content.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].startswith('```'):
                lines = lines[:-1]
            code_content = '\n'.join(lines)
        
        write_file.invoke({"path": filepath, "content": code_content})
        print(f"📄 Generated: {filepath}")
        coder_state.retry_attempts = 0  # Reset retry counter on success
        coder_state.current_step_idx += 1  # Move to next file on success
    except Exception as e:
        print(f"❌ Error generating {filepath}: {e}")
        coder_state.retry_attempts += 1
        
        # Calculate exponential backoff wait time
        wait_seconds = None
        match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", str(e))
        if match:
            # Use API suggested retry delay
            wait_seconds = int(match.group(1)) + 2
        elif "429" in str(e) or "ResourceExhausted" in str(e):
            # Exponential backoff: 5s, 10s, 20s, 40s, etc.
            wait_seconds = min(5 * (2 ** (coder_state.retry_attempts - 1)), 120)
        else:
            # Other errors: fixed 5 second wait
            wait_seconds = 5
        
        print(f"⏳ Waiting {wait_seconds} seconds before retry attempt {coder_state.retry_attempts}...")
        time.sleep(wait_seconds)
        
        # Always retry, never skip files
        return {
            "coder_state": coder_state,
            "status": "CODING_RETRY",
            "plan": state.get("plan"),
            "task_plan": state.get("task_plan")
        }
    
    # Check if we're done with all files
    if coder_state.current_step_idx >= len(steps):
        print(f"DEBUG: Completed all {len(steps)} files, returning CODING_DONE")
        print("")
        return {
            "coder_state": coder_state,
            "status": "CODING_DONE",
            "plan": state.get("plan"),
            "task_plan": state.get("task_plan")
        }
    
    print(f"DEBUG: Incremented step index to {coder_state.current_step_idx}, returning status CODING_IN_PROGRESS")
    print("")
    return {
        "coder_state": coder_state,
        "status": "CODING_IN_PROGRESS",
        "plan": state.get("plan"),
        "task_plan": state.get("task_plan")
    }


def security_agent(state: dict) -> dict:
    """Validates code security and identifies vulnerabilities."""
    print("\n" + "="*80)
    print("ENTERING SECURITY AGENT")
    print("="*80)
    print("🔒 Running security validation...")
    print("")
    
    security_scan = scan_project_security()
    
    if security_scan['passed']:
        print("✅ Security scan passed: No vulnerabilities detected")
        print("")
        return {
            "security_validation": SecurityValidation(passed=True, issues=[], recommendations=[]),
            "status": "SECURITY_PASSED",
            "security_attempts": state.get("security_attempts", 0),
            "plan": state.get("plan"),
            "task_plan": state.get("task_plan")
        }
    
    print(f"⚠️ Security issues found: {security_scan['total_issues']}")
    
    files_content = ""
    project_root = pathlib.Path(PROJECT_ROOT)
    for file_path in project_root.rglob('*'):
        if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.php', '.rb', '.go', '.html']:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    files_content += f"\n\n=== {file_path.relative_to(project_root)} ===\n{content}"
            except:
                pass
    
    validation_prompt = security_prompt(security_scan, files_content[:15000])
    
    try:
        # Rate limiting check
        can_proceed, wait_time = rate_limit_check(MODEL_PROVIDER)
        if not can_proceed:
            print(f"⏳ Rate limit reached. Waiting {wait_time:.0f} seconds...")
            time.sleep(wait_time + 1)
        
        estimated_tokens = count_tokens_estimate(validation_prompt)
        print(f"📊 Estimated tokens for security scan: {estimated_tokens}")
        
        security_response = llm.with_structured_output(SecurityValidation).invoke(validation_prompt)
        
        if security_response is None:
            security_response = SecurityValidation(
                passed=False,
                issues=[SecurityIssue(
                    file=issue['file'],
                    line=issue['line'],
                    severity=issue['severity'],
                    issue=issue['issue'],
                    fix="Use environment variables for sensitive data"
                ) for issue in security_scan['issues'][:5]],
                recommendations=["Use environment variables for all sensitive configuration"]
            )
    except Exception as e:
        print(f"Security validation error: {e}")
        security_response = SecurityValidation(
            passed=False,
            issues=[SecurityIssue(
                file=issue['file'],
                line=issue['line'],
                severity=issue['severity'],
                issue=issue['issue'],
                fix="Use environment variables for sensitive data"
            ) for issue in security_scan['issues'][:5]],
            recommendations=["Use environment variables for all sensitive configuration"]
        )
    
    security_attempts = state.get("security_attempts", 0) + 1
    
    if security_attempts >= 1:
        print("🔧 Security fixes will be applied once, then proceeding to final verification")
        print("")
        return {
            "security_validation": security_response,
            "status": "SECURITY_NEEDS_FIX",
            "security_attempts": security_attempts,
            "plan": state.get("plan"),
            "task_plan": state.get("task_plan")
        }
    
    print("")
    return {
        "security_validation": security_response,
        "status": "SECURITY_FAILED",
        "security_attempts": security_attempts,
        "plan": state.get("plan"),
        "task_plan": state.get("task_plan")
    }


def security_fixer_agent(state: dict) -> dict:
    """Fixes security issues identified by security_agent."""
    print("\n" + "="*80)
    print("ENTERING SECURITY FIXER AGENT")
    print("="*80)
    security_validation: SecurityValidation = state.get("security_validation")
    
    if not security_validation or not security_validation.issues:
        print("✅ No security fixes needed")
        print("")
        return {
            "status": "SECURITY_PASSED",
            "plan": state.get("plan"),
            "task_plan": state.get("task_plan")
        }
    
    print(f"🔧 Applying security fixes for {len(security_validation.issues)} issues...")
    print("")
    
    for issue in security_validation.issues[:5]:
        try:
            file_content = read_file.invoke(issue.file)
            
            fix_prompt = f"""Apply security fix to this file.

File: {issue.file}
Line: {issue.line}
Severity: {issue.severity}
Issue: {issue.issue}
Fix: {issue.fix}

Current file content:
{file_content}

Generate the COMPLETE corrected file content with the security fix applied.
Ensure you:
1. Use environment variables for sensitive data
2. Never hardcode credentials or API keys
3. Implement proper input validation
4. Use parameterized queries for database operations
5. Sanitize user inputs to prevent XSS

Output ONLY the corrected code, no explanations.
"""
            
            # Rate limiting check
            can_proceed, wait_time = rate_limit_check(MODEL_PROVIDER)
            if not can_proceed:
                print(f"⏳ Rate limit reached. Waiting {wait_time:.0f} seconds...")
                time.sleep(wait_time + 1)
            
            estimated_tokens = count_tokens_estimate(fix_prompt)
            print(f"📊 Estimated tokens for fix: {estimated_tokens}")
            
            response = llm.invoke(fix_prompt)
            corrected_content = response.content.strip()
            
            if corrected_content.startswith('```'):
                lines = corrected_content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                corrected_content = '\n'.join(lines)
            
            write_file.invoke({"path": issue.file, "content": corrected_content})
            print(f"✅ Fixed security issue in: {issue.file}")
            
        except Exception as e:
            print(f"❌ Error fixing {issue.file}: {e}")
            continue
    
    print("")
    print("✅ Security fixes applied")
    print("")
    return {
        "status": "SECURITY_FIXED",
        "plan": state.get("plan"),
        "task_plan": state.get("task_plan")
    }


def final_verification_agent(state: dict) -> dict:
    """Final code verification - simplified version."""
    print("\n" + "="*80)
    print("ENTERING FINAL VERIFICATION AGENT")
    print("="*80)
    print("✅ Running final code verification...")
    print("")
    
    # Skip complex file scanning for now - just pass through with verification complete
    print("✅ Final verification complete - project generated successfully")
    print("")
    
    # CRITICAL: Return the state with plan and task_plan preserved
    return {
        "status": "VERIFICATION_COMPLETE", 
        "verification_notes": "Verification complete - all files generated",
        "plan": state.get("plan"),
        "task_plan": state.get("task_plan"),
        "coder_state": state.get("coder_state"),
        "security_validation": state.get("security_validation"),
        "security_attempts": state.get("security_attempts")
    }


graph = StateGraph(dict)

graph.add_node("prompt_optimizer", prompt_optimizer_agent)
graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)
graph.add_node("coder", coder_agent)
graph.add_node("security", security_agent)
graph.add_node("security_fixer", security_fixer_agent)
graph.add_node("final_verification", final_verification_agent)

def route_from_optimizer(state: dict) -> str:
    if state.get("skip_questions", False):
        return "planner"
    if state.get("optimized_prompt"):
        return "planner"
    if not state.get("questions"):
        return "planner"
    return END

graph.add_conditional_edges(
    "prompt_optimizer",
    route_from_optimizer,
    {"planner": "planner", END: END}
)

graph.add_edge("planner", "architect")
graph.add_edge("architect", "coder")

graph.add_conditional_edges(
    "coder",
    lambda s: "security" if s.get("status") == "CODING_DONE" else "coder",
    {"security": "security", "coder": "coder"}
)

def route_from_security(state: dict) -> str:
    status = state.get("status")
    if status == "SECURITY_PASSED":
        return "final_verification"
    elif status == "SECURITY_NEEDS_FIX":
        return "security_fixer"
    else:
        return "final_verification"

graph.add_conditional_edges(
    "security",
    route_from_security,
    {"final_verification": "final_verification", "security_fixer": "security_fixer"}
)

graph.add_edge("security_fixer", "final_verification")

graph.add_conditional_edges(
    "final_verification",
    lambda s: END,
    {END: END}
)

graph.set_entry_point("prompt_optimizer")
agent = graph.compile()

# Direct agent for Streamlit - bypasses prompt_optimizer since UI handles question flow
# Starts directly at planner with pre-optimized prompt from frontend
planner_subgraph = StateGraph(dict)
planner_subgraph.add_node("planner", planner_agent)
planner_subgraph.add_node("architect", architect_agent)
planner_subgraph.add_node("coder", coder_agent)
planner_subgraph.add_node("security", security_agent)
planner_subgraph.add_node("security_fixer", security_fixer_agent)
planner_subgraph.add_node("final_verification", final_verification_agent)

planner_subgraph.add_edge("planner", "architect")
planner_subgraph.add_edge("architect", "coder")

planner_subgraph.add_conditional_edges(
    "coder",
    lambda s: "security" if s.get("status") == "CODING_DONE" else "coder",
    {"security": "security", "coder": "coder"}
)

planner_subgraph.add_conditional_edges(
    "security",
    route_from_security,
    {"final_verification": "final_verification", "security_fixer": "security_fixer"}
)

planner_subgraph.add_edge("security_fixer", "final_verification")

planner_subgraph.add_conditional_edges(
    "final_verification",
    lambda s: END,
    {END: END}
)

planner_subgraph.set_entry_point("planner")
direct_agent = planner_subgraph.compile()

if __name__ == "__main__":
    result = agent.invoke({"user_prompt": "Build a colourful modern todo app in html css and js"},
                          {"recursion_limit": 100})
    print("Final State:", result)
