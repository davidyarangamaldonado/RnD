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

# ---------------- Token Normalization ----------------
def normalize_token(token):
    """Normalize numeric/unit and alphanumeric engineering parameters."""
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

# ---------------- Extract Engineering/Test Parameters ----------------
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
                        comparison_results = compare_rule_to_plan_robust(rule_text, plan_text)

                        # --- Legend
                        st.markdown("## Legend")
                        st.markdown("<span style='color:green'>✅ Covered: Parameter addressed in plan</span>", unsafe_allow_html=True)
                        st.markdown("<span style='color:red'>❌ Missing: Parameter not addressed in plan</span>", unsafe_allow_html=True)

                        # --- Highlighted rule lines (green/red inline)
                        st.markdown("## Rule Coverage Highlights")
                        plan_tokens = extract_check_items_robust(plan_text)
                        normalized_plan_items = {normalize_token(t) for t in plan_tokens}

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

                        # --- Test Coverage Suggestions (only missing items)
                        st.markdown("## Test Coverage Suggestions (Missing Parameters Only)")
                        missing_params = set()
                        for _, status, missing_tokens in comparison_results:
                            for token in missing_tokens:
                                missing_params.add(token)

                        for token in sorted(missing_params):
                            st.markdown(f"- {token}")
