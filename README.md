Here’s a professional, Streamlit-ready `README.md` tailored for your **SEMILOGE TEXTILES Receipt Generator** app 👇

---

# 🧾 SEMILOGE TEXTILES Receipt Generator

A clean, modern Streamlit application that lets SEMILOGE TEXTILES generate **VAT-compliant receipts** for customers.
It supports multiple items per receipt, automatic VAT (7.5%) computation, branded PDF output with the company logo, and a purple-themed, mobile-friendly interface.

---

## 🚀 Features

* 🟣 **Beautiful UI:** custom purple theme, rounded buttons, and centered layout
* 🧍 **Customer Details:** enter customer name once per receipt
* 🛍️ **Multiple Items:** add up to 10 items via expandable panels
* 💰 **Automatic VAT Calculation:** 7.5 % of subtotal is added to the total
* 🧾 **Instant PDF Receipt:** branded with company logo and timestamped receipt number
* 🔄 **Clear All Button:** reset session and start a new receipt without refreshing
* ☁️ **Streamlit Cloud Ready:** no local dependencies needed

---

## 🧱 Project Structure

```
semiloge-receipt/
│
├── app.py                 # Main Streamlit app
├── logo.png               # Company logo (ensure this file is in the repo)
├── requirements.txt       # Python dependencies
└── README.md              # Project documentation
```

---

## ⚙️ Setup and Installation

### 1️⃣ Clone the repository

```bash
git clone https://github.com/<your-username>/semiloge-receipt.git
cd semiloge-receipt
```

### 2️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ Run locally

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 🌐 Deployment on Streamlit Cloud

1. Push your repository to GitHub (including `logo.png`).
2. Go to [streamlit.io/cloud](https://streamlit.io/cloud).
3. Click **New app → Connect GitHub → Select repo → Deploy**.
4. That’s it 🎉 — your receipt generator is live!

---

## 🧩 Requirements

Add the following to `requirements.txt`:

```
streamlit
fpdf2
pandas
```

---

## 🖼️ Logo Handling

To ensure the app works both locally and on Streamlit Cloud, the logo is loaded using a relative path:

```python
import os
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")
```

Make sure `logo.png` exists in the same directory as `app.py`.

---

## 📄 Receipt Number Logic

Each receipt number is auto-generated using a timestamp:

```
YYYYMMDDHHMMSS
```

This guarantees a unique receipt ID for every transaction.

---

## 👏 Acknowledgments

Developed by **Dr. Adekunle Adegbie (SEMILOGE TEXTILES)**
Powered by **Python + Streamlit + FPDF2**

