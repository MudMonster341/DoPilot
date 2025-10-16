import streamlit as st
import sys
import json
import time
import zipfile
import io
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from agent.graph import direct_agent, prompt_optimizer_agent
from agent.tools import PROJECT_ROOT
from agent.rate_limiter import init_rate_limiting_state, check_session_limits, get_rate_limit_status

st.set_page_config(
    page_title="DoPilot - AI Code Generator",
    page_icon="🚀",
    layout="centered",
    initial_sidebar_state="auto"
)

if 'stage' not in st.session_state:
    st.session_state.stage = 'welcome'
    st.session_state.user_prompt = ''
    st.session_state.all_questions = []
    st.session_state.current_batch = 0
    st.session_state.all_answers = {}
    st.session_state.optimized_prompt = ''
    st.session_state.generation_result = None
    st.session_state.show_other_input = {}
    # Initialize rate limiting
    init_rate_limiting_state()

def reset_app():
    st.session_state.stage = 'welcome'
    st.session_state.user_prompt = ''
    st.session_state.all_questions = []
    st.session_state.current_batch = 0
    st.session_state.all_answers = {}
    st.session_state.optimized_prompt = ''
    st.session_state.generation_result = None
    st.session_state.show_other_input = {}

st.markdown("""
<style>
    .main-title {
        text-align: center;
        font-size: 3.5rem;
        font-weight: 700;
        background: linear-gradient(120deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        text-align: center;
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 3rem;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar with rate limit status
with st.sidebar:
    st.markdown("### 📊 API Usage Status")
    
    status = get_rate_limit_status()
    
    st.metric("Calls This Minute", f"{status['calls_this_minute']}/{status['max_calls_per_minute']}")
    st.metric("Total Session Tokens", f"{status['total_tokens']:,}")
    st.metric("Total API Calls", status['total_calls'])
    
    st.markdown("---")
    st.markdown("### 💡 Tips")
    st.markdown("""
    - Keep prompts under 3000 characters
    - Answer questions for better results
    - Rate limits reset every minute
    """)

if st.session_state.stage == 'welcome':
    st.markdown('<h1 class="main-title">🚀 DoPilot</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Transform your ideas into production-ready applications</p>', unsafe_allow_html=True)
    
    st.markdown("###")
    
    user_prompt = st.text_area(
        "Describe your app idea",
        placeholder="💡 Describe your app idea...\n\nExample: Create a task management app with user authentication, real-time updates, and a modern dashboard",
        height=200,
        key="main_prompt_input",
        label_visibility="collapsed"
    )
    
    st.markdown("###")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("✨ Start Building", type="primary", disabled=not user_prompt, use_container_width=True):
            st.session_state.user_prompt = user_prompt
            st.session_state.stage = 'loading_questions'
            st.rerun()

elif st.session_state.stage == 'loading_questions':
    st.markdown('<h1 class="main-title">🤔 Analyzing Your Idea</h1>', unsafe_allow_html=True)
    
    progress_bar = st.progress(0)
    status = st.empty()
    
    status.text("🔍 Understanding your requirements...")
    progress_bar.progress(30)
    time.sleep(0.5)
    
    # Determine if this is the first batch or follow-up
    is_first_batch = st.session_state.current_batch == 0
    
    context = f"User prompt: {st.session_state.user_prompt}\n\n"
    if st.session_state.all_answers:
        context += "Previous answers:\n" + "\n".join([f"- {q}: {a}" for q, a in st.session_state.all_answers.items()])
    
    status.text("💭 Generating relevant questions...")
    progress_bar.progress(50)
    
    # Check rate limits before making API call
    can_proceed, message = check_session_limits()
    if not can_proceed:
        st.error(f"⚠️ Rate Limit Exceeded\n\n{message}")
        st.info("Please wait a moment before continuing.")
        time.sleep(2)
        st.session_state.stage = 'welcome'
        st.rerun()
    
    try:
        result = prompt_optimizer_agent({
            'user_prompt': context,
            'is_first_batch': is_first_batch
        })
        
        progress_bar.progress(80)
        
        if 'questions' in result and result['questions']:
            new_questions = result['questions']
            
            # First batch should have exactly 10 questions
            if is_first_batch:
                new_questions = new_questions[:10]
            else:
                new_questions = new_questions[:8]
            
            st.session_state.all_questions = new_questions
            
            progress_bar.progress(100)
            status.text("✅ Questions ready!")
            time.sleep(0.5)
            
            st.session_state.stage = 'questions'
            st.rerun()
        else:
            # No questions generated, proceed to prompt confirmation
            st.session_state.optimized_prompt = st.session_state.user_prompt
            st.session_state.stage = 'confirm_prompt'
            st.rerun()
            
    except Exception as e:
        st.error(f"Error generating questions: {str(e)}")
        # Fall back to confirm prompt
        st.session_state.optimized_prompt = st.session_state.user_prompt
        st.session_state.stage = 'confirm_prompt'
        time.sleep(2)
        st.rerun()

elif st.session_state.stage == 'questions':
    batch_num = st.session_state.current_batch + 1
    total_answered = len(st.session_state.all_answers)
    is_first_batch = st.session_state.current_batch == 0
    
    st.markdown('<div id="questions-section"></div>', unsafe_allow_html=True)
    
    if is_first_batch:
        st.markdown(f'<h1 class="main-title">❓ Core Questions (10)</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="subtitle">These essential questions help us understand your project requirements</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<h1 class="main-title">❓ Follow-up Questions</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="subtitle">Batch {batch_num} • {total_answered} questions answered so far</p>', unsafe_allow_html=True)
    
    st.info(f"💡 **Your idea:** {st.session_state.user_prompt}")
    
    st.markdown("---")
    
    questions = st.session_state.all_questions
    batch_answers = {}
    
    for i, question in enumerate(questions):
        q_text = question['question']
        q_type = question['type']
        q_options = question.get('options', [])
        
        st.markdown(f"### {i+1}. {q_text}")
        
        if q_type == 'choice':
            clean_options = [opt for opt in q_options if opt.lower() != 'skip']
            options_with_skip = ['Skip'] + clean_options + ['Other']
            selected = st.radio(
                "Choose one:",
                options_with_skip,
                key=f"q_batch{batch_num}_{i}",
                index=0,
                horizontal=len(clean_options) <= 3,
                label_visibility="collapsed"
            )
            
            if selected == 'Other':
                if f"other_{i}" not in st.session_state.show_other_input:
                    st.session_state.show_other_input[f"other_{i}"] = True
                
                other_input = st.text_input(
                    "Please specify:",
                    key=f"other_input_batch{batch_num}_{i}",
                    placeholder="Type your answer here..."
                )
                batch_answers[q_text] = other_input if other_input else None
            elif selected != 'Skip':
                batch_answers[q_text] = selected
                
        elif q_type == 'multiple':
            selected_multiple = st.multiselect(
                "Select all that apply:",
                q_options,
                key=f"q_multi_batch{batch_num}_{i}",
                label_visibility="collapsed"
            )
            
            col1, col2 = st.columns([3, 1])
            with col1:
                include_other = st.checkbox("Other (specify below)", key=f"other_check_batch{batch_num}_{i}")
            
            if include_other:
                other_multi = st.text_input(
                    "Please specify:",
                    key=f"other_multi_batch{batch_num}_{i}",
                    placeholder="Type your answer here..."
                )
                if other_multi:
                    selected_multiple.append(other_multi)
            
            if selected_multiple:
                batch_answers[q_text] = ", ".join(selected_multiple)
                
        else:
            text_input = st.text_input(
                "Your answer:",
                key=f"q_text_batch{batch_num}_{i}",
                placeholder="Type your answer or leave blank to skip...",
                label_visibility="collapsed"
            )
            if text_input:
                batch_answers[q_text] = text_input
        
        st.markdown("---")
    
    st.markdown("###")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("⏭️ Skip All", use_container_width=True):
            st.session_state.stage = 'confirm_prompt'
            st.rerun()
    
    with col2:
        if st.button("➡️ Continue", use_container_width=True):
            st.session_state.all_answers.update(batch_answers)
            st.session_state.current_batch += 1
            st.session_state.stage = 'loading_questions'
            st.rerun()
    
    with col3:
        if st.button("✅ Finish & Build", type="primary", use_container_width=True):
            st.session_state.all_answers.update(batch_answers)
            st.session_state.stage = 'confirm_prompt'
            st.rerun()

elif st.session_state.stage == 'confirm_prompt':
    st.markdown('<h1 class="main-title">📝 Review Final Prompt</h1>', unsafe_allow_html=True)
    
    optimized = st.session_state.user_prompt
    if st.session_state.all_answers:
        answers_text = "\n".join([f"- {q}: {a}" for q, a in st.session_state.all_answers.items()])
        optimized = f"{st.session_state.user_prompt}\n\n**Additional Requirements:**\n{answers_text}"
    
    st.session_state.optimized_prompt = optimized
    
    st.markdown("### 📋 Enhanced Prompt")
    st.text_area(
        "Enhanced Prompt",
        value=optimized,
        height=300,
        key="final_prompt_display",
        label_visibility="collapsed"
    )
    
    st.markdown("###")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔙 Edit Answers", use_container_width=True):
            st.session_state.stage = 'questions'
            st.rerun()
    
    with col2:
        if st.button("🚀 Generate Project", type="primary", use_container_width=True):
            st.session_state.stage = 'enhancing_prompt'
            st.rerun()

elif st.session_state.stage == 'enhancing_prompt':
    st.markdown('<h1 class="main-title">✨ Optimizing Your Specification</h1>', unsafe_allow_html=True)
    
    progress_bar = st.progress(0)
    status = st.empty()
    
    status.text("🔍 Analyzing requirements...")
    progress_bar.progress(30)
    
    from agent.prompts import final_prompt_enhancer
    from agent.graph import llm
    
    enhancer_prompt = final_prompt_enhancer(st.session_state.user_prompt, st.session_state.all_answers)
    
    status.text("🧠 Enhancing specification with AI...")
    progress_bar.progress(60)
    
    # Check rate limits before making API call
    can_proceed, message = check_session_limits()
    if not can_proceed:
        st.error(f"⚠️ Rate Limit Exceeded\n\n{message}")
        st.info("Using original prompt without enhancement.")
        st.session_state.optimized_prompt = st.session_state.user_prompt
        time.sleep(2)
        st.session_state.stage = 'show_enhanced_prompt'
        st.rerun()
    
    try:
        response = llm.invoke(enhancer_prompt)
        final_enhanced_prompt = response.content.strip()
        
        # Enforce 3000 character limit
        if len(final_enhanced_prompt) > 3000:
            final_enhanced_prompt = final_enhanced_prompt[:3000]
        
        st.session_state.optimized_prompt = final_enhanced_prompt
        
        progress_bar.progress(100)
        status.text("✅ Specification optimized!")
        time.sleep(0.5)
        
        st.session_state.stage = 'show_enhanced_prompt'
        st.rerun()
        
    except Exception as e:
        st.error(f"Enhancement failed: {str(e)}")
        st.session_state.optimized_prompt = st.session_state.user_prompt
        st.session_state.stage = 'show_enhanced_prompt'
        time.sleep(2)
        st.rerun()

elif st.session_state.stage == 'show_enhanced_prompt':
    st.markdown('<h1 class="main-title">📋 Final Enhanced Specification</h1>', unsafe_allow_html=True)
    
    st.markdown("### AI-Optimized Project Specification")
    st.markdown("_Edit the specification below before building your project_")
    
    # Calculate character count
    current_length = len(st.session_state.optimized_prompt)
    char_limit = 3000
    
    # Display character counter
    if current_length > char_limit:
        st.error(f"⚠️ {current_length}/{char_limit} characters (exceeded by {current_length - char_limit})")
    elif current_length > char_limit * 0.9:
        st.warning(f"📊 {current_length}/{char_limit} characters (close to limit)")
    else:
        st.info(f"📊 {current_length}/{char_limit} characters")
    
    # Editable text area with character limit validation
    edited_prompt = st.text_area(
        "Final Specification",
        value=st.session_state.optimized_prompt,
        height=400,
        key="enhanced_final_display",
        label_visibility="collapsed",
        max_chars=char_limit,
        help=f"Maximum {char_limit} characters"
    )
    
    # Update the optimized prompt with edited content
    st.session_state.optimized_prompt = edited_prompt
    
    st.markdown("###")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔙 Back to Questions", use_container_width=True):
            st.session_state.stage = 'questions'
            st.rerun()
    
    with col2:
        # Disable build button if over character limit
        can_build = len(edited_prompt) <= char_limit and len(edited_prompt) > 0
        if st.button("🚀 Build Project", type="primary", use_container_width=True, disabled=not can_build):
            st.session_state.stage = 'generating'
            st.rerun()

elif st.session_state.stage == 'generating':
    st.markdown('<h1 class="main-title">⚙️ Building Your Application</h1>', unsafe_allow_html=True)
    
    progress_container = st.container()
    status_container = st.empty()
    log_container = st.expander("📋 Generation Log", expanded=True)
    
    with progress_container:
        progress_bar = st.progress(0)
    
    try:
        initial_state = {
            "user_prompt": st.session_state.optimized_prompt,
            "optimized_prompt": st.session_state.optimized_prompt
        }
        
        # Check rate limits before starting generation
        can_proceed, message = check_session_limits()
        if not can_proceed:
            st.error(f"⚠️ Rate Limit Exceeded\n\n{message}")
            st.info("Please wait before generating another project.")
            with log_container:
                st.write(f"❌ {message}")
                # Display current rate limit status
                status = get_rate_limit_status()
                st.write(f"📊 Total API calls: {status['total_calls']}")
                st.write(f"📊 Total tokens used: {status['total_tokens']:,}")
            time.sleep(3)
            st.session_state.stage = 'show_enhanced_prompt'
            st.rerun()
        
        status_container.markdown("### 📋 Planning project structure")
        progress_bar.progress(10)
        
        with log_container:
            st.write("🚀 Starting generation with enhanced prompt...")
            st.write(f"📊 Prompt length: {len(st.session_state.optimized_prompt)} characters")
            # Display rate limit status
            status = get_rate_limit_status()
            st.write(f"📊 API calls this minute: {status['calls_this_minute']}")
            st.write(f"📊 Tokens used this session: {status['total_tokens']:,}")
            st.write("")
            st.write("📋 Analyzing project requirements...")
        
        # Import required modules
        try:
            from agent.graph import direct_agent
        except ValueError as api_error:
            st.error(f"⚠️ Configuration Error: {str(api_error)}")
            with log_container:
                st.write("")
                st.write("Configuration Steps:")
                st.write("1. Copy .sample_env to .env")
                st.write("2. Add your API key to the .env file")
                st.write("3. Restart the application")
            st.markdown("###")
            if st.button("🔄 Try Again After Configuration"):
                st.rerun()
            st.stop()
        import io
        import contextlib
        
        # Capture stdout to get agent logs
        captured_output = io.StringIO()
        
        with log_container:
            st.write("Invoking agent with state...")
            st.write(f"State keys: {list(initial_state.keys())}")
            st.write(f"DEBUG: About to invoke direct_agent with recursion_limit=500")
        
        # Run the agent and capture its output
        try:
            # TEMPORARILY DISABLED stdout redirect to see real-time output for debugging
            # with contextlib.redirect_stdout(captured_output):
            print("=" * 100)
            print("STARTING DIRECT_AGENT.INVOKE()")
            print("=" * 100)
            result = direct_agent.invoke(initial_state, {"recursion_limit": 500})
            print("=" * 100)
            print("FINISHED DIRECT_AGENT.INVOKE()")
            print("=" * 100)
            
            with log_container:
                st.write("Agent execution completed")
                st.write(f"Result type: {type(result)}")
                st.write(f"Result keys: {list(result.keys())}")
                
                # Debug: Check each key
                for key in result.keys():
                    value = result[key]
                    st.write(f"Key '{key}': type={type(value).__name__}")
                
                # Check if plan is nested somewhere
                if "task_plan" in result:
                    st.write(f"task_plan has 'plan' attribute: {hasattr(result.get('task_plan'), 'plan')}")
                    
        except Exception as agent_error:
            with log_container:
                st.write(f"Agent execution failed: {str(agent_error)}")
            raise agent_error
        
        # Parse the captured output for logs
        # TEMPORARILY DISABLED - not capturing stdout anymore for debugging
        # output_lines = captured_output.getvalue().split('\n')
        # 
        # with log_container:
        #     for line in output_lines:
        #         if line.strip():
        #             st.write(line.strip())
        
        with log_container:
            st.write("Check your terminal/console for real-time output")
        
        # Verify we have a plan
        if not result.get("plan"):
            with log_container:
                st.write("")
                st.write("Plan not found in result, checking alternatives...")
                
                # Check if plan is nested in task_plan
                if "task_plan" in result:
                    task_plan = result.get("task_plan")
                    if hasattr(task_plan, 'plan') and task_plan.plan is not None:
                        st.write("Found plan nested in task_plan, extracting...")
                        result["plan"] = task_plan.plan
                        st.write(f"Extracted plan: {result['plan'].name}")
                
            # After trying to extract, check again
            if not result.get("plan"):
                # Check if project was actually created
                if PROJECT_ROOT.exists():
                    files = list(PROJECT_ROOT.rglob("*"))
                    file_list = [f for f in files if f.is_file()]
                    
                    if len(file_list) > 0:
                        with log_container:
                            st.write("")
                            st.write("⚠️ Warning: Plan metadata missing, but project files were generated")
                            st.write(f"📁 Found {len(file_list)} files in project directory")
                            st.write("")
                        
                        # Create a minimal result with project info
                        from agent.states import Plan
                        
                        project_name = PROJECT_ROOT.name
                        result["plan"] = Plan(
                            name=project_name,
                            description=f"Generated project based on: {st.session_state.optimized_prompt[:100]}...",
                            features=["Custom implementation based on specifications"],
                            techstack="Various technologies",
                            dependencies=[]
                        )
                    else:
                        raise ValueError("No plan generated and no files created - agent did not complete successfully")
                else:
                    raise ValueError("No plan generated - agent did not complete successfully")
        
        progress_bar.progress(100)
        status_container.markdown("### 🎉 Project generated successfully!")
        
        with log_container:
            st.write("")
            st.write("✅ Generation completed successfully")
            st.write(f"📦 Project: {result.get('plan').name}")
            st.write(f"🛠️ Tech Stack: {result.get('plan').techstack}")
        
        time.sleep(1)
        
        st.session_state.generation_result = result
        st.session_state.stage = 'complete'
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error during generation: {str(e)}")
        with log_container:
            st.write("")
            st.write(f"❌ ERROR: {str(e)}")
            st.write("")
            st.write("Debug Information:")
            st.write(f"State keys: {list(initial_state.keys())}")
            st.write(f"Prompt preview: {initial_state.get('optimized_prompt', '')[:200]}...")
        st.exception(e)
        st.markdown("###")
        if st.button("🔄 Try Again"):
            reset_app()
            st.rerun()

elif st.session_state.stage == 'complete':
    st.markdown('<h1 class="main-title">🎉 Project Ready!</h1>', unsafe_allow_html=True)
    
    result = st.session_state.generation_result
    
    if result and result.get("plan"):
        plan = result["plan"]
        
        st.success(f"✅ Successfully generated **{plan.name}**")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📦 Project", plan.name)
        with col2:
            st.metric("🛠️ Tech Stack", plan.techstack)
        with col3:
            if PROJECT_ROOT.exists():
                files = list(PROJECT_ROOT.rglob("*"))
                file_count = len([f for f in files if f.is_file()])
                st.metric("📄 Files", file_count)
        
        st.markdown("---")
        
        st.markdown("### 📝 Description")
        st.write(plan.description)
        
        st.markdown("### ✨ Features")
        for feature in plan.features:
            st.markdown(f"- {feature}")
        
        st.markdown("---")
        
        if PROJECT_ROOT.exists():
            files = list(PROJECT_ROOT.rglob("*"))
            file_list = [f for f in files if f.is_file()]
            
            readme_path = PROJECT_ROOT / "README.md"
            readme_content = ""
            if readme_path.exists():
                try:
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        readme_content = f.read()
                except Exception:
                    pass
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in file_list:
                    arcname = file_path.relative_to(PROJECT_ROOT)
                    zip_file.write(file_path, arcname)
            
            zip_buffer.seek(0)
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.download_button(
                    label="📥 Download Project (ZIP)",
                    data=zip_buffer,
                    file_name=f"{plan.name.replace(' ', '_')}.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True
                )
            with col2:
                if st.button("🔄 New Project", use_container_width=True):
                    reset_app()
                    st.rerun()
            
            if readme_content:
                st.markdown("###")
                with st.expander("📖 README.md", expanded=True):
                    st.markdown(readme_content)
            
            st.markdown("###")
            
            with st.expander(f"📂 View Generated Files ({len(file_list)} files)", expanded=False):
                for file in sorted(file_list):
                    rel_path = file.relative_to(PROJECT_ROOT)
                    
                    with st.expander(f"📄 {rel_path}"):
                        try:
                            with open(file, 'r', encoding='utf-8') as f:
                                content = f.read()
                                
                                file_ext = file.suffix[1:] if file.suffix else 'text'
                                st.code(content, language=file_ext)
                        except Exception as e:
                            st.text(f"Unable to display: {str(e)}")
        
        st.markdown("###")
        st.info(f"💾 Project saved to: `{PROJECT_ROOT.absolute()}`")
    
    else:
        st.error("❌ Generation failed - no project data available")
        if st.button("🔄 Start Over"):
            reset_app()
            st.rerun()
