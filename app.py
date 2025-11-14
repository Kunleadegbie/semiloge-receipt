import streamlit as st
from datetime import datetime
from fpdf import FPDF
import pandas as pd
from io import BytesIO
import os
from supabase import create_client

# -----------------------------------------------------
# PAGE CONFIG (MUST BE FIRST)
# -----------------------------------------------------
st.set_page_config(page_title="SEMILOGE TEXTILES Receipt Generator", page_icon="🧾", layout="centered")

# -----------------------------------------------------
# SESSION STATE FIX (CRITICAL FOR STREAMLIT CLOUD)
# -----------------------------------------------------
if "items" not in st.session_state or not isinstance(st.session_state["items"], list):
    st.session_state["items"] = []

if "inventory" not in st.session_state:
    # Example inventory structure: item_name, quantity_available
    st.session_state["inventory"] = [
        {"name": "Ankara", "qty": 50},
        {"name": "Lace", "qty": 30},
        {"name": "Jewelry Set", "qty": 20},
        {"name": "Head Tie", "qty": 40},
    ]

# -----------------------------------------------------
# SUPABASE CONFIG
# -----------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
BUCKET = st.secrets["BUCKET_NAME"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------------------------------
# SETTINGS
# -----------------------------------------------------
COMPANY_NAME = "SEMILOGE TEXTILES"
LOGO_PATH = "logo.png"  # Place logo.png in GitHub repo beside app.py
VAT_RATE = 0.075

# -----------------------------------------------------
# STYLE
# -----------------------------------------------------
st.markdown("""
<style>
h1, h2, h3 { text-align: center; }

.stButton>button {
    background-color: purple;
    color: white;
    padding: 0.6rem 1.2rem;
    border-radius: 8px;
    border: none;
    font-weight: bold;
}

.stDownloadButton>button {
    background-color: green;
    color: white;
    padding: 0.6rem 1.2rem;
    border-radius: 8px;
    border: none;
}

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------
# PDF GENERATION
# -----------------------------------------------------
def generate_receipt_pdf(customer_name, items, logo_path):
    receipt_no = datetime.now().strftime("%Y%m%d%H%M%S")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)

    # Logo + Header
    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 30)
    pdf.cell(80)
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align="C")

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Receipt No: {receipt_no}", ln=True, align="R")
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align="R")

    pdf.ln(10)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)

    # Table Header
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 10, "Item", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(40, 10, "Unit Price", 1)
    pdf.cell(40, 10, "Total", 1, ln=True)

    # Table Rows
    pdf.set_font("Helvetica", "", 12)
    subtotal = 0

    for it in items:
        line_total = it["quantity"] * it["unit_price"]
        subtotal += line_total

        pdf.cell(60, 10, it["item"], 1)
        pdf.cell(30, 10, str(it["quantity"]), 1)
        pdf.cell(40, 10, f"₦{it['unit_price']:,.2f}", 1)
        pdf.cell(40, 10, f"₦{line_total:,.2f}", 1, ln=True)

    vat = subtotal * VAT_RATE
    total = subtotal + vat

    pdf.ln(5)
    pdf.cell(130)
    pdf.cell(0, 10, f"Subtotal: ₦{subtotal:,.2f}", ln=True)
    pdf.cell(130)
    pdf.cell(0, 10, f"VAT (7.5%): ₦{vat:,.2f}", ln=True)
    pdf.cell(130)
    pdf.cell(0, 10, f"TOTAL: ₦{total:,.2f}", ln=True)

    pdf.ln(10)
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align="C")

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)

    return buffer, receipt_no, subtotal, vat, total

# -----------------------------------------------------
# SUPABASE UPLOAD
# -----------------------------------------------------
def upload_receipt_to_supabase(pdf_buffer, receipt_no):
    path = f"receipts/receipt_{receipt_no}.pdf"
    file_bytes = pdf_buffer.getvalue()

    res = supabase.storage.from_(BUCKET).upload(
        path=path,
        file=file_bytes,
        file_options={"content-type": "application/pdf"}
    )

    if res is None or "error" in str(res).lower():
        return None

    return path

# -----------------------------------------------------
# INVENTORY DEDUCTION
# -----------------------------------------------------
def deduct_inventory(items):
    for it in items:
        for inv in st.session_state["inventory"]:
            if inv["name"] == it["item"]:
                inv["qty"] -= it["quantity"]
                if inv["qty"] < 0:
                    inv["qty"] = 0

# -----------------------------------------------------
# UI HEADER
# -----------------------------------------------------
st.title("🧾 SEMILOGE TEXTILES Receipt Generator")

# -----------------------------------------------------
# CUSTOMER NAME
# -----------------------------------------------------
customer_name = st.text_input("Customer Name")

# -----------------------------------------------------
# ADD ITEMS (up to 10)
# -----------------------------------------------------
st.subheader("Add Items")

for i in range(10):
    with st.expander(f"Item {i+1}"):
        item_name = st.text_input(f"Item Name {i+1}", key=f"item_{i}")
        qty = st.number_input(f"Quantity {i+1}", min_value=0, step=1, key=f"qty_{i}")
        price = st.number_input(f"Unit Price {i+1}", min_value=0.0, step=0.01, key=f"price_{i}")

        if st.button(f"Add Item {i+1}", key=f"add_{i}"):
            if item_name and qty > 0 and price > 0:
                st.session_state["items"].append({
                    "item": item_name,
                    "quantity": qty,
                    "unit_price": price
                })
                st.success(f"Added: {item_name}")
            else:
                st.error("Enter valid item, quantity and price.")

# -----------------------------------------------------
# SHOW ITEMS TABLE
# -----------------------------------------------------
if st.session_state["items"]:
    st.subheader("Items Added")
    st.table(pd.DataFrame(st.session_state["items"]))

# CLEAR ITEMS
if st.button("🗑️ Clear Items"):
    st.session_state["items"] = []
    st.success("Items cleared!")

# -----------------------------------------------------
# GENERATE RECEIPT
# -----------------------------------------------------
if st.button("Generate Receipt PDF"):
    if not customer_name:
        st.error("Customer name required.")
    elif not st.session_state["items"]:
        st.error("Add at least one item.")
    else:
        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name,
            st.session_state["items"],
            LOGO_PATH
        )

        # Upload to Supabase
        cloud_path = upload_receipt_to_supabase(pdf_buffer, receipt_no)

        if cloud_path:
            st.success(f"Uploaded to Supabase: {cloud_path}")
        else:
            st.warning("Upload failed. Check bucket permissions.")

        # Deduct inventory
        deduct_inventory(st.session_state["items"])

        # Allow download
        st.download_button(
            "📄 Download Receipt PDF",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )

        st.success(f"Receipt {receipt_no} generated successfully!")

# -----------------------------------------------------
# VIEW INVENTORY
# -----------------------------------------------------
st.subheader("📦 Current Inventory")
st.table(pd.DataFrame(st.session_state["inventory"]))
