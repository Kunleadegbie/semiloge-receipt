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
# LOGIN FUNCTIONS
# ------------------------------------------------------------
def login(full_name, password):
    res = supabase.table("app_users")\
        .select("*")\
        .eq("full_name", full_name)\
        .eq("password", password)\
        .execute()

    if res.data:
        return res.data[0]
    return None


def create_user(full_name, password, role):
    supabase.table("app_users").insert({
        "full_name": full_name,
        "password": password,
        "role": role
    }).execute()


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
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align="C")

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Receipt No: {receipt_no}", ln=True, align="R")
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align="R")
    pdf.cell(0, 10, f"Issued By: {issued_by}", ln=True)

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
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align="C")

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)

    return buffer, receipt_no, subtotal, vat, total


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
# INVENTORY DEDUCTION USING FUNCTION (stable)
# ------------------------------------------------------------
def deduct_inventory(items):
    for item in items:
        supabase.rpc(
            "deduct_inventory",
            {"item_name_text": item["item"], "qty_int": item["quantity"]}
        ).execute()


# ------------------------------------------------------------
# SAVE RECEIPT HISTORY
# ------------------------------------------------------------
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

if "user_info" not in st.session_state:
    st.session_state.user_info = None

if "receipt_items" not in st.session_state:
    st.session_state.receipt_items = []



# ------------------------------------------------------------
# LOGIN PAGE
# ------------------------------------------------------------
if not st.session_state.logged_in:

    st.title("🔐 Login to Continue")

    full_name = st.text_input("Full Name")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(full_name, password)

        if user:
            st.session_state.logged_in = True
            st.session_state.user_info = user
            st.rerun()
        else:
            st.error("Invalid login credentials.")

    st.stop()


# ------------------------------------------------------------
# LOGOUT BUTTON
# ------------------------------------------------------------
st.sidebar.button("🚪 Logout", on_click=lambda: st.session_state.update({
    "logged_in": False,
    "user_info": None
}))

# ------------------------------------------------------------
# CHECK LOGIN SESSION BEFORE LOADING DASHBOARD
# ------------------------------------------------------------

if "user_info" not in st.session_state or st.session_state.user_info is None:
    st.error("Session expired. Please log in again.")
    st.session_state.logged_in = False
    st.rerun()

role = st.session_state.user_info["role"]

# ------------------------------------------------------------
# SIDEBAR NAVIGATION (Role-based)
# ------------------------------------------------------------
role = st.session_state.user_info["role"]

if role == "Admin":
    menu = st.sidebar.radio(
        "Navigation",
        ["Generate Receipt", "Receipt History", "Inventory Viewer", "User Management", "Logout"]
    )
else:
    # Regular User
    menu = st.sidebar.radio(
        "Navigation",
        ["Generate Receipt", "Logout"]
    )

# ------------------------------------------------------------
# PAGE: GENERATE RECEIPT
# ------------------------------------------------------------
if menu == "Generate Receipt":

    st.title("🧾 Generate Receipt")

    customer_name = st.text_input("Customer Name")

    # ADD ITEM PANEL
    with st.expander("➕ Add Item"):
        item = st.text_input("Item Name")
        qty = st.number_input("Quantity", min_value=0, step=1)
        price = st.number_input("Unit Price", min_value=0.0, step=0.01)

        if st.button("Add Item"):
            if not item or qty <= 0:
                st.error("Enter valid item details.")
            else:
                st.session_state.receipt_items.append({
                    "item": item,
                    "quantity": qty,
                    "unit_price": price
                })
                st.success("Item added successfully!")
                st.rerun()

    st.subheader("📝 Items Added")

    if st.session_state.receipt_items:
        st.table(pd.DataFrame(st.session_state.receipt_items))
    else:
        st.info("No items added.")

    if st.button("🗑️ Clear Items"):
        st.session_state.receipt_items = []
        st.rerun()

    if st.button("Generate Receipt Now"):
        if not customer_name:
            st.error("Enter customer name.")
            st.stop()

        if not st.session_state.receipt_items:
            st.error("Add items before generating receipt.")
            st.stop()

        issued_by = st.session_state.user_info["full_name"]

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name,
            st.session_state.receipt_items,
            LOGO_PATH,
            issued_by
        )

        upload_pdf_to_supabase(pdf_buffer, receipt_no)

        receipt_url = (
            f"{SUPABASE_URL}/storage/v1/object/public/"
            f"{BUCKET}/receipts/receipt_{receipt_no}.pdf"
        )

        save_receipt_history(receipt_no, customer_name, total, receipt_url, issued_by)
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
# PAGE: RECEIPT HISTORY (ADMIN ONLY)
# ------------------------------------------------------------
elif menu == "Receipt History":

    st.title("📚 All Receipts")

    data = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute()
    df = pd.DataFrame(data.data)

    st.dataframe(df)


# ------------------------------------------------------------
# PAGE: INVENTORY VIEWER
# ------------------------------------------------------------
elif menu == "Inventory Viewer":

    st.title("📦 Inventory Overview")

    data = supabase.table("inventory").select("*").order("item_name").execute()
    df = pd.DataFrame(data.data)

    st.dataframe(df)


# ------------------------------------------------------------
# PAGE: CREATE USER (ADMIN ONLY)
# ------------------------------------------------------------
elif menu == "Create User":

    st.title("👤 Create New User")

    full_name_new = st.text_input("Full Name")
    password_new = st.text_input("Password")
    role_new = st.selectbox("Role", ["User", "Admin"])

    if st.button("Create User"):
        create_user(full_name_new, password_new, role_new)
        st.success("User created successfully!")
