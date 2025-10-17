import os
import re
import pandas as pd
import streamlit as st
from docx import Document
from google import genai

# Set up page configuration
st.set_page_config(page_title="RnD DVT Test Planner", layout="wide")
st.title("RnD DVT Test Planner")

# Define paths
REPO_PATH = "."  # Path to your linked repo
REQUIREMENTS_FILE = os.path.join(REPO_PATH, "dvt_requirements.csv")
HISTORY_DIR = os.path.join(REPO_PATH, "history")
os.makedirs(HISTORY_DIR, exist_ok=True)

# Load API key from Streamlit secrets or environment variable
def load_api_key():
    api_key = st.secrets.get("google", {}).get("api_key")
    if api_key:
        return api_key
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return api_key
    return None

api_key = load_api_key()
if not api_key:
    st.error("Google Gemini API key not found. Please add it in `.streamlit/secrets.toml` or set the environment variable GOOGLE_API_KEY.")
    st.stop()

# Initialize GenAI client
client = genai.Client(api_key=api_key)
st.write("✅ Google Gemini API key loaded successfully")

# Read requirements file
def read_requirements_file():
    if not os.path.exists(REQUIREMENTS_FILE):
        st.error(f"Requirements file not found at {REQUIREMENTS_FILE}")
        return None
    try:
        df = pd.read_csv(REQUIREMENTS_FILE)
        return df
    except Exception as e:
        st.error(f"Failed to read requirements file: {e}")
        return None

# Convert DOCX to text
def docx_to_text(file):
    doc = Document(file)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]

# Load rules for a specific requirement
def load_rules_for_requirement(requirement_id):
    rule_file = os.path.join(REPO_PATH, f"{requirement_id}_Rule.docx")
    if os.path.exists(rule_file):
        try:
            doc = Document(rule_file)
            return [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        except Exception as e:
            st.warning(f"Failed to read rule file {rule_file}: {e}")
            return []
    else:
        st.warning(f"No rules file found for {requirement_id}")
        return []

# Normalize tokens
def normalize_token(token):
    token = token.lower()
    match = re.match(r'(-?\d+\.?\d*)([a-z%]*)', token)
    if match:
        number_part = match.group(1)
        unit_part = match.group(2)
        normalized = f"{number_part}{unit_part}"
        normalized = re.sub(r'[^a-z0-9]', '', normalized)
        return normalized
    else:
        token = re.sub(r'[^a-z0-9]', '', token)
        return token

# Extract check items from text
def extract_check_items_robust(text):
    text = text.lower()
    number_matches = re.findall(r'-?\d+\.?\d*\s*[a-z%]*', text)
    alnum_matches = re.findall(r'\b[\w\-]{2,}\b', text)
    items = set()
    for n in number_matches + alnum_matches:
        cleaned = re.sub(r'[^a-z0-9]', '', n)
        if cleaned:
            items.add(cleaned)
    return items

# Compare rule lines with plan text
def get_missing_rule_lines(rule_lines, plan_text):
    plan_tokens = extract_check_items_robust(plan_text)
    normalized_plan_tokens = {normalize_token(t) for t in plan_tokens}

    missing_lines = []

    for line in rule_lines:
        rule_tokens = re.findall(r'\b[\w\-\+\.]+\b', line)
        if any(normalize_token(token) not in normalized_plan_tokens for token in rule_tokens):
            missing_lines.append(line)

    return missing_lines

# Load history for a requirement
def load_history(requirement_id):
    if not os.path.exists(HISTORY_DIR):
        return ""
    history_files = [f for f in os.listdir(HISTORY_DIR) if f.startswith(requirement_id)]
    history_texts = []
    for file in history_files:
        with open(os.path.join(HISTORY_DIR, file), "r") as f:
            history_texts.append(f.read())
    return "\n".join(history_texts)

# Save history for a requirement
def save_history(requirement_id, missing_rule_lines, plan_text, ai_suggestions):
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    history_file = os.path.join(HISTORY_DIR, f"{requirement_id}_{timestamp}.txt")
    with open(history_file, "w") as f:
        f.write("Rule Lines:\n" + "\n".join(missing_rule_lines) + "\n\n")
        f.write("Proposed Plan:\n" + plan_text + "\n\n")
        f.write("AI Suggestions:\n" + "\n".join(ai_suggestions))

# Get AI suggestions
def get_ai_suggestions(plan_text, missing_rule_lines, requirement_id):
    if not missing_rule_lines:
        return []

    history_context = load_history(requirement_id)

    system_prompt = """
You are an engineering test coverage assistant.
Analyze the proposed test plan and provide actionable suggestions for missing coverage.
Do not include items already covered.
Provide concise bullet points.
"""

    user_prompt = f"""
Proposed test plan:
{plan_text}

Missing rule lines:
{chr(10).join(missing_rule_lines)}

History of previous analyses for this requirement:
{history_context}
"""

    try:
        response = client.chats.create(model="gemini-1.5-flash")
        response.send_message(user_prompt)
        ai_text = response.get_response().text
        suggestions = [line.strip("- ").strip() for line in ai_text.split("\n") if line.strip()]

        save_history(requirement_id, missing_rule_lines, plan_text, suggestions)

        return suggestions
    except Exception as e:
        return [f"AI suggestion failed: {e}"]

# Main UI
df = read_requirements_file()

if df is not None:
    df.columns = [str(col).strip() for col in df.columns]

    try:
        requirement_ids = df.iloc[:, 0].astype(str).tolist()
        descriptions = df.iloc[:, 2].astype(str).tolist()
    except IndexError:
        st.error("Requirements file must have at least 3 columns (ID, ..., Description).")
        st.stop()

    id_to_description = {rid.upper(): desc for rid, desc in zip(requirement_ids, descriptions)}

    user_input = st.text_input("Enter the Requirement ID (e.g. DS-1):").strip().upper()
    valid_id = False

    if user_input:
        if user_input in id_to_description:
            valid_id = True
            st.success(f"**{user_input}**\n\n**Description:** {id_to_description[user_input]}")
        else:
            st.error("No match found for that Requirement ID.")

    if valid_id:
        uploaded_plan_file = st.file_uploader(
            "Upload Proposed Test Plan (.docx or .txt)", 
            type=["docx", "txt"]
        )

        if uploaded_plan_file:
            if uploaded_plan_file.name.endswith(".docx"):
                plan_lines = docx_to_text(uploaded_plan_file)
            else:
                try:
                    plan_lines = uploaded_plan_file.read().decode("utf-8").splitlines()
                except UnicodeDecodeError:
                    plan_lines = uploaded_plan_file.read().decode("latin1").splitlines()

            plan_text = "\n".join(plan_lines)

            if st.button("Analyze Test Plan"):
                with st.spinner("Analyzing test plan..."):
                    rule_lines = load_rules_for_requirement(user_input)
                    missing_lines = get_missing_rule_lines(rule_lines, plan_text) if rule_lines else []

                    st.markdown("## Your Proposed Test Plan")
                    for line in plan_lines:
                        if line.strip():
                            st.markdown(f"- {line.strip()}")

                    st.markdown("## Based on past Test Cases"
                    if missing_lines:
                        for line in missing_lines:
                            st.markdown(f"- {line}")
                    else:
                        st.success("All rule lines are fully covered in the proposed plan!")

                    ai_suggestions = get_ai_suggestions(plan_text, missing_lines, user_input)
                    if ai_suggestions:
                        st.markdown("## AI Suggestions")
                        for sug in ai_suggestions:
                            st.markdown(f"- {sug}")
