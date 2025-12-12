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
    
    # Load Logs (Handle missing tab gracefully)
    try:
        logs_tab = sheet.worksheet("Daily_Logs")
        df_logs = pd.DataFrame(logs_tab.get_all_records())
    except:
        df_logs = pd.DataFrame()

    # Load Users
    try:
        users_tab = sheet.worksheet("Users")
        df_users = pd.DataFrame(users_tab.get_all_records())
    except:
        df_users = pd.DataFrame()
    
    # Load Tutorials
    try:
        tutorials_tab = sheet.worksheet("Tutorials")
        df_tutorials = pd.DataFrame(tutorials_tab.get_all_records())
    except:
        df_tutorials = pd.DataFrame()

    return df_logs, df_users, df_tutorials

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

# --- VIEW 1: GAMIFIED DAILY REPORTING (Wizard Style) ---
def show_daily_reporting():
    st.header(f"📝 Daily Check-In: {st.session_state['center']}")
    
    # Initialize the 'step' in session state
    if 'daily_step' not in st.session_state:
        st.session_state['daily_step'] = 1
        st.session_state['daily_answers'] = {}

    def next_step(): st.session_state['daily_step'] += 1
    def prev_step(): st.session_state['daily_step'] -= 1
    def restart_form():
        st.session_state['daily_step'] = 1
        st.session_state['daily_answers'] = {}

    # Progress Bar
    total_steps = 9
    progress = (st.session_state['daily_step'] - 1) / total_steps
    st.progress(progress)

    # Question 1
    if st.session_state['daily_step'] == 1:
        st.subheader("1️⃣ Database Backup")
        st.write("Did the offline backup complete successfully today?")
        val = st.radio("Backup Status", ["Yes", "No"], key="q1_temp")
        if st.button("Next ➡️", type="primary"):
            st.session_state['daily_answers']['p1'] = val
            next_step(); st.rerun()

    # Question 2
    elif st.session_state['daily_step'] == 2:
        st.subheader("2️⃣ Server Protocol")
        st.write("Was the server shutdown/startup protocol followed correctly?")
        val = st.radio("Server Status", ["Yes", "No"], key="q2_temp")
        c1, c2 = st.columns([1, 1])
        if c1.button("⬅️ Back"): prev_step(); st.rerun()
        if c2.button("Next ➡️", type="primary"):
            st.session_state['daily_answers']['p2'] = val
            next_step(); st.rerun()

    # Question 3
    elif st.session_state['daily_step'] == 3:
        st.subheader("3️⃣ Total Encounters")
        st.write("Total patient encounters today?")
        val = st.number_input("Count", min_value=0, value=50, key="q3_temp")
        c1, c2 = st.columns([1, 1])
        if c1.button("⬅️ Back"): prev_step(); st.rerun()
        if c2.button("Next ➡️", type="primary"):
            st.session_state['daily_answers']['p3'] = val
            next_step(); st.rerun()

    # Question 4
    elif st.session_state['daily_step'] == 4:
        st.subheader("4️⃣ New Patients")
        st.write("Count of **New Patients** (First time visits)?")
        val = st.number_input("New Patient Count", min_value=0, key="q8_temp")
        c1, c2 = st.columns([1, 1])
        if c1.button("⬅️ Back"): prev_step(); st.rerun()
        if c2.button("Next ➡️", type="primary"):
            st.session_state['daily_answers']['p8'] = val
            next_step(); st.rerun()

    # Question 5
    elif st.session_state['daily_step'] == 5:
        st.subheader("5️⃣ Walk-ins")
        st.write("Count of direct **Walk-ins**?")
        val = st.number_input("Walk-in Count", min_value=0, key="q9_temp")
        c1, c2 = st.columns([1, 1])
        if c1.button("⬅️ Back"): prev_step(); st.rerun()
        if c2.button("Next ➡️", type="primary"):
            st.session_state['daily_answers']['p9'] = val
            next_step(); st.rerun()

    # Question 6
    elif st.session_state['daily_step'] == 6:
        st.subheader("6️⃣ Rebookings")
        st.write("Future appointments rebooked today?")
        val = st.number_input("Rebooking Count", min_value=0, key="q7_temp")
        c1, c2 = st.columns([1, 1])
        if c1.button("⬅️ Back"): prev_step(); st.rerun()
        if c2.button("Next ➡️", type="primary"):
            st.session_state['daily_answers']['p7'] = val
            next_step(); st.rerun()

    # Question 7
    elif st.session_state['daily_step'] == 7:
        st.subheader("7️⃣ Cash Deposit")
        st.write("Total cash deposit amount (₹)?")
        val = st.number_input("Amount (₹)", min_value=0, step=100, key="q6_temp")
        c1, c2 = st.columns([1, 1])
        if c1.button("⬅️ Back"): prev_step(); st.rerun()
        if c2.button("Next ➡️", type="primary"):
            st.session_state['daily_answers']['p6'] = val
            next_step(); st.rerun()

    # Question 8
    elif st.session_state['daily_step'] == 8:
        st.subheader("8️⃣ Google Reviews")
        st.write("Google Reviews collected today?")
        val = st.slider("Select Count", 0, 25, 0, key="q4_temp")
        c1, c2 = st.columns([1, 1])
        if c1.button("⬅️ Back"): prev_step(); st.rerun()
        if c2.button("Next ➡️", type="primary"):
            st.session_state['daily_answers']['p4'] = val
            next_step(); st.rerun()

    # Question 9 (Final)
    elif st.session_state['daily_step'] == 9:
        st.subheader("9️⃣ Daily Notes")
        st.write("Any operational issues or notes?")
        val = st.text_area("Notes", height=150, key="q5_temp")
        c1, c2 = st.columns([1, 1])
        if c1.button("⬅️ Back"): prev_step(); st.rerun()
        
        if c2.button("✅ Finish & Submit", type="primary"):
            st.session_state['daily_answers']['p5'] = val
            try:
                with st.spinner("Submitting your report..."):
                    client = get_google_sheet_client()
                    sheet = client.open(SHEET_NAME).worksheet("Daily_Logs")
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    a = st.session_state['daily_answers']
                    # Order: Timestamp, User, Center, P1, P2, P3, P4, P5, P6, P7, P8, P9
                    row_data = [
                        ts, st.session_state['username'], st.session_state['center'],
                        a.get('p1'), a.get('p2'), a.get('p3'), a.get('p4'), a.get('p5'),
                        a.get('p6'), a.get('p7'), a.get('p8'), a.get('p9')
                    ]
                    sheet.append_row(row_data)
                    st.success("🎉 Report Submitted!"); st.balloons()
                    restart_form()
            except Exception as e:
                st.error(f"Error submitting: {e}")

