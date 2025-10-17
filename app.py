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
def normalize_token(token):
    """
    Normalize a token to handle:
    - Modulation formats like 256-QAM vs 256QAM
    - Numeric values with units like 25C vs 25 °C
    """
    token = token.lower()
    
    # Separate number + optional unit
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

# ---------------- Extract Engineering/Test Parameters ----------------
def extract_check_items_robust(text):
    """
    Extracts numeric values, units, modulation orders, and alphanumeric test parameters.
    """
    text = text.lower()
    # Numbers with optional units
    number_matches = re.findall(r'-?\d+\.?\d*\s*[a-z%]*', text)
    # Alphanumeric combos (modulation, OFDM, etc.)
    alnum_matches = re.findall(r'\b[\w\-]{2,}\b', text)
    
    items = set()
    for n in number_matches + alnum_matches:
        cleaned = re.sub(r'[^a-z0-9]', '', n)
        if cleaned:
            items.add(cleaned)
    return items

# ---------------- Robust Rule Comparison ----------------
def compare_rule_to_plan_robust(rule_text, plan_text):
    plan_items = extract_check_items_robust(plan_text)
    normalized_plan_items = {normalize_token(t) for t in plan_items}

    rule_lines = [line.strip() for line in rule_text.split("\n") if line.strip()]
    results = []

    for rline in rule_lines:
        rule_items = extract_check_items_robust(rline)
        missing_items = [item for item in rule_items if normalize_token(item) not in normalized_plan_items]
        status = "covered" if not missing_items else "missing"
        results.append((rline, status, missing_items))

    return results

# ---------------- AI Suggestions Placeholder ----------------
def get_ai_suggestions(plan_text, missing_items):
    if missing_items:
        # Return each missing item as an actionable bullet point
        return [f"Missing parameter: {mi}" for mi in missing_items]
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

            # Display Proposed Test Plan
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
                        # --- Compare rules to plan
                        comparison_results = compare_rule_to_plan_robust(rule_text, plan_text)

                        # --- Legend
                        st.markdown("## Legend")
                        st.markdown("<span style='color:green'>✅ Covered: Parameter is addressed in the proposed plan</span>", unsafe_allow_html=True)
                        st.markdown("<span style='color:red'>❌ Missing: Parameter is not addressed in the proposed plan</span>", unsafe_allow_html=True)

                        # --- Test Coverage Suggestions (bullets)
                        st.markdown("## Test Coverage Suggestions")
                        plan_tokens = extract_check_items_robust(plan_text)
                        normalized_plan_items = {normalize_token(t) for t in plan_tokens}

                        # Rule-based suggestions
                        for item, status, missing_tokens in comparison_results:
                            tokens = re.findall(r'\b[\w\-\+\.]+\b', item)
                            highlighted_line = item
                            for token in tokens:
                                if normalize_token(token) in normalized_plan_items:
                                    highlighted_line = re.sub(
                                        rf'\b{re.escape(token)}\b',
                                        f"<span style='color:green'>{token}</span>",
                                        highlighted_line,
                                        flags=re.IGNORECASE
                                    )
                                else:
                                    highlighted_line = re.sub(
                                        rf'\b{re.escape(token)}\b',
                                        f"<span style='color:red'>{token}</span>",
                                        highlighted_line,
                                        flags=re.IGNORECASE
                                    )
                            st.markdown(f"- {highlighted_line}", unsafe_allow_html=True)

                        # AI-based suggestions
                        missing_items = [mi for _, status, mi_list in comparison_results if status == "missing" for mi in mi_list]
                        ai_output = get_ai_suggestions(plan_text, missing_items)
                        for suggestion in ai_output:
                            st.markdown(f"- {suggestion}")
