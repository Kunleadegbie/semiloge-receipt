import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import base64
from io import BytesIO
import os

# ---------------- PAGE CONFIG (FIRST COMMAND!) -------------------
st.set_page_config(
    page_title="SEMILOGE TEXTILES Receipt Generator",
    page_icon="💰",
    layout="centered"
)

# ---------------- SAFE SESSION STATE INITIALIZATION --------------
if "items" not in st.session_state or not isinstance(st.session_state["items"], list):
    st.session_state["items"] = []

# ------------------- OPTIONAL: SUPABASE CLIENT -------------------
# (Commented out until you enable storage upload)
# from supabase import create_client
# SUPABASE_URL = st.secrets["SUPABASE_URL"]
# SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
# BUCKET = "semiloge-receipts"

# ------------------------ CONFIG -------------------------------
COMPANY_NAME = "SEMILOGE TEXTILES"
LOGO_PATH = "logo.png"   # Logo must be in same folder as app.py
VAT_RATE = 0.075

# ---------------------- STYLING -------------------------------
st.markdown(
    """
    <style>
        .title {
            text-align: center;
            color: #5A189A;
            font-weight: 900;
            font-size: 36px;
        }
        .stButton > button {
            background-color: #7B2CBF;
            color: white;
            border-radius: 10px;
            padding: 0.6em 1.2em;
        }
        .stButton > button:hover {
            background-color: #5A189A;
            color: white;
        }
        .item-table {
            font-size: 14px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------- PDF GENERATOR ---------------------------
def generate_receipt_pdf(customer_name, items, logo_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", "B", 16)

    # Header with logo
    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 33)
    pdf.cell(80)
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align='C')

    # Receipt info
    pdf.set_font("Helvetica", "", 12)
    receipt_no = datetime.now().strftime("%Y%m%d%H%M%S")
    pdf.cell(0, 10, f"Receipt No: {receipt_no}", ln=True, align="R")
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align="R")

    pdf.ln(10)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)

    # Table header
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 10, "Item", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(40, 10, "Unit Price (NGN)", 1)
    pdf.cell(40, 10, "Total (NGN)", 1, ln=True)

    # Table rows
    pdf.set_font("Helvetica", "", 12)
    subtotal = 0

    for entry in items:
        item = entry["item"]
        qty = entry["qty"]
        price = entry["price"]
        line_total = qty * price
        subtotal += line_total

        pdf.cell(60, 10, item, 1)
        pdf.cell(30, 10, str(qty), 1)
        pdf.cell(40, 10, f"{price:,.2f}", 1)
        pdf.cell(40, 10, f"{line_total:,.2f}", 1, ln=True)

    vat = subtotal * VAT_RATE
    total = subtotal + vat

    # Totals
    pdf.ln(5)
    pdf.cell(130)
    pdf.cell(0, 10, f"Subtotal: NGN{subtotal:,.2f}", ln=True)
    pdf.cell(130)
    pdf.cell(0, 10, f"VAT (7.5%): NGN{vat:,.2f}", ln=True)
    pdf.cell(130)
    pdf.cell(0, 10, f"Total: NGN{total:,.2f}", ln=True)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align="C")

    # Save PDF into memory buffer
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    return pdf_buffer, receipt_no


# --------------------------- UI -------------------------------
st.markdown("<h1 class='title'>🧾 SEMILOGE TEXTILES Receipt Generator</h1>", unsafe_allow_html=True)
st.write("Generate multi-item VAT receipts with branding and PDF download.")

customer_name = st.text_input("Customer Name")

st.subheader("➕ Add Items to Receipt")

with st.expander("Add New Item"):
    col1, col2 = st.columns(2)
    item = col1.text_input("Item Name")
    qty = col1.number_input("Quantity", min_value=1, step=1)
    price = col2.number_input("Unit Price (NGN)", min_value=0.0, step=0.01)

    if st.button("Add Item"):
        if item.strip() == "":
            st.error("Item name cannot be empty.")
        else:
            st.session_state["items"].append(
                {"item": item.strip(), "qty": qty, "price": price}
            )
            st.success(f"Added: {item}")

# ---------------------- ITEMS TABLE ----------------------------
st.subheader("🛒 Items Added")
if len(st.session_state["items"]) > 0:
    df = pd.DataFrame(st.session_state["items"])
    st.table(df)

    if st.button("🗑️ Clear Items"):
        st.session_state["items"] = []
        st.success("All items cleared.")
else:
    st.info("No items added yet.")

# ---------------------- GENERATE RECEIPT ------------------------
if st.button("📥 Generate Receipt PDF"):
    if customer_name.strip() == "":
        st.error("Enter customer name.")
    elif len(st.session_state["items"]) == 0:
        st.error("Add at least one item.")
    else:
        pdf_buffer, receipt_no = generate_receipt_pdf(
            customer_name,
            st.session_state["items"],
            LOGO_PATH
        )

        st.success("Receipt generated successfully!")

        st.download_button(
            label="📄 Download PDF Receipt",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )
