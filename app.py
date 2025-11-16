import streamlit as st
from datetime import datetime
from fpdf import FPDF
import pandas as pd
from io import BytesIO
import os
from supabase import create_client

# ------------------------------------------------------------
# PAGE CONFIG
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
# APP SETTINGS
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
# AUTHENTICATION
# ------------------------------------------------------------
def login(full_name, password):
    user = supabase.table("users").select("*").eq("full_name", full_name).eq("password", password).execute()
    if user.data:
        return user.data[0]["role"]
    return None

# ------------------------------------------------------------
# PDF GENERATION
# ------------------------------------------------------------
def generate_receipt_pdf(customer_name, items, issued_by, logo_path):
    receipt_no = datetime.now().strftime('%Y%m%d%H%M%S')

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 33)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(85)
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align='C')

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Receipt No: {receipt_no}", ln=True, align='R')
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='R')
    pdf.cell(0, 10, f"Issued By: {issued_by}", ln=True)

    pdf.ln(5)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)

    # Table header
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 10, "Item", 1)
    pdf.cell(40, 10, "Qty", 1)
    pdf.cell(40, 10, "Unit Price (NGN)", 1)
    pdf.cell(40, 10, "Total (NGN)", 1, ln=True)

    # Table rows
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

    pdf.ln(5)
    pdf.cell(140)
    pdf.cell(0, 10, f"Subtotal: NGN{subtotal:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 10, f"VAT (7.5%): NGN{vat:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 10, f"Total: NGN{total:,.2f}", ln=True)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align='C')

    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    return pdf_buffer, receipt_no, subtotal, vat, total

# ------------------------------------------------------------
# SUPABASE OPERATIONS
# ------------------------------------------------------------
def upload_pdf_to_supabase(pdf_buffer, receipt_no):
    file_path = f"receipts/receipt_{receipt_no}.pdf"
    return supabase.storage.from_(BUCKET).upload(
        file_path,
        pdf_buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )

def deduct_inventory(items):
    """Safe inventory deduction with validation."""
    for item in items:
        name = item["item"]
        qty = item["quantity"]

        res = supabase.table("inventory").select("*").eq("item_name", name).execute()
        if not res.data:
            continue

        current_qty = res.data[0]["quantity"]
        new_qty = max(current_qty - qty, 0)

        supabase.table("inventory").update({
            "quantity": new_qty
        }).eq("item_name", name).execute()

