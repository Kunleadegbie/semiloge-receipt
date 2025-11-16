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
# APP CONSTANTS
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
    padding: 6px 18px !important;
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
# AUTH FUNCTIONS
# ------------------------------------------------------------
def login(username, password):
    res = supabase.table("users_app").select("*").eq("username", username).eq("password", password).single().execute()
    return res.data if res.data else None

def create_user(full_name, username, password, role):
    return supabase.table("users_app").insert({
        "full_name": full_name,
        "username": username,
        "password": password,
        "role": role.lower()
    }).execute()

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

    pdf.ln(10)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(40, 10, "Category", 1)
    pdf.cell(40, 10, "Item", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(40, 10, "Unit Price", 1)
    pdf.cell(40, 10, "Total", 1, ln=True)

    pdf.set_font("Helvetica", "", 11)
    subtotal = 0

    for item in items:
        row_total = item["quantity"] * item["unit_price"]
        subtotal += row_total

        pdf.cell(40, 10, item["category"], 1)
        pdf.cell(40, 10, item["item_name"], 1)
        pdf.cell(30, 10, str(item["quantity"]), 1)
        pdf.cell(40, 10, f"{item['unit_price']:,.2f}", 1)
        pdf.cell(40, 10, f"{row_total:,.2f}", 1, ln=True)

    vat = subtotal * VAT_RATE
    total = subtotal + vat

    pdf.ln(5)
    pdf.cell(140)
    pdf.cell(0, 10, f"Subtotal: NGN{subtotal:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 10, f"VAT: NGN{vat:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 10, f"Total: NGN{total:,.2f}", ln=True)

    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    return pdf_buffer, receipt_no, subtotal, vat, total

# ------------------------------------------------------------
# SUPABASE OPERATIONS
# ------------------------------------------------------------
def upload_receipt(pdf_buffer, receipt_no):
    path = f"receipts/receipt_{receipt_no}.pdf"
    supabase.storage.from_(BUCKET).upload(
        path,
        pdf_buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"

def save_receipt_history(receipt_no, customer_name, total_amount, issued_by, receipt_url):
    supabase.table("receipt_history").insert({
        "receipt_no": receipt_no,
        "customer_name": customer_name,
        "total_amount": total_amount,
        "issued_by": issued_by,
        "receipt_url": receipt_url
    }).execute()

def save_receipt_items(receipt_no, items):
    for item in items:
        supabase.table("receipt_items").insert({
            "receipt_no": receipt_no,
            "category": item["category"],
            "item_name": item["item_name"],
            "quantity": item["quantity"],
            "unit_price": item["unit_price"]
        }).execute()

def deduct_inventory(items):
    for item in items:
        supabase.rpc(
            "deduct_inventory_correct",
            {"item_name_text": item["item_name"], "qty_to_deduct": item["quantity"]}
        ).execute()

# ------------------------------------------------------------
# SESSION STATE
# ------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "role" not in st.session_state:
    st.session_state.role = None

if "full_name" not in st.session_state:
    st.session_state.full_name = None

if "receipt_items" not in st.session_state:
    st.session_state.receipt_items = []

# ------------------------------------------------------------
# LOGIN PAGE
# ------------------------------------------------------------
if not st.session_state.logged_in:

    st.title("🔐 SEMILOGE TEXTILES LOGIN")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.role = user["role"]
            st.session_state.full_name = user["full_name"]
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()

# ------------------------------------------------------------
# MAIN APP (AFTER LOGIN)
# ------------------------------------------------------------

st.sidebar.title(f"Welcome, {st.session_state.full_name}")
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

role = st.session_state.role
full_name = st.session_state.full_name

# -------------------------- DASHBOARD ROUTING --------------------------

if role == "admin":
    menu = st.sidebar.radio("Menu", [
        "Generate Receipt",
        "Receipt History",
        "Inventory Viewer",
        "Create User",
        "Profit Calculation"
    ])
else:
    menu = st.sidebar.radio("Menu", [
        "Generate Receipt",
        "Inventory Viewer",
        "Profit Calculation"
    ])

# -------------------------- GENERATE RECEIPT --------------------------
if menu == "Generate Receipt":

    st.title("🧾 Generate Receipt")

    customer_name = st.text_input("Customer Name")

    st.subheader("➕ Add Item")

    with st.expander("Click to Add Item"):
        category = st.text_input("Category")
        item_name = st.text_input("Item Name")
        qty = st.number_input("Quantity", min_value=1, step=1)
        price = st.number_input("Unit Price", min_value=0.0, step=0.01)

        if st.button("Add Item"):
            st.session_state.receipt_items.append({
                "category": category,
                "item_name": item_name,
                "quantity": qty,
                "unit_price": price
            })
            st.success("Item added!")
            st.rerun()

    st.subheader("📝 Items Added")
    if st.session_state.receipt_items:
        st.table(pd.DataFrame(st.session_state.receipt_items))
    else:
        st.info("No items yet.")

    if st.button("Clear Items"):
        st.session_state.receipt_items = []
        st.rerun()

    if st.button("Generate Receipt Now"):
        if not customer_name:
            st.error("Enter customer name.")
            st.stop()

        if len(st.session_state.receipt_items) == 0:
            st.error("Add at least one item.")
            st.stop()

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name, st.session_state.receipt_items, full_name, LOGO_PATH
        )

        receipt_url = upload_receipt(pdf_buffer, receipt_no)

        save_receipt_history(receipt_no, customer_name, total, full_name, receipt_url)
        save_receipt_items(receipt_no, st.session_state.receipt_items)
        deduct_inventory(st.session_state.receipt_items)

        st.success("Receipt generated successfully!")
        st.write(f"🔗 Receipt URL: {receipt_url}")

        st.download_button(
            label="Download PDF",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )

# -------------------------- RECEIPT HISTORY (ADMIN ONLY) --------------------------
elif menu == "Receipt History":
    st.title("📚 Receipt History")

    data = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute()
    df = pd.DataFrame(data.data)

    st.dataframe(df)

# -------------------------- INVENTORY VIEWER --------------------------
elif menu == "Inventory Viewer":
    st.title("📦 Inventory Viewer")

    inv = supabase.table("inventory").select("*").execute()
    df = pd.DataFrame(inv.data)

    st.dataframe(df)

# -------------------------- CREATE USER (ADMIN ONLY) --------------------------
elif menu == "Create User":
    st.title("👤 Add New User")

    full = st.text_input("Full Name")
    usr = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    role_new = st.selectbox("Role", ["admin", "user"])

    if st.button("Create User"):
        create_user(full, usr, pwd, role_new)
        st.success("User created successfully!")

# -------------------------- PROFIT CALCULATION --------------------------
elif menu == "Profit Calculation":
    st.title("💰 Profit Calculation")

    receipts = supabase.table("receipt_items").select("*").execute()
    df = pd.DataFrame(receipts.data)

    inventory = supabase.table("inventory").select("*").execute()
    inv_df = pd.DataFrame(inventory.data)

    merged = df.merge(inv_df, on="item_name", suffixes=("_sold", "_inv"))

    merged["profit"] = (merged["unit_price_sold"] - merged["unit_price_inv"]) * merged["quantity_sold"]

    st.dataframe(merged[["item_name", "quantity_sold", "unit_price_sold", "unit_price_inv", "profit"]])
