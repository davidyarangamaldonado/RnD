import streamlit as st
import pandas as pd
import os
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from io import BytesIO
from PIL import Image

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Design Verification Testing (DVT) Test Planner", layout="wide")

st.markdown("""
    <style>
        .main .block-container {
            max-width: 60%;
            padding-left: 6rem;
            padding-right: 6rem;
        }

        .reportview-container .main {
            font-family: "Times New Roman", Times, serif;
            font-size: 16px;
            line-height: 1.6;
        }

        h1, h2, h3 {
            color: #003366;
        }

        table {
            width: 100%;
        }

        pre {
            white-space: pre-wrap;
            font-family: "Courier New", Courier, monospace;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Design Verification Testing (DVT) Test Planner")

# --- Configurable Requirements File ---
REQUIREMENTS_FILE = "dvt_requirements.csv"  # Update path if needed

# --- Load Description (Word/Text with formatting and images) ---
def load_description_from_file(req_id):
    """Loads .docx or .txt file with formatting and block diagram support."""
    for ext in [".docx", ".txt"]:
        filename = f"{req_id}{ext}"
        if os.path.isfile(filename):
            try:
                if ext == ".docx":
                    doc = Document(filename)
                    html_content = ""
                    images = []

                    # --- Parse paragraphs with formatting ---
                    for para in doc.paragraphs:
                        text = para.text.strip()
                        style = para.style.name.lower()

                        if not text:
                            html_content += "<br>"
                            continue

                        if "heading 1" in style:
                            html_content += f"<h1>{text}</h1>"
                        elif "heading 2" in style:
                            html_content += f"<h2>{text}</h2>"
                        elif "heading 3" in style:
                            html_content += f"<h3>{text}</h3>"
                        else:
                            runs_html = ""
                            for run in para.runs:
                                run_text = run.text.replace("\n", "<br>")
                                if run.bold:
                                    run_text = f"<b>{run_text}</b>"
                                if run.italic:
                                    run_text = f"<i>{run_text}</i>"
                                if run.underline:
                                    run_text = f"<u>{run_text}</u>"
                                runs_html += run_text
                            html_content += f"<p>{runs_html}</p>"

                    # --- Parse tables ---
                    for table in doc.tables:
                        html_content += "<table border='1' style='border-collapse: collapse; margin-bottom: 10px;'>"
                        for row in table.rows:
                            html_content += "<tr>"
                            for cell in row.cells:
                                cell_text = cell.text.strip().replace("\n", "<br>")
                                html_content += f"<td style='padding: 6px;'>{cell_text}</td>"
                            html_content += "</tr>"
                        html_content += "</table><br>"

                    # --- Extract images (block diagrams etc.) ---
                    rels = doc.part.rels
                    for rel in rels.values():
                        if rel.reltype == RT.IMAGE:
                            image_data = rel.target_part.blob
                            image_stream = BytesIO(image_data)
                            try:
                                img = Image.open(image_stream)
                                images.append(img)
                            except Exception:
                                continue  # Skip unreadable images

                    return {
                        "html": html_content,
                        "images": images
                    }

                else:  # .txt fallback
                    with open(filename, "r", encoding="utf-8") as file:
                        return {
                            "html": f"<pre>{file.read()}</pre>",
                            "images": []
                        }

            except Exception as e:
                return {
                    "html": f"<p style='color:red;'>Error reading {ext} file: {e}</p>",
                    "images": []
                }

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
        st.error("Requirements file must have at least 3 columns (ID in column 1, Description in column 3).")
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
                st.markdown(test_description["html"], unsafe_allow_html=True)

                if test_description["images"]:
                    st.subheader("Block Diagrams / Embedded Images")
                    for idx, img in enumerate(test_description["images"]):
                        st.image(img, caption=f"Figure {idx + 1}", use_column_width=True)
            else:
                st.warning(
                    f"No `.docx` or `.txt` file found for `{user_input}` "
                    f"(expected `{user_input_upper}.docx` or `{user_input_upper}.txt`)."
                )
        else:
            st.error("No match found for that Requirement ID.")
else:
    st.error("Could not load the requirements file.")