# --- VIEW 2: DETAILED INCIDENT REPORTING ---
def show_incident_reporting():
    st.header(f"⚠️ Incident Reporting: {st.session_state['center']}")
    st.info("Fill out all relevant sections. Multiple selections allowed for categories.")
    
    with st.form("incident_form", clear_on_submit=True):
        
        # 1. General Info
        st.subheader("1. General Information")
        c1, c2 = st.columns(2)
        with c1:
            i_staff_id = st.text_input("Staff ID")
            i_opd = st.text_input("OPD No. (if Patient involved)")
        with c2:
            i_date = st.date_input("Date of Incident", datetime.now())
            i_time = st.time_input("Time of Incident", datetime.now().time())

        st.write("Report Initiated By:")
        i_initiated = st.radio("Select One:", ["Patient", "Bystander", "Staff"], horizontal=True)

        st.markdown("---")

        # 2. Categories
        st.subheader("2. Incident Categories")
        st.caption("Select all that apply.")

        c3, c4 = st.columns(2)
        with c3:
            st.markdown("**Patient Safety**")
            cat_patient = st.multiselect("Select:", 
                ["Falls", "Injuries (cuts, bruises)", "Needlestick Injuries", "Exposure to Hazards", "Violence or Aggression", "Other"], key="cat1")
            
            st.markdown("**Staff Safety**")
            cat_staff = st.multiselect("Select:", 
                ["Workplace Injuries (slips, falls)", "Exposure to Hazards", "Needlestick Injuries", "Violence or Aggression", "Other"], key="cat2")
            
            st.markdown("**Equipment & Facility**")
            cat_equip = st.multiselect("Select:", 
                ["Equipment Failure", "Utility Failures (Power/Water)", "Fire Safety", "Structural Damage"], key="cat3")
            
            st.markdown("**Data & Confidentiality**")
            cat_data = st.multiselect("Select:", 
                ["Data Breaches", "Documentation Errors", "Confidentiality Breaches"], key="cat4")
            
            st.markdown("**Operational**")
            cat_ops = st.multiselect("Select:", 
                ["Appointment Scheduling", "Communication Failures", "Service Interruptions"], key="cat5")

        with c4:
            st.markdown("**Environmental**")
            cat_env = st.multiselect("Select:", 
                ["Cleanliness & Hygiene", "Waste Management", "Environmental Hazards"], key="cat6")
            
            st.markdown("**Security**")
            cat_sec = st.multiselect("Select:", 
                ["Theft", "Unauthorized Access", "Vandalism"], key="cat7")
            
            st.markdown("**Patient Behaviour**")
            cat_beh = st.multiselect("Select:", 
                ["Non-Compliance", "Aggressive Behaviour", "Elopement"], key="cat8")
            
            st.markdown("**Medication/Clinical**")
            cat_med = st.multiselect("Select:", 
                ["Medication Errors", "Misdiagnosis", "Treatment Errors", "Adverse Reactions"], key="cat9")
            
            st.markdown("**Other**")
            cat_other = st.multiselect("Select:", 
                ["Natural Disasters", "Transport Incidents", "Miscellaneous"], key="cat10")

        st.markdown("---")

        # 3. Details
        st.subheader("3. Additional Details")
        i_desc = st.text_area("Descriptive Explanation of Issue", height=150)
        
        c5, c6 = st.columns(2)
        with c5:
            i_witness = st.text_input("Witness Details (Name & Staff ID)")
        with c6:
            st.write("Escalation Reported To:")
            # HARDCODED ESCALATION OPTIONS
            i_escalation = st.radio("Select One:", 
                ["Centre Supervisor", "HR Manager", "Lab Manager", "Growth Manager"])

        st.markdown("---")

        # Submit
        if st.form_submit_button("🚨 SUBMIT INCIDENT REPORT", type="primary", use_container_width=True):
            if not i_desc:
                st.error("⚠️ Description is required.")
            else:
                try:
                    client = get_google_sheet_client()
                    # Connect to 'Incidents' tab (creates it if missing)
                    try:
                        sheet = client.open(SHEET_NAME).worksheet("Incidents")
                    except:
                        sheet = client.open(SHEET_NAME).add_worksheet(title="Incidents", rows=100, cols=21)
                    
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    def join_list(l): return ", ".join(l) if l else ""

                    row_data = [
                        ts, st.session_state['username'], st.session_state['center'], # Auto-filled
                        i_staff_id, i_initiated, i_opd, str(i_date), str(i_time),
                        join_list(cat_patient), join_list(cat_staff), join_list(cat_equip),
                        join_list(cat_data), join_list(cat_ops), join_list(cat_env),
                        join_list(cat_sec), join_list(cat_beh), join_list(cat_med), join_list(cat_other),
                        i_desc, i_witness, i_escalation
                    ]
                    sheet.append_row(row_data)
                    st.success("✅ Incident logged successfully."); st.balloons()
                except Exception as e:
                    st.error(f"Error logging incident: {e}")

