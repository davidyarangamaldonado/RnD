import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="ERM4 DVT Test Planner", layout="centered")
st.title("ERM4 DVT Test Planner")

REQUIREMENTS_FILE = "dvt_requirements.csv"  # update if you use xlsx

def load_description_from_file(req_id):
    filename = f"{req_id}.txt"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as file:
            return file.read()
    return None

def read_requirements_file():
    try:
        if REQUIREMENTS_FILE.endswith(".csv"):
            df = pd.read_csv(REQUIREMENTS_FILE)
        elif REQUIREMENTS_FILE.endswith(".xlsx"):
            df = pd.read_excel(REQUIREMENTS_FILE, engine="openpyxl")
        elif REQUIREMENTS_FILE.endswith(".xls"):
            df = pd.read_excel(REQUIREMENTS_FILE, engine="xlrd")
        else:
            st.error("Unsupported file format.")
            return None
        st.write("### Loaded DataFrame preview:")
        st.dataframe(df.head())  # Show first few rows so you can verify it's loaded
        return df
    except Exception as e:
        st.error(f"Failed to read requirements file: {e}")
        return None

df = read_requirements_file()

if df is not None:
    # Strip spaces from column headers
    df.columns = [str(col).strip() for col in df.columns]
    st.write("### Columns detected:", df.columns.tolist())

    # Check if df has at least 3 columns
    if df.shape[1] < 3:
        st.error("The file must have at least 3 columns (Requirement_ID in first, Description in third).")
        st.stop()

    # Extract columns safely
    try:
        requirement_ids = df.iloc[:, 0].astype(str).tolist()
        descriptions = df.iloc[:, 2].astype(str).tolist()
    except Exception as e:
        st.error(f"Error reading columns: {e}")
        st.stop()

    # Show a sample of IDs and descriptions to verify extraction
    st.write("### Sample Requirement IDs:", requirement_ids[:5])
    st.write("### Sample Descriptions:", descriptions[:5])

    # Map Requirement_ID to Description
    id_to_description = dict(zip(requirement_ids, descriptions))

    user_input = st.text_input("Enter the Requirement ID (e.g. FREQ-1):").strip()

    if user_input:
        if user_input in id_to_description:
            matched_description = id_to_description[user_input]
            st.success(f"**{user_input}**\n\n**Description:** {matched_description}")

            test_description = load_description_from_file(user_input)

            if test_description:
                st.subheader("DVT Test Description")
                st.markdown(test_description)
            else:
                st.warning(f"No `.txt` file found for `{user_input}` (expected `{user_input}.txt`)")
        else:
            st.error("No match found for that Requirement ID.")
else:
    st.error("Could not load the requirements file.")
