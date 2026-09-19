import io
import sqlite3
import hashlib
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# ==============================================================================
# 1. OOP DATA MODELS & DATABASE MANAGER
# ==============================================================================

class User:
    """Represents an authenticated user account."""
    def __init__(self, username: str, user_id: int = None):
        self.id = user_id
        self.username = username


class Expense:
    """Represents an individual expense item linked to a user."""
    def __init__(self, amount: float, category: str, date: str, user_id: int, expense_id: int = None):
        self.id = expense_id
        self.user_id = user_id
        self.amount = float(amount)
        self.category = category.strip()
        self.date = str(date)


class UserDemographics:
    """Represents demographic metadata and preferred currency linked to a user."""
    def __init__(self, country: str, currency_symbol: str, age_group: str, occupation: str, user_id: int):
        self.user_id = user_id
        self.country = country
        self.currency_symbol = currency_symbol
        self.age_group = age_group
        self.occupation = occupation


class DatabaseManager:
    """Handles SQLite database operations for users, expenses, and demographics."""
    def __init__(self, db_name="expenses.db"):
        self.db_name = db_name
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_name)

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    date TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS demographics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    country TEXT NOT NULL,
                    currency_symbol TEXT NOT NULL,
                    age_group TEXT NOT NULL,
                    occupation TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.commit()

    def create_user(self, username: str, password: str) -> bool:
        try:
            hashed_pw = self._hash_password(password)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username.strip(), hashed_pw)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def authenticate_user(self, username: str, password: str):
        hashed_pw = self._hash_password(password)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username FROM users WHERE username = ? AND password = ?",
                (username.strip(), hashed_pw)
            )
            row = cursor.fetchone()
            if row:
                return User(user_id=row[0], username=row[1])
            return None

    def add_expense(self, expense: Expense):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
                (expense.user_id, expense.amount, expense.category, expense.date)
            )
            conn.commit()

    def fetch_user_expenses(self, user_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, amount, category, date FROM expenses WHERE user_id = ? ORDER BY date DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [Expense(expense_id=r[0], user_id=user_id, amount=r[1], category=r[2], date=r[3]) for r in rows]

    def update_expense(self, expense_id: int, amount: float, category: str, date: str, user_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE expenses SET amount = ?, category = ?, date = ? WHERE id = ? AND user_id = ?",
                (amount, category, date, expense_id, user_id)
            )
            conn.commit()

    def delete_expense(self, expense_id: int, user_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
            conn.commit()

    def save_demographics(self, demo: UserDemographics):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO demographics (user_id, country, currency_symbol, age_group, occupation) 
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    country=excluded.country,
                    currency_symbol=excluded.currency_symbol,
                    age_group=excluded.age_group,
                    occupation=excluded.occupation
            """, (demo.user_id, demo.country, demo.currency_symbol, demo.age_group, demo.occupation))
            conn.commit()

    def fetch_demographics(self, user_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT country, currency_symbol, age_group, occupation FROM demographics WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return UserDemographics(user_id=user_id, country=row[0], currency_symbol=row[1], age_group=row[2], occupation=row[3])
            return None


# ==============================================================================
# 2. ANALYTICS & EXPORT ENGINE
# ==============================================================================

class ReportGenerator:
    @staticmethod
    def generate_bar_chart(expenses, currency="$"):
        breakdown = {}
        for exp in expenses:
            breakdown[exp.category] = breakdown.get(exp.category, 0.0) + exp.amount

        if not breakdown:
            fig = go.Figure()
            fig.add_annotation(text="No Expenses Logged Yet", showarrow=False, font=dict(size=16))
            fig.update_layout(template="plotly_dark", height=320)
            return fig

        categories = list(breakdown.keys())
        amounts = list(breakdown.values())

        fig = px.bar(
            x=categories, 
            y=amounts, 
            labels={'x': 'Category', 'y': f'Amount ({currency})'},
            title="Expenses by Category",
            color_discrete_sequence=['#3B82F6']
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=320,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig

    @staticmethod
    def generate_pie_chart(expenses):
        breakdown = {}
        for exp in expenses:
            breakdown[exp.category] = breakdown.get(exp.category, 0.0) + exp.amount

        if not breakdown:
            fig = go.Figure()
            fig.add_annotation(text="No Expenses Logged Yet", showarrow=False, font=dict(size=16))
            fig.update_layout(template="plotly_dark", height=320)
            return fig

        fig = px.pie(
            names=list(breakdown.keys()), 
            values=list(breakdown.values()),
            title="Category Share",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=320,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig

    @staticmethod
    def generate_csv(expenses, username: str, demo: UserDemographics):
        output = io.StringIO()
        output.write("Username,Country,Currency,Age_Group,Occupation,Expense_ID,Amount,Category,Date\n")
        country = demo.country if demo else "N/A"
        currency = demo.currency_symbol if demo else "N/A"
        age = demo.age_group if demo else "N/A"
        occ = demo.occupation if demo else "N/A"

        for exp in expenses:
            output.write(f'"{username}","{country}","{currency}","{age}","{occ}",{exp.id},{exp.amount:.2f},"{exp.category}","{exp.date}"\n')
        return output.getvalue()

    @staticmethod
    def generate_pdf(expenses, username: str, demo: UserDemographics):
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 750, "Financial Summary Report")
        p.setFont("Helvetica", 10)
        p.drawString(100, 735, f"User: {username} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        curr = demo.currency_symbol if demo else "$"

        if demo:
            p.setFont("Helvetica-Bold", 11)
            p.drawString(100, 705, "User Demographics Profile:")
            p.setFont("Helvetica", 10)
            p.drawString(100, 690, f"Country: {demo.country} ({demo.currency_symbol}) | Age: {demo.age_group} | Occupation: {demo.occupation}")
            y_start = 655
        else:
            y_start = 690

        p.setFont("Helvetica-Bold", 11)
        p.drawString(100, y_start, "Date")
        p.drawString(220, y_start, "Category")
        p.drawString(380, y_start, f"Amount ({curr})")
        p.line(100, y_start - 5, 500, y_start - 5)

        y = y_start - 20
        total = 0.0
        p.setFont("Helvetica", 10)
        for exp in expenses:
            if y < 50:
                p.showPage()
                y = 750
            p.drawString(100, y, str(exp.date))
            p.drawString(220, y, str(exp.category))
            p.drawString(380, y, f"{curr}{exp.amount:.2f}")
            total += exp.amount
            y -= 20

        p.line(100, y + 10, 500, y + 10)
        p.setFont("Helvetica-Bold", 11)
        p.drawString(220, y - 10, "Total Expenditure:")
        p.drawString(380, y - 10, f"{curr}{total:.2f}")

        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer.getvalue()


db = DatabaseManager()


# ==============================================================================
# 3. GLOBAL UI STYLING & ONBOARDING MODAL
# ==============================================================================

st.set_page_config(page_title="FinTrack Pro - Expense Intelligence", page_icon="💳", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 18px 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 15px;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94A3B8;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-top: 5px;
    }
    .section-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #F1F5F9;
        margin-bottom: 12px;
        border-left: 4px solid #3B82F6;
        padding-left: 10px;
    }
</style>
""", unsafe_allow_html=True)


def check_onboarding(user: User):
    """Enforces onboarding form on first-time user login."""
    demo = db.fetch_demographics(user.id)
    if not demo:
        st.warning("⚠️ **Profile Setup Required**: Please enter your profile details below to customize your app currency and setup.")
        with st.form("onboarding_form"):
            st.subheader("👤 First-Time User Profile Setup")
            
            c1, c2 = st.columns(2)
            country = c1.text_input("Country Name", placeholder="e.g., United States, India, UK")
            currency_symbol = c2.text_input("Currency Symbol", value="$", placeholder="e.g., $, €, £, ₹, ₨")
            
            c3, c4 = st.columns(2)
            age_group = c3.selectbox("Age Group", ["<18", "18-24", "25-34", "35-49", "50+"], index=1)
            occupation = c4.selectbox("Occupation", ["Student", "Employed", "Self-Employed", "Freelancer", "Other"])

            if st.form_submit_button("Complete Setup", type="primary", use_container_width=True):
                if country and currency_symbol:
                    db.save_demographics(UserDemographics(
                        country=country.strip(),
                        currency_symbol=currency_symbol.strip(),
                        age_group=age_group,
                        occupation=occupation,
                        user_id=user.id
                    ))
                    st.success("Profile saved! Redirecting to dashboard...")
                    st.rerun()
                else:
                    st.error("Please provide both Country and Currency Symbol.")
        st.stop()


# ==============================================================================
# 4. VIEW CONTROLLERS
# ==============================================================================

def login_signup_page():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h2 style='text-align: center; margin-bottom: 20px;'>💳 FinTrack Pro Portal</h2>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])

        with tab1:
            login_user = st.text_input("Username", key="login_user")
            login_pass = st.text_input("Password", type="password", key="login_pass")
            if st.button("Sign In", use_container_width=True, type="primary"):
                user = db.authenticate_user(login_user, login_pass)
                if user:
                    st.session_state["user"] = user
                    st.rerun()
                else:
                    st.error("Invalid credentials provided.")

        with tab2:
            new_user = st.text_input("Choose Username", key="signup_user")
            new_pass = st.text_input("Choose Password", type="password", key="signup_pass")
            if st.button("Create Account", use_container_width=True):
                if new_user and new_pass:
                    if db.create_user(new_user, new_pass):
                        st.success("Account created successfully! Please sign in.")
                    else:
                        st.error("Username already registered.")
                else:
                    st.warning("Please fill out all fields.")


