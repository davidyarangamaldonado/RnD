import streamlit as st
import pandas as pd
import os
from docx import Document
import mammoth  # For converting .docx to HTML

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Design verification testing (DVT) Test Planner", layout="centered")
st.markdown("""
    <style>
        .reportview-container .main {
            font-family: "Times New Roman", Times, serif;
            font-size: 16px;
            line-height: 1.6;
        }
        h1, h2, h3 {
            color: #003366;
        }
        pre {
            white-space: pre-wrap;
            font-family: "Courier New", Courier, monospace;
        }
    </style>
""", unsafe_allow_html=True)

st.title("ERM4 DVT Test Planner")

# --- Requirements file ---
REQUIREMENTS_FILE = "dvt_requirements.csv"  # Or .xlsx if needed

# --- Load Description from .docx or .txt ---
def load_description_from_file(req_id):
    """Loads .docx or .txt file with formatting preserved."""
    for ext in [".docx", ".txt"]:
        filename = f"{req_id}{ext}"
        if os.path.isfile(filename):
            try:
                if ext == ".docx":
                    with open(filename, "rb") as docx_file:
                        result = mammoth.convert_to_html(docx_file)
                        return result.value  # HTML content
                else:
                    with open(filename, "r", encoding="utf-8") as file:
                        return f"<pre>{file.read()}</pre>"
            except Exception as e:
                return f"<p style='color:red;'>Error reading {ext} file: {e}</p>"
    return None

# --- Read Requirements File ---
def read_requirements_file():
    try:
        if REQUIREMENTS_FILE.endswith(".csv"):
            return pd.read_csv(REQUIREMENTS_FILE)
        elif REQUIREMENTS_FILE.endswith(".xlsx"):
            return pd.read_excel(REQUIREMENTS_FILE, engine="openpyxl")
        elif REQUIREMENTS_FILE.endswith(".xls"):
            return pd.read_excel(REQUIREMENTS_FILE, engine="xlrd")
        else:
            st.error("Unsupported file format.")
            return None
    except Exception as e:
        st.error(f"Failed to read requirements file: {e}")
        return None

# --- Load and Process Data ---
df = read_requirements_file()

if df is not None:
    df.columns = [str(col).strip() for col in df.columns]

    try:
        requirement_ids = df.iloc[:, 0].astype(str).tolist()
        descriptions = df.iloc[:, 2].astype(str).tolist()
    except IndexError:
        st.error("File must have at least 3 columns (ID in col 1, Description in col 3).")
        st.stop()

    id_to_description = {rid.upper(): desc for rid, desc in zip(requirement_ids, descriptions)}

    # --- User Input ---
    user_input = st.text_input("Enter the Requirement ID (e.g. FREQ-1):").strip()

    if user_input:
        user_input_upper = user_input.upper()
        if user_input_upper in id_to_description:
            matched_description = id_to_description[user_input_upper]
            st.success(f"**{user_input}**\n\n**Description:** {matched_description}")

            test_description = load_description_from_file(user_input_upper)

            if test_description:
                st.subheader("DVT Test Description")
                st.markdown(test_description, unsafe_allow_html=True)
            else:
                st.warning(
                    f"No `.docx` or `.txt` file found for `{user_input}` "
                    f"(expected `{user_input_upper}.docx` or `{user_input_upper}.txt`)."
                )
        else:
            st.error("No match found for that Requirement ID.")
else:
    st.error("Could not load the requirements file from the repository.")


