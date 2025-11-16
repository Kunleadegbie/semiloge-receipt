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
# CONSTANTS
# ------------------------------------------------------------
COMPANY_NAME = "SEMILOGE TEXTILES"
LOGO_PATH = "logo.png"
VAT_RATE = 0.075

# ------------------------------------------------------------
# CSS STYLES
# ------------------------------------------------------------
st.markdown("""
<style>
h1, h2, h3 { text-align: center; color: purple; }
.stButton > button { 
    background-color: purple !important; 
    color:white !important;
    border-radius:8px !important;
    padding:8px 20px !important;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# PDF GENERATOR
# ------------------------------------------------------------
def generate_receipt_pdf(customer_name, items, logo_path, issued_by):

    receipt_no = datetime.now().strftime('%Y%m%d%H%M%S')

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
    pdf.cell(0, 10, f"Receipt No: {receipt_no}", ln=True, align='R')
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='R')
    pdf.cell(0, 10, f"Issued By: {issued_by}", ln=True)

    pdf.ln(8)
    pdf.cell(0, 10, f"Customer Name: {customer_name}", ln=True)

    # Table Header
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 10, "Item", 1)
    pdf.cell(40, 10, "Qty", 1)
    pdf.cell(40, 10, "Unit Price", 1)
    pdf.cell(40, 10, "Total", 1, ln=True)

    pdf.set_font("Helvetica", "", 12)

    subtotal = 0
    for item in items:
        row_total = item["quantity"] * item["unit_price"]
        subtotal += row_total

        pdf.cell(60, 10, item["item_name"], 1)
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
    pdf.cell(0, 10, f"TOTAL: NGN{total:,.2f}", ln=True)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 10, "Thank you for your patronage!", ln=True, align='C')

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)

    return buffer, receipt_no, subtotal, vat, total

# ------------------------------------------------------------
# UPLOAD RECEIPT PDF
# ------------------------------------------------------------
def upload_pdf_to_supabase(buffer, receipt_no):
    path = f"receipts/receipt_{receipt_no}.pdf"
    return supabase.storage.from_(BUCKET).upload(
        path,
        buffer.getvalue(),
        file_options={"content-type": "application/pdf"}
    )

# ------------------------------------------------------------
# INVENTORY FUNCTIONS
# ------------------------------------------------------------
def deduct_inventory(items):
    for item in items:
        supabase.rpc(
            "deduct_inventory",
            {"item_name": item["item_name"], "qty": item["quantity"]}
        ).execute()

def fetch_inventory():
    response = supabase.table("inventory").select("*").execute()
    return response.data if response.data else []

# ------------------------------------------------------------
# SAVE RECEIPT HISTORY
# ------------------------------------------------------------
def save_receipt_history(receipt_no, customer, total, url, issued_by):
    supabase.table("receipt_history").insert({
        "receipt_no": receipt_no,
        "customer_name": customer,
        "total_amount": total,
        "receipt_url": url,
        "issued_by": issued_by
    }).execute()

def save_receipt_items(receipt_no, items):
    for item in items:
        supabase.table("receipt_items").insert({
            "receipt_no": receipt_no,
            "item_name": item["item_name"],
            "quantity": item["quantity"],
            "unit_price": item["unit_price"]
        }).execute()

# ------------------------------------------------------------
# USER AUTHENTICATION
# ------------------------------------------------------------
def login(username, password):
    res = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
    return res.data[0] if res.data else None

def create_user(username, fullname, password, role):
    supabase.table("users").insert({
        "username": username,
        "fullname": fullname,
        "password": password,
        "role": role
    }).execute()

# ------------------------------------------------------------
# SESSION VARIABLES
# ------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "role" not in st.session_state:
    st.session_state.role = None

if "fullname" not in st.session_state:
    st.session_state.fullname = None

if "receipt_items" not in st.session_state:
    st.session_state.receipt_items = []

# ------------------------------------------------------------
# LOGIN PAGE
# ------------------------------------------------------------
if not st.session_state.logged_in:

    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        user = login(username, password)

        if user:
            st.session_state.logged_in = True
            st.session_state.role = user["role"]
            st.session_state.fullname = user["fullname"]
            st.rerun()
        else:
            st.error("Invalid login details")

    st.stop()

# ------------------------------------------------------------
# LOGOUT BUTTON
# ------------------------------------------------------------
st.sidebar.success(f"Logged in as: {st.session_state.fullname} ({st.session_state.role})")

if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.receipt_items = []
    st.rerun()

# ------------------------------------------------------------
# SIDEBAR NAVIGATION
# ------------------------------------------------------------
menu = ["Generate Receipt"]
if st.session_state.role == "admin":
    menu += ["Inventory Viewer", "Profit Calculator", "Receipt History", "Create User"]

choice = st.sidebar.selectbox("Navigation", menu)

# ------------------------------------------------------------
# GENERATE RECEIPT
# ------------------------------------------------------------
if choice == "Generate Receipt":

    st.title("🧾 Generate Receipt")

    customer = st.text_input("Customer Name")

    inventory_data = fetch_inventory()
    inventory_names = [x["item_name"] for x in inventory_data]

    with st.form("add_item_form"):
        item_name = st.selectbox("Select Product", options=inventory_names)
        qty = st.number_input("Quantity", min_value=1)
        price = st.number_input("Unit Price", min_value=0.0, step=0.01)
        submitted = st.form_submit_button("Add Item")

        if submitted:
            st.session_state.receipt_items.append({
                "item_name": item_name,
                "quantity": qty,
                "unit_price": price
            })
            st.success("Item added successfully!")

    if st.session_state.receipt_items:
        st.subheader("Items Added")
        st.table(pd.DataFrame(st.session_state.receipt_items))

    if st.button("🗑️ Clear Items"):
        st.session_state.receipt_items = []
        st.rerun()

    if st.button("Generate Receipt PDF"):

        if not customer:
            st.error("Enter customer name")
            st.stop()

        if not st.session_state.receipt_items:
            st.error("Add at least one item")
            st.stop()

        pdf_buffer, receipt_no, subtotal, vat, total = generate_receipt_pdf(
            customer, st.session_state.receipt_items, LOGO_PATH, st.session_state.fullname
        )

        upload_pdf_to_supabase(pdf_buffer, receipt_no)

        receipt_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/receipts/receipt_{receipt_no}.pdf"

        save_receipt_history(receipt_no, customer, total, receipt_url, st.session_state.fullname)
        save_receipt_items(receipt_no, st.session_state.receipt_items)
        deduct_inventory(st.session_state.receipt_items)

        st.success("Receipt generated successfully!")
        st.write("🔗 Download Link:", receipt_url)

        st.download_button(
            "📥 Download PDF",
            data=pdf_buffer,
            file_name=f"receipt_{receipt_no}.pdf",
            mime="application/pdf"
        )

# ------------------------------------------------------------
# INVENTORY VIEWER (ADMIN ONLY)
# ------------------------------------------------------------
elif choice == "Inventory Viewer":
    st.title("📦 Inventory Viewer")
    data = fetch_inventory()
    st.dataframe(pd.DataFrame(data))

# ------------------------------------------------------------
# PROFIT CALCULATOR (ADMIN ONLY)
# ------------------------------------------------------------
elif choice == "Profit Calculator":
    st.title("💰 Profit Calculator")

    receipts = supabase.table("receipt_items").select("*").execute().data
    if receipts:
        df = pd.DataFrame(receipts)
        df["profit"] = df["unit_price"] * df["quantity"]
        st.dataframe(df)
        st.metric("Total Profit", f"NGN{df['profit'].sum():,.2f}")
    else:
        st.info("No sales history found.")

# ------------------------------------------------------------
# RECEIPT HISTORY (ADMIN ONLY)
# ------------------------------------------------------------
elif choice == "Receipt History":
    st.title("📚 Receipt History")

    data = supabase.table("receipt_history").select("*").order("created_at", desc=True).execute().data

    if not data:
        st.info("No receipts available")
    else:
        st.dataframe(pd.DataFrame(data))

# ------------------------------------------------------------
# CREATE USER (ADMIN ONLY)
# ------------------------------------------------------------
elif choice == "Create User":
    st.title("👤 Create New User")

    new_username = st.text_input("Username")
    fullname = st.text_input("Full Name")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["user", "admin"])

    if st.button("Create User"):
        create_user(new_username, fullname, password, role)
        st.success("User account created successfully!")
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


