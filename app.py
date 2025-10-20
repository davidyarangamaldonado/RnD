import os
import re
import pandas as pd
import streamlit as st
from docx import Document
import google.generativeai as genai
import traceback

# ---------------- Streamlit Setup ----------------
st.set_page_config(page_title="RnD DVT Test Planner", layout="wide")
st.title("RnD DVT Test Planner")

# ---------------- Repo Config ----------------
REPO_PATH = "."
REQUIREMENTS_FILE = os.path.join(REPO_PATH, "dvt_requirements.csv")
HISTORY_DIR = os.path.join(REPO_PATH, "history")
os.makedirs(HISTORY_DIR, exist_ok=True)

# ---------------- API Key Loader ----------------
def load_api_key():
    if hasattr(st, "secrets"):
        api_key = st.secrets.get("google_gemini", {}).get("api_key")
        if api_key:
            return api_key
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return api_key
    return None

api_key = load_api_key()
if api_key:
    genai.configure(api_key=api_key)
else:
    st.warning(
        "Google Gemini API key not found. AI suggestions will show 'AI suggestion failed'."
    )

# ---------------- File Readers ----------------
def read_requirements_file():
    if not os.path.exists(REQUIREMENTS_FILE):
        st.error(f"Requirements file not found at {REQUIREMENTS_FILE}")
        return None
    try:
        return pd.read_csv(REQUIREMENTS_FILE)
    except Exception as e:
        st.error(f"Failed to read requirements file: {e}")
        return None

def docx_to_text(file):
    doc = Document(file)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]

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
    return re.sub(r'[^a-z0-9]', '', token)

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

# ---------------- Comparison ----------------
def get_missing_rule_lines(rule_lines, plan_text):
    plan_tokens = extract_check_items_robust(plan_text)
    normalized_plan_tokens = {normalize_token(t) for t in plan_tokens}

    missing_lines = []
    for line in rule_lines:
        rule_tokens = re.findall(r'\b[\w\-\+\.]+\b', line)
        if any(normalize_token(token) not in normalized_plan_tokens for token in rule_tokens):
            missing_lines.append(line)
    return missing_lines

# ---------------- History ----------------
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

# ---------------- Gemini AI Suggestions with Error Logging ----------------
def get_gemini_suggestions(plan_text, missing_rule_lines, requirement_id):
    if not missing_rule_lines:
        return ["No missing rules; coverage complete"]

    chunks = [plan_text[i:i+1000] for i in range(0, len(plan_text), 1000)]
    all_suggestions = []

    for chunk in chunks:
        prompt = f"""
You are an engineering test coverage assistant.
Analyze the proposed test plan below and provide up to 3 concise suggestions to improve coverage.
Include a short reasoning for each suggestion.

Proposed Test Plan:
{chunk}

Missing Rules:
{chr(10).join(missing_rule_lines)}
"""
        try:
            if not api_key:
                return ["AI suggestion failed: No API key configured"]

            response = genai.generate_text(
                model="gemini-2.5-flash-lite",
                prompt=prompt,
                temperature=0.3,
                max_output_tokens=300
            )

            if response.result and len(response.result) > 0:
                ai_text = response.result[0].content[0].text
                suggestions = [line.strip("- ").strip() for line in ai_text.split("\n") if line.strip()]
                all_suggestions.extend(suggestions)
        except Exception as e:
            # Show the actual exception and traceback in UI
            tb = traceback.format_exc()
            return [f"AI suggestion failed: {str(e)}", f"Traceback: {tb}"]

    final_suggestions = list(dict.fromkeys(all_suggestions))[:3]
    return final_suggestions if final_suggestions else ["AI suggestion failed"]

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
                    rule_lines = load_rules_for_requirement(user_input)
                    missing_lines = get_missing_rule_lines(rule_lines, plan_text) if rule_lines else []

                    st.markdown("## Your Proposed Test Plan")
                    for line in plan_lines:
                        if line.strip():
                            st.markdown(f"- {line.strip()}")

                    st.markdown("## Based on Past Test Cases")
                    if missing_lines:
                        for line in missing_lines:
                            st.markdown(f"- {line}")
                    else:
                        st.success("All rule lines are fully covered in the proposed plan!")

                    # Run Gemini ChatGPT-style suggestions
                    ai_suggestions = get_gemini_suggestions(plan_text, missing_lines, user_input)
                    st.markdown("## AI Suggestions with Reasoning (Top 3)")
                    for suggestion in ai_suggestions:
                        st.markdown(f"- {suggestion}")
