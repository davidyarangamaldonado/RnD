import streamlit as st
import pandas as pd
import os
from sentence_transformers import SentenceTransformer, util

# Load model once
@st.cache_resource
def load_model():
    return SentenceTransformer("paraphrase-MiniLM-L6-v2")

model = load_model()

st.set_page_config(page_title="ERM4 DVT Test Planner", layout="centered")
st.title("ERM4 DVT Test Planner")

# 🔁 Replace this with the actual file name in your GitHub repo
REQUIREMENTS_FILE = "dvt_requirements.csv"  # or .xlsx if needed

def load_description_from_file(req_id):
    """Load the test description from a .txt file based on the requirement ID"""
    filename = f"{req_id}.txt"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as file:
            return file.read()
    return None

def get_available_txt_ids():
    """Get all requirement IDs that have a .txt file in this folder"""
    return set(os.path.splitext(f)[0] for f in os.listdir() if f.endswith(".txt"))

def read_requirements_file():
    """Read requirements from CSV or Excel file in the repo"""
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

# Load data
df = read_requirements_file()

if df is not None:
    df.columns = [str(col).strip() for col in df.columns]

    try:
        # Get Requirement_ID from first column, Description from third
        requirement_ids = df.iloc[:, 0].astype(str).tolist()
        descriptions = df.iloc[:, 2].astype(str).tolist()
    except IndexError:
        st.error("File must have at least 3 columns.")
        st.stop()

    available_ids = get_available_txt_ids()

    # Only keep rows with matching .txt files
    filtered_data = [
        (rid, desc)
        for rid, desc in zip(requirement_ids, descriptions)
        if rid in available_ids
    ]

    if not filtered_data:
        st.warning("No matching .txt test description files found.")
    else:
        filtered_ids = [item[0] for item in filtered_data]
        filtered_desc = [item[1] for item in filtered_data]

        # Embed only the requirement IDs
        with st.spinner("Indexing Requirement_IDs..."):
            embedded_ids = model.encode(filtered_ids, convert_to_tensor=True)

        user_input = st.text_input("Enter the Requirement ID (e.g. FREQ-1):")

        if user_input:
            query_vec = model.encode(user_input, convert_to_tensor=True)
            scores = util.cos_sim(query_vec, embedded_ids)[0]

            best_idx = int(scores.argmax())
            best_score = float(scores[best_idx])

            if best_score == 1.0:
                matched_id = filtered_ids[best_idx]
                matched_description = filtered_desc[best_idx]

                st.success(
                    f"**{matched_id}**\n\n**Description:** {matched_description}"
                )

                test_description = load_description_from_file(matched_id)

                if test_description:
                    st.subheader("DVT Test Description")
                    st.markdown(test_description)
                else:
                    st.error(f"No test description file found for `{matched_id}` (expected `{matched_id}.txt`)")
            else:
                st.warning("No match found. Please check your Requirement ID or contact the DVT team.")
else:
    st.error("Could not load the requirements file from the repository.")