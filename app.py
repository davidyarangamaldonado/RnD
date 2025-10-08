import streamlit as st
import pandas as pd
import os
from docx import Document  # for reading Word docs

st.set_page_config(page_title="ERM4 DVT Test Planner", layout="centered")
st.title("ERM4 DVT Test Planner")

# File must be in your GitHub repo
REQUIREMENTS_FILE = "dvt_requirements.csv"  # or .xlsx if you're using Excel

def load_description_from_file(req_id):
    for ext in [".docx", ".txt"]:
        filename = f"{req_id}{ext}"
        if os.path.exists(filename):
            if ext == ".docx":
                try:
                    doc = Document(filename)
                    full_text = [para.text for para in doc.paragraphs]
                    return "\n\n".join(full_text)
                except Exception as e:
                    st.error(f"Error reading Word document: {e}")
                    return None
            else:  # .txt file
                try:
                    with open(filename, "r", encoding="utf-8") as file:
                        return file.read()
                except Exception as e:
                    st.error(f"Error reading text file: {e}")
                    return None
    return None

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

# Load and prepare data
df = read_requirements_file()

if df is not None:
    df.columns = [str(col).strip() for col in df.columns]

    try:
        requirement_ids = df.iloc[:, 0].astype(str).tolist()
        descriptions = df.iloc[:, 2].astype(str).tolist()
    except IndexError:
        st.error("File must have at least 3 columns (ID in col 1, Description in col 3).")
        st.stop()

    # Create a dictionary with uppercase keys for case-insensitive matching
    id_to_description = {rid.upper(): desc for rid, desc in zip(requirement_ids, descriptions)}

    user_input = st.text_input("Enter the Requirement ID (e.g. FREQ-1):").strip()

    if user_input:
        user_input_upper = user_input.upper()
        if user_input_upper in id_to_description:
            matched_description = id_to_description[user_input_upper]
            st.success(f"**{user_input}**\n\n**Description:** {matched_description}")

            test_description = load_description_from_file(user_input_upper)

            if test_description:
                st.subheader("DVT Test Description")
                st.markdown(test_description)
            else:
                st.warning(f"No `.docx` or `.txt` file found for `{user_input}` (expected `{user_input_upper}.docx` or `{user_input_upper}.txt`)")
        else:
            st.error("No match found for that Requirement ID.")
else:
    st.error("Could not load the requirements file from the repository.")

