import streamlit as st
from datetime import datetime
from fpdf import FPDF
import os
import pandas as pd
from supabase import create_client, Client
import uuid
import io

# -----------------------------------------------------------
# PAGE CONFIG (must be FIRST)
# -----------------------------------------------------------
st.set_page_config(page_title="SEMILOGE TEXTILES Receipt Generator",
                   page_icon="🧾", layout="centered")

# -----------------------------------------------------------
# SUPABASE CONFIG (from secrets.toml)
# -----------------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
BUCKET_NAME = st.secrets["BUCKET_NAME"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------------------------------------
# APP CONSTANTS
# -----------------------------------------------------------
COMPANY_NAME = "SEMILOGE TEXTILES"
VAT_RATE = 0.075

# -----------------------------------------------------------
# STREAMLIT STYLING (Purple theme)
# -----------------------------------------------------------
st.markdown("""
    <style>
        .main {background-color: #faf5ff;}
        .stButton > button {
            background-color: #7b2cbf !important;
            color: white !important;
            border-radius: 8px;
            height: 3em;
            width: 100%;
        }
        .receipt-table td, .receipt-table th {
            padding: 6px 12px;
        }
        .purple-header {
            color: #4b0082;
            text-align: center;
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# SESSION STATE INITIALIZATION
# -----------------------------------------------------------
if "items" not in st.session_state:
    st.session_state.items = []


# -----------------------------------------------------------
# PDF GENERATOR
# -----------------------------------------------------------
def generate_receipt_pdf(customer_name, items, logo_path=""):
    receipt_no = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"receipt_{customer_name.replace(' ', '')}_{receipt_no}.pdf"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 33)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(80)
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align="C")

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Receipt No: {receipt_no}", ln=True, align="R")
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align="R")

    # Customer
    pdf.ln(10)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)

    # Table Header
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 10, "Item", 1)
    pdf.cell(40, 10, "Qty", 1)
    pdf.cell(40, 10, "Unit (NGN)", 1)
    pdf.cell(40, 10, "Total (NGN)", 1, ln=True)

    # Table Rows
    pdf.set_font("Helvetica", "", 12)
    subtotal_sum = 0

    for item in items:
        name = item["item"]
        qty = item["qty"]
        price = item["price"]
        total = qty * price
        subtotal_sum += total

        pdf.cell(60, 10, name, 1)
        pdf.cell(40, 10, str(qty), 1)
        pdf.cell(40, 10, f"{price:,.2f}", 1)
        pdf.cell(40, 10, f"{total:,.2f}", 1, ln=True)

    # Totals
    vat_amount = subtotal_sum * VAT_RATE
    final_total = subtotal_sum + vat_amount

    pdf.ln(5)
    pdf.cell(140)
    pdf.cell(0, 10, f"Subtotal: NGN{subtotal_sum:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 10, f"VAT (7.5%): NGN{vat_amount:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 10, f"Total: NGN{final_total:,.2f}", ln=True)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align="C")

    # Save PDF to memory
    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    return filename, pdf_bytes, receipt_no, final_total


# -----------------------------------------------------------
# INVENTORY CHECK & DEDUCTION
# -----------------------------------------------------------
def deduct_inventory(items):
    warnings = []

    for item in items:
        name = item["item"]
        qty = item["qty"]

        # Search inventory by name
        res = supabase.table("inventory").select("*").eq("item_name", name).execute()

        if not res.data:  # Not found
            warnings.append(f"⚠ Item '{name}' not found in inventory. No deduction.")
            continue

        product = res.data[0]

        if qty > product["quantity"]:
            warnings.append(
                f"⚠ Insufficient stock for '{name}'. Available: {product['quantity']}. Requested: {qty}. No deduction."
            )
            continue

        # Deduct
        new_qty = product["quantity"] - qty
        supabase.table("inventory").update({"quantity": new_qty}).eq("id", product["id"]).execute()

    return warnings


# -----------------------------------------------------------
# UPLOAD PDF TO SUPABASE STORAGE
# -----------------------------------------------------------
def upload_pdf_to_bucket(filename, pdf_bytes):
    unique_name = f"{uuid.uuid4()}_{filename}"

    supabase.storage.from_(BUCKET_NAME).upload(
        unique_name,
        pdf_bytes,
        file_options={"content-type": "application/pdf"},
    )

    url = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_name)
    return url


# -----------------------------------------------------------
# LOG RECEIPT INTO DATABASE
# -----------------------------------------------------------
def log_receipt(receipt_no, customer_name, total_amount, pdf_url):
    supabase.table("receipt_logs").insert({
        "receipt_no": receipt_no,
        "customer_name": customer_name,
        "total_amount": total_amount,
        "pdf_url": pdf_url
    }).execute()


# -----------------------------------------------------------
# MAIN APP
# -----------------------------------------------------------
st.markdown('<div class="purple-header">SEMILOGE TEXTILES RECEIPT GENERATOR</div>', unsafe_allow_html=True)

menu = st.sidebar.selectbox("Menu", ["Generate Receipt", "Receipt Archive"])

# -----------------------------------------------------------
# PAGE 1 — GENERATE RECEIPT
# -----------------------------------------------------------
if menu == "Generate Receipt":

    st.subheader("🧾 Create a New Receipt")

    customer_name = st.text_input("Customer Name")

    with st.expander("➕ Add Item"):
        item = st.text_input("Item Name")
        qty = st.number_input("Quantity", min_value=1, step=1)
        price = st.number_input("Unit Price (NGN)", min_value=0.0, step=0.01)

        if st.button("Add to Receipt"):
            if item.strip() == "":
                st.error("Enter item name!")
            else:
                st.session_state.items.append(
                    {"item": item, "qty": qty, "price": price}
                )
                st.success(f"Added '{item}'")

    # Show added items
    if st.session_state.items:
        st.write("### 🧾 Items Added")
        df = pd.DataFrame(st.session_state.items)
        df["Total"] = df["qty"] * df["price"]
        st.table(df)

        if st.button("🗑️ Clear Items"):
            st.session_state.items = []
            st.rerun()

    # Generate Receipt
    if st.button("Generate Receipt PDF"):
        if not customer_name:
            st.error("Customer name is required.")
        elif not st.session_state.items:
            st.error("Add at least one item.")
        else:
            # Deduct inventory
            warnings = deduct_inventory(st.session_state.items)
            for w in warnings:
                st.warning(w)

            # Create PDF
            filename, pdf_bytes, receipt_no, total_amount = generate_receipt_pdf(
                customer_name, st.session_state.items
            )

            # Upload to Supabase
            pdf_url = upload_pdf_to_bucket(filename, pdf_bytes)

            # Log to database
            log_receipt(receipt_no, customer_name, total_amount, pdf_url)

            st.success("Receipt generated successfully!")
            st.download_button("📥 Download Receipt", data=pdf_bytes,
                               file_name=filename, mime="application/pdf")

            st.info(f"📤 Cloud Copy: {pdf_url}")

# -----------------------------------------------------------
# PAGE 2 — RECEIPT ARCHIVE
# -----------------------------------------------------------
elif menu == "Receipt Archive":
    st.subheader("📁 Receipt Archive (from Supabase)")

    res = supabase.table("receipt_logs").select("*").order("id", desc=True).execute()

    if not res.data:
        st.info("No receipts found.")
    else:
        df = pd.DataFrame(res.data)
        st.dataframe(df)

