"""
File operations and utility tools for DoPilot.
Handles project creation, file I/O, security scanning, and requirements management.
"""

import pathlib
import subprocess
import re
from typing import Tuple, Dict, List, Any
from langchain_core.tools import tool

from agent.states import Plan


# Global variable for project root
PROJECT_ROOT = pathlib.Path.cwd() / "generated_project"


def safe_path_for_project(path: str) -> pathlib.Path:
    """
    Validate that a file path is within the project root.
    Prevents directory traversal attacks.
    """
    p = (PROJECT_ROOT / path).resolve()
    if PROJECT_ROOT.resolve() not in p.parents and PROJECT_ROOT.resolve() != p.parent and PROJECT_ROOT.resolve() != p:
        raise ValueError("Attempt to write outside project root")
    return p


@tool
def write_file(input_dict: Dict[str, str]) -> str:
    """
    Writes content to a file at the specified path within the project root.
    Args:
        input_dict: Dictionary with 'path' and 'content' keys
    """
    path = input_dict["path"]
    content = input_dict["content"]
    p = safe_path_for_project(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return f"WROTE:{p}"


@tool
def read_file(path: str) -> str:
    """Reads content from a file at the specified path within the project root."""
    p = safe_path_for_project(path)
    if not p.exists():
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


@tool
def get_current_directory() -> str:
    """Returns the current working directory."""
    return str(PROJECT_ROOT)


@tool
def list_files(directory: str = ".") -> str:
    """Lists all files in the specified directory within the project root."""
    p = safe_path_for_project(directory)
    if not p.is_dir():
        return f"ERROR: {p} is not a directory"
    files = [str(f.relative_to(PROJECT_ROOT)) for f in p.glob("**/*") if f.is_file()]
    return "\n".join(files) if files else "No files found."


@tool
def list_file(filepath: str) -> str:
    """
    Get information about a specific file.
    Alias for read_file for compatibility.
    """
    return read_file.invoke(filepath)


@tool
def run_cmd(cmd: str, cwd: str = None, timeout: int = 30) -> Tuple[int, str, str]:
    """Runs a shell command in the specified directory and returns the result."""
    cwd_dir = safe_path_for_project(cwd) if cwd else PROJECT_ROOT
    res = subprocess.run(cmd, shell=True, cwd=str(cwd_dir), capture_output=True, text=True, timeout=timeout)
    return res.returncode, res.stdout, res.stderr


def init_project_root():
    """Initialize the project root directory."""
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    return str(PROJECT_ROOT)


@tool
def set_project_root(project_name: str) -> str:
    """
    Set up the project root directory for code generation.
    Returns the absolute path to the project directory.
    """
    global PROJECT_ROOT
    
    # Sanitize project name
    clean_name = re.sub(r'[^\w\s-]', '', project_name.lower())
    clean_name = re.sub(r'[\s_]+', '_', clean_name).strip('_')
    if len(clean_name) > 50:
        clean_name = clean_name[:50]
    if not clean_name:
        clean_name = "generated_project"
    
    PROJECT_ROOT = pathlib.Path.cwd() / clean_name
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    
    return str(PROJECT_ROOT)


def create_project_readme(plan: Plan) -> str:
    """
    Generate a professional README.md for the project.
    Returns the path to the created README file.
    """
    readme_content = f"""# {plan.name.replace('_', ' ').replace('-', ' ').title()}

## Description
{plan.description}

## Purpose
This project implements the following key features:
{chr(10).join(f"- {feature}" for feature in plan.features)}

## Tech Stack
{plan.techstack}

## Project Structure
```
(Files will be listed here after generation)
```

## How to Run

### Prerequisites
Ensure you have the required dependencies installed based on the tech stack mentioned above.

### Setup Instructions
1. Clone or download this repository
2. Navigate to the project directory
3. Follow tech-stack specific setup:

#### Node.js Setup
```bash
npm install
npm start
```

#### Python Setup
```bash
pip install -r requirements.txt
python main.py
```

## Development
Follow standard development practices for the chosen tech stack. Ensure all dependencies are properly configured before running the application.

## Security Considerations
- Do not commit sensitive credentials or API keys
- Use environment variables for configuration
- Follow secure coding practices for your tech stack
- Implement proper input validation and sanitization
- Use HTTPS in production environments

## License
This project is provided as-is for development purposes.
"""
    
    readme_path = PROJECT_ROOT / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    return str(readme_path)


# Security patterns for scanning
SECURITY_PATTERNS = {
    'api_keys': [
        r'api[_-]?key\s*=\s*["\']([a-zA-Z0-9_\-]{20,})["\']',
        r'apikey\s*=\s*["\']([a-zA-Z0-9_\-]{20,})["\']',
        r'api[_-]?secret\s*=\s*["\']([a-zA-Z0-9_\-]{20,})["\']',
        r'access[_-]?token\s*=\s*["\']([a-zA-Z0-9_\-]{20,})["\']',
        r'auth[_-]?token\s*=\s*["\']([a-zA-Z0-9_\-]{20,})["\']',
        r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}',
    ],
    'credentials': [
        r'password\s*=\s*["\'](?!.*\{|.*process\.env|.*os\.getenv)([^"\']+)["\']',
        r'passwd\s*=\s*["\'](?!.*\{|.*process\.env|.*os\.getenv)([^"\']+)["\']',
        r'pwd\s*=\s*["\'](?!.*\{|.*process\.env|.*os\.getenv)([^"\']+)["\']',
        r'username\s*=\s*["\'](?!.*\{|.*process\.env|.*os\.getenv)([^"\']+)["\']',
    ],
    'database_urls': [
        r'(mongodb|mysql|postgresql|redis)://[^:]+:[^@]+@',
        r'DATABASE_URL\s*=\s*["\'](?!.*process\.env|.*os\.getenv)([^"\']+)["\']',
        r'DB_PASSWORD\s*=\s*["\'](?!.*process\.env|.*os\.getenv)([^"\']+)["\']',
    ],
    'private_keys': [
        r'-----BEGIN\s+(RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----',
        r'private[_-]?key\s*=\s*["\']([^"\']{20,})["\']',
    ],
    'aws_credentials': [
        r'AKIA[0-9A-Z]{16}',
        r'aws[_-]?access[_-]?key[_-]?id\s*=\s*["\']([A-Z0-9]{20})["\']',
        r'aws[_-]?secret[_-]?access[_-]?key\s*=\s*["\']([a-zA-Z0-9/+=]{40})["\']',
    ],
    'jwt_secrets': [
        r'jwt[_-]?secret\s*=\s*["\'](?!.*process\.env|.*os\.getenv)([^"\']{10,})["\']',
        r'secret[_-]?key\s*=\s*["\'](?!.*process\.env|.*os\.getenv)([^"\']{10,})["\']',
    ],
}

