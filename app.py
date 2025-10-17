import streamlit as st
import pandas as pd
from docx import Document
import os
import re
import google.generativeai as genai

# ---------------- Streamlit Setup ----------------
st.set_page_config(page_title="RnD DVT Test Planner", layout="wide")
st.title("RnD DVT Test Planner")

# ---------------- Repo / API Config ----------------
REPO_PATH = "."  # Path to your linked repo
REQUIREMENTS_FILE = os.path.join(REPO_PATH, "dvt_requirements.csv")
HISTORY_DIR = os.path.join(REPO_PATH, "history")
os.makedirs(HISTORY_DIR, exist_ok=True)

# ---------------- Load API Key from Streamlit Secrets ----------------
try:
    api_key = st.secrets["google"]["api_key"]
    genai.api_key = api_key
except Exception as e:
    st.error("Google Gemini API key not found in Streamlit secrets. Please add it in .streamlit/secrets.toml")
    st.stop()

# ---------------- Read CSV ----------------
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

# ---------------- Word Parsing ----------------
def docx_to_text(file):
    doc = Document(file)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]

# ---------------- Load Rules ----------------
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

# ---------------- Token Normalization ----------------
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

# ---------------- Extract Tokens ----------------
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

# ---------------- Compare Rule Lines ----------------
def get_missing_rule_lines(rule_lines, plan_text):
    plan_tokens = extract_check_items_robust(plan_text)
    normalized_plan_tokens = {normalize_token(t) for t in plan_tokens}

    missing_lines = []

    for line in rule_lines:
        rule_tokens = re.findall(r'\b[\w\-\+\.]+\b', line)
        if any(normalize_token(token) not in normalized_plan_tokens for token in rule_tokens):
            missing_lines.append(line)

    return missing_lines

# ---------------- History / Simulated Learning ----------------
def load_history(requirement_id):
    if not os.path.exists(HISTORY_DIR):
        return ""
    history_files = [f for f in os.listdir(HISTORY_DIR) if f.startswith(requirement_id)]
    history_texts = []
    for file in history_files:
        with open(os.path.join(HISTORY_DIR, file), "r") as f:
            history_texts.append(f.read())
    return "\n".join(history_texts)

def save_history(requirement_id, missing_rule_lines, plan_text, ai_suggestions):
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    history_file = os.path.join(HISTORY_DIR, f"{requirement_id}_{timestamp}.txt")
    with open(history_file, "w") as f:
        f.write("Rule Lines:\n" + "\n".join(missing_rule_lines) + "\n\n")
        f.write("Proposed Plan:\n" + plan_text + "\n\n")
        f.write("AI Suggestions:\n" + "\n".join(ai_suggestions))

# ---------------- AI Suggestions with Gemini Chat ----------------
def get_ai_suggestions(plan_text, missing_rule_lines, requirement_id):
    if not missing_rule_lines:
        return []

    history_context = load_history(requirement_id)

    system_prompt = """
You are an engineering test coverage assistant.
Your task is to analyze a proposed test plan and provide actionable suggestions for missing coverage.
Do not include items already covered.
Be concise and provide suggestions as bullet points.
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
        response = genai.chat(
            model="chat-bison-1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_output_tokens=300
        )

        ai_text = response.last.response
        suggestions = [line.strip("- ").strip() for line in ai_text.split("\n") if line.strip()]

        save_history(requirement_id, missing_rule_lines, plan_text, suggestions)

        return suggestions
    except Exception as e:
        return [f"AI suggestion failed: {e}"]

# ---------------- Main UI ----------------
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
                    # Load rule lines
                    rule_lines = load_rules_for_requirement(user_input)
                    missing_lines = get_missing_rule_lines(rule_lines, plan_text) if rule_lines else []

                    # --- Display Proposed Test Plan
                    st.markdown("## Your Proposed Test Plan")
                    for line in plan_lines:
                        if line.strip():
                            st.markdown(f"- {line.strip()}")

                    # --- Display Rule-Based Missing Lines
                    st.markdown("## Rule-Based Missing Lines")
                    if missing_lines:
                        for line in missing_lines:
                            st.markdown(f"- {line}")
                    else:
                        st.success("All rule lines are fully covered in the proposed plan!")

                    # --- AI Suggestions
                    ai_suggestions = get_ai_suggestions(plan_text, missing_lines, user_input)
                    if ai_suggestions:
                        st.markdown("## AI Suggestions for Better Test Coverage")
                        for sug in ai_suggestions:
                            st.markdown(f"- {sug}")
