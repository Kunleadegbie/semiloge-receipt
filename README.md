
# ✅ **1. requirements.txt**

These are the exact dependencies your app needs.

```
streamlit
fpdf2
pandas
supabase
python-dotenv
requests
```

> ⚠️ If Streamlit Cloud ever complains about the `supabase` version, I can pin it (e.g., `supabase==2.4.4`).
> But the generic version normally works fine.

---

# ✅ **2. .gitignore**

This ensures NO secrets, cache files, or local system files get uploaded to GitHub.

```
# Streamlit secrets
.streamlit/secrets.toml

# Python cache
__pycache__/
*.pyc

# MacOS / Windows junk
.DS_Store
desktop.ini

# Local environment
.env
venv/
.venv/

# PDF receipts generated locally
*.pdf

# Any temp files
tmp/
temp/
```

✔ Safe
✔ Clean GitHub repo
✔ No credential leakage

---

# ✅ **3. .streamlit/secrets.toml (PLACE THIS ON STREAMLIT CLOUD ONLY)**

⚠️ **DO NOT put this file on GitHub. It belongs only inside Streamlit Cloud → Settings → Secrets.**

Here is the template you should paste in **Streamlit Cloud → App Settings → Secrets**:

```toml
SUPABASE_URL = "https://luvicbfapuqbxdjfoegd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx1dmljYmZhcHVxYnhkamZvZWdkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjMxMzM2NTMsImV4cCI6MjA3ODcwOTY1M30.35ltjT0sU9f6Uc-q-YPafk-ptx0T_kWe4TG8A0lLbfU"
BUCKET_NAME = "semiloge-receipts"
```

✔ Secure
✔ Only accessible to your Streamlit app
✔ Not committed to GitHub

---

# ✅ **4. README.md (for your GitHub repo)**

---

# 🧾 SEMILOGE TEXTILES — Receipt Generator (Streamlit + Supabase)

A professional multi-item receipt generator for **SEMILOGE TEXTILES**, featuring:

### ✅ Multi-item receipts (up to 10 items)

### ✅ VAT Auto-calculation (7.5%)

### ✅ Automatic inventory deduction (Supabase)

### ✅ PDF receipt generation

### ✅ Upload receipts to Supabase Storage

### ✅ Store receipt metadata in Supabase `receipt_logs`

### ✅ View receipt archive

### ✅ Stylish purple theme

### ✅ Cloud-ready (Streamlit Cloud)

---

## 🚀 Live App

*(Add your Streamlit Cloud link here after deployment)*

```
https://your-app-name.streamlit.app
```

---

## 📦 Features

### ✔ Add up to 10 receipt line items

* Item name
* Quantity
* Unit price
* Automatic total

### ✔ Live preview table

### ✔ Clear items button

### ✔ VAT calculation

### ✔ NGN formatting

### ✔ Receipt numbering

### ✔ File name format:

```
receipt_<CustomerName>_<ReceiptNo>.pdf
```

### ✔ Cloud upload

Receipts automatically upload to your Supabase Storage bucket:
`semiloge-receipts`

### ✔ Inventory deduction

* If item exists → deduct stock
* If insufficient stock → warn
* If not found → warn
* Does NOT block the receipt (Option C)

### ✔ Receipt archive

Displays all stored receipts with download links.

---

## 🛠️ Installation (Local)

```bash
git clone <your-repo>
cd <your-repo>
pip install -r requirements.txt
streamlit run app.py
```

---

## 🔐 Create `.streamlit/secrets.toml`

Create folder:

```
mkdir .streamlit
```

Inside it, create:

```
secrets.toml
```

Paste:

```toml
SUPABASE_URL = "https://luvicbfapuqbxdjfoegd.supabase.co"
SUPABASE_KEY = "<your-anon-key>"
BUCKET_NAME = "semiloge-receipts"
```

---

## 🗄️ Supabase Setup

### 1. Create Tables

#### **inventory**

```sql
create table if not exists public.inventory (
    id bigint generated always as identity primary key,
    item_name text not null,
    quantity integer not null,
    unit_price numeric not null,
    created_at timestamp with time zone default now()
);
```

#### **receipt_logs**

```sql
create table if not exists public.receipt_logs (
    id bigint generated always as identity primary key,
    receipt_no text not null,
    customer_name text not null,
    total_amount numeric not null,
    pdf_url text not null,
    created_at timestamp with time zone default now()
);
```

### 2. Storage Bucket

Create bucket:

```
semiloge-receipts
```

### 3. Storage Policies

```sql
create policy "Allow public read"
on storage.objects for select
using (bucket_id = 'semiloge-receipts');

create policy "Allow uploads"
on storage.objects for insert
to public
with check (bucket_id = 'semiloge-receipts');
```

### 4. Disable RLS (recommended)

```sql
alter table public.inventory disable row level security;
alter table public.receipt_logs disable row level security;
```

---

## 🌐 Deploy on Streamlit Cloud

1. Push repo to GitHub
2. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud)
3. Create new app
4. Add your GitHub repo
5. In Settings → Secrets, paste:

```toml
SUPABASE_URL = "https://luvicbfapuqbxdjfoegd.supabase.co"
SUPABASE_KEY = "<your-anon-key>"
BUCKET_NAME = "semiloge-receipts"
```

6. Deploy 🎉

---

## 👨‍💻 Author

Developed by **Dr. Adekunle Adegbie (SEMILOGE TEXTILES)**
Built with ❤️ using Python, Streamlit, and Supabase.

---



