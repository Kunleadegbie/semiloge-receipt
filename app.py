import streamlit as st
from datetime import datetime
from fpdf import FPDF
import pandas as pd
from io import BytesIO
import os
from supabase import create_client

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="SEMILOGE TEXTILES Receipt System",
    page_icon="🧾",
    layout="wide"
)

# =========================================================
# SUPABASE SETTINGS
# =========================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
BUCKET_NAME = st.secrets["BUCKET_NAME"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# CONSTANTS
# =========================================================
COMPANY_NAME = "SEMILOGE TEXTILES"
LOGO_PATH = "logo.png"
VAT_RATE = 0.075

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
.dashboard-tile {
    background-color: #f7f0ff;
    border-radius: 15px;
    padding: 25px;
    text-align: center;
    border: 1px solid #d8b9ff;
    transition: 0.3s;
}
.dashboard-tile:hover {
    background-color: #e8d4ff;
    cursor: pointer;
    transform: scale(1.03);
}
.stButton > button {
    background-color: purple !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 10px 25px !important;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# PDF GENERATION
# =========================================================
def generate_receipt_pdf(customer_name, items, issued_by, logo_path):
    receipt_no = datetime.now().strftime('%Y%m%d%H%M%S')

    pdf = FPDF()
    pdf.add_page()

    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 30)

    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(80)
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align='C')

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Receipt No: {receipt_no}", ln=True, align='R')
    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='R')
    pdf.cell(0, 8, f"Issued By: {issued_by}", ln=True, align='R')

    pdf.ln(8)
    pdf.cell(0, 10, f"Customer: {customer_name}", ln=True)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 10, "Item", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(40, 10, "Unit Price", 1)
    pdf.cell(40, 10, "Category", 1)
    pdf.cell(30, 10, "Total", 1, ln=True)

    subtotal = 0

    pdf.set_font("Helvetica", "", 11)

    for it in items:
        row_total = it["quantity"] * it["unit_price"]
        subtotal += row_total

        pdf.cell(60, 10, it["item"], 1)
        pdf.cell(30, 10, str(it["quantity"]), 1)
        pdf.cell(40, 10, f"{it['unit_price']:,.2f}", 1)
        pdf.cell(40, 10, it["category"], 1)
        pdf.cell(30, 10, f"{row_total:,.2f}", 1, ln=True)

    vat = subtotal * VAT_RATE
    total = subtotal + vat

    pdf.ln(5)
    pdf.cell(140)
    pdf.cell(0, 8, f"Subtotal: NGN{subtotal:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 8, f"VAT (7.5%): NGN{vat:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 8, f"Total: NGN{total:,.2f}", ln=True)

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align='C')

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)

    return buffer, receipt_no, subtotal, vat, total

