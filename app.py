import streamlit as st
import pandas as pd
import os
from docx import Document
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

# --- Load Description from Word / Text ---
def load_description_from_file(req_id):
    filename = f"{req_id}.docx"
    if not os.path.isfile(filename):
        txt_file = f"{req_id}.txt"
        if os.path.isfile(txt_file):
            with open(txt_file, "r", encoding="utf-8") as file:
                return {"html": f"<pre>{file.read()}</pre>"}
        return None

    doc = Document(filename)
    html_content = ""

    def run_to_html(run):
        text = run.text
        if not text:
            return ""
        if run.bold:
            text = f"<b>{text}</b>"
        if run.italic:
            text = f"<i>{text}</i>"
        if run.underline:
            text = f"<u>{text}</u>"
        return text

    # --- Track nested list stack ---
    list_stack = []

    def close_lists_to_level(level):
        nonlocal html_content
        while len(list_stack) > level:
            tag = list_stack.pop()
            html_content += f"</{tag}>"

    for para in doc.paragraphs:
        style_name = para.style.name
        is_list = style_name.startswith("List")
        level = 0
        try:
            numPr = para._p.get_or_add_pPr().numPr
            if numPr is not None and numPr.ilvl is not None:
                level = int(numPr.ilvl.val)
        except Exception:
            level = 0

        if is_list:
            list_type = "ul" if "Bullet" in style_name else "ol"
            close_lists_to_level(level)
            while len(list_stack) <= level:
                html_content += f"<{list_type}>"
                list_stack.append(list_type)
            html_content += f"<li>{''.join(run_to_html(r) for r in para.runs)}</li>"
        else:
            close_lists_to_level(0)
            html_content += f"<p>{''.join(run_to_html(r) for r in para.runs)}</p>"

        # --- Inline images ---
        for run in para.runs:
            for inline_shape in run.element.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
                embed = inline_shape.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                if embed in doc.part.rels:
                    img_data = doc.part.rels[embed].target_part.blob
                    img_base64 = base64.b64encode(img_data).decode("utf-8")
                    html_content += f'<img src="data:image/png;base64,{img_base64}" style="max-width:100%; height:auto; margin-top:10px;">'

    close_lists_to_level(0)

    # --- Tables ---
    for block in doc.element.body:
        if block.tag.endswith("tbl"):
            table_idx = doc.element.body.index(block)
            table = doc.tables[table_idx]
            html_content += "<table>"
            for row in table.rows:
                html_content += "<tr>"
                for cell in row.cells:
                    cell_text = cell.text.strip().replace("\n", "<br>")
                    html_content += f"<td>{cell_text}</td>"
                html_content += "</tr>"
            html_content += "</table><br>"

    return {"html": html_content}

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
            else:
                st.warning(
                    f"No `.docx` or `.txt` file found for `{user_input}` "
                    f"(expected `{user_input_upper}.docx` or `{user_input_upper}.txt`)."
                )
        else:
            st.error("No match found for that Requirement ID.")
else:
    st.error("Could not load the requirements file.")
