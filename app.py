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

    pdf.ln(10)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)
    pdf.cell(0, 10, f"Issued By: {issued_by}", ln=True)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(50, 10, "Item", 1)
    pdf.cell(40, 10, "Category", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(35, 10, "Unit Price", 1)
    pdf.cell(35, 10, "Total", 1, ln=True)

    pdf.set_font("Helvetica", "", 12)
    subtotal = 0

    for item in items:
        row_total = item["quantity"] * item["unit_price"]
        subtotal += row_total
        pdf.cell(50, 10, item["item"], 1)
        pdf.cell(40, 10, item.get("category", "Uncategorized"), 1)  # FIXED
        pdf.cell(30, 10, str(item["quantity"]), 1)
        pdf.cell(35, 10, f"{item['unit_price']:,.2f}", 1)
        pdf.cell(35, 10, f"{row_total:,.2f}", 1, ln=True)

    vat = subtotal * VAT_RATE
    total = subtotal + vat

    pdf.ln(5)
    pdf.cell(140)
    pdf.cell(0, 10, f"Subtotal: NGN{subtotal:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 10, f"VAT (7.5%): NGN{vat:,.2f}", ln=True)
    pdf.cell(140)
    pdf.cell(0, 10, f"Total: NGN{total:,.2f}", ln=True)

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
        file_path, pdf_buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{file_path}"


# ------------------------------------------------------------
# DATABASE FUNCTIONS
# ------------------------------------------------------------
def deduct_inventory(item_name, qty):
    supabase.rpc("deduct_inventory", {
        "item_name_param": item_name,
        "qty_param": qty
    }).execute()


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
            "category": item.get("category", "Uncategorized"),
            "quantity": item["quantity"],
            "unit_price": item["unit_price"]
        }).execute()


def login_user(fullname, password):
    res = supabase.table("app_users").select("*").eq("full_name", fullname).eq("password", password).execute()
    if res.data:
        return res.data[0]
    return None


# ------------------------------------------------------------
# SESSION STATE INIT
# ------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_info" not in st.session_state:
    st.session_state.user_info = None

if "receipt_items" not in st.session_state:
    st.session_state.receipt_items = []

if "adding_item" not in st.session_state:
    st.session_state.adding_item = False


# ------------------------------------------------------------
# LOGIN PAGE
# ------------------------------------------------------------
if not st.session_state.logged_in:

    st.title("🔐 SEMILOGE TEXTILES Login")

    fullname = st.text_input("Full Name")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login_user(fullname, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_info = user
            st.rerun()
        else:
            st.error("Invalid login details")

    st.stop()


# ------------------------------------------------------------
# MAIN DASHBOARD
# ------------------------------------------------------------
role = st.session_state.user_info["role"]
fullname = st.session_state.user_info["full_name"]

st.sidebar.success(f"Logged in as: {fullname} ({role})")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.session_state.receipt_items = []
    st.rerun()

menu_options = ["Generate Receipt", "Inventory Viewer"]
if role == "admin":
    menu_options.insert(1, "Create Users")
    menu_options.append("Receipt History")

menu = st.sidebar.radio("Navigation", menu_options)


# ------------------------------------------------------------
# PAGE 1: GENERATE RECEIPT
# ------------------------------------------------------------
if menu == "Generate Receipt":

    st.title("🧾 Generate Receipt")

    customer_name = st.text_input("Customer Name")

    st.subheader("🛒 Items Added")
    if st.session_state.receipt_items:
        st.table(pd.DataFrame(st.session_state.receipt_items))
    else:
        st.info("No items added")

    if st.button("➕ Add Item"):
        st.session_state.adding_item = True

    if st.session_state.adding_item:

        st.subheader("Add New Item")

        item_name = st.text_input("Item Name")
        qty = st.number_input("Quantity", min_value=1, step=1)
        price = st.number_input("Unit Price", min_value=0.0, step=0.01)

        # -------- CATEGORY DROPDOWN --------
        cat_query = supabase.table("inventory").select("category").execute()
        categories = sorted(list({c["category"] for c in cat_query.data if c["category"]}))

        selected_category = st.selectbox(
            "Category",
            ["Select category", *categories, "Other (type manually)"]
        )

        manual_category = st.text_input("Type New Category") if selected_category == "Other (type manually)" else None

        if st.button("Save Item"):

            if selected_category == "Select category":
                st.error("Please select category")
                st.stop()

            category_value = manual_category if selected_category == "Other (type manually)" else selected_category

            # -------- FIXED AREA --------
            st.session_state.receipt_items.append({
                "item": item_name,
                "category": category_value if category_value else "Uncategorized",
                "quantity": qty,
                "unit_price": price
            })
            # -------- END FIX --------

            st.session_state.adding_item = False
            st.rerun()

        if st.button("Cancel"):
            st.session_state.adding_item = False
            st.rerun()

    if st.button("Generate Receipt"):

        if not customer_name:
            st.error("Enter customer name")
            st.stop()

        if not st.session_state.receipt_items:
            st.error("No items added")
            st.stop()

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer_name, st.session_state.receipt_items, fullname, LOGO_PATH
        )

        link = upload_pdf_to_supabase(pdf_buffer, receipt_no)

        save_receipt_history(receipt_no, customer_name, total, fullname, link)
        save_receipt_items(receipt_no, st.session_state.receipt_items)

        for item in st.session_state.receipt_items:
            deduct_inventory(item["item"], item["quantity"])

        st.success("Receipt generated successfully!")
        st.write(f"🔗 Receipt URL: {link}")

        st.download_button(
            "📄 Download Receipt",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )

        st.session_state.receipt_items = []


# ------------------------------------------------------------
# PAGE 2: INVENTORY VIEWER (Admin + Users)
# ------------------------------------------------------------
elif menu == "Inventory Viewer":

    st.title("📦 Inventory Viewer")

    data = supabase.table("inventory").select("*").execute()
    st.dataframe(pd.DataFrame(data.data))


# ------------------------------------------------------------
# PAGE 3: CREATE USERS (Admin Only)
# ------------------------------------------------------------
elif menu == "Create Users":

    if role != "admin":
        st.error("Access denied")
        st.stop()

    st.title("👤 Create New User")

    full_name_new = st.text_input("Full Name")
    password_new = st.text_input("Password", type="password")
    role_new = st.selectbox("Role", ["user", "admin"])

    if st.button("Create User"):
        supabase.table("app_users").insert({
            "full_name": full_name_new,
            "password": password_new,
            "role": role_new
        }).execute()
        st.success("User created successfully")


# ------------------------------------------------------------
# PAGE 4: RECEIPT HISTORY (Admin Only)
# ------------------------------------------------------------
elif menu == "Receipt History":

    if role != "admin":
        st.error("Access denied")
        st.stop()

    st.title("📚 Receipt History")

    res = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute()

    if not res.data:
        st.info("No receipts found")
    else:
        st.dataframe(pd.DataFrame(res.data))
