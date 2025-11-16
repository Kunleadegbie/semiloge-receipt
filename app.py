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
BUCKET_NAME = st.secrets["BUCKET_NAME"]

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
.item-row {
    border: 1px solid #ccc;
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# PDF GENERATION
# ------------------------------------------------------------
def generate_receipt_pdf(customer_name, items, issued_by, logo_path):
    receipt_no = datetime.now().strftime("%Y%m%d%H%M%S")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 33)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(85)
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align="C")

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Receipt No: {receipt_no}", ln=True, align="R")
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align="R")

    pdf.ln(10)
    pdf.cell(0, 8, f"Customer Name: {customer_name}", ln=True)
    pdf.cell(0, 8, f"Issued By: {issued_by}", ln=True)

    # Table header
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(50, 10, "Item", 1)
    pdf.cell(40, 10, "Category", 1)
    pdf.cell(25, 10, "Qty", 1)
    pdf.cell(35, 10, "Unit Price", 1)
    pdf.cell(40, 10, "Total", 1, ln=True)

    pdf.set_font("Helvetica", "", 12)

    subtotal = 0
    for it in items:
        row_total = it["quantity"] * it["unit_price"]
        subtotal += row_total

        pdf.cell(50, 10, it["item"], 1)
        pdf.cell(40, 10, it["category"], 1)
        pdf.cell(25, 10, str(it["quantity"]), 1)
        pdf.cell(35, 10, f"{it['unit_price']:,.2f}", 1)
        pdf.cell(40, 10, f"{row_total:,.2f}", 1, ln=True)

    vat = subtotal * VAT_RATE
    total = subtotal + vat

    # Totals
    pdf.ln(6)
    pdf.cell(150)
    pdf.cell(0, 8, f"Subtotal: NGN{subtotal:,.2f}", ln=True)
    pdf.cell(150)
    pdf.cell(0, 8, f"VAT (7.5%): NGN{vat:,.2f}", ln=True)
    pdf.cell(150)
    pdf.cell(0, 8, f"Total: NGN{total:,.2f}", ln=True)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align="C")

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)

    return buffer, receipt_no, subtotal, vat, total


