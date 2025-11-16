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
h1, h2, h3 { text-align: center; color: purple; }
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
    pdf.cell(30, 10, COMPANY_NAME, ln=True, align="C")

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Receipt No: {receipt_no}", ln=True, align="R")
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align="R")

    pdf.ln(8)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)
    pdf.cell(0, 10, f"Issued By: {issued_by}", ln=True)

    pdf.ln(5)
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
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align="C")

    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    return pdf_buffer, receipt_no, subtotal, vat, total


# ------------------------------------------------------------
# SUPABASE STORAGE UPLOAD
# ------------------------------------------------------------
def upload_receipt(receipt_no, pdf_buffer):
    file_path = f"receipts/receipt_{receipt_no}.pdf"
    supabase.storage.from_(BUCKET).upload(
        file_path,
        pdf_buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{file_path}"


# ------------------------------------------------------------
# WRITE RECEIPT HISTORY
# ------------------------------------------------------------
def save_receipt_history(receipt_no, customer_name, total, issued_by, receipt_url):
    supabase.table("receipt_history").insert({
        "receipt_no": receipt_no,
        "customer_name": customer_name,
        "total_amount": total,
        "issued_by": issued_by,
        "receipt_url": receipt_url
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
# CORRECT INVENTORY DEDUCTION FUNCTION  ✅ FIXED
# ------------------------------------------------------------
def deduct_inventory(items):
    for item in items:
        supabase.rpc("deduct_inventory", {
            "item_name": item["item"],
            "quantity": item["quantity"]
        }).execute()


# ------------------------------------------------------------
# LOGIN HANDLING
# ------------------------------------------------------------
def login(username, password):
    res = supabase.table("users_app").select("*").eq("username", username).eq("password", password).execute()
    if res.data:
        return res.data[0]
    return None


# ------------------------------------------------------------
# SESSION STATE INIT
# ------------------------------------------------------------
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
        user = login(username, password)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Invalid login details.")

    st.stop()


# ------------------------------------------------------------
# AFTER LOGIN — SHOW DASHBOARD
# ------------------------------------------------------------
full_name = st.session_state.user["full_name"]
role = st.session_state.user["role"]

st.sidebar.title(f"Welcome, {full_name} 👋")
if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.session_state.receipt_items = []
    st.rerun()

# MENU
if role == "Admin":
    menu = st.sidebar.radio("Menu", [
        "Generate Receipt",
        "Inventory Viewer",
        "Receipt History",
        "Create User",
        "Profit Calculator"
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

    st.title("🧾 Generate Receipt")

    customer_name = st.text_input("Customer Name")

    # ADD ITEM POPUP
    with st.expander("➕ Add Item"):
        item = st.text_input("Item Name", key="new_item")
        qty = st.number_input("Quantity", min_value=1, step=1, key="new_qty")
        price = st.number_input("Unit Price (NGN)", min_value=0.0, step=0.01, key="new_price")

        if st.button("Add Item"):
            st.session_state.receipt_items.append({
                "item": item,
                "quantity": qty,
                "unit_price": price
            })
            st.success("Item added.")
            st.rerun()

    # SHOW ITEMS TABLE
    st.subheader("📝 Items Added")

    if st.session_state.receipt_items:
        df = pd.DataFrame(st.session_state.receipt_items)
        st.table(df)
    else:
        st.info("No items added yet.")

    if st.button("🗑️ Clear Items"):
        st.session_state.receipt_items = []
        st.rerun()

    # GENERATE RECEIPT BUTTON
    if st.button("Generate Receipt PDF"):
        if not customer_name:
            st.error("Enter customer name.")
            st.stop()

        if not st.session_state.receipt_items:
            st.error("Add at least one item.")
            st.stop()

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name, st.session_state.receipt_items, full_name, LOGO_PATH
        )

        link = upload_receipt(receipt_no, pdf_buffer)

        save_receipt_history(receipt_no, customer_name, total, full_name, link)
        save_receipt_items(receipt_no, st.session_state.receipt_items)

        deduct_inventory(st.session_state.receipt_items)

        st.success("Receipt generated successfully!")
        st.write(f"🔗 Receipt Link: {link}")

        st.download_button(
            "📄 Download Receipt",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )


# ------------------------------------------------------------
# PAGE: INVENTORY VIEWER (Admin + User)
# ------------------------------------------------------------
elif menu == "Inventory Viewer":
    st.title("📦 Inventory Viewer")

    data = supabase.table("inventory").select("*").execute()

    if not data.data:
        st.info("No inventory found.")
    else:
        st.dataframe(pd.DataFrame(data.data))


# ------------------------------------------------------------
# PAGE: RECEIPT HISTORY (Admin Only)
# ------------------------------------------------------------
elif menu == "Receipt History" and role == "Admin":
    st.title("📚 Receipt History")

    data = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute()

    if not data.data:
        st.info("No receipts yet.")
    else:
        st.dataframe(pd.DataFrame(data.data))


# ------------------------------------------------------------
# PAGE: CREATE USER (Admin Only)
# ------------------------------------------------------------
elif menu == "Create User" and role == "Admin":
    st.title("➕ Create New User")

    full = st.text_input("Full Name")
    un = st.text_input("Username")
    pw = st.text_input("Password", type="password")
    rl = st.selectbox("Role", ["admin", "user"])

    if st.button("Create User"):
        supabase.table("users_app").insert({
            "full_name": full,
            "username": un,
            "password": pw,
            "role": rl
        }).execute()
        st.success("User created successfully")


# ------------------------------------------------------------
# PAGE: PROFIT CALCULATOR (Admin Only)
# ------------------------------------------------------------
elif menu == "Profit Calculator" and role == "Admin":
    st.title("📈 Profit Calculator")

    data = supabase.table("inventory").select("item_name, unit_price, quantity").execute()

    if not data.data:
        st.info("No inventory items.")
    else:
        df = pd.DataFrame(data.data)
        df["Total Value"] = df["unit_price"] * df["quantity"]

        st.metric("Total Inventory Value", f"₦{df['Total Value'].sum():,.2f}")
        st.dataframe(df)
