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

def load_data():
    client = get_google_sheet_client()
    sheet = client.open(SHEET_NAME)
    # Load Logs
    logs_tab = sheet.worksheet("Daily_Logs")
    df_logs = pd.DataFrame(logs_tab.get_all_records())
    # Load Users (for adherence checks)
    users_tab = sheet.worksheet("Users")
    df_users = pd.DataFrame(users_tab.get_all_records())
    return df_logs, df_users

def check_login(username, password):
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_NAME)
        users_tab = sheet.worksheet("Users")
        df_users = pd.DataFrame(users_tab.get_all_records())

        # Check Username & Password
        user_match = df_users[(df_users['Username'].astype(str).str.strip() == username.strip()) & 
                              (df_users['Password'].astype(str).str.strip() == password.strip())]
        
        if not user_match.empty:
            # RETURN 3 VALUES: Success, Center Name, AND ROLE
            return True, user_match.iloc[0]['Center_Name'], user_match.iloc[0]['Role']
        else:
            return False, None, None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return False, None, None

# --- VIEW: SUPERVISOR COMMAND CENTRE ---
def show_command_centre(df_logs, df_users):
    st.title("🚀 Operations Command Centre")
    st.markdown("### Supervisory Analysis View")
    st.markdown("---")

    # Data Clean Up
    if not df_logs.empty:
        df_logs['Date'] = pd.to_datetime(df_logs['Timestamp']).dt.date
    
    # 1. TOP METRICS ROW
    col1, col2, col3, col4 = st.columns(4)
    
    # Time Filter
    days = st.sidebar.selectbox("📅 Time Range", [7, 30, 90, 365], index=0)
    start_date = datetime.now().date() - timedelta(days=days)
    
    if not df_logs.empty:
        mask = df_logs['Date'] >= start_date
        df_view = df_logs.loc[mask]
    else:
        df_view = pd.DataFrame()

    # Calculate Adherence
    active_centers = df_users[df_users['Role'] == 'Manager']['Center_Name'].unique()
    days_range = [datetime.now().date() - timedelta(days=x) for x in range(days)]
    total_expected = len(active_centers) * len(days_range)
    total_actual = len(df_view)
    adherence = int((total_actual/total_expected)*100) if total_expected > 0 else 0

    col1.metric("🏥 Active Centers", len(active_centers))
    col2.metric("👥 Total Patients", df_view['P3_Patient_Count'].sum() if not df_view.empty else 0)
    col3.metric("⭐ Total Reviews", df_view['P4_Google_Reviews'].sum() if not df_view.empty else 0)
    col4.metric("✅ Adherence Rate", f"{adherence}%", delta_color="normal")

    st.markdown("---")

    # 2. MISSED LOGS TRACKER (The "Adherence" View)
    st.subheader("⚠️ Non-Compliance Tracker (Missed Logs)")
    
    missed_data = []
    for d in days_range:
        for c in active_centers:
            # Check if entry exists
            if df_view.empty or df_view[(df_view['Date'] == d) & (df_view['Center_Name'] == c)].empty:
                missed_data.append({'Date': d.strftime('%d-%b'), 'Center': c, 'Status': 'MISSING ❌'})
    
    if missed_data:
        df_missed = pd.DataFrame(missed_data)
        st.dataframe(df_missed, use_container_width=True)
    else:
        st.success("✨ 100% Adherence! No missed logs in this period.")

    st.markdown("---")

    # 3. ANALYSIS CHARTS
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Patient Volume Trends")
        if not df_view.empty:
            fig = px.bar(df_view, x='Center_Name', y='P3_Patient_Count', color='Center_Name')
            st.plotly_chart(fig, use_container_width=True)
    
    with c2:
        st.subheader("Reviews Performance")
        if not df_view.empty:
            fig2 = px.pie(df_view, values='P4_Google_Reviews', names='Center_Name', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)

    # 4. RAW DATA INSPECTION
    with st.expander("🔎 View Raw Data Logs"):
        st.dataframe(df_view, use_container_width=True)


# --- MAIN APP LOGIC ---
def main():
    st.set_page_config(page_title="RheumaCare Ops", page_icon="🏥", layout="wide")
    
    # Initialize Session
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['role'] = ''
        st.session_state['center'] = ''

    # ---------------------------
    # LOGIN SCREEN
    # ---------------------------
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
                is_valid, center, role = check_login(username, password)
                if is_valid:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.session_state['center'] = center
                    st.session_state['role'] = role # SAVE THE ROLE
                    st.rerun()
                else:
                    st.error("Invalid credentials")

    # ---------------------------
    # LOGGED IN VIEW (Role Based)
    # ---------------------------
    else:
        st.sidebar.title(f"👤 {st.session_state['username']}")
        st.sidebar.caption(f"Role: {st.session_state['role']}")
        
        if st.sidebar.button("Log Out"):
            st.session_state['logged_in'] = False
            st.rerun()
        
        # --- LOGIC SPLIT: SUPERVISOR VS MANAGER ---
        
        # SCENARIO A: YOU ARE THE BOSS (Supervisor)
        if st.session_state['role'] == "Supervisor":
            df_logs, df_users = load_data()
            show_command_centre(df_logs, df_users)
            
        # SCENARIO B: THEY ARE MANAGERS
        else:
            st.title(f"Daily Log: {st.session_state['center']}")
            
            # Simple Navigation for Managers
            view_mode = st.radio("Select Action:", ["📝 Submit Daily Log", "📜 View My History"], horizontal=True)
            
            if view_mode == "📝 Submit Daily Log":
                with st.form("daily_form", clear_on_submit=True):
                    st.write(f"Date: {datetime.now().strftime('%d-%m-%Y')}")
                    p1 = st.radio("1. DB Backup Done?", ["Yes", "No"], horizontal=True)
                    p2 = st.radio("2. Server Protocol Followed?", ["Yes", "No"], horizontal=True)
                    p3 = st.slider("3. Patient Count", 0, 200, 50)
                    p4 = st.selectbox("4. Google Reviews", list(range(26)))
                    p5 = st.text_area("5. Daily Notes")
                    
                    if st.form_submit_button("✅ Submit Report", use_container_width=True):
                        try:
                            client = get_google_sheet_client()
                            sheet = client.open(SHEET_NAME).worksheet("Daily_Logs")
                            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            sheet.append_row([ts, st.session_state['username'], st.session_state['center'], p1, p2, p3, p4, p5])
                            st.success("Submitted!")
                        except Exception as e:
                            st.error(f"Error: {e}")

            elif view_mode == "📜 View My History":
                client = get_google_sheet_client()
                sheet = client.open(SHEET_NAME).worksheet("Daily_Logs")
                df = pd.DataFrame(sheet.get_all_records())
                # Filter for ONLY their center
                if not df.empty:
                    my_logs = df[df['Center_Name'] == st.session_state['center']]
                    st.dataframe(my_logs, use_container_width=True)
                else:
                    st.info("No logs found.")

if __name__ == '__main__':
    main()