# --- VIEW 3: TUTORIALS ---
def show_tutorials(df_tutorials):
    st.header("📚 Training & Tutorials")
    if df_tutorials.empty:
        st.warning("No tutorials found in the 'Tutorials' tab.")
        return
    for index, row in df_tutorials.iterrows():
        with st.expander(f"🎥 {row['Title']}"):
            st.write(row['Description'])
            if "youtube.com" in str(row['Video_Link']) or "youtu.be" in str(row['Video_Link']):
                st.video(row['Video_Link'])
            else:
                st.write(f"Link: {row['Video_Link']}")

# --- VIEW 4: SETTINGS ---
def show_settings():
    st.header("⚙️ Settings")
    
    st.subheader("⏰ Daily Reminder Preference")
    st.time_input("Set your preferred reminder time", datetime.strptime("08:00", "%H:%M").time())
    if st.button("Save Preference"):
        st.toast("Preference saved locally!")

    st.markdown("---")
    st.subheader("🗓️ Add Holiday")
    with st.form("holiday_form", clear_on_submit=True):
        h_date = st.date_input("Holiday Date")
        h_desc = st.text_input("Description")
        if st.form_submit_button("➕ Add"):
            try:
                client = get_google_sheet_client()
                try:
                    sheet = client.open(SHEET_NAME).worksheet("Holidays")
                except:
                    sheet = client.open(SHEET_NAME).add_worksheet(title="Holidays", rows=100, cols=3)
                sheet.append_row([st.session_state['center'], str(h_date), h_desc])
                st.success(f"Added holiday for {st.session_state['center']}")
            except Exception as e:
                st.error(f"Error: {e}")

