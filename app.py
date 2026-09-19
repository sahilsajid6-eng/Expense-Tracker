import io
import sqlite3
from datetime import datetime
import streamlit as st
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# ==============================================================================
# 1. OOP DATA MODELS & DATABASE MANAGER
# ==============================================================================

class Expense:
    """Represents an individual expense item."""
    def __init__(self, amount: float, category: str, date: str, expense_id: int = None):
        self.id = expense_id
        self.amount = float(amount)
        self.category = category.strip()
        self.date = str(date)


class UserDemographics:
    """Represents user demographic metadata."""
    def __init__(self, age_group: str, occupation: str, location: str, id: int = None):
        self.id = id
        self.age_group = age_group
        self.occupation = occupation
        self.location = location


class DatabaseManager:
    """Handles SQLite database connection and operations."""
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS demographics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    age_group TEXT NOT NULL,
                    occupation TEXT NOT NULL,
                    location TEXT NOT NULL
                )
            """)
            conn.commit()

    # Expense CRUD Operations
    def add_expense(self, expense: Expense):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO expenses (amount, category, date) VALUES (?, ?, ?)",
                (expense.amount, expense.category, expense.date)
            )
            conn.commit()

    def fetch_all_expenses(self):
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

    # Demographics CRUD Operations
    def save_demographics(self, demo: UserDemographics):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM demographics")  # Overwrite with latest profile
            cursor.execute(
                "INSERT INTO demographics (age_group, occupation, location) VALUES (?, ?, ?)",
                (demo.age_group, demo.occupation, demo.location)
            )
            conn.commit()

    def fetch_demographics(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT age_group, occupation, location FROM demographics ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return UserDemographics(age_group=row[0], occupation=row[1], location=row[2])
            return None


# ==============================================================================
# 2. REPORT GENERATOR & EXPORTER
# ==============================================================================

class ReportGenerator:
    """Generates charts, CSV data, and PDF reports."""

    @staticmethod
    def calculate_category_breakdown(expenses):
        breakdown = {}
        for exp in expenses:
            breakdown[exp.category] = breakdown.get(exp.category, 0.0) + exp.amount
        return breakdown

    @staticmethod
    def generate_bar_chart(expenses):
        breakdown = ReportGenerator.calculate_category_breakdown(expenses)
        fig, ax = plt.subplots(figsize=(6, 4))
        if not breakdown:
            ax.text(0.5, 0.5, 'No Expenses Recorded', horizontalalignment='center', verticalalignment='center')
            ax.axis('off')
        else:
            categories = list(breakdown.keys())
            amounts = list(breakdown.values())
            ax.bar(categories, amounts, color='#2563EB')
            ax.set_ylabel('Amount ($)')
            ax.set_title('Category Spending')
            plt.xticks(rotation=20)
            plt.tight_layout()
        return fig

    @staticmethod
    def generate_pie_chart(expenses):
        breakdown = ReportGenerator.calculate_category_breakdown(expenses)
        fig, ax = plt.subplots(figsize=(6, 4))
        if not breakdown:
            ax.text(0.5, 0.5, 'No Expenses Recorded', horizontalalignment='center', verticalalignment='center')
            ax.axis('off')
        else:
            categories = list(breakdown.keys())
            amounts = list(breakdown.values())
            ax.pie(
                amounts, 
                labels=categories, 
                autopct='%1.1f%%', 
                startangle=140, 
                colors=['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']
            )
            ax.set_title('Spending Share')
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
    def generate_pdf(expenses, demo):
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Header
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 750, "Expense & Demographic Report")
        
        p.setFont("Helvetica", 10)
        p.drawString(100, 735, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Demographics Summary
        if demo:
            p.setFont("Helvetica-Bold", 11)
            p.drawString(100, 705, "User Demographics Profile:")
            p.setFont("Helvetica", 10)
            p.drawString(100, 690, f"Age Group: {demo.age_group} | Occupation: {demo.occupation} | Location: {demo.location}")
            y_start = 655
        else:
            y_start = 690

        # Expense Table Header
        p.setFont("Helvetica-Bold", 11)
        p.drawString(100, y_start, "Date")
        p.drawString(220, y_start, "Category")
        p.drawString(380, y_start, "Amount ($)")
        p.line(100, y_start - 5, 500, y_start - 5)

        y = y_start - 20
        total = 0.0
        p.setFont("Helvetica", 10)
        
        for exp in expenses:
            if y < 50:  # Page overflow check
                p.showPage()
                y = 750
            p.drawString(100, y, str(exp.date))
            p.drawString(220, y, str(exp.category))
            p.drawString(380, y, f"${exp.amount:.2f}")
            total += exp.amount
            y -= 20

        p.line(100, y + 10, 500, y + 10)
        p.setFont("Helvetica-Bold", 11)
        p.drawString(220, y - 10, "Total Spent:")
        p.drawString(380, y - 10, f"${total:.2f}")

        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer.getvalue()


# Initialize Database Manager Globally
db = DatabaseManager()


# ==============================================================================
# 3. PAGE FUNCTIONS
# ==============================================================================

def main_dashboard():
    st.title("💸 Expense Tracker Dashboard")
    st.caption("Log expenses and update user demographics profile.")

    # Top Navigation Links
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("📊 Go to Visual Analytics Page", use_container_width=True):
            st.switch_page(page_charts)
    with nav_col2:
        if st.button("👤 Go to Demographics & Reports Page", use_container_width=True):
            st.switch_page(page_demographics)

    st.divider()

    col1, col2 = st.columns([1, 1])

    # Left Column: Inputs & Forms
    with col1:
        st.subheader("➕ Log New Expense")
        with st.form(key="expense_form", clear_on_submit=True):
            amount = st.number_input("Amount ($)", min_value=0.01, step=0.01)
            category = st.selectbox("Category", ["Food", "Travel", "Study", "Entertainment", "Bills", "Shopping"])
            expense_date = st.date_input("Date", datetime.now())
            submit_button = st.form_submit_button(label="Save Expense")

            if submit_button:
                db.add_expense(Expense(amount=amount, category=category, date=expense_date))
                st.success("Expense added successfully!")
                st.rerun()

        st.subheader("⚙️ Update Demographics Profile")
        current_demo = db.fetch_demographics()
        
        default_age = current_demo.age_group if current_demo else "18-24"
        default_occ = current_demo.occupation if current_demo else "Student"
        default_loc = current_demo.location if current_demo else "Urban"

        age_options = ["<18", "18-24", "25-34", "35-49", "50+"]
        occ_options = ["Student", "Employed", "Self-Employed", "Freelancer", "Other"]
        loc_options = ["Urban", "Suburban", "Rural"]

        with st.form(key="demo_form"):
            age_group = st.selectbox("Age Group", age_options, index=age_options.index(default_age))
            occupation = st.selectbox("Occupation", occ_options, index=occ_options.index(default_occ))
            location = st.selectbox("Location Type", loc_options, index=loc_options.index(default_loc))
            save_demo = st.form_submit_button("Update Profile")

            if save_demo:
                db.save_demographics(UserDemographics(age_group=age_group, occupation=occupation, location=location))
                st.success("Demographics profile updated!")
                st.rerun()

    # Right Column: Recent Activity & Quick Overview
    with col2:
        expenses = db.fetch_all_expenses()
        total_spent = sum(e.amount for e in expenses)

        st.subheader("📋 Quick Overview")
        st.metric(label="Total Expenses Recorded", value=f"${total_spent:.2f}")

        st.write("### Expense History Log")
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
            st.info("No expense entries logged yet.")


def charts_page():
    if st.button("⬅️ Return to Main Dashboard"):
        st.switch_page(page_main)

    st.title("📊 Visual Analytics & Charts")

    expenses = db.fetch_all_expenses()

    if not expenses:
        st.warning("No expense data recorded yet. Return to the main page to add expenses.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Category Distribution (Bar Chart)")
            bar_fig = ReportGenerator.generate_bar_chart(expenses)
            st.pyplot(bar_fig)

        with col2:
            st.subheader("Category Breakdown (Pie Chart)")
            pie_fig = ReportGenerator.generate_pie_chart(expenses)
            st.pyplot(pie_fig)


def demographics_page():
    if st.button("⬅️ Return to Main Dashboard"):
        st.switch_page(page_main)

    st.title("👤 Demographic Insights & Export Reports")

    expenses = db.fetch_all_expenses()
    demo = db.fetch_demographics()

    st.subheader("User Demographic Profile")
    if demo:
        d_col1, d_col2, d_col3 = st.columns(3)
        d_col1.metric("Age Group", demo.age_group)
        d_col2.metric("Occupation", demo.occupation)
        d_col3.metric("Location Type", demo.location)
    else:
        st.info("No demographic profile set. Update your profile on the main dashboard.")

    st.divider()

    st.subheader("📥 Export Summary Data")
    exp_col1, exp_col2 = st.columns(2)

    with exp_col1:
        csv_bytes = ReportGenerator.generate_csv(expenses)
        st.download_button(
            label="📄 Export to CSV",
            data=csv_bytes,
            file_name="expense_report.csv",
            mime="text/csv",
            use_container_width=True
        )

    with exp_col2:
        pdf_bytes = ReportGenerator.generate_pdf(expenses, demo)
        st.download_button(
            label="🔴 Export to PDF",
            data=pdf_bytes,
            file_name="demographic_expense_report.pdf",
            mime="application/pdf",
            use_container_width=True
        )


# ==============================================================================
# 4. MULTI-PAGE ROUTING SYSTEM
# ==============================================================================

st.set_page_config(page_title="OOP Expense Tracker", layout="wide")

page_main = st.Page(main_dashboard, title="Main Dashboard", icon="💸", default=True)
page_charts = st.Page(charts_page, title="Visual Analytics", icon="📊")
page_demographics = st.Page(demographics_page, title="Demographics & Reports", icon="👤")

pg = st.navigation([page_main, page_charts, page_demographics])
pg.run()