def main_dashboard():
    user: User = st.session_state["user"]
    check_onboarding(user)

    demo = db.fetch_demographics(user.id)
    expenses = db.fetch_user_expenses(user.id)
    curr = demo.currency_symbol

    st.title("💸 Executive Dashboard")
    st.caption("Track, record, and manage personal expenses effortlessly.")

    # High-level Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    total_spent = sum(e.amount for e in expenses)
    avg_expense = (total_spent / len(expenses)) if expenses else 0.0

    with m1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total Expenditure</div><div class="metric-value">{curr}{total_spent:,.2f}</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total Transactions</div><div class="metric-value">{len(expenses)}</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Average Transaction</div><div class="metric-value">{curr}{avg_expense:,.2f}</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Country / Currency</div><div class="metric-value">{demo.country} ({curr})</div></div>', unsafe_allow_html=True)

    st.divider()

    col1, col2 = st.columns([1, 1.2])

    with col1:
        st.markdown('<div class="section-title">Log New Expense</div>', unsafe_allow_html=True)
        with st.form(key="expense_form", clear_on_submit=True):
            amount = st.number_input(f"Amount ({curr})", min_value=0.01, step=0.01)
            category = st.selectbox("Category", ["Food", "Travel", "Study", "Entertainment", "Bills", "Shopping"])
            expense_date = st.date_input("Date", datetime.now())
            if st.form_submit_button("Record Expense", type="primary", use_container_width=True):
                db.add_expense(Expense(amount=amount, category=category, date=expense_date, user_id=user.id))
                st.toast("Expense added successfully!", icon="✅")
                st.rerun()

    with col2:
        st.markdown('<div class="section-title">Recent Transactions</div>', unsafe_allow_html=True)
        if expenses:
            for exp in expenses[:5]:  # Display recent 5
                c1, c2, c3, c4 = st.columns([2, 2, 2, 0.8])
                c1.text(f"📅 {exp.date}")
                c2.text(f"🏷️ {exp.category}")
                c3.markdown(f"**{curr}{exp.amount:,.2f}**")
                if c4.button("🗑️", key=f"del_{exp.id}"):
                    db.delete_expense(exp.id, user.id)
                    st.rerun()
        else:
            st.info("No expense entries logged yet.")


