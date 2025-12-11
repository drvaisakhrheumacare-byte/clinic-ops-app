import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import plotly.express as px
import os

# --- Configuration ---
SHEET_NAME = 'Clinic_Daily_Ops_DB'
SCOPE = ['https://www.googleapis.com/auth/spreadsheets',
         'https://www.googleapis.com/auth/drive']

# --- Helper Functions ---

def get_google_sheet_client():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    except Exception as e:
        st.error(f"Error reading secrets: {e}")
        st.stop()
    client = gspread.authorize(creds)
    return client

# Function to fetch all data
def load_data():
    client = get_google_sheet_client()
    sheet = client.open(SHEET_NAME)
    
    # Load Logs
    logs_tab = sheet.worksheet("Daily_Logs")
    logs_data = logs_tab.get_all_records()
    df_logs = pd.DataFrame(logs_data)
    
    # Load Users (for adherence checks)
    users_tab = sheet.worksheet("Users")
    users_data = users_tab.get_all_records()
    df_users = pd.DataFrame(users_data)
    
    return df_logs, df_users

def check_login(username, password):
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_NAME)
        users_tab = sheet.worksheet("Users")
        users_data = users_tab.get_all_records()
        df_users = pd.DataFrame(users_data)

        # Basic auth check
        user_match = df_users[(df_users['Username'].astype(str).str.strip() == username.strip()) & 
                              (df_users['Password'].astype(str).str.strip() == password.strip())]
        
        if not user_match.empty:
            return True, user_match.iloc[0]['Center_Name']
        else:
            return False, None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return False, None

# --- VIEW 1: THE GLOBAL DASHBOARD (Analysis) ---
def show_dashboard(df_logs, df_users):
    st.title("📊 Global Operations Dashboard")
    st.info("This view shows performance data across ALL centers.")

    # Data Pre-processing
    if not df_logs.empty:
        df_logs['Date'] = pd.to_datetime(df_logs['Timestamp']).dt.date
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        days_to_look_back = st.selectbox("Select Time Range", [7, 14, 30, 90], index=0)
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_to_look_back)
    
    if not df_logs.empty:
        mask = (df_logs['Date'] >= start_date) & (df_logs['Date'] <= end_date)
        df_filtered = df_logs.loc[mask]
    else:
        df_filtered = pd.DataFrame()

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    total_patients = df_filtered['P3_Patient_Count'].sum() if not df_filtered.empty else 0
    m1.metric("Total Patients", total_patients)
    
    total_reviews = df_filtered['P4_Google_Reviews'].sum() if not df_filtered.empty else 0
    m2.metric("Google Reviews", total_reviews)
    
    # Adherence Logic
    all_centers = df_users['Center_Name'].unique()
    expected_dates = [end_date - timedelta(days=x) for x in range(days_to_look_back + 1)]
    
    total_expected_logs = len(all_centers) * len(expected_dates)
    total_actual_logs = len(df_filtered)
    adherence_rate = round((total_actual_logs / total_expected_logs) * 100, 1) if total_expected_logs > 0 else 0
    
    m3.metric("Adherence Rate", f"{adherence_rate}%")
    
    missed_count = max(0, total_expected_logs - total_actual_logs)
    m4.metric("Missed Logs", missed_count, delta_color="inverse")
    
    st.markdown("---")

    # Charts
    c1, c2 = st.columns(2)
    with c1:
        if not df_filtered.empty:
            fig_patients = px.bar(df_filtered, x='Center_Name', y='P3_Patient_Count', title="Total Patients", color='Center_Name')
            st.plotly_chart(fig_patients, use_container_width=True)
    with c2:
        if not df_filtered.empty:
            fig_reviews = px.pie(df_filtered, values='P4_Google_Reviews', names='Center_Name', title="Reviews Share")
            st.plotly_chart(fig_reviews, use_container_width=True)

    # Missed Logs Table
    st.subheader("⚠️ Missed Logs Report")
    missed_logs_data = []
    for check_date in expected_dates:
        for center in all_centers:
            if not df_filtered.empty:
                exists = df_filtered[(df_filtered['Date'] == check_date) & (df_filtered['Center_Name'] == center)]
                if exists.empty:
                    missed_logs_data.append({'Date': check_date, 'Center Name': center, 'Status': 'MISSING ❌'})
            else:
                missed_logs_data.append({'Date': check_date, 'Center Name': center, 'Status': 'MISSING ❌'})

    if missed_logs_data:
        df_missed = pd.DataFrame(missed_logs_data)
        st.dataframe(df_missed, use_container_width=True)
    else:
        st.success("100% Adherence!")

