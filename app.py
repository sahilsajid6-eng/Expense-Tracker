import io
import sqlite3
from datetime import datetime
import streamlit as st
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# --- OOP MODEL & DATABASE LAYER ---

class Expense:
    """Represents an individual expense entry."""
    def __init__(self, amount: float, category: str, date: str, expense_id: int = None):
        self.id = expense_id
        self.amount = float(amount)
        self.category = category.strip()
        self.date = str(date)


class DatabaseManager:
    """Handles SQLite database operations."""
    def __init__(self, db_name="expenses.db"):
        self.db_name = db_name
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_name)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    date TEXT NOT NULL
                )
            """)
            conn.commit()

    def add_expense(self, expense: Expense):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO expenses (amount, category, date) VALUES (?, ?, ?)",
                (expense.amount, expense.category, expense.date)
            )
            conn.commit()

    def fetch_all(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, amount, category, date FROM expenses ORDER BY date DESC")
            rows = cursor.fetchall()
            return [Expense(expense_id=r[0], amount=r[1], category=r[2], date=r[3]) for r in rows]

    def delete_expense(self, expense_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            conn.commit()


class ReportGenerator:
    """Handles calculations, charts, and file exports."""

    @staticmethod
    def calculate_category_breakdown(expenses):
        breakdown = {}
        for exp in expenses:
            breakdown[exp.category] = breakdown.get(exp.category, 0.0) + exp.amount
        return breakdown

    @staticmethod
    def generate_chart(expenses):
        breakdown = ReportGenerator.calculate_category_breakdown(expenses)
        fig, ax = plt.subplots(figsize=(6, 4))
        
        if not breakdown:
            ax.text(0.5, 0.5, 'No Expenses Recorded', horizontalalignment='center', verticalalignment='center')
            ax.axis('off')
        else:
            categories = list(breakdown.keys())
            amounts = list(breakdown.values())
            ax.bar(categories, amounts, color='#3B82F6')
            ax.set_title('Expenses by Category')
            ax.set_xlabel('Category')
            ax.set_ylabel('Amount ($)')
            plt.xticks(rotation=15)
            plt.tight_layout()

        return fig

    @staticmethod
    def generate_csv(expenses):
        output = io.StringIO()
        output.write("ID,Amount,Category,Date\n")
        for exp in expenses:
            output.write(f"{exp.id},{exp.amount:.2f},{exp.category},{exp.date}\n")
        return output.getvalue()

    @staticmethod
    def generate_pdf(expenses):
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 750, "Expense Tracker Report")
        
        p.setFont("Helvetica", 10)
        p.drawString(100, 735, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        p.setFont("Helvetica-Bold", 11)
        p.drawString(100, 700, "ID")
        p.drawString(150, 700, "Date")
        p.drawString(250, 700, "Category")
        p.drawString(400, 700, "Amount ($)")
        p.line(100, 693, 500, 693)
        
        y = 675
        total = 0.0
        p.setFont("Helvetica", 10)
        for exp in expenses:
            if y < 50:
                p.showPage()
                y = 750
            p.drawString(100, y, str(exp.id))
            p.drawString(150, y, exp.date)
            p.drawString(250, y, exp.category)
            p.drawString(400, y, f"{exp.amount:.2f}")
            total += exp.amount
            y -= 20

        p.line(100, y + 10, 500, y + 10)
        p.setFont("Helvetica-Bold", 11)
        p.drawString(250, y - 10, "Total:")
        p.drawString(400, y - 10, f"${total:.2f}")

        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer.getvalue()


# --- STREAMLIT UI ---

st.set_page_config(page_title="Expense Tracker", layout="wide")

# Initialize DB
db = DatabaseManager()

st.title("💸 Expense Tracker")

# App Layout
col1, col2 = st.columns([1, 1])

# Left Column: Add Entry & Summary
with col1:
    st.subheader("Add New Expense")
    
    with st.form(key="expense_form", clear_on_submit=True):
        amount = st.number_input("Amount ($)", min_value=0.01, step=0.01)
        category = st.selectbox("Category", ["Food", "Travel", "Study", "Entertainment", "Bills"])
        expense_date = st.date_input("Date", datetime.now())
        submit_button = st.form_submit_button(label="Add Expense")

        if submit_button:
            new_expense = Expense(amount=amount, category=category, date=expense_date)
            db.add_expense(new_expense)
            st.success("Expense added successfully!")
            st.rerun()

    st.divider()

    # Load data for totals
    expenses = db.fetch_all()
    total_spent = sum(e.amount for e in expenses)
    breakdown = ReportGenerator.calculate_category_breakdown(expenses)

    st.subheader("Summary")
    st.metric(label="Total Spent", value=f"${total_spent:.2f}")

    if breakdown:
        for cat, amt in breakdown.items():
            st.write(f"- **{cat}:** ${amt:.2f}")

    st.divider()

    st.subheader("Export Data")
    exp_col1, exp_col2 = st.columns(2)
    
    with exp_col1:
        csv_data = ReportGenerator.generate_csv(expenses)
        st.download_button(
            label="📄 Export CSV",
            data=csv_data,
            file_name="expense_report.csv",
            mime="text/csv"
        )
        
    with exp_col2:
        pdf_data = ReportGenerator.generate_pdf(expenses)
        st.download_button(
            label="🔴 Export PDF",
            data=pdf_data,
            file_name="expense_report.pdf",
            mime="application/pdf"
        )

# Right Column: Chart & Table
with col2:
    st.subheader("Category Breakdown")
    fig = ReportGenerator.generate_chart(expenses)
    st.pyplot(fig)

    st.subheader("Expense History")
    if expenses:
        for exp in expenses:
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            c1.write(exp.date)
            c2.write(exp.category)
            c3.write(f"${exp.amount:.2f}")
            if c4.button("❌", key=f"del_{exp.id}"):
                db.delete_expense(exp.id)
                st.rerun()
    else:
        st.info("No expense entries found.")