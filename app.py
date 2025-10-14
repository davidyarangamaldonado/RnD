import streamlit as st
import pandas as pd
from docx import Document
from io import BytesIO

# ---------------- Streamlit Setup ----------------
st.set_page_config(page_title="DVT Test Planner - Rule Based", layout="wide")
st.title("DVT Test Planner with Rule-Based Coverage Analysis")

# ---------------- File Config ----------------
REQUIREMENTS_FILE = "dvt_requirements.csv"  # taxonomy in column 4

# ---------------- Read Requirements ----------------
def read_requirements_file():
    try:
        if REQUIREMENTS_FILE.endswith(".csv"):
            return pd.read_csv(REQUIREMENTS_FILE)
        elif REQUIREMENTS_FILE.endswith(".xlsx"):
            return pd.read_excel(REQUIREMENTS_FILE, engine="openpyxl")
        elif REQUIREMENTS_FILE.endswith(".xls"):
            return pd.read_excel(REQUIREMENTS_FILE, engine="xlrd")
        else:
            st.error("Unsupported requirements file format.")
            return None
    except Exception as e:
        st.error(f"Failed to read requirements file: {e}")
        return None

# ---------------- Word Parsing ----------------
def docx_to_text(file):
    doc = Document(file)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def txt_to_text(file):
    return file.read().decode("utf-8")

# ---------------- Rule-Based Analysis ----------------
def analyze_rule_based(plan_text, requirement_id, taxonomy_rule):
    """
    Simulate AI coverage using column 4 rules:
    - Checks which keywords from taxonomy exist in the plan.
    - Outputs complete plan and suggestions for missing items.
    """
    plan_lines = [line.strip() for line in plan_text.split("\n") if line.strip()]
    taxonomy_keywords = [kw.strip() for kw in taxonomy_rule.split(",") if kw.strip()]
    
    covered = []
    missing = []

    for kw in taxonomy_keywords:
        if any(kw.lower() in line.lower() for line in plan_lines):
            covered.append(kw)
        else:
            missing.append(kw)

    output = f"**Requirement ID:** {requirement_id}\n\n"
    output += "### Complete Test Plan (from uploaded file)\n"
    output += "\n".join(plan_lines) + "\n\n"
    
    output += "### Analysis:\n"
    output += f"**Covered Tests:** {', '.join(covered) if covered else 'None'}\n"
    output += f"**Missing Tests:** {', '.join(missing) if missing else 'None'}\n"
    
    if missing:
        output += "\n### Suggestions:\n"
        for m in missing:
            output += f"- Add test steps to cover: {m}\n"
    else:
        output += "\nAll taxonomy rules are covered. No additional tests needed.\n"

    return output

# ---------------- Main UI ----------------
df = read_requirements_file()
if df is not None:
    df.columns = [str(col).strip() for col in df.columns]

    try:
        requirement_ids = df.iloc[:, 0].astype(str).tolist()
        descriptions = df.iloc[:, 2].astype(str).tolist()
        taxonomy_col = df.iloc[:, 3].astype(str).tolist()
    except IndexError:
        st.error("Requirements file must have at least 4 columns (ID, ..., Description, Taxonomy).")
        st.stop()

    id_to_description = {rid.upper(): desc for rid, desc in zip(requirement_ids, descriptions)}
    id_to_taxonomy = {rid.upper(): tax for rid, tax in zip(requirement_ids, taxonomy_col)}

    # User enters requirement ID
    user_input = st.text_input("Enter the Requirement ID (e.g. FREQ-1):").strip().upper()
    valid_id = False

    if user_input:
        if user_input in id_to_description:
            valid_id = True
            st.success(f"**{user_input}**\n\n**Description:** {id_to_description[user_input]}")
        else:
            st.error("No match found for that Requirement ID.")

    # File uploader
    uploaded_file = st.file_uploader(
        "Upload Proposed Test Plan (.docx or .txt)", 
        type=["docx", "txt"], 
        disabled=not valid_id
    )

    if valid_id and uploaded_file:
        if uploaded_file.name.endswith(".docx"):
            plan_text = docx_to_text(uploaded_file)
        else:
            plan_text = txt_to_text(uploaded_file)

        if st.button("Analyze Test Plan"):
            with st.spinner("Analyzing test plan against taxonomy..."):
                taxonomy_rule = id_to_taxonomy.get(user_input, "")
                analysis_output = analyze_rule_based(plan_text, user_input, taxonomy_rule)
            st.markdown(analysis_output)
else:
    st.error("Could not load the requirements file.")