def charts_page():
    user: User = st.session_state["user"]
    check_onboarding(user)

    expenses = db.fetch_user_expenses(user.id)
    demo = db.fetch_demographics(user.id)

    st.title("📊 Financial Analytics & Visualizations")
    st.caption("Interactive visual breakdown of expenditures by category.")

    if not expenses:
        st.warning("No expense data recorded yet. Log expenses on the main dashboard to view charts.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(ReportGenerator.generate_bar_chart(expenses, demo.currency_symbol), use_container_width=True)
        with c2:
            st.plotly_chart(ReportGenerator.generate_pie_chart(expenses), use_container_width=True)


def demographics_page():
    user: User = st.session_state["user"]
    check_onboarding(user)

    expenses = db.fetch_user_expenses(user.id)
    demo = db.fetch_demographics(user.id)

    st.title("👤 Demographic Reports & Data Management")
    st.caption("Manage your profile settings, perform in-place expense edits, and export statements.")

    # Section 1: Demographics Cards & Update
    st.markdown('<div class="section-title">Demographic Profile</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="metric-card"><div class="metric-label">Country</div><div class="metric-value">{demo.country}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="metric-label">Currency</div><div class="metric-value">{demo.currency_symbol}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><div class="metric-label">Age Group</div><div class="metric-value">{demo.age_group}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card"><div class="metric-label">Occupation</div><div class="metric-value">{demo.occupation}</div></div>', unsafe_allow_html=True)

    with st.expander("⚙️ Edit Profile & Currency Settings"):
        with st.form("update_demo_form"):
            ec1, ec2 = st.columns(2)
            u_country = ec1.text_input("Country", value=demo.country)
            u_currency = ec2.text_input("Currency Symbol", value=demo.currency_symbol)

            ec3, ec4 = st.columns(2)
            age_opts = ["<18", "18-24", "25-34", "35-49", "50+"]
            occ_opts = ["Student", "Employed", "Self-Employed", "Freelancer", "Other"]
            u_age = ec3.selectbox("Age Group", age_opts, index=age_opts.index(demo.age_group) if demo.age_group in age_opts else 0)
            u_occ = ec4.selectbox("Occupation", occ_opts, index=occ_opts.index(demo.occupation) if demo.occupation in occ_opts else 0)

            if st.form_submit_button("Save Profile Changes"):
                db.save_demographics(UserDemographics(
                    country=u_country.strip(),
                    currency_symbol=u_currency.strip(),
                    age_group=u_age,
                    occupation=u_occ,
                    user_id=user.id
                ))
                st.toast("Profile updated!", icon="✅")
                st.rerun()

    st.divider()

    # Section 2: Interactive Expense Editor Table
    st.markdown('<div class="section-title">Editable Expense Table</div>', unsafe_allow_html=True)
    st.caption("💡 **Tip**: Double-click any cell below to edit Amount, Category, or Date directly, then click **'Save Table Changes'**.")

    if expenses:
        # Build pandas dataframe for st.data_editor
        data = [{
            "ID": exp.id,
            "Amount": exp.amount,
            "Category": exp.category,
            "Date": exp.date
        } for exp in expenses]
        df = pd.DataFrame(data)

        edited_df = st.data_editor(
            df,
            column_config={
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "Amount": st.column_config.NumberColumn(f"Amount ({demo.currency_symbol})", min_value=0.01, format="%.2f", required=True),
                "Category": st.column_config.SelectboxColumn("Category", options=["Food", "Travel", "Study", "Entertainment", "Bills", "Shopping"], required=True),
                "Date": st.column_config.DateColumn("Date", required=True)
            },
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic"
        )

        col_save, col_del = st.columns([1, 4])
        if col_save.button("💾 Save Table Changes", type="primary"):
            # Update database based on edited Dataframe
            current_ids = set(edited_df["ID"].dropna().astype(int))
            original_ids = {exp.id for exp in expenses}

            # Handle Deleted Rows
            deleted_ids = original_ids - current_ids
            for del_id in deleted_ids:
                db.delete_expense(del_id, user.id)

            # Handle Updates & Edits
            for _, row in edited_df.iterrows():
                if pd.notna(row["ID"]):
                    db.update_expense(
                        expense_id=int(row["ID"]),
                        amount=float(row["Amount"]),
                        category=str(row["Category"]),
                        date=str(row["Date"]),
                        user_id=user.id
                    )

            st.toast("Database successfully updated!", icon="🎉")
            st.rerun()
    else:
        st.info("No expense data recorded yet.")

    st.divider()

    # Section 3: Downloads
    st.markdown('<div class="section-title">Download Statements</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        csv_bytes = ReportGenerator.generate_csv(expenses, user.username, demo)
        st.download_button(
            label="📄 Export Data (CSV)",
            data=csv_bytes,
            file_name=f"{user.username}_expense_demographics.csv",
            mime="text/csv",
            use_container_width=True,
            type="primary"
        )

    with col2:
        pdf_bytes = ReportGenerator.generate_pdf(expenses, user.username, demo)
        st.download_button(
            label="🔴 Export Statement (PDF)",
            data=pdf_bytes,
            file_name=f"{user.username}_expense_report.pdf",
            mime="application/pdf",
            use_container_width=True
        )


# ==============================================================================
# 5. NAVIGATION & SIDEBAR ROUTING
# ==============================================================================

if "user" not in st.session_state:
    page_login = st.Page(login_signup_page, title="Portal", icon="🔐")
    pg = st.navigation([page_login])
else:
    user: User = st.session_state["user"]
    st.sidebar.markdown(f"### 👤 Active Account:\n**{user.username}**")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        del st.session_state["user"]
        st.rerun()

    st.sidebar.divider()

    page_main = st.Page(main_dashboard, title="Executive Dashboard", icon="💸", default=True)
    page_charts = st.Page(charts_page, title="Financial Analytics", icon="📊")
    page_demographics = st.Page(demographics_page, title="Demographics & Reports", icon="👤")
    
    pg = st.navigation({
        "Application Menu": [page_main, page_charts, page_demographics]
    })

pg.run()