# --- VIEW 2: INDIVIDUAL LOGS (New Feature) ---
def show_my_logs(df_logs):
    st.title(f"📜 History: {st.session_state['center']}")
    st.markdown("Below is a list of all submissions made for this center.")

    if df_logs.empty:
        st.warning("No logs found yet.")
        return

    # Filter strictly for the logged-in center
    my_data = df_logs[df_logs['Center_Name'] == st.session_state['center']]

    if my_data.empty:
        st.info("No logs found for your center.")
    else:
        # Sort by Timestamp descending (newest first)
        my_data = my_data.sort_values(by='Timestamp', ascending=False)
        st.dataframe(my_data, use_container_width=True)

# --- MAIN APP LOGIC ---
def main():
    st.set_page_config(page_title="RheumaCare Ops", page_icon="🏥", layout="wide")
    
    hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['username'] = ''
        st.session_state['center'] = ''

    # LOGIN SCREEN
    if not st.session_state['logged_in']:
        left_co, cent_co, last_co = st.columns([1, 2, 1])
        with cent_co:
            if os.path.exists("logo.png"):
                st.image("logo.png", width=250)
            else:
                st.write("RheumaCare Ops")

        st.title("RheumaCare Operations Portal")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Log In", type="primary", use_container_width=True):
                is_valid, center = check_login(username, password)
                if is_valid:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.session_state['center'] = center
                    st.rerun()
                else:
                    st.error("Invalid credentials")

    # LOGGED IN VIEW
    else:
        # Load data once for efficiency
        df_logs, df_users = load_data()

        st.sidebar.title(f"👤 {st.session_state['username']}")
        st.sidebar.write(f"📍 {st.session_state['center']}")
        st.sidebar.markdown("---")
        
        # NEW NAVIGATION OPTION ADDED
        menu_choice = st.sidebar.radio("Navigate", ["📝 Daily Entry Form", "📜 View My Center Logs", "📊 Global Dashboard"])
        
        if st.sidebar.button("Log Out"):
            st.session_state['logged_in'] = False
            st.rerun()

        # --- OPTION 1: DAILY ENTRY FORM ---
        if menu_choice == "📝 Daily Entry Form":
            st.title(f"Daily Log: {st.session_state['center']}")
            st.markdown(f"**Date:** {datetime.now().strftime('%d-%m-%Y')}")
            st.markdown("---")

            with st.form("daily_entry_form", clear_on_submit=True):
                st.markdown("### 1️⃣ Daily Offline DB Backup Completed?")
                p1 = st.radio("Status:", ["Yes", "No"], horizontal=True, label_visibility="collapsed", key="p1")
                st.markdown("---")

                st.markdown("### 2️⃣ Weekly/Holiday Server Shutdown Protocol Followed?")
                p2 = st.radio("Status:", ["Yes", "No"], horizontal=True, label_visibility="collapsed", key="p2")
                st.markdown("---")

                st.markdown("### 3️⃣ Total Patients Encountered")
                p3 = st.slider("Count:", 0, 200, 50, label_visibility="collapsed", key="p3")
                st.markdown("---")
                
                st.markdown("### 4️⃣ Google Reviews Collected")
                p4 = st.selectbox("Count:", list(range(26)), label_visibility="collapsed", key="p4")
                st.markdown("---")

                st.markdown("### 5️⃣ Daily Operational Notes")
                p5 = st.text_area("Notes:", max_chars=250, label_visibility="collapsed", key="p5")
                st.markdown("---")

                if st.form_submit_button("✅ SUBMIT REPORT", type="primary", use_container_width=True):
                    try:
                        client = get_google_sheet_client()
                        sheet = client.open(SHEET_NAME).worksheet("Daily_Logs")
                        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        sheet.append_row([ts, st.session_state['username'], st.session_state['center'], p1, p2, p3, p4, p5])
                        st.success("Saved successfully!")
                        # Clear cache so new data shows up instantly in other views
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Error: {e}")

        # --- OPTION 2: MY LOGS (NEW) ---
        elif menu_choice == "📜 View My Center Logs":
            show_my_logs(df_logs)

        # --- OPTION 3: GLOBAL DASHBOARD ---
        elif menu_choice == "📊 Global Dashboard":
            show_dashboard(df_logs, df_users)

if __name__ == '__main__':
    main()
