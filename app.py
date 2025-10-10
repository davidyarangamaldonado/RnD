import streamlit as st
from docx import Document
from docx.oxml.ns import qn
from io import BytesIO
from PIL import Image
import base64
import pandas as pd
import os

# --- Streamlit Setup ---
st.set_page_config(page_title="DVT Test Planner", layout="wide")

st.markdown("""
    <style>
        .main .block-container { max-width: 60%; padding-left: 6rem; padding-right: 6rem; }
        .reportview-container .main { font-family: "Times New Roman", Times, serif; font-size: 20px; line-height: 1.6; }
        h1, h2, h3 { color: #003366; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
        table, th, td { border: 1px solid black; }
        td { padding: 6px; }
        ol, ul { margin-left: 1.5em; list-style-type: none; padding-left: 1.5em; }
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

# --- Convert PIL image to base64 HTML ---
def pil_image_to_base64_html(pil_img):
    buffer = BytesIO()
    pil_img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode()
    return f'<img src="data:image/png;base64,{b64_str}" />'

# --- Convert integer to roman numeral ---
def int_to_roman(num):
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_num = ''
    i = 0
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syms[i]
            num -= val[i]
        i += 1
    return roman_num.lower()

# --- Determine list info ---
def get_list_info(paragraph):
    numPr = paragraph._p.xpath('./w:pPr/w:numPr')
    if numPr:
        ilvl = int(numPr[0].xpath('./w:ilvl')[0].get(qn('w:val')))
        numId = int(numPr[0].xpath('./w:numId')[0].get(qn('w:val')))
        return ilvl, numId
    if paragraph.style.name.lower().startswith("bullet"):
        return 0, -1  # bullet
    return None, None

# --- Convert paragraph runs to HTML (bold, italic, underline) ---
def paragraph_to_html(paragraph):
    html = ""
    for run in paragraph.runs:
        text = run.text.replace("\n", "<br>")
        if run.bold:
            text = f"<b>{text}</b>"
        if run.italic:
            text = f"<i>{text}</i>"
        if run.underline:
            text = f"<u>{text}</u>"
        html += text
    return html

# --- Render Word document exactly ---
def render_word_doc(filename):
    doc = Document(filename)
    html_content = ""
    open_lists = []  # stack: (tag, level)
    numbering_counters = {}  # numId -> {level: counter}

    def close_lists_to_level(level):
        nonlocal html_content
        while open_lists and open_lists[-1][1] >= level:
            tag, lvl = open_lists.pop()
            html_content += f"</{tag}>"

    for paragraph in doc.paragraphs:
        text = paragraph_to_html(paragraph).strip()
        if text == "":
            continue

        # Headings
        if paragraph.style.name.startswith("Heading"):
            close_lists_to_level(0)
            html_content += f"<h3>{text}</h3>"
            continue

        level, numId = get_list_info(paragraph)

        if level is not None:
            if numId not in numbering_counters:
                numbering_counters[numId] = {}
            if level not in numbering_counters[numId]:
                numbering_counters[numId][level] = 0
            numbering_counters[numId][level] += 1
            # reset deeper levels
            for l in range(level+1, 10):
                if l in numbering_counters[numId]:
                    numbering_counters[numId][l] = 0

            # Determine list tag
            tag = "ul" if numId == -1 else "ol"

            # Determine prefix for numbered lists only
            prefix = ""
            if tag == "ol":
                if level == 0:
                    prefix = f"{numbering_counters[numId][level]}) "
                elif level == 1:
                    prefix = f"{chr(96 + numbering_counters[numId][level])}) "
                elif level == 2:
                    prefix = f"{int_to_roman(numbering_counters[numId][level])}) "
                else:
                    prefix = f"{numbering_counters[numId][level]}) "

            # Close higher or same level lists
            close_lists_to_level(level)

            # Open new list if needed
            if not open_lists or open_lists[-1][1] < level or open_lists[-1][0] != tag:
                html_content += f"<{tag}>"
                open_lists.append((tag, level))

            html_content += f"<li>{prefix}{text}</li>"

        else:
            close_lists_to_level(0)
            html_content += f"<p>{text}</p>"

    # Close remaining lists
    close_lists_to_level(0)

    # Tables
    for table in doc.tables:
        table_html = "<table>"
        for row in table.rows:
            table_html += "<tr>"
            for cell in row.cells:
                cell_text = paragraph_to_html(cell.paragraphs[0]).strip() if cell.paragraphs else ""
                table_html += f"<td>{cell_text}</td>"
            table_html += "</tr>"
        table_html += "</table><br>"
        html_content += table_html

    # Images
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            try:
                img = Image.open(BytesIO(rel.target_part.blob))
                html_content += pil_image_to_base64_html(img)
            except:
                continue

    return html_content

# --- Load Requirements ---
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