SECURITY_CHECKS = {
    'sql_injection': [
        r'execute\(["\'].*\+.*["\']',
        r'query\(["\'].*\+.*["\']',
        r'SELECT\s+.*\+.*FROM',
        r'INSERT\s+.*\+.*VALUES',
        r'UPDATE\s+.*\+.*SET',
        r'DELETE\s+.*\+.*WHERE',
    ],
    'xss_vulnerabilities': [
        r'innerHTML\s*=\s*[^;]*(?!sanitize|escape|encode)',
        r'document\.write\(',
        r'eval\(',
        r'dangerouslySetInnerHTML',
    ],
    'insecure_storage': [
        r'localStorage\.setItem\(["\'][^"\']*(?:password|token|secret|key)',
        r'sessionStorage\.setItem\(["\'][^"\']*(?:password|token|secret|key)',
    ],
    'cors_issues': [
        r'Access-Control-Allow-Origin\s*:\s*["\']?\*["\']?',
        r'cors\(\{\s*origin\s*:\s*["\']?\*["\']?',
    ],
}


def scan_file_security(file_path: pathlib.Path) -> List[Dict[str, Any]]:
    """Scan a single file for security issues."""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for hardcoded secrets
        for category, patterns in SECURITY_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    # Skip if it's in a comment
                    line_start = content.rfind('\n', 0, match.start()) + 1
                    line_content = content[line_start:match.end()]
                    if line_content.strip().startswith('#') or line_content.strip().startswith('//'):
                        continue
                    
                    issues.append({
                        'file': str(file_path.relative_to(PROJECT_ROOT)),
                        'category': category,
                        'line': content[:match.start()].count('\n') + 1,
                        'issue': f'Potential {category.replace("_", " ")} exposed',
                        'severity': 'HIGH'
                    })
        
        # Check for vulnerabilities
        for category, patterns in SECURITY_CHECKS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    line_start = content.rfind('\n', 0, match.start()) + 1
                    line_content = content[line_start:match.end()]
                    if line_content.strip().startswith('#') or line_content.strip().startswith('//'):
                        continue
                    
                    issues.append({
                        'file': str(file_path.relative_to(PROJECT_ROOT)),
                        'category': category,
                        'line': content[:match.start()].count('\n') + 1,
                        'issue': f'Potential {category.replace("_", " ")} vulnerability',
                        'severity': 'MEDIUM'
                    })
    
    except Exception:
        pass
    
    return issues


