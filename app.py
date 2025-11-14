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
# AUTHENTICATION FUNCTIONS
# ------------------------------------------------------------
def login(full_name, password):
    """Validate login and return role."""
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

    # Logo
    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 33)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(85)
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align='C')

    # Receipt details
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
# SUPABASE FUNCTIONS
# ------------------------------------------------------------
def upload_pdf_to_supabase(pdf_buffer, receipt_no):
    file_path = f"receipts/receipt_{receipt_no}.pdf"
    return supabase.storage.from_(BUCKET).upload(
        file_path,
        pdf_buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )

def deduct_inventory(items):
    for item in items:
        supabase.rpc("deduct_inventory", {
            "item_name": item["item"],
            "qty": item["quantity"]
        }).execute()

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
# SIDEBAR NAVIGATION + LOGOUT
# ------------------------------------------------------------
st.sidebar.markdown(f"👤 Logged in as: **{st.session_state.full_name}** ({st.session_state.role})")

menu = ["Generate Receipt"]

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
# GENERATE RECEIPT PAGE
# ------------------------------------------------------------
if choice == "Generate Receipt":

    st.title("🧾 SEMILOGE TEXTILES Receipt Generator")

    customer_name = st.text_input("Customer Name")

    with st.expander("➕ Add Item"):
        item = st.text_input("Item name")
        qty = st.number_input("Quantity", min_value=1, step=1)
        price = st.number_input("Unit Price (NGN)", min_value=0.0, step=0.01)

        if st.button("Add Item"):
            st.session_state.receipt_items.append({
                "item": item,
                "quantity": qty,
                "unit_price": price
            })
            st.rerun()

    st.subheader("📝 Items Added")
    if st.session_state.receipt_items:
        st.table(pd.DataFrame(st.session_state.receipt_items))
    else:
        st.info("No items added.")

    if st.button("🗑️ Clear Items"):
        st.session_state.receipt_items = []
        st.rerun()

    if st.button("Generate Receipt"):
        if not customer_name:
            st.error("Enter customer name.")
            st.stop()

        if not st.session_state.receipt_items:
            st.error("Add at least one item.")
            st.stop()

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name, st.session_state.receipt_items, st.session_state.full_name, LOGO_PATH
        )

        upload_pdf_to_supabase(pdf_buffer, receipt_no)

        receipt_url = (
            f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/"
            f"receipts/receipt_{receipt_no}.pdf"
        )

        save_receipt_history(receipt_no, customer_name, total, receipt_url, st.session_state.full_name)
        save_receipt_items(receipt_no, st.session_state.receipt_items)
        deduct_inventory(st.session_state.receipt_items)

        st.success("Receipt generated successfully!")
        st.write(f"🔗 **Receipt URL:** {receipt_url}")

        st.download_button(
            "📄 Download Receipt",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )

# ------------------------------------------------------------
# RECEIPT HISTORY PAGE (Admin Only)
# ------------------------------------------------------------
elif choice == "Receipt History":

    st.title("📚 Receipt History")

    data = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute()
    receipts = data.data

    if not receipts:
        st.info("No receipts found.")
    else:
        df = pd.DataFrame(receipts)
        st.dataframe(df)

# ------------------------------------------------------------
# PAGE 3: CREATE USER (Admin Only)
# ------------------------------------------------------------
elif choice == "Create User":

    st.title("👥 Create New User (Admin Only)")

    new_name = st.text_input("Full Name")
    new_password = st.text_input("Password", type="password")
    new_role = st.selectbox("Role", ["user", "admin"])

    if st.button("Create User"):
        if not new_name or not new_password:
            st.error("Full name and password are required.")
        else:
            # Insert into Supabase
            result = supabase.table("users").insert({
                "full_name": new_name,
                "password": new_password,
                "role": new_role
            }).execute()

            if result.data:
                st.success(f"User **{new_name}** created successfully!")
            else:
                st.error("Failed to create user. Possibly name already exists.")


