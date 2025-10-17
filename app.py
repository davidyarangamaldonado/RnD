import streamlit as st
import pandas as pd
from docx import Document
import os

# ---------------- Streamlit Setup ----------------
st.set_page_config(page_title="RnD DVT Test Planner", layout="wide")
st.title("RnD DVT Test Planner")

# ---------------- Repo Config ----------------
REPO_PATH = "."  # Path to your linked repo
REQUIREMENTS_FILE = os.path.join(REPO_PATH, "dvt_requirements.csv")

# ---------------- Read Requirements CSV ----------------
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
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

# ---------------- Load Rules ----------------
def load_rules_for_requirement(requirement_id):
    rule_file = os.path.join(REPO_PATH, f"{requirement_id}_Rule.docx")
    if os.path.exists(rule_file):
        doc = Document(rule_file)
        return "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    else:
        st.warning(f"No rules file found for {requirement_id}")
        return ""

# ---------------- Compare Rule vs Plan ----------------
def compare_rule_to_plan(rule_text, plan_text):
    rule_lines = [line.strip() for line in rule_text.split("\n") if line.strip()]
    plan_lines = [line.strip().lower() for line in plan_text.split("\n") if line.strip()]

    missing_items = []
    for rline in rule_lines:
        rline_lower = rline.lower()
        if not any(rline_lower in pline for pline in plan_lines):
            missing_items.append(rline)

    # Format as bullet points
    if missing_items:
        output = [f"- {item}" for item in missing_items]
    else:
        st.warning(f"Rule.docx missing")

    return output, missing_items

# ---------------- AI Suggestions Placeholder ----------------
def get_ai_suggestions(missing_items):
    # Placeholder: AI not yet configured
    if missing_items:
        return ["- AI suggestions not available. Please configure your API key"]
    else:
        return []

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

    # --- Requirement ID input
    user_input = st.text_input("Enter the Requirement ID (e.g. DS-1):").strip().upper()
    valid_id = False

    if user_input:
        if user_input in id_to_description:
            valid_id = True
            st.success(f"**{user_input}**\n\n**Description:** {id_to_description[user_input]}")
        else:
            st.error("No match found for that Requirement ID.")

    if valid_id:
        # --- Test Plan uploader
        uploaded_plan_file = st.file_uploader(
            "Upload Proposed Test Plan (.docx or .txt)", 
            type=["docx", "txt"]
        )

        if uploaded_plan_file:
            if uploaded_plan_file.name.endswith(".docx"):
                plan_text = docx_to_text(uploaded_plan_file)
            else:
                plan_text = uploaded_plan_file.read().decode("utf-8")

            if st.button("Analyze Test Plan"):
                with st.spinner("Analyzing test plan..."):
                    # Load rule from repo automatically
                    rule_text = load_rules_for_requirement(user_input)
                    else:
                        st.warning(f"Rule.docx missing")
                       
                    # --- Rule-based missing items
                    rule_output, missing_items = compare_rule_to_plan(rule_text, plan_text)

                    # --- AI-based suggestions placeholder
                    ai_output = get_ai_suggestions(missing_items)

                    # --- Combined Test Coverage Suggestions
                    st.markdown("## Test Coverage Suggestions")
                    for item in rule_output + ai_output:
                        st.markdown(item)
