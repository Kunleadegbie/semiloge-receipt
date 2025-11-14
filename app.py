import streamlit as st
from datetime import datetime
from fpdf import FPDF
import os
import pandas as pd

# 🟣 Must be first Streamlit command
st.set_page_config(page_title="SEMILOGE TEXTILES Receipt Generator", page_icon="💰", layout="centered")

# --- Configuration ---
COMPANY_NAME = "SEMILOGE TEXTILES"
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")
VAT_RATE = 0.075

# --- Styling ---
st.markdown("""
    <style>
        .main {
            background-color: #f9f6ff;
        }
        .company-banner {
            background-color: #5e2b97;
            color: white;
            padding: 15px;
            text-align: center;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .stButton > button {
            background-color: #5e2b97 !important;
            color: white !important;
            border-radius: 10px !important;
            padding: 8px 16px !important;
            font-weight: bold !important;
        }
        .stButton > button:hover {
            background-color: #783fb3 !important;
        }
        th {
            background-color: #5e2b97;
            color: white;
        }
    </style>
""", unsafe_allow_html=True)

# --- Helper Function ---
def generate_receipt_pdf(customer_name, items, logo_path):
    subtotal = sum(qty * price for _, qty, price in items)
    vat = subtotal * VAT_RATE
    total = subtotal + vat

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", "B", 16)

    # Header
    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 33)
    pdf.cell(80)
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align='C')

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Receipt No: {datetime.now().strftime('%Y%m%d%H%M%S')}", ln=True, align='R')
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='R')

    pdf.ln(10)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)

    # Table header
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(70, 10, "Item", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(45, 10, "Unit Price (N)", 1)
    pdf.cell(45, 10, "Total (N)", 1, ln=True)

    # Table rows
    pdf.set_font("Helvetica", "", 12)
    for item, qty, price in items:
        total_price = qty * price
        pdf.cell(70, 10, item, 1)
        pdf.cell(30, 10, str(qty), 1)
        pdf.cell(45, 10, f"N {price:,.2f}", 1)
        pdf.cell(45, 10, f"N {total_price:,.2f}", 1, ln=True)

    # Totals
    pdf.ln(5)
    pdf.cell(150)
    pdf.cell(0, 10, f"Subtotal: N{subtotal:,.2f}", ln=True)
    pdf.cell(150)
    pdf.cell(0, 10, f"VAT (7.5%): N{vat:,.2f}", ln=True)
    pdf.cell(150)
    pdf.cell(0, 10, f"Total: N{total:,.2f}", ln=True)

    # Footer
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align='C')

    file_name = f"receipt_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    pdf.output(file_name)
    return file_name


# --- Header ---
st.markdown(f'<div class="company-banner"><h2>{COMPANY_NAME} - Receipt Generator</h2></div>', unsafe_allow_html=True)
st.markdown("Easily generate VAT-compliant receipts with multiple items.")

customer_name = st.text_input("🧍 Customer Name")

# --- Initialize session state safely ---
if "item_list" not in st.session_state or not isinstance(st.session_state.get("item_list"), list):
    st.session_state["item_list"] = []

# --- Add Items Section ---
st.subheader("➕ Add Items")
for i in range(len(st.session_state["item_list"]), 10):
    with st.expander(f"Add Item {i+1}", expanded=False):
        item_name = st.text_input(f"Item {i+1} Name", key=f"name_{i}")
        quantity = st.number_input(f"Quantity for Item {i+1}", min_value=0, step=1, key=f"qty_{i}")
        unit_price = st.number_input(f"Unit Price (N) for Item {i+1}", min_value=0.0, step=0.01, key=f"price_{i}")
        if st.button(f"✅ Save Item {i+1}", key=f"save_{i}"):
            if item_name and quantity > 0 and unit_price > 0:
                st.session_state["item_list"].append((item_name, quantity, unit_price))
                st.success(f"Item {i+1} added successfully.")
            else:
                st.warning("Please enter valid item details before saving.")

# --- Display Added Items ---
if st.session_state["item_list"]:
    st.subheader("🧾 Current Items")
    df = pd.DataFrame(st.session_state["item_list"], columns=["Item", "Quantity", "Unit Price (N)"])
    df["Total (N)"] = df["Quantity"] * df["Unit Price (N)"]
    st.dataframe(df, use_container_width=True)

# --- Clear Items ---
if st.button("🗑️ Clear All Items"):
    st.session_state["item_list"] = []
    st.rerun()

# --- Generate Receipt ---
if st.button("💳 Generate Receipt"):
    if not customer_name:
        st.error("Please enter the customer name.")
    elif not st.session_state["item_list"]:
        st.error("Please add at least one item before generating a receipt.")
    else:
        subtotal = sum(qty * price for _, qty, price in st.session_state["item_list"])
        vat = subtotal * VAT_RATE
        total = subtotal + vat

        st.success("Receipt generated successfully!")
        st.markdown(f"**Customer:** {customer_name}")
        st.markdown(f"**Items Purchased:** {len(st.session_state['item_list'])}")
        st.markdown(f"**Subtotal:** N{subtotal:,.2f}")
        st.markdown(f"**VAT (7.5%):** N{vat:,.2f}")
        st.markdown(f"**Total Payable:** N{total:,.2f}")

        receipt_file = generate_receipt_pdf(customer_name, st.session_state["item_list"], LOGO_PATH)
        with open(receipt_file, "rb") as f:
            st.download_button(
                label="📥 Download Receipt (PDF)",
                data=f,
                file_name=receipt_file,
                mime="application/pdf"
            )
