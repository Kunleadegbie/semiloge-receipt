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
    """Validate login and return user record."""
    res = supabase.table("users_app").select("*").eq("full_name", full_name).eq("password", password).execute()
    if res.data:
        return res.data[0]
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
    pdf.cell(80)
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align='C')

    # Meta
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Receipt No: {receipt_no}", ln=True, align='R')
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='R')
    pdf.cell(0, 10, f"Issued By: {issued_by}", ln=True)

    pdf.ln(8)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)

    # Table header
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 10, "Item", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(50, 10, "Unit Price (NGN)", 1)
    pdf.cell(50, 10, "Total (NGN)", 1, ln=True)

    pdf.set_font("Helvetica", "", 12)
    subtotal = 0

    for i in items:
        row_total = i["quantity"] * i["unit_price"]
        subtotal += row_total

        pdf.cell(60, 10, i["item"], 1)
        pdf.cell(30, 10, str(i["quantity"]), 1)
        pdf.cell(50, 10, f"{i['unit_price']:,.2f}", 1)
        pdf.cell(50, 10, f"{row_total:,.2f}", 1, ln=True)

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

    # Return PDF buffer
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    return pdf_buffer, receipt_no, subtotal, vat, total

# ------------------------------------------------------------
# SUPABASE HELPERS
# ------------------------------------------------------------
def upload_pdf_to_supabase(pdf_buffer, receipt_no):
    path = f"receipts/receipt_{receipt_no}.pdf"
    supabase.storage.from_(BUCKET).upload(
        path,
        pdf_buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"

def deduct_inventory(items):
    for item in items:
        name = item["item"].strip().lower()
        qty = item["quantity"]

        # Find matching inventory row (case-insensitive)
        res = supabase.table("inventory").select("*").execute()

        match = None
        for r in res.data:
            if r["item_name"].strip().lower() == name:
                match = r
                break

        if match:
            new_qty = max(match["quantity"] - qty, 0)
            supabase.table("inventory").update({"quantity": new_qty}).eq("id", match["id"]).execute()

def save_receipt_history(receipt_no, customer_name, total, issued_by, url):
    supabase.table("receipt_history").insert({
        "receipt_no": receipt_no,
        "customer_name": customer_name,
        "total_amount": total,
        "issued_by": issued_by,
        "receipt_url": url
    }).execute()

def save_receipt_items(receipt_no, items):
    for item in items:
        supabase.table("receipt_items").insert({
            "receipt_no": receipt_no,
            "item_name": item["item"],
            "quantity": item["quantity"],
            "unit_price": item["unit_price"],
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
        user = login(full_name, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.role = user["role"]
            st.session_state.full_name = user["full_name"]
            st.rerun()
        else:
            st.error("Invalid login details")

    st.stop()

# ------------------------------------------------------------
# SIDEBAR (NAVIGATION)
# ------------------------------------------------------------
st.sidebar.markdown(f"👤 **{st.session_state.full_name}** ({st.session_state.role})")

menu = ["Generate Receipt", "Inventory Viewer"]

if st.session_state.role == "admin":
    menu += ["Receipt History", "Create User", "Profit Calculator"]

choice = st.sidebar.radio("Navigation", menu)

if st.sidebar.button("🚪 Logout"):
    st.session_state.clear()
    st.rerun()

# ------------------------------------------------------------
# PAGE: GENERATE RECEIPT
# ------------------------------------------------------------
if choice == "Generate Receipt":

    st.title("🧾 Generate Receipt")

    customer_name = st.text_input("Customer Name")

    st.subheader("Add Item")

    col1, col2, col3 = st.columns([4, 2, 2])

    with col1:
        item_name = st.text_input("Item name")

    with col2:
        qty = st.number_input("Quantity", min_value=1, step=1)

    with col3:
        price = st.number_input("Unit Price (NGN)", min_value=0.0, step=0.01)

    if st.button("➕ Add Item"):
        if not item_name:
            st.error("Item name required")
        else:
            st.session_state.receipt_items.append({
                "item": item_name,
                "quantity": qty,
                "unit_price": price
            })
            st.success("Item added!")

    st.subheader("Items Added")
    if st.session_state.receipt_items:
        st.table(pd.DataFrame(st.session_state.receipt_items))

        if st.button("🗑️ Clear Items"):
            st.session_state.receipt_items = []
            st.rerun()
    else:
        st.info("No items added.")

    if st.button("Generate Receipt PDF"):
        if not customer_name:
            st.error("Enter customer name")
            st.stop()

        if not st.session_state.receipt_items:
            st.error("No items added")
            st.stop()

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name,
            st.session_state.receipt_items,
            st.session_state.full_name,
            LOGO_PATH
        )

        url = upload_pdf_to_supabase(pdf_buffer, receipt_no)
        save_receipt_history(receipt_no, customer_name, total, st.session_state.full_name, url)
        save_receipt_items(receipt_no, st.session_state.receipt_items)
        deduct_inventory(st.session_state.receipt_items)

        st.success("Receipt generated successfully!")
        st.write(f"🔗 **Download Link:** {url}")

        st.download_button(
            "📄 Download Receipt",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )

# ------------------------------------------------------------
# PAGE: INVENTORY VIEWER
# ------------------------------------------------------------
elif choice == "Inventory Viewer":

    st.title("📦 Inventory Viewer")

    res = supabase.table("inventory").select("*").execute()
    df = pd.DataFrame(res.data)

    st.dataframe(df)

# ------------------------------------------------------------
# PAGE: RECEIPT HISTORY (ADMIN)
# ------------------------------------------------------------
elif choice == "Receipt History" and st.session_state.role == "admin":

    st.title("📚 Receipt History")

    res = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute()
    df = pd.DataFrame(res.data)

    st.dataframe(df)

# ------------------------------------------------------------
# PAGE: CREATE USER (ADMIN)
# ------------------------------------------------------------
elif choice == "Create User" and st.session_state.role == "admin":

    st.title("👤 Create User")

    full_name = st.text_input("Full Name")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["user", "admin"])

    if st.button("Create User"):
        supabase.table("users_app").insert({
            "full_name": full_name,
            "username": username,
            "password": password,
            "role": role
        }).execute()

        st.success("User created successfully!")

# ------------------------------------------------------------
# PAGE: PROFIT CALCULATOR (ADMIN)
# ------------------------------------------------------------
elif choice == "Profit Calculator" and st.session_state.role == "admin":

    st.title("📈 Profit Calculator")

    res = supabase.table("inventory").select("*").execute()
    df = pd.DataFrame(res.data)

    if df.empty:
        st.info("No inventory data found.")
    else:
        # Check if unit_price column exists
        if "unit_price" not in df.columns:
            st.warning("⚠ The inventory table does not contain a 'unit_price' column.")
            st.info("Please add 'unit_price' to inventory table before using Profit Calculator.")
            st.stop()

        df["profit_per_item"] = df["unit_price"]  # or profit logic if cost exists

        st.subheader("Profit Summary")
        st.dataframe(df[["item_name", "quantity", "unit_price", "profit_per_item"]])