# ------------------------------------------------------------
# SUPABASE HELPERS
# ------------------------------------------------------------
def upload_pdf(receipt_no, pdf_buffer):
    path = f"receipts/receipt_{receipt_no}.pdf"
    supabase.storage.from_(BUCKET_NAME).upload(
        path,
        pdf_buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{path}"


def deduct_inventory(items):
    for it in items:
        supabase.rpc("deduct_inventory", {
            "item_name": it["item"],
            "qty": it["quantity"]
        }).execute()


def save_receipt_history(receipt_no, customer, total, issued_by, url):
    supabase.table("receipt_history").insert({
        "receipt_no": receipt_no,
        "customer_name": customer,
        "total_amount": total,
        "issued_by": issued_by,
        "receipt_url": url
    }).execute()


def save_receipt_items(receipt_no, items):
    for it in items:
        supabase.table("receipt_items").insert({
            "receipt_no": receipt_no,
            "item_name": it["item"],
            "quantity": it["quantity"],
            "unit_price": it["unit_price"],
            "category": it["category"]
        }).execute()


def load_categories():
    res = supabase.table("inventory").select("category").execute()
    cats = list({row["category"] for row in res.data if row["category"]})
    cats.sort()
    return cats


# ------------------------------------------------------------
# LOGIN SYSTEM
# ------------------------------------------------------------
def login_user(username, password):
    res = supabase.table("users_app").select("*").eq("username", username).eq("password", password).execute()
    if res.data:
        return res.data[0]
    return None


# SESSION STATE
if "user" not in st.session_state:
    st.session_state.user = None

if "receipt_items" not in st.session_state:
    st.session_state.receipt_items = []


# ------------------------------------------------------------
# LOGIN PAGE
# ------------------------------------------------------------
if st.session_state.user is None:
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login_user(username, password)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()


# ------------------------------------------------------------
# AUTHORIZED AREA
# ------------------------------------------------------------
role = st.session_state.user["role"]
fullname = st.session_state.user["fullname"]

# Logout button
st.sidebar.warning(f"Logged in as: {fullname} ({role})")
if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.session_state.receipt_items = []
    st.rerun()

# Sidebar menu based on role
if role == "admin":
    menu = st.sidebar.radio("Navigation", [
        "Generate Receipt",
        "Receipt History",
        "Inventory Viewer",
        "Create User",
    ])
else:
    menu = st.sidebar.radio("Navigation", [
        "Generate Receipt",
        "Inventory Viewer",
    ])

# ------------------------------------------------------------
# PAGE: GENERATE RECEIPT
# ------------------------------------------------------------
if menu == "Generate Receipt":

    st.title("🧾 Generate Receipt")

    customer_name = st.text_input("Customer Name")

    with st.expander("➕ Add Item"):
        item_name = st.text_input("Item Name")
        quantity = st.number_input("Quantity", min_value=1, step=1)
        unit_price = st.number_input("Unit Price (NGN)", min_value=0.0, step=0.01)

        categories = load_categories()
        category = st.selectbox("Category", categories + ["Other"])

        if category == "Other":
            category = st.text_input("Enter new category")

        if st.button("Add to List"):
            if item_name and quantity > 0:
                st.session_state.receipt_items.append({
                    "item": item_name,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "category": category
                })
                st.success("Item added!")
                st.rerun()

    st.subheader("Items Added")
    if st.session_state.receipt_items:
        st.table(pd.DataFrame(st.session_state.receipt_items))
    else:
        st.info("No items added yet.")

    if st.button("Clear Items"):
        st.session_state.receipt_items = []
        st.rerun()

    if st.button("Generate Receipt PDF"):
        if not customer_name:
            st.error("Enter customer name")
            st.stop()

        if not st.session_state.receipt_items:
            st.error("Add at least one item")
            st.stop()

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name,
            st.session_state.receipt_items,
            fullname,
            LOGO_PATH
        )

        url = upload_pdf(receipt_no, pdf_buffer)

        save_receipt_history(receipt_no, customer_name, total, fullname, url)
        save_receipt_items(receipt_no, st.session_state.receipt_items)
        deduct_inventory(st.session_state.receipt_items)

        st.success(f"Receipt created! Receipt No: {receipt_no}")
        st.write(f"🔗 Receipt URL: {url}")

        st.download_button(
            "Download PDF",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )

# ------------------------------------------------------------
# PAGE: RECEIPT HISTORY (Admin only)
# ------------------------------------------------------------
elif menu == "Receipt History" and role == "admin":
    st.title("📚 Receipt History")

    res = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute()

    if not res.data:
        st.info("No receipts yet.")
    else:
        st.dataframe(pd.DataFrame(res.data))

# ------------------------------------------------------------
# PAGE: INVENTORY VIEWER
# ------------------------------------------------------------
elif menu == "Inventory Viewer":
    st.title("📦 Inventory Viewer")

    res = supabase.table("inventory").select("*").execute()

    if not res.data:
        st.info("No inventory available.")
    else:
        st.dataframe(pd.DataFrame(res.data))

# ------------------------------------------------------------
# PAGE: CREATE USER (Admin only)
# ------------------------------------------------------------
elif menu == "Create User" and role == "admin":
    st.title("👤 Create New User")

    new_fullname = st.text_input("Full Name")
    new_username = st.text_input("Username")
    new_password = st.text_input("Password", type="password")
    new_role = st.selectbox("Role", ["Admin", "User"])

    if st.button("Create User"):
        supabase.table("users_app").insert({
            "fullname": new_fullname,
            "username": new_username,
            "password": new_password,
            "role": new_role
        }).execute()

        st.success("User created successfully!")
