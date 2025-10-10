import streamlit as st
from docx import Document
from io import BytesIO
from PIL import Image
import base64
import pandas as pd
import os

# --- Streamlit Setup ---
st.set_page_config(page_title="Design Verification Testing (DVT) Test Planner", layout="wide")

st.markdown("""
    <style>
        .main .block-container { max-width: 60%; padding-left: 6rem; padding-right: 6rem; }
        .reportview-container .main { font-family: "Times New Roman", Times, serif; font-size: 20px; line-height: 1.6; }
        h1, h2, h3 { color: #003366; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
        table, th, td { border: 1px solid black; }
        td { padding: 6px; }
        ol { list-style-type: decimal; margin-left: 1.5em; }
        ol ol { list-style-type: lower-alpha; }
        ol ol ol { list-style-type: lower-roman; }
        ul { list-style-type: disc; margin-left: 1.5em; }
        ul ul { list-style-type: circle; }
        ul ul ul { list-style-type: square; }
        img { max-width: 100%; height: auto; margin-top: 10px; }
        pre { white-space: pre-wrap; font-family: "Courier New", Courier, monospace; }
    </style>
""", unsafe_allow_html=True)

st.title("Design Verification Testing (DVT) Test Planner")

# --- Configurable Requirements File ---
REQUIREMENTS_FILE = "dvt_requirements.csv"

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

# --- Convert image bytes to base64 HTML ---
def pil_image_to_base64_html(pil_img):
    buffer = BytesIO()
    pil_img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode()
    return f'<img src="data:image/png;base64,{b64_str}" />'

# --- Render Word Document exactly as it appears ---
def render_word_doc(filename):
    doc = Document(filename)
    html_content = ""

    # Iterate through each block in order
    for block in doc.element.body:
        # Paragraph
        if block.tag.endswith('p'):
            paragraph = doc.paragraphs[doc.element.body.index(block)]
            text = paragraph.text
            if text.strip() != "":
                if paragraph.style.name.startswith('Heading'):
                    html_content += f"<h3>{text}</h3>"
                else:
                    html_content += f"<p>{text}</p>"

        # Table
        elif block.tag.endswith('tbl'):
            table_idx = doc.element.body.index(block)
            table = [t for t in doc.tables if t._element == block][0]
            table_html = "<table>"
            for row in table.rows:
                table_html += "<tr>"
                for cell in row.cells:
                    cell_text = cell.text.strip().replace("\n", "<br>")
                    table_html += f"<td>{cell_text}</td>"
                table_html += "</tr>"
            table_html += "</table>"
            html_content += table_html

    # Extract images from document relationships
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            try:
                img = Image.open(BytesIO(rel.target_part.blob))
                html_content += pil_image_to_base64_html(img)
            except:
                continue

    return html_content

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

            # Try .docx first
            docx_file = f"{user_input_upper}.docx"
            txt_file = f"{user_input_upper}.txt"
            if os.path.isfile(docx_file):
                html_content = render_word_doc(docx_file)
                st.markdown(html_content, unsafe_allow_html=True)
            elif os.path.isfile(txt_file):
                with open(txt_file, "r", encoding="utf-8") as f:
                    st.markdown(f"<pre>{f.read()}</pre>", unsafe_allow_html=True)
            else:
                st.warning(f"No `.docx` or `.txt` file found for `{user_input_upper}`.")
        else:
            st.error("No match found for that Requirement ID.")
else:
    st.error("Could not load the requirements file.")