# --- VIEW 5: SUPERVISOR DASHBOARD ---
def show_command_centre(df_logs, df_users):
    st.title("🚀 Operations Command Centre")
    st.markdown("### Supervisory Analysis View")
    st.markdown("---")

    if not df_logs.empty:
        df_logs['Date'] = pd.to_datetime(df_logs['Timestamp']).dt.date
    
    col1, col2, col3, col4 = st.columns(4)
    days = st.sidebar.selectbox("📅 Time Range", [7, 30, 90, 365], index=0)
    start_date = datetime.now().date() - timedelta(days=days)
    
    if not df_logs.empty:
        mask = df_logs['Date'] >= start_date
        df_view = df_logs.loc[mask]
    else:
        df_view = pd.DataFrame()

    active_centers = df_users[df_users['Role'] == 'Manager']['Center_Name'].unique() if not df_users.empty else []
    days_range = [datetime.now().date() - timedelta(days=x) for x in range(days)]
    total_expected = len(active_centers) * len(days_range)
    total_actual = len(df_view)
    adherence = int((total_actual/total_expected)*100) if total_expected > 0 else 0

    col1.metric("🏥 Active Centers", len(active_centers))
    col2.metric("👥 Total Patients", df_view['P3_Patient_Count'].sum() if not df_view.empty else 0)
    col3.metric("⭐ Total Reviews", df_view['P4_Google_Reviews'].sum() if not df_view.empty else 0)
    col4.metric("✅ Adherence Rate", f"{adherence}%")

    st.markdown("---")
    st.subheader("⚠️ Missed Logs Tracker")
    missed_data = []
    for d in days_range:
        for c in active_centers:
            if df_view.empty or df_view[(df_view['Date'] == d) & (df_view['Center_Name'] == c)].empty:
                missed_data.append({'Date': d.strftime('%d-%b'), 'Center': c, 'Status': 'MISSING ❌'})
    
    if missed_data:
        st.dataframe(pd.DataFrame(missed_data), use_container_width=True)
    else:
        st.success("✨ 100% Adherence!")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Patient Trends")
        if not df_view.empty:
            fig = px.bar(df_view, x='Center_Name', y='P3_Patient_Count', color='Center_Name')
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("Review Share")
        if not df_view.empty:
            fig2 = px.pie(df_view, values='P4_Google_Reviews', names='Center_Name', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)

# --- MAIN APP LOGIC ---
def main():
    st.set_page_config(page_title="RheumaCare Ops", page_icon="🏥", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['role'] = ''
        st.session_state['center'] = ''

    # LOGIN SCREEN
    if not st.session_state['logged_in']:
        left_co, cent_co, last_co = st.columns([1, 2, 1])
        with cent_co:
            if os.path.exists("logo.png"): st.image("logo.png", width=250)
            else: st.title("RheumaCare Ops")
        
        st.markdown("### Login")
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
                    st.session_state['role'] = role
                    st.rerun()
                else:
                    st.error("Invalid credentials")

    # LOGGED IN VIEW
    else:
        st.sidebar.title(f"👤 {st.session_state['username']}")
        st.sidebar.caption(f"{st.session_state['center']} | {st.session_state['role']}")
        st.sidebar.markdown("---")
        
        if st.session_state['role'] == "Supervisor":
            df_logs, df_users, df_tuts = load_data()
            show_command_centre(df_logs, df_users)
            if st.sidebar.button("Log Out"):
                st.session_state['logged_in'] = False; st.rerun()
        else:
            menu = st.sidebar.radio("Main Menu", ["📝 Daily Check-In", "⚠️ Incident Reporting", "📚 Tutorials", "⚙️ Settings"])
            st.sidebar.markdown("---")
            if st.sidebar.button("Log Out"):
                st.session_state['logged_in'] = False; st.rerun()

            df_logs, df_users, df_tutorials = load_data()

            if menu == "📝 Daily Check-In": show_daily_reporting()
            elif menu == "⚠️ Incident Reporting": show_incident_reporting()
            elif menu == "📚 Tutorials": show_tutorials(df_tutorials)
            elif menu == "⚙️ Settings": show_settings()

if __name__ == '__main__':
    main()