# =========================================================
# SUPABASE FUNCTIONS
# =========================================================
def upload_pdf(buffer, receipt_no):
    path = f"receipts/receipt_{receipt_no}.pdf"
    supabase.storage.from_(BUCKET_NAME).upload(
        path,
        buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{path}"

def deduct_inventory(items):
    for it in items:
        supabase.rpc("deduct_inventory", {
            "item_name_text": it["item"],
            "qty": it["quantity"]
        }).execute()

def save_receipt_history(no, cust, total, issued_by, link):
    supabase.table("receipt_history").insert({
        "receipt_no": no,
        "customer_name": cust,
        "total_amount": total,
        "issued_by": issued_by,
        "receipt_url": link
    }).execute()

def save_receipt_items(no, items):
    for i in items:
        supabase.table("receipt_items").insert({
            "receipt_no": no,
            "item_name": i["item"],
            "quantity": i["quantity"],
            "unit_price": i["unit_price"],
            "category": i["category"]
        }).execute()

# =========================================================
# SESSION STATE FIXED
# =========================================================
if "receipt_items" not in st.session_state:
    st.session_state["receipt_items"] = []

if "page" not in st.session_state:
    st.session_state.page = "login"

if "user" not in st.session_state:
    st.session_state.user = None

# =========================================================
# LOGIN FUNCTION
# =========================================================
def authenticate(username, password):
    res = supabase.table("users_app").select("*").eq("username", username).eq("password", password).execute()
    if res.data:
        return res.data[0]
    return None

# =========================================================
# LOGIN PAGE
# =========================================================
if st.session_state.page == "login":
    st.title("🔐 SEMILOGE TEXTILES Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        user = authenticate(u, p)
        if user:
            st.session_state.user = user
            st.session_state.page = "dashboard"
            st.success("Login Successful!")
            st.rerun()
        else:
            st.error("Invalid Username or Password")
    st.stop()

# =========================================================
# DASHBOARD PAGE
# =========================================================
user = st.session_state.user
role = user["role"]
full_name = user["full_name"]

st.title(f"👋 Welcome, {full_name} ({role.upper()})")

if st.button("🚪 Logout"):
    st.session_state.user = None
    st.session_state.page = "login"
    st.rerun()

st.subheader("📌 Dashboard")

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("🧾 Generate Receipt"):
        st.session_state.page = "generate"
        st.rerun()

with c2:
    if st.button("📦 Inventory Viewer"):
        st.session_state.page = "inventory"
        st.rerun()

with c3:
    if role == "admin":
        if st.button("📚 Receipt History"):
            st.session_state.page = "history"
            st.rerun()
    else:
        st.info("Admin Only")

# =========================================================
# GENERATE RECEIPT PAGE
# =========================================================
if st.session_state.page == "generate":

    st.header("🧾 Generate Receipt")

    customer_name = st.text_input("Customer Name")

    with st.expander("➕ Add Item"):
        item = st.text_input("Item Name")
        qty = st.number_input("Quantity", min_value=1)
        price = st.number_input("Unit Price", min_value=0.0)
        category = st.text_input("Category")

        if st.button("Add This Item"):
            st.session_state["receipt_items"].append({
                "item": item,
                "quantity": qty,
                "unit_price": price,
                "category": category
            })
            st.success("Item added!")
            st.rerun()

    st.subheader("📝 Items Added")

    if st.session_state["receipt_items"]:
        df = pd.DataFrame(st.session_state["receipt_items"])
        st.table(df)
    else:
        st.info("No items added yet.")

    if st.button("🗑️ Clear Items"):
        st.session_state["receipt_items"] = []
        st.rerun()

    if st.button("Generate Receipt Now"):

        if not customer_name:
            st.error("Customer name required!")
            st.stop()

        if not st.session_state["receipt_items"]:
            st.error("Add at least one item!")
            st.stop()

        buffer, no, sub, vat, tot = generate_receipt_pdf(
            customer_name,
            st.session_state["receipt_items"],
            full_name,
            LOGO_PATH
        )

        link = upload_pdf(buffer, no)
        save_receipt_history(no, customer_name, tot, full_name, link)
        save_receipt_items(no, st.session_state["receipt_items"])
        deduct_inventory(st.session_state["receipt_items"])

        st.success("Receipt generated successfully!")
        st.write("🔗 Receipt URL:", link)
        st.download_button("📄 Download Receipt", buffer, f"receipt_{no}.pdf")

# =========================================================
# INVENTORY VIEWER PAGE
# =========================================================
if st.session_state.page == "inventory":

    st.header("📦 Inventory Viewer")

    data = supabase.table("inventory").select("*").execute().data

    if data:
        st.dataframe(pd.DataFrame(data))
    else:
        st.info("No inventory available.")

# =========================================================
# RECEIPT HISTORY PAGE (ADMIN ONLY)
# =========================================================
if st.session_state.page == "history" and role == "admin":

    st.header("📚 Receipt History")

    data = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute().data

    if data:
        st.dataframe(pd.DataFrame(data))
    else:
        st.info("No receipts found.")

