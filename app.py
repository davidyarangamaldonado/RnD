import streamlit as st
import pandas as pd
from docx import Document
import os
import re

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

# ---------------- Utility ----------------
def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s\d\-]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text)         # Normalize whitespace
    return text.strip()

# ---------------- Robust Smart Comparison ----------------
def extract_check_items_robust(text):
    """
    Extracts:
    - Numbers with optional units (e.g., 25C, -30C, 5GHz)
    - Alphanumeric items (e.g., 256-QAM)
    - Meaningful phrases (words longer than 2 letters)
    Returns a set of normalized items.
    """
    text = text.lower()
    
    # Find numbers with optional units, signed numbers
    number_matches = re.findall(r'-?\d+\.?\d*\w*', text)
    
    # Find alphanumeric combos (like 256-QAM)
    alnum_matches = re.findall(r'\b[\w\-]{2,}\b', text)
    
    # Combine and normalize
    items = set()
    for n in number_matches + alnum_matches:
        cleaned = re.sub(r'[^\w\d\-]', '', n)
        if cleaned:
            items.add(cleaned)
    return items


def compare_rule_to_plan_robust(rule_text, plan_text):
    """
    Granular comparison:
    - Splits each rule line into multiple check items.
    - Marks 'covered' only if all items are present in proposed plan.
    - Returns list of tuples: (rule_line, status, missing_items_list)
    """
    # Normalize entire plan text once
    plan_items = extract_check_items_robust(plan_text)

    rule_lines = [line.strip() for line in rule_text.split("\n") if line.strip()]
    results = []

    for rline in rule_lines:
        rule_items = extract_check_items_robust(rline)
        missing_items = [item for item in rule_items if item not in plan_items]
        status = "covered" if not missing_items else "missing"
        results.append((rline, status, missing_items))

    return results

# ---------------- AI Suggestions Placeholder ----------------
def get_ai_suggestions(plan_text, missing_items):
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
                plan_text = docx_to_text(uploaded_plan_file)
            else:
                try:
                    plan_text = uploaded_plan_file.read().decode("utf-8")
                except UnicodeDecodeError:
                    plan_text = uploaded_plan_file.read().decode("latin1")

            # --- Display Proposed Test Plan nicely
            st.markdown("## Your Proposed Plan")
            plan_lines = [line.strip() for line in plan_text.split("\n") if line.strip()]
            for line in plan_lines:
                st.markdown(f"- {line}")

            if st.button("Analyze Test Plan"):
                with st.spinner("Analyzing test plan..."):
                    rule_text = load_rules_for_requirement(user_input)

                    if not rule_text:
                        st.warning(f"Rule.docx missing")
                    else:
                        # --- Robust smart comparison
                        comparison_results = compare_rule_to_plan_robust(rule_text, plan_text)

                        # --- Display Legend
                        st.markdown("## Legend")
                        st.markdown("<span style='color:green'>✅ Covered: Rule item is fully addressed in the proposed plan</span>", unsafe_allow_html=True)
                        st.markdown("<span style='color:red'>❌ Missing: Rule item is not addressed in the proposed plan</span>", unsafe_allow_html=True)

                        # --- Display Test Coverage Suggestions (color-only highlight)
                        st.markdown("## Test Coverage Suggestions")
                        for item, status, _ in comparison_results:  # ignore missing tokens
                            if status == "covered":
                                st.markdown(f"<span style='color:green'>✅ {item}</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<span style='color:red'>❌ {item}</span>", unsafe_allow_html=True)

                        # --- AI-based suggestions placeholder
                        missing_items = [mi for _, status, mi_list in comparison_results if status == "missing" for mi in mi_list]
                        ai_output = get_ai_suggestions(plan_text, missing_items)
                        for suggestion in ai_output:
                            st.markdown(suggestion)
