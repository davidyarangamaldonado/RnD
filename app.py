import streamlit as st
import pandas as pd
import os
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from io import BytesIO
from PIL import Image
import mammoth
import base64

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
            font-size: 20px;
            line-height: 1.6;
        }

        h1, h2, h3 {
            color: #003366;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 10px;
        }
        table, th, td {
            border: 1px solid black;
        }
        td {
            padding: 6px;
        }

        pre {
            white-space: pre-wrap;
            font-family: "Courier New", Courier, monospace;
        }

        /* --- Fix ordered list sub-numbering --- */
        ol { list-style-type: decimal; margin-left: 1.5em; }
        ol ol { list-style-type: lower-alpha; }
        ol ol ol { list-style-type: lower-roman; }

        /* --- Unordered list consistency --- */
        ul { list-style-type: disc; margin-left: 1.5em; }
        ul ul { list-style-type: circle; }
        ul ul ul { list-style-type: square; }

        img { max-width: 100%; height: auto; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

st.title("Design Verification Testing (DVT) Test Planner")

# --- Configurable Requirements File ---
REQUIREMENTS_FILE = "dvt_requirements.csv"  # Update path if needed

def image_to_base64(img: Image.Image) -> str:
    """Convert a PIL image to a base64 string for HTML embedding."""
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# --- Load Description (Word/Text with formatting, bullets, numbering, tables, and images) ---
def load_description_from_file(req_id):
    for ext in [".docx", ".txt"]:
        filename = f"{req_id}{ext}"
        if os.path.isfile(filename):
            try:
                if ext == ".docx":
                    html_content = ""
                    images = []

                    # --- 1) Use Mammoth for main text with bullets & numbering ---
                    with open(filename, "rb") as docx_file:
                        result = mammoth.convert_to_html(docx_file)
                        html_content = result.value

                    # --- 2) Use python-docx for tables & images ---
                    doc = Document(filename)

                    # Extract tables
                    for table in doc.tables:
                        html_content += "<table>"
                        for row in table.rows:
                            html_content += "<tr>"
                            for cell in row.cells:
                                cell_text = cell.text.strip().replace("\n", "<br>")
                                html_content += f"<td>{cell_text}</td>"
                            html_content += "</tr>"
                        html_content += "</table><br>"

                    # Extract images
                    for rel in doc.part.rels.values():
                        if rel.reltype == RT.IMAGE:
                            image_data = rel.target_part.blob
                            try:
                                img = Image.open(BytesIO(image_data))
                                images.append(img)

                                # Embed inline image (base64)
                                img_b64 = image_to_base64(img)
                                html_content += (
                                    f'<div><img src="data:image/png;base64,{img_b64}" '
                                    f'style="max-width:100%;height:auto;"/></div><br>'
                                )
                            except Exception:
                                continue

                    return {"html": html_content, "images": images}

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
                    st.write("📷 Extracted Images:")
                    for idx, img in enumerate(test_description["images"]):
                        st.image(img, caption=f"Figure {idx + 1}", use_container_width=True)
            else:
                st.warning(
                    f"No `.docx` or `.txt` file found for `{user_input}` "
                    f"(expected `{user_input_upper}.docx` or `{user_input_upper}.txt`)."
                )
        else:
            st.error("No match found for that Requirement ID.")
else:
    st.error("Could not load the requirements file.")
