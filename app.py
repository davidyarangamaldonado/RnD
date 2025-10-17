import streamlit as st
import pandas as pd
from docx import Document
import os
import openai

# ---------------- Streamlit Setup ----------------
st.set_page_config(page_title="DVT Test Planner - Rule + AI", layout="wide")
st.title("DVT Test Planner with Rule-Based + AI Coverage Analysis")

# ---------------- Repo Config ----------------
# Set this to the path where your linked GitHub repo is mounted
REPO_PATH = "."  # If the repo is cloned at the root of the app environment
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
        st.warning(f"No rules file found for {requirement_id} at {rule_file}")
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
                    taxonomy_rule = load_rules_for_requirement(user_input)
                    if not taxonomy_rule:
                        st.warning(f"⚠️ No rules found for {user_input}. Check that the rule file exists in your repo.")
                    analysis_output, missing_tests = analyze_rule_based(plan_text, user_input, taxonomy_rule)
                    st.markdown(analysis_output)

                    if missing_tests:
                        st.markdown("### AI-Based Suggestions:")
                        ai_output = get_ai_suggestions(plan_text, missing_tests)
                        st.markdown(ai_output)
else:
    st.error("Could not load the requirements file from the repo.")