def save_receipt_history(receipt_no, customer_name, total_amount, receipt_url, issued_by):
    supabase.table("receipt_history").insert({
        "receipt_no": receipt_no,
        "customer_name": customer_name,
        "total_amount": total_amount,
        "receipt_url": receipt_url,
        "issued_by": issued_by
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
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.full_name = None

if "receipt_items" not in st.session_state:
    st.session_state.receipt_items = []

# ------------------------------------------------------------
# LOGIN PAGE
# ------------------------------------------------------------
if not st.session_state.logged_in:
    st.title("🔐 Login")

    full_name = st.text_input("Full Name")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        role = login(full_name, password)
        if role:
            st.session_state.logged_in = True
            st.session_state.role = role
            st.session_state.full_name = full_name
            st.rerun()
        else:
            st.error("Invalid login details.")

    st.stop()

# ------------------------------------------------------------
# SIDEBAR NAVIGATION
# ------------------------------------------------------------
st.sidebar.markdown(f"👤 Logged in as: **{st.session_state.full_name}** ({st.session_state.role})")

menu = ["Dashboard", "Generate Receipt"]

if st.session_state.role == "admin":
    menu.append("Receipt History")
    menu.append("Create User")

choice = st.sidebar.radio("Navigation", menu)

# Logout button
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.full_name = None
    st.session_state.role = None
    st.session_state.receipt_items = []
    st.rerun()

# ------------------------------------------------------------
# DASHBOARD PAGE
# ------------------------------------------------------------
if choice == "Dashboard":
    st.title("📊 SEMILOGE Dashboard")

    st.subheader(f"Welcome, {st.session_state.full_name}!")

    if st.session_state.role == "admin":
        st.info("Admin rights: You can view all receipts, manage users, and see inventory.")
    else:
        st.info("User rights: You can generate receipts and view inventory.")

# ------------------------------------------------------------
# GENERATE RECEIPT PAGE
# ------------------------------------------------------------
if choice == "Generate Receipt":

    st.title("🧾 SEMILOGE TEXTILES Receipt Generator")

    customer_name = st.text_input("Customer Name")

    # --------------------------------------------------------
    # Load inventory for dropdown
    # --------------------------------------------------------
    inv = supabase.table("inventory").select("*").execute().data
    item_names = [i["item_name"] for i in inv]

    # --------------------------------------------------------
    # ADD ITEM (Popup Style)
    # --------------------------------------------------------
    with st.expander("➕ Add Item"):
        col1, col2, col3 = st.columns([3,1,1])

        with col1:
            selected_item = st.selectbox("Select Item", ["--- Select Item ---"] + item_names)

        qty_available = None
        unit_price = None

        if selected_item != "--- Select Item ---":
            # Fetch stock + unit price
            stock_row = next((x for x in inv if x["item_name"] == selected_item), None)
            if stock_row:
                qty_available = stock_row["quantity"]
                unit_price = float(stock_row["unit_price"])

                st.info(f"Available stock: {qty_available}")

        with col2:
            qty = st.number_input("Qty", min_value=1, step=1, key="qty_add")

        with col3:
            price = st.number_input("Unit Price", min_value=0.0, step=0.01, value=unit_price if unit_price else 0.0)

        # Validate stock BEFORE add
        if st.button("Add to Receipt"):
            if selected_item == "--- Select Item ---":
                st.error("Choose an item.")
            elif qty_available is not None and qty > qty_available:
                st.error(f"Not enough stock! Available: {qty_available}, Requested: {qty}")
            else:
                st.session_state.receipt_items.append({
                    "item": selected_item,
                    "quantity": qty,
                    "unit_price": price
                })
                st.success(f"Added: {selected_item}")
                st.rerun()

    # --------------------------------------------------------
    # ITEMS TABLE
    # --------------------------------------------------------
    st.subheader("📝 Items Added")

    if st.session_state.receipt_items:
        st.table(pd.DataFrame(st.session_state.receipt_items))
    else:
        st.info("No items added.")

    # Clear items
    if st.button("🗑️ Clear Items"):
        st.session_state.receipt_items = []
        st.rerun()

    # --------------------------------------------------------
    # GENERATE RECEIPT
    # --------------------------------------------------------
    if st.button("Generate Receipt"):

        if not customer_name:
            st.error("Enter customer name.")
            st.stop()

        if not st.session_state.receipt_items:
            st.error("Add items before generating receipt.")
            st.stop()

        # Last stock validation before generating receipt
        for item in st.session_state.receipt_items:
            selected = next((x for x in inv if x["item_name"] == item["item"]), None)
            if selected and item["quantity"] > selected["quantity"]:
                st.error(f"Stock changed: '{item['item']}' now has only {selected['quantity']} left.")
                st.stop()

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name, st.session_state.receipt_items, st.session_state.full_name, LOGO_PATH
        )

        upload_pdf_to_supabase(pdf_buffer, receipt_no)

        receipt_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/receipts/receipt_{receipt_no}.pdf"

        save_receipt_history(receipt_no, customer_name, total, receipt_url, st.session_state.full_name)
        save_receipt_items(receipt_no, st.session_state.receipt_items)

        deduct_inventory(st.session_state.receipt_items)

        st.success("Receipt generated successfully!")

        st.write(f"🔗 Receipt URL: {receipt_url}")

        st.download_button(
            "📄 Download Receipt",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )

# ------------------------------------------------------------
# RECEIPT HISTORY PAGE (Admin Only)
# ------------------------------------------------------------
if choice == "Receipt History" and st.session_state.role == "admin":

    st.title("📚 Receipt History")

    data = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute().data

    if not data:
        st.info("No receipts found.")
    else:
        st.dataframe(pd.DataFrame(data))

# ------------------------------------------------------------
# CREATE USER PAGE (Admin Only)
# ------------------------------------------------------------
if choice == "Create User" and st.session_state.role == "admin":

    st.title("👤 Create New User")

    new_full_name = st.text_input("Full Name")
    new_username = st.text_input("Username")
    new_password = st.text_input("Password", type="password")
    new_role = st.selectbox("Role", ["user", "admin"])

    if st.button("Create User"):
        supabase.table("users").insert({
            "full_name": new_full_name,
            "username": new_username,
            "password": new_password,
            "role": new_role
        }).execute()

        st.success(f"User '{new_full_name}' created successfully!")
