import os
import re
import pandas as pd
import streamlit as st
from docx import Document
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

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
if not api_key:
    st.error(
        "Google Gemini API key not found.\n\n"
        "Make sure you either:\n"
        "1. Add it in `.streamlit/secrets.toml` as:\n"
        "   [google_gemini]\n"
        "   api_key = \"YOUR_API_KEY\"\n"
        "OR\n"
        "2. Set the environment variable `GOOGLE_API_KEY`."
    )
    st.stop()

genai.configure(api_key=api_key)

# ---------------- File Readers ----------------
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
    else:
        token = re.sub(r'[^a-z0-9]', '', token)
        return token

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

# ---------------- AI Suggestions (POC with first online insight) ----------------
@st.cache_data(show_spinner=False)
def get_ai_suggestions_with_online(plan_text, missing_rule_lines, requirement_id):
    history_context = load_history(requirement_id)

    # Try fetching first online resource
    online_snippet = ""
    try:
        keywords = re.findall(r'\b\w{4,}\b', plan_text.lower())[:5]
        for keyword in keywords:
            query = f"{keyword} testing best practices"
            resp = requests.get(
                f"https://www.google.com/search?q={query}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=3
            )
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Take first link
            link = next((a.get('href').split('url?q=')[1].split('&')[0]
                         for a in soup.find_all('a') if a.get('href') and 'url?q=' in a.get('href')), None)
            if link:
                page_resp = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
                page_soup = BeautifulSoup(page_resp.text, 'html.parser')
                online_snippet = ' '.join(p.get_text() for p in page_soup.find_all('p'))[:1000]
                break
    except Exception:
        online_snippet = ""

    system_prompt = """
You are an engineering test coverage assistant.
Analyze the proposed test plan and provide actionable suggestions to improve test coverage.
Do not include items already covered.
Provide concise bullet points.
"""

    user_prompt = f"""
Proposed test plan:
{plan_text}

Missing rule lines:
{chr(10).join(missing_rule_lines) if missing_rule_lines else 'None'}

History of previous analyses:
{history_context if history_context else 'None'}

Online snippet (if available):
{online_snippet if online_snippet else 'None'}
"""

    try:
        response = genai.generate_text(
            model="gemini-2.5-flash-lite",
            prompt=system_prompt + "\n" + user_prompt,
            temperature=0.2
        )
        ai_text = response.result[0].content[0].text
        suggestions = [line.strip("- ").strip() for line in ai_text.split("\n") if line.strip()]
        if not suggestions:
            suggestions = ["AI suggestion failed"]
        save_history(requirement_id, missing_rule_lines, plan_text, suggestions)
        return suggestions
    except Exception:
        return ["AI suggestion failed"]

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

                    # Run AI suggestions (POC)
                    ai_suggestions = get_ai_suggestions_with_online(plan_text, missing_lines, user_input)
                    st.markdown("## AI Suggestions (Proof of Concept with Online Insight)")
                    for suggestion in ai_suggestions:
                        st.markdown(f"- {suggestion}")