def scan_project_security() -> Dict[str, Any]:
    """
    Scan all project files for security vulnerabilities.
    Returns dictionary with scan results.
    """
    all_issues = []
    
    if not PROJECT_ROOT.exists():
        return {'issues': [], 'passed': True, 'summary': 'No files to scan', 'total_issues': 0}
    
    # Scan code files
    extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.php', '.rb', '.go']
    for file_path in PROJECT_ROOT.rglob('*'):
        if file_path.is_file() and file_path.suffix in extensions:
            issues = scan_file_security(file_path)
            all_issues.extend(issues)
    
    passed = len(all_issues) == 0
    summary = 'Security scan passed. No issues detected' if passed else f'Found {len(all_issues)} security issues'
    
    return {
        'issues': all_issues,
        'passed': passed,
        'summary': summary,
        'total_issues': len(all_issues)
    }


# Package name mappings for requirements generation
PACKAGE_MAPPINGS = {
    'flask': 'Flask',
    'django': 'Django',
    'fastapi': 'fastapi',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'requests': 'requests',
    'beautifulsoup4': 'beautifulsoup4',
    'bs4': 'beautifulsoup4',
    'PIL': 'Pillow',
    'cv2': 'opencv-python',
    'sklearn': 'scikit-learn',
    'torch': 'torch',
    'tensorflow': 'tensorflow',
    'matplotlib': 'matplotlib',
    'seaborn': 'seaborn',
    'sqlalchemy': 'SQLAlchemy',
    'psycopg2': 'psycopg2-binary',
    'pymongo': 'pymongo',
    'redis': 'redis',
    'celery': 'celery',
    'pytest': 'pytest',
    'dotenv': 'python-dotenv',
    'jwt': 'PyJWT',
    'cryptography': 'cryptography',
    'bcrypt': 'bcrypt',
    'pydantic': 'pydantic',
    'uvicorn': 'uvicorn',
    'gunicorn': 'gunicorn',
    'streamlit': 'streamlit',
    'gradio': 'gradio',
}


