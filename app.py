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
    border-radius: 6px !important;
    padding: 6px 18px !important;
}
.header-logout {
    display: flex;
    justify-content: flex-end;
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
def generate_receipt_pdf(customer_name, created_by, items, logo_path):
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
    pdf.cell(0, 10, f"Issued By: {created_by}", ln=True)

    # Table header
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 10, "Item", 1)
    pdf.cell(40, 10, "Qty", 1)
    pdf.cell(40, 10, "Unit Price", 1)
    pdf.cell(40, 10, "Total", 1, ln=True)

    pdf.set_font("Helvetica", "", 12)

    subtotal = 0
    for item in items:
        total_row = item['quantity'] * item['unit_price']
        subtotal += total_row
        pdf.cell(60, 10, item['item'], 1)
        pdf.cell(40, 10, str(item['quantity']), 1)
        pdf.cell(40, 10, f"{item['unit_price']:,.2f}", 1)
        pdf.cell(40, 10, f"{total_row:,.2f}", 1, ln=True)

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

    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    return pdf_buffer, receipt_no, subtotal, vat, total


# ------------------------------------------------------------
# SUPABASE STORAGE UPLOAD
# ------------------------------------------------------------
def upload_pdf_to_supabase(pdf_buffer, receipt_no):
    file_path = f"receipts/receipt_{receipt_no}.pdf"
    supabase.storage.from_(BUCKET).upload(
        file_path,
        pdf_buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{file_path}"


# ------------------------------------------------------------
# INVENTORY DEDUCTION (RPC FIXED)
# ------------------------------------------------------------
def deduct_inventory(items):
    for item in items:
        supabase.rpc("deduct_inventory", {
            "item_name_param": item["item"],
            "qty_param": item["quantity"]
        }).execute()


# ------------------------------------------------------------
# SAVE RECEIPT HISTORY
# ------------------------------------------------------------
def save_receipt_history(receipt_no, customer_name, total_amount, created_by, link):
    supabase.table("receipt_history").insert({
        "receipt_no": receipt_no,
        "customer_name": customer_name,
        "total_amount": total_amount,
        "created_by": created_by,
        "receipt_url": link
    }).execute()


def save_receipt_items(receipt_no, items):
    for it in items:
        supabase.table("receipt_items").insert({
            "receipt_no": receipt_no,
            "item_name": it["item"],
            "quantity": it["quantity"],
            "unit_price": it["unit_price"]
        }).execute()


# ------------------------------------------------------------
# USER LOGIN FUNCTIONS
# ------------------------------------------------------------
def login(username, password):
    res = supabase.table("app_users") \
        .select("*") \
        .eq("username", username) \
        .eq("password", password) \
        .execute()
    if res.data:
        return res.data[0]
    return None


# ------------------------------------------------------------
# SESSION STATE INIT
# ------------------------------------------------------------
if "user_info" not in st.session_state:
    st.session_state.user_info = None

if "receipt_items" not in st.session_state:
    st.session_state.receipt_items = []


# ------------------------------------------------------------
# LOGIN PAGE
# ------------------------------------------------------------
if not st.session_state.user_info:
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(username, password)
        if user:
            st.session_state.user_info = user
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid username or password.")

    st.stop()


# ------------------------------------------------------------
# AUTHENTICATED AREA
# ------------------------------------------------------------
role = st.session_state.user_info["role"]
fullname = st.session_state.user_info["full_name"]

# Logout button (top-right)
st.markdown('<div class="header-logout">', unsafe_allow_html=True)
if st.button("🚪 Logout"):
    st.session_state.user_info = None
    st.session_state.receipt_items = []
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------------------------------------
# SIDEBAR MENU BASED ON ROLE
# ------------------------------------------------------------
if role == "admin":
    menu = st.sidebar.radio("Menu", [
        "Generate Receipt",
        "Inventory Viewer",
        "Profit Calculator",
        "Receipt History",
        "User Management"
    ])
else:
    menu = st.sidebar.radio("Menu", [
        "Generate Receipt",
        "Inventory Viewer"
    ])

# ------------------------------------------------------------
# PAGE: Generate Receipt (BOTH ROLES)
# ------------------------------------------------------------
if menu == "Generate Receipt":

    st.title("🧾 Generate Receipt")

    customer_name = st.text_input("Customer Name")

    st.subheader("➕ Add Item")
    with st.expander("Click to Add Item"):
        col1, col2, col3 = st.columns([3, 1, 1])
        item = col1.text_input("Item Name")
        qty = col2.number_input("Quantity", min_value=1, step=1)
        price = col3.number_input("Unit Price", min_value=0.0, step=0.01)

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
        st.info("No items added yet.")

    if st.button("🗑️ Clear Items"):
        st.session_state.receipt_items = []
        st.rerun()

    if st.button("Generate Receipt PDF"):
        if not customer_name:
            st.error("Enter customer name.")
            st.stop()

        if not st.session_state.receipt_items:
            st.error("Add at least one item.")
            st.stop()

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name,
            fullname,
            st.session_state.receipt_items,
            LOGO_PATH
        )

        # Upload PDF
        link = upload_pdf_to_supabase(pdf_buffer, receipt_no)

        # Save history
        save_receipt_history(receipt_no, customer_name, total, fullname, link)
        save_receipt_items(receipt_no, st.session_state.receipt_items)

        # Deduct inventory
        deduct_inventory(st.session_state.receipt_items)

        st.success("Receipt Generated & Saved Successfully")
        st.write("🔗 Receipt URL:", link)

        st.download_button(
            "📄 Download Receipt",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )

# ------------------------------------------------------------
# PAGE: Inventory Viewer (BOTH ROLES)
# ------------------------------------------------------------
elif menu == "Inventory Viewer":
    st.title("📦 Inventory Viewer")

    data = supabase.table("inventory").select("*").execute()
    df = pd.DataFrame(data.data)

    if df.empty:
        st.info("No inventory records.")
    else:
        st.dataframe(df)

# ------------------------------------------------------------
# PAGE: Profit Calculator (ADMIN)
# ------------------------------------------------------------
elif menu == "Profit Calculator" and role == "admin":
    st.title("💰 Profit Calculator")

    sales = supabase.table("receipt_items").select("*").execute()
    df = pd.DataFrame(sales.data)

    if df.empty:
        st.info("No sales yet.")
    else:
        df["total"] = df["quantity"] * df["unit_price"]
        st.metric("Total Revenue", f"NGN{df['total'].sum():,.2f}")
        st.dataframe(df)

# ------------------------------------------------------------
# PAGE: Receipt History (ADMIN ONLY)
# ------------------------------------------------------------
elif menu == "Receipt History" and role == "admin":
    st.title("📚 Receipt History")

    data = supabase.table("receipt_history").select("*").execute()
    df = pd.DataFrame(data.data)

    if df.empty:
        st.info("No receipts found.")
    else:
        st.dataframe(df)

# ------------------------------------------------------------
# PAGE: User Management (ADMIN ONLY)
# ------------------------------------------------------------
elif menu == "User Management" and role == "admin":
    st.title("👥 User Management")

    new_fullname = st.text_input("Full Name")
    new_user = st.text_input("Username")
    new_pass = st.text_input("Password", type="password")
    role_choice = st.selectbox("Role", ["user", "admin"])

    if st.button("Create User"):
        supabase.table("app_users").insert({
            "username": new_user,
            "full_name": new_fullname,
            "password": new_pass,
            "role": role_choice
        }).execute()
        st.success("User created.")
