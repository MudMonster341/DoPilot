import argparse
import sys
import traceback
from pathlib import Path

from agent.graph import agent
from agent.tools import PROJECT_ROOT


def main():
    parser = argparse.ArgumentParser(description="Run engineering project planner")
    parser.add_argument("--recursion-limit", "-r", type=int, default=100,
                        help="Recursion limit for processing (default: 100)")

    args = parser.parse_args()

    try:
        user_prompt = input("Enter your project prompt: ")
        result = agent.invoke(
            {"user_prompt": user_prompt},
            {"recursion_limit": args.recursion_limit}
        )
        
        print("\n" + "="*60)
        print("Project generation completed successfully")
        print("="*60)
        
        if result.get("plan"):
            plan = result["plan"]
            print(f"\nProject Name: {plan.name}")
            print(f"Description: {plan.description}")
            print(f"Tech Stack: {plan.techstack}")
            print(f"Location: {PROJECT_ROOT.absolute()}")
            
            if PROJECT_ROOT.exists():
                files = list(PROJECT_ROOT.rglob("*"))
                file_list = [f for f in files if f.is_file()]
                if file_list:
                    print(f"\nGenerated Files ({len(file_list)}):")
                    for file in sorted(file_list):
                        print(f"  - {file.relative_to(PROJECT_ROOT)}")
        
        print("\n" + "="*60)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()