def detect_imports_from_code(file_path: pathlib.Path) -> set:
    """Detect imports from Python code files."""
    imports = set()
    stdlib_modules = {
        'os', 'sys', 'json', 'time', 'datetime', 're', 'math', 'random', 
        'collections', 'itertools', 'functools', 'pathlib', 'typing', 
        'enum', 'abc', 'copy', 'io', 'logging', 'argparse', 'subprocess',
        'threading', 'multiprocessing', 'asyncio', 'socket', 'ssl', 'urllib',
        'http', 'email', 'html', 'xml', 'csv', 'string', 'textwrap', 'unicodedata',
        'struct', 'codecs', 'warnings', 'contextlib', 'weakref', 'array', 'queue'
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        import_patterns = [
            r'^\s*import\s+([a-zA-Z0-9_]+)',
            r'^\s*from\s+([a-zA-Z0-9_]+)\s+import',
        ]
        
        for pattern in import_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                module = match.group(1)
                if module not in stdlib_modules:
                    imports.add(module)
    
    except Exception:
        pass
    
    return imports


def generate_requirements_txt() -> bool:
    """
    Generate requirements.txt based on actual imports found in Python files.
    Returns True if file was created successfully.
    """
    if not PROJECT_ROOT.exists():
        return False
    
    readme_path = PROJECT_ROOT / "README.md"
    requirements_path = PROJECT_ROOT / "requirements.txt"
    
    # Check if README mentions requirements
    readme_mentions_requirements = False
    if readme_path.exists():
        with open(readme_path, 'r', encoding='utf-8') as f:
            readme_content = f.read()
            if 'requirements.txt' in readme_content or 'pip install -r' in readme_content:
                readme_mentions_requirements = True
    
    if not readme_mentions_requirements:
        return False
    
    # Detect imports from Python files
    detected_imports = set()
    for file_path in PROJECT_ROOT.rglob('*.py'):
        if file_path.name == '__init__.py':
            continue
        imports = detect_imports_from_code(file_path)
        detected_imports.update(imports)
    
    if not detected_imports:
        return False
    
    # Map imports to package names
    requirements = set()
    for imp in detected_imports:
        if imp in PACKAGE_MAPPINGS:
            requirements.add(PACKAGE_MAPPINGS[imp])
        else:
            requirements.add(imp)
    
    # Write requirements.txt
    if requirements:
        with open(requirements_path, 'w', encoding='utf-8') as f:
            for req in sorted(requirements):
                f.write(f"{req}\n")
        return True
    
    return False


def validate_requirements_file() -> Dict[str, Any]:
    """
    Validate that requirements.txt exists if mentioned in README and contains relevant packages.
    Returns validation results with any issues found.
    """
    issues = []
    
    readme_path = PROJECT_ROOT / "README.md"
    requirements_path = PROJECT_ROOT / "requirements.txt"
    
    if not readme_path.exists():
        return {'valid': True, 'issues': [], 'total_issues': 0}
    
    with open(readme_path, 'r', encoding='utf-8') as f:
        readme_content = f.read()
    
    readme_mentions_requirements = 'requirements.txt' in readme_content or 'pip install -r' in readme_content
    
    if readme_mentions_requirements:
        if not requirements_path.exists():
            issues.append({
                'type': 'MISSING_FILE',
                'message': 'README.md mentions requirements.txt but file does not exist',
                'severity': 'HIGH'
            })
        else:
            with open(requirements_path, 'r', encoding='utf-8') as f:
                req_content = f.read().strip()
            
            if not req_content:
                issues.append({
                    'type': 'EMPTY_FILE',
                    'message': 'requirements.txt is empty but mentioned in README',
                    'severity': 'HIGH'
                })
            else:
                # Check if imported packages are in requirements
                detected_imports = set()
                for file_path in PROJECT_ROOT.rglob('*.py'):
                    imports = detect_imports_from_code(file_path)
                    detected_imports.update(imports)
                
                req_packages = set()
                for line in req_content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        pkg = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                        req_packages.add(pkg.lower())
                
                if detected_imports:
                    relevant_packages = set()
                    for imp in detected_imports:
                        if imp in PACKAGE_MAPPINGS:
                            relevant_packages.add(PACKAGE_MAPPINGS[imp].lower())
                        else:
                            relevant_packages.add(imp.lower())
                    
                    missing_in_requirements = relevant_packages - req_packages
                    if missing_in_requirements:
                        issues.append({
                            'type': 'MISSING_DEPENDENCIES',
                            'message': f'Missing packages in requirements.txt: {", ".join(missing_in_requirements)}',
                            'severity': 'MEDIUM'
                        })
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'total_issues': len(issues)
    }
