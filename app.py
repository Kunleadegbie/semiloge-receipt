import streamlit as st
from datetime import datetime
from fpdf import FPDF
import pandas as pd
from io import BytesIO
import os
from supabase import create_client

# ------------------------------------------------------------
# PAGE CONFIG (Must be first Streamlit command)
# ------------------------------------------------------------
st.set_page_config(
    page_title="SEMILOGE TEXTILES Receipt Generator",
    page_icon="🧾",
    layout="wide"
)

# ------------------------------------------------------------
# SUPABASE CONFIG
# ------------------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
BUCKET = st.secrets["BUCKET_NAME"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------
COMPANY_NAME = "SEMILOGE TEXTILES"
LOGO_PATH = "logo.png"
VAT_RATE = 0.075

# ------------------------------------------------------------
# CSS
# ------------------------------------------------------------
st.markdown("""
<style>
h1, h2, h3 {
    text-align: center;
    color: purple;
}

.stButton > button {
    background-color: purple !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 8px 20px !important;
}

.item-box {
    border: 1px solid #ccc;
    padding: 10px;
    border-radius: 6px;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# PDF GENERATION
# ------------------------------------------------------------
def generate_receipt_pdf(customer_name, items, logo_path):
    receipt_no = datetime.now().strftime('%Y%m%d%H%M%S')

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 33)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(85)
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align='C')

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Receipt No: {receipt_no}", ln=True, align='R')
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='R')

    pdf.ln(10)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)

    # Table header
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 10, "Item", 1)
    pdf.cell(40, 10, "Qty", 1)
    pdf.cell(40, 10, "Unit Price (NGN)", 1)
    pdf.cell(40, 10, "Total (NGN)", 1, ln=True)

    pdf.set_font("Helvetica", "", 12)

    subtotal = 0
    for item in items:
        row_total = item["quantity"] * item["unit_price"]
        subtotal += row_total

        pdf.cell(60, 10, item["item"], 1)
        pdf.cell(40, 10, str(item["quantity"]), 1)
        pdf.cell(40, 10, f"{item['unit_price']:,.2f}", 1)
        pdf.cell(40, 10, f"{row_total:,.2f}", 1, ln=True)

    vat = subtotal * VAT_RATE
    total = subtotal + vat

    # Totals
    pdf.ln(5)
    pdf.cell(140)
    pdf.cell(0, 10, f"Subtotal: NGN{subtotal:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 10, f"VAT (7.5%): NGN{vat:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 10, f"Total: NGN{total:,.2f}", ln=True)

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align='C')

    # Return PDF buffer
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    return pdf_buffer, receipt_no, subtotal, vat, total


# ------------------------------------------------------------
# SUPABASE UPLOAD
# ------------------------------------------------------------
def upload_pdf_to_supabase(pdf_buffer, receipt_no):
    file_path = f"receipts/receipt_{receipt_no}.pdf"
    return supabase.storage.from_(BUCKET).upload(
        file_path,
        pdf_buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )


# ------------------------------------------------------------
# SUPABASE INVENTORY UPDATE
# ------------------------------------------------------------
def deduct_inventory(items):
    for item in items:
        name = item["item"]
        qty = item["quantity"]
        supabase.rpc("deduct_inventory", {"item_name": name, "qty": qty}).execute()


# ------------------------------------------------------------
# SAVE RECEIPT HISTORY
# ------------------------------------------------------------
def save_receipt_history(receipt_no, customer_name, total_amount, receipt_url):
    supabase.table("receipt_history").insert({
        "receipt_no": receipt_no,
        "customer_name": customer_name,
        "total_amount": total_amount,
        "receipt_url": receipt_url
    }).execute()


def save_receipt_items(receipt_no, items):
    for item in items:
        supabase.table("receipt_items").insert({
            "receipt_no": receipt_no,
            "item_name": item["item"],
            "quantity": item["quantity"],
            "unit_price": item["unit_price"]
        }).execute()


# ------------------------------------------------------------
# SESSION INIT
# ------------------------------------------------------------
if "receipt_items" not in st.session_state:
    st.session_state["receipt_items"] = []


# ------------------------------------------------------------
# SIDEBAR NAVIGATION
# ------------------------------------------------------------
menu = st.sidebar.radio("Navigation", ["Generate Receipt", "Receipt History"])

# ------------------------------------------------------------
# PAGE 1: GENERATE RECEIPT
# ------------------------------------------------------------
if menu == "Generate Receipt":

    st.title("🧾 SEMILOGE TEXTILES Receipt Generator")

    customer_name = st.text_input("Customer Name")

    st.subheader("➕ Add Item")

    col1, col2, col3 = st.columns([4, 2, 2])
    with col1:
        new_item_name = st.text_input("Item Name")
    with col2:
        new_item_qty = st.number_input("Quantity", min_value=0, step=1)
    with col3:
        new_item_price = st.number_input("Unit Price (NGN)", min_value=0.0, step=0.01)

    if st.button("Add Item"):
        if new_item_name and new_item_qty > 0:
            st.session_state["receipt_items"].append({
                "item": new_item_name,
                "quantity": new_item_qty,
                "unit_price": new_item_price
            })
            st.success("Item added.")
        else:
            st.error("Please enter item name and quantity.")

    st.subheader("📝 Items Added")
    if st.session_state["receipt_items"]:
        st.table(pd.DataFrame(st.session_state["receipt_items"]))
    else:
        st.info("No items added yet.")

    if st.button("🗑️ Clear Items"):
        st.session_state["receipt_items"] = []
        st.rerun()

    if st.button("Generate Receipt"):
        if not customer_name:
            st.error("Enter customer name.")
            st.stop()
        if not st.session_state["receipt_items"]:
            st.error("Add at least one item.")
            st.stop()

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name, st.session_state["receipt_items"], LOGO_PATH
        )

        upload_pdf_to_supabase(pdf_buffer, receipt_no)

        receipt_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/receipts/receipt_{receipt_no}.pdf"

        save_receipt_history(receipt_no, customer_name, total, receipt_url)
        save_receipt_items(receipt_no, st.session_state["receipt_items"])

        deduct_inventory(st.session_state["receipt_items"])

        st.success("Receipt generated and recorded successfully!")
        st.write(f"🔗 **Receipt URL:** {receipt_url}")

        st.download_button(
            "📄 Download Receipt",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )


# ------------------------------------------------------------
# PAGE 2: RECEIPT HISTORY
# ------------------------------------------------------------
elif menu == "Receipt History":

    st.title("📚 Receipt History")

    data = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute()
    receipts = data.data

    if not receipts:
        st.info("No receipts found.")
    else:
        df = pd.DataFrame(receipts)
        st.dataframe(df)
