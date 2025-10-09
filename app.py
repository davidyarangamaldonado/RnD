import os
from io import BytesIO
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
import mammoth
from PIL import Image
import streamlit as st

# ----------------------------
# Styling
# ----------------------------
st.markdown("""
    <style>
    /* Make the markdown look clean */
    body { font-family: Arial, sans-serif; line-height: 1.6; }

    /* Ordered list styles */
    ol { list-style-type: decimal; margin-left: 1.5em; }
    ol ol { list-style-type: lower-alpha; }
    ol ol ol { list-style-type: lower-roman; }

    /* Unordered list styles */
    ul { list-style-type: disc; margin-left: 1.5em; }
    ul ul { list-style-type: circle; }
    ul ul ul { list-style-type: square; }

    /* Table styling */
    table { border-collapse: collapse; margin-top: 10px; }
    td, th { border: 1px solid #ccc; padding: 6px; }

    img { max-width: 100%; height: auto; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

# ----------------------------
# Load function
# ----------------------------
def load_description_from_file(req_id):
    """Loads .docx or .txt file with Mammoth for text + bullets,
       python-docx for tables and images."""
    for ext in [".docx", ".txt"]:
        filename = f"{req_id}{ext}"
        if os.path.isfile(filename):
            try:
                if ext == ".docx":
                    html_content = ""
                    images = []

                    # --- 1) Mammoth for clean text (bullets/numbering/headings) ---
                    with open(filename, "rb") as docx_file:
                        result = mammoth.convert_to_html(docx_file)
                        html_content = result.value

                    # --- 2) python-docx for tables ---
                    doc = Document(filename)
                    for table in doc.tables:
                        html_content += "<table>"
                        for row in table.rows:
                            html_content += "<tr>"
                            for cell in row.cells:
                                cell_text = cell.text.strip().replace("\n", "<br>")
                                html_content += f"<td>{cell_text}</td>"
                            html_content += "</tr>"
                        html_content += "</table><br>"

                    # --- 3) python-docx for images ---
                    rels = doc.part.rels
                    for rel in rels.values():
                        if rel.reltype == RT.IMAGE:
                            image_data = rel.target_part.blob
                            image_stream = BytesIO(image_data)
                            try:
                                img = Image.open(image_stream)
                                images.append(img)
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

# ----------------------------
# Example usage
# ----------------------------
st.title("Requirement Viewer")

req_id = st.text_input("Enter requirement ID:", "req1")

if req_id:
    description = load_description_from_file(req_id)
    if description:
        st.markdown(description["html"], unsafe_allow_html=True)

        # Display extracted images
        if description["images"]:
            st.subheader("Images")
            for img in description["images"]:
                st.image(img)
    else:
        st.warning(f"No file found for {req_id}.docx or {req_id}.txt")
