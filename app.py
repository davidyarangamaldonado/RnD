import streamlit as st
import pandas as pd
from docx import Document
import json
from io import BytesIO
from PIL import Image
import openai

# ---------------- Streamlit Setup ----------------
st.set_page_config(page_title="DVT Test Planner with AI", layout="wide")
st.title("Design Verification Testing (DVT) Test Planner with AI Coverage Analysis")

# ---------------- Security Info Banner ----------------
st.info(
    "🔒 Your OpenAI API key is used securely. "
    "It is stored in Streamlit secrets and never exposed in the code or to other users."
)

# ---------------- OpenAI API Key ----------------
openai.api_key = st.secrets["openai"]["api_key"]

# ---------------- File Config ----------------
REQUIREMENTS_FILE = "dvt_requirements.csv"  # contains your taxonomy in column 4

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
    text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return text

def txt_to_text(file):
    return file.read().decode("utf-8")

# ---------------- JSON Structuring ----------------
def parse_plan_to_json(text):
    plan_dict = {"sections": []}
    lines = text.split("\n")
    current_section = {"title": "", "content": []}

    for line in lines:
        if line.strip() == "":
            continue
        if line.endswith(":"):  # treat as section header
            if current_section["title"]:
                plan_dict["sections"].append(current_section)
            current_section = {"title": line.strip(), "content": []}
        else:
            current_section["content"].append(line.strip())

    if current_section["title"]:
        plan_dict["sections"].append(current_section)

    return plan_dict

# ---------------- AI Coverage Analysis using OpenAI >=1.0.0 ----------------
def analyze_coverage_openai(plan_json, taxonomy_rules, model="gpt-4"):
    """
    Uses OpenAI >=1.0.0 chat API to analyze test coverage.
    """
    prompt = f"""
You are a senior validation engineer. A test plan in JSON format is given, along with the required test taxonomy.
Compare the test plan against the taxonomy and identify strengths, gaps, and suggestions.

Taxonomy of Required Tests:
{taxonomy_rules}

Proposed Test Plan (JSON):
{json.dumps(plan_json, indent=2)}

Respond with three sections:
1. Strengths (covered tests)
2. Gaps (missing tests)
3. Suggestions (improvements for full coverage)
"""
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error calling OpenAI API: {e}"

# ---------------- Main UI ----------------
df = read_requirements_file()
if df is not None:
    df.columns = [str(col).strip() for col in df.columns]

    try:
        requirement_ids = df.iloc[:, 0].astype(str).tolist()
        descriptions = df.iloc[:, 2].astype(str).tolist()
        taxonomy_col = df.iloc[:, 3].astype(str).tolist()  # taxonomy in column 4
    except IndexError:
        st.error("Requirements file must have at least 4 columns (ID, ..., Description, Taxonomy).")
        st.stop()

    id_to_description = {rid.upper(): desc for rid, desc in zip(requirement_ids, descriptions)}
    id_to_taxonomy = {rid.upper(): tax for rid, tax in zip(requirement_ids, taxonomy_col)}

    # User enters requirement ID
    user_input = st.text_input("Enter the Requirement ID (e.g. FREQ-1):").strip()
    user_input_upper = user_input.upper()

    valid_id = False
    if user_input_upper:
        if user_input_upper in id_to_description:
            valid_id = True
            st.success(f"**{user_input_upper}**\n\n**Description:** {id_to_description[user_input_upper]}")
        else:
            st.error("No match found for that Requirement ID.")

    # File uploader is disabled until a valid requirement ID is entered
    uploaded_file = st.file_uploader(
        "Upload Proposed Test Plan (.docx or .txt)", 
        type=["docx", "txt"], 
        disabled=not valid_id
    )

    # Proceed with coverage analysis only if both ID and file are provided
    if valid_id and uploaded_file:
        matched_description = id_to_description[user_input_upper]
        matched_taxonomy = id_to_taxonomy.get(user_input_upper, "No taxonomy found for this requirement.")

        # Extract text from file
        if uploaded_file.name.endswith(".docx"):
            plan_text = docx_to_text(uploaded_file)
        else:
            plan_text = txt_to_text(uploaded_file)

        # Parse to JSON
        plan_json = parse_plan_to_json(plan_text)

        st.subheader("Parsed Test Plan (JSON)")
        st.json(plan_json)

        # Run OpenAI Analysis
        if st.button("Analyze Test Coverage"):
            with st.spinner("Analyzing coverage with OpenAI..."):
                analysis = analyze_coverage_openai(plan_json, matched_taxonomy)
            st.subheader("AI Coverage Analysis")
            st.markdown(analysis)
else:
    st.error("Could not load the requirements file.")
