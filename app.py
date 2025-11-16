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
def generate_receipt_pdf(customer_name, items, logo_path, issued_by):
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
    pdf.cell(0, 10, f"Issued By: {issued_by}", ln=True, align='R')

    pdf.ln(10)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)

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

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align='C')

    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    return pdf_buffer, receipt_no, subtotal, vat, total


# ------------------------------------------------------------
# SUPABASE HELPERS
# ------------------------------------------------------------
def upload_pdf(pdf_buffer, receipt_no):
    file_path = f"receipts/receipt_{receipt_no}.pdf"
    supabase.storage.from_(BUCKET).upload(
        file_path,
        pdf_buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{file_path}"


def deduct_inventory(items):
    for item in items:
        supabase.rpc("deduct_inventory", {
            "item_name": item["item"],
            "qty": item["quantity"]
        }).execute()


def save_history(receipt_no, customer, total, url, issued_by):
    supabase.table("receipt_history").insert({
        "receipt_no": receipt_no,
        "customer_name": customer,
        "total_amount": total,
        "receipt_url": url,
        "issued_by": issued_by
    }).execute()


def save_items(receipt_no, items):
    for item in items:
        supabase.table("receipt_items").insert({
            "receipt_no": receipt_no,
            "item_name": item["item"],
            "quantity": item["quantity"],
            "unit_price": item["unit_price"]
        }).execute()


def login(username, password):
    res = supabase.table("users").select("*").eq("full_name", username).eq("password", password).execute()
    if res.data:
        return res.data[0]
    return None

# ------------------------------------------------------------
# SESSION INIT
# ------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_info" not in st.session_state:
    st.session_state.user_info = {}

if "receipt_items" not in st.session_state:
    st.session_state.receipt_items = []

# ------------------------------------------------------------
# LOGIN PAGE
# ------------------------------------------------------------
if not st.session_state.logged_in:
    st.title("🔐 Login")
    username = st.text_input("Full Name")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_info = user
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

# ------------------------------------------------------------
# DASHBOARD (ROLE-BASED)
# ------------------------------------------------------------
role = st.session_state.user_info["role"]

st.title(f"Welcome, {st.session_state.user_info['full_name']} 👋")

# Logout button stays EXACTLY where it currently lives
if st.button("Logout"):
    st.session_state.clear()
    st.rerun()

# Sidebar Navigation
if role == "admin":
    menu = st.sidebar.radio("Menu", [
        "Generate Receipt",
        "Receipt History",
        "Inventory Viewer",
        "User Management"
    ])
else:
    menu = st.sidebar.radio("Menu", [
        "Generate Receipt",
        "Inventory Viewer"
    ])

# ------------------------------------------------------------
# PAGE: GENERATE RECEIPT
# ------------------------------------------------------------
if menu == "Generate Receipt":
    customer_name = st.text_input("Customer Name")

    with st.expander("➕ Add Item"):
        item_name = st.text_input("Item Name")
        qty = st.number_input("Quantity", min_value=1, step=1)
        price = st.number_input("Unit Price (NGN)", min_value=0.0, step=0.01)

        if st.button("Add Item"):
            st.session_state.receipt_items.append({
                "item": item_name,
                "quantity": qty,
                "unit_price": price
            })
            st.rerun()

    st.subheader("Items Added")
    if st.session_state.receipt_items:
        st.table(pd.DataFrame(st.session_state.receipt_items))

    if st.button("🗑 Clear Items"):
        st.session_state.receipt_items = []
        st.rerun()

    if st.button("Generate Receipt PDF"):
        if not customer_name:
            st.error("Enter customer name.")
            st.stop()

        buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name,
            st.session_state.receipt_items,
            LOGO_PATH,
            st.session_state.user_info["full_name"]
        )

        url = upload_pdf(buffer, receipt_no)

        save_history(receipt_no, customer_name, total, url, st.session_state.user_info["full_name"])
        save_items(receipt_no, st.session_state.receipt_items)
        deduct_inventory(st.session_state.receipt_items)

        st.success("Receipt generated & saved!")
        st.write(f"🔗 Receipt URL: {url}")

        st.download_button(
            "📄 Download PDF",
            data=buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )

# ------------------------------------------------------------
# PAGE: RECEIPT HISTORY (ADMIN ONLY)
# ------------------------------------------------------------
elif menu == "Receipt History" and role == "admin":
    st.header("📚 Receipt History")
    data = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute()
    st.dataframe(pd.DataFrame(data.data))

# ------------------------------------------------------------
# PAGE: INVENTORY VIEWER (Admin + Users)
# ------------------------------------------------------------
elif menu == "Inventory Viewer":
    st.header("📦 Inventory Viewer")
    data = supabase.table("inventory").select("*").execute()
    st.dataframe(pd.DataFrame(data.data))

# ------------------------------------------------------------
# PAGE: USER MANAGEMENT (ADMIN ONLY)
# ------------------------------------------------------------
elif menu == "User Management" and role == "admin":
    st.header("👥 User Management")

    new_name = st.text_input("Full Name")
    new_pass = st.text_input("Password")
    new_role = st.selectbox("Role", ["user", "admin"])

    if st.button("Create User"):
        supabase.table("users").insert({
            "full_name": new_name,
            "password": new_pass,
            "role": new_role
        }).execute()
        st.success("User created successfully!")
