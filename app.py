import streamlit as st
import pandas as pd
from docx import Document
from io import BytesIO
import openai

# ---------------- Streamlit Setup ----------------
st.set_page_config(page_title="DVT Test Planner - Rule + AI", layout="wide")
st.title("DVT Test Planner with Rule-Based + AI Coverage Analysis")

# ---------------- File Config ----------------
REQUIREMENTS_FILE = "dvt_requirements.csv"   # CSV in your repo/local

# ---------------- Read Requirements ----------------
def read_requirements_file():
    try:
        if REQUIREMENTS_FILE.endswith(".csv"):
            return pd.read_csv(REQUIREMENTS_FILE)
        elif REQUIREMENTS_FILE.endswith(".xlsx"):
            return pd.read_excel(REQUIREMENTS_FILE, engine="openpyxl")
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

# ---------------- Load Rules ----------------
def load_rules_for_requirement(requirement_id, uploaded_file=None):
    """Use uploaded rule file if provided, otherwise return empty"""
    if uploaded_file:
        doc = Document(uploaded_file)
        return "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    # If no uploaded file, return empty (no GitHub fetching here)
    return ""

# ---------------- Rule-Based Analysis ----------------
def analyze_rule_based(plan_text, requirement_id, taxonomy_rule):
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
    output += "### Uploaded Test Plan\n"
    output += "\n".join(plan_lines) + "\n\n"

    output += "### Rule-Based Analysis:\n"
    output += f"**Covered Tests:** {', '.join(covered) if covered else 'None'}\n"
    output += f"**Missing Tests:** {', '.join(missing) if missing else 'None'}\n"

    if missing:
        output += "\n### Suggestions (Rule-Based):\n"
        for m in missing:
            output += f"- Add test steps to cover: {m}\n"
    else:
        output += "\nAll taxonomy rules are covered. No additional tests needed.\n"

    return output, missing

# ---------------- AI-Based Suggestions ----------------
def get_ai_suggestions(plan_text, missing_tests):
    if not st.session_state.get("OPENAI_API_KEY"):
        return "_AI suggestions not available. Please configure your API key._"

    try:
        openai.api_key = st.session_state["OPENAI_API_KEY"]
        prompt = f"""
        You are an expert test engineer. A proposed test plan is given below:

        {plan_text}

        The following important tests appear to be missing: {', '.join(missing_tests)}.

        Suggest additional detailed test cases or improvements that would strengthen the coverage.
        """

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a senior test engineer."},
                      {"role": "user", "content": prompt}],
            max_tokens=400
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"_AI suggestion failed: {e}_"

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

    # --- API Key input
    st.sidebar.subheader("🔑 OpenAI API Key")
    api_key_input = st.sidebar.text_input("Enter API Key:", type="password")
    if api_key_input:
        st.session_state["OPENAI_API_KEY"] = api_key_input

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
        # --- Rule File uploader
        uploaded_rule_file = st.file_uploader(
            "Upload Rule File (.docx) for this Requirement ID",
            type=["docx"]
        )

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
                    taxonomy_rule = load_rules_for_requirement(user_input, uploaded_file=uploaded_rule_file)
                    if not taxonomy_rule:
                        st.warning(f"⚠️ No rules found for {user_input}. Please upload a rule file.")
                    analysis_output, missing_tests = analyze_rule_based(plan_text, user_input, taxonomy_rule)
                    st.markdown(analysis_output)

                    if missing_tests:
                        st.markdown("### AI-Based Suggestions:")
                        ai_output = get_ai_suggestions(plan_text, missing_tests)
                        st.markdown(ai_output)
else:
    st.error("Could not load the requirements file.")
