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
    text = re.sub(r'[^\w\s\d]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text)       # Normalize whitespace
    return text.strip()

# ---------------- Smart Comparison (Covered / Missing) ----------------
def compare_rule_to_plan_smart(rule_text, plan_text):
    """
    Smart comparison: check each rule line if it is fully covered somewhere in the proposed plan.
    Only two statuses: covered ✅ and missing ❌
    """
    plan_norm = normalize_text(plan_text)
    rule_lines = [line.strip() for line in rule_text.split("\n") if line.strip()]
    results = []

    for rline in rule_lines:
        rline_norm = normalize_text(rline)

        # Extract numbers and words
        numbers_in_rline = re.findall(r'\d+\.?\d*', rline_norm)
        words_in_rline = [w for w in rline_norm.split() if not w.isdigit()]

        all_matched = True

        # Check numbers
        for num in numbers_in_rline:
            if num not in plan_norm:
                all_matched = False
                break

        # Check words
        if all_matched:
            for word in words_in_rline:
                if word not in plan_norm:
                    all_matched = False
                    break

        status = "covered" if all_matched else "missing"
        results.append((rline, status))

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
                plan_text = uploaded_plan_file.read().decode("utf-8")

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
                        # --- Smart comparison
                        comparison_results = compare_rule_to_plan_smart(rule_text, plan_text)

                        # --- Display Legend
                        st.markdown("## Legend")
                        st.markdown("<span style='color:green'>✅ Covered: Rule item is fully addressed in the proposed plan</span>", unsafe_allow_html=True)
                        st.markdown("<span style='color:red'>❌ Missing: Rule item is not addressed in the proposed plan</span>", unsafe_allow_html=True)

                        # --- Display Test Coverage Suggestions
                        st.markdown("## Test Coverage Suggestions")
                        for item, status in comparison_results:
                            if status == "covered":
                                st.markdown(f"<span style='color:green'>✅ {item}</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<span style='color:red'>❌ {item}</span>", unsafe_allow_html=True)

                        # --- AI-based suggestions placeholder
                        missing_items = [item for item, status in comparison_results if status == "missing"]
                        ai_output = get_ai_suggestions(plan_text, missing_items)
                        for suggestion in ai_output:
                            st.markdown(suggestion)
