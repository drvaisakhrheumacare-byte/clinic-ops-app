import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta
import plotly.express as px
import os
import time

# --- Configuration ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1vqZT4ul1kJXilVdK0Avw0U2frZPGvnlHZEWOFzqCnag/edit"
LOGO_URL = "https://raw.githubusercontent.com/drvaisakhrheumacare-byte/clinic-ops-app/refs/heads/main/download.jpeg"
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

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

def get_or_create_worksheet(sheet, name, rows=100, cols=10):
    try:
        return sheet.worksheet(name)
    except:
        return sheet.add_worksheet(title=name, rows=rows, cols=cols)

# --- DATA LOADER ---
@st.cache_data(ttl=60)
def load_data():
    client = get_google_sheet_client()
    sheet = client.open_by_url(SHEET_URL)
    
    data = {}
    tabs = ["Daily_Logs", "Users", "Incidents", "Service_Logs", "Reminders", "Holidays"]
    
    for tab in tabs:
        try:
            ws = sheet.worksheet(tab)
            data[tab] = pd.DataFrame(ws.get_all_records())
        except:
            data[tab] = pd.DataFrame() # Return empty DF if tab missing
            
    return data

def check_login(username, password):
    client = get_google_sheet_client()
    sheet = client.open_by_url(SHEET_URL)
    try:
        users_tab = sheet.worksheet("Users")
        df_users = pd.DataFrame(users_tab.get_all_records())
        
        # Check Username & Password
        user_match = df_users[(df_users['Username'].astype(str).str.strip() == username.strip()) & 
                              (df_users['Password'].astype(str).str.strip() == password.strip())]
        
        if not user_match.empty:
            return True, user_match.iloc[0]['Center_Name'], user_match.iloc[0]['Role']
        else:
            return False, None, None
    except:
        return False, None, None

def get_service_numbers():
    return {
        "AC Service": "+919800000001", "Interior Service": "+919800000002",
        "Electrical Service": "+919800000003", "Plumbing Service": "+919800000004",
        "CCTV Service": "+919800000005", "Network Service": "+919800000006",
        "Desktop Service": "+919800000007", "PBX Service": "+919800000008",
        "Telephone Service": "+919800000009", "Bitvoice Service": "+919800000010",
        "Server Service": "+919800000011", "EMR Elixir Service": "+919800000012",
    }

# --- VIEW: GAMIFIED DAILY REPORTING (Updated) ---
def show_daily_reporting():
    # UPDATED TITLE HERE
    st.header(f"📝 Rheuma CARE Daily: {st.session_state['center']}")
    
    with st.form("daily_log_new"):
        st.subheader("1. Time Logs")
        c1, c2 = st.columns(2)
        open_time = c1.time_input("Centre Open Time", value=None)
        close_time = c2.time_input("Centre Close Time", value=None)
        
        st.subheader("2. Operational Status")
        shutdown_tmrw = st.checkbox("Is the Centre Shutting Down Tomorrow (Holiday)?")
        
        st.subheader("3. Metrics")
        col_a, col_b = st.columns(2)
        encounters = col_a.number_input("Total Patient Encounters", min_value=0)
        cash_dep = col_b.number_input("Cash Deposit Amount (₹)", min_value=0.0)
        
        notes = st.text_area("Daily Notes / Handover")
        
        if st.form_submit_button("Submit Daily Log", type="primary"):
            try:
                client = get_google_sheet_client()
                sheet = client.open_by_url(SHEET_URL)
                ws = get_or_create_worksheet(sheet, "Daily_Logs")
                
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Structure: Timestamp, User, Center, Open, Close, Shutdown_Tmrw, Encounters, Cash, Notes
                row_data = [
                    ts, st.session_state['username'], st.session_state['center'],
                    str(open_time), str(close_time), "YES" if shutdown_tmrw else "NO",
                    encounters, cash_dep, notes
                ]
                ws.append_row(row_data)
                st.cache_data.clear()
                st.success("Daily log saved!")
            except Exception as e:
                st.error(f"Error: {e}")

# --- VIEW: GAMIFIED INCIDENT REPORTING (Quiz Style) ---
def show_incident_reporting():
    st.header(f"⚠️ Incident Reporting")
    
    # Define Hierarchy
    incident_structure = {
        "Facility": ["AC Not Cooling", "Water Leakage", "Power Failure", "Furniture Broken"],
        "IT & Network": ["Internet Down", "Printer Issue", "PC Slow/Crash", "Software Error"],
        "Medical Equipment": ["BP Apparatus", "Weighing Scale", "X-Ray Issue"],
        "Staffing": ["Staff Absent", "Late Arrival", "Uniform Issue"]
    }

    if 'inc_step' not in st.session_state: st.session_state['inc_step'] = 1
    if 'inc_data' not in st.session_state: st.session_state['inc_data'] = {}

    # Step 1: Category
    if st.session_state['inc_step'] == 1:
        st.subheader("Step 1: Which area is affected?")
        cat = st.radio("Select Category", list(incident_structure.keys()))
        if st.button("Next"):
            st.session_state['inc_data']['category'] = cat
            st.session_state['inc_step'] = 2
            st.rerun()

    # Step 2: Subcategory
    elif st.session_state['inc_step'] == 2:
        cat = st.session_state['inc_data']['category']
        st.subheader(f"Step 2: What is the specific {cat} issue?")
        subcat = st.radio("Select Issue", incident_structure[cat])
        
        c1, c2 = st.columns(2)
        if c1.button("Back"): 
            st.session_state['inc_step'] = 1
            st.rerun()
        if c2.button("Next"):
            st.session_state['inc_data']['subcategory'] = subcat
            st.session_state['inc_step'] = 3
            st.rerun()

    # Step 3: Details & Submit
    elif st.session_state['inc_step'] == 3:
        st.subheader("Step 3: Final Details")
        st.write(f"**Issue:** {st.session_state['inc_data']['category']} > {st.session_state['inc_data']['subcategory']}")
        
        desc = st.text_input("Short Description")
        priority = st.select_slider("Severity", options=["Low", "Medium", "High", "Critical"])
        
        c1, c2 = st.columns(2)
        if c1.button("Back"):
            st.session_state['inc_step'] = 2
            st.rerun()
            
        if c2.button("🚨 Report Incident", type="primary"):
            try:
                client = get_google_sheet_client()
                sheet = client.open_by_url(SHEET_URL)
                ws = get_or_create_worksheet(sheet, "Incidents")
                
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row_data = [
                    ts, st.session_state['center'], 
                    st.session_state['inc_data']['category'],
                    st.session_state['inc_data']['subcategory'],
                    desc, priority, "Open"
                ]
                ws.append_row(row_data)
                st.cache_data.clear()
                st.success("Incident Reported & Supervisor Notified!")
                # Reset
                st.session_state['inc_step'] = 1
                st.session_state['inc_data'] = {}
            except Exception as e:
                st.error(f"Error: {e}")

# --- VIEW: CONTACT US (Updated with Dr Vaisakh Info) ---
def show_contact_us():
    st.header("📞 Contact Us")
    
    # --- Part 1: Main Medical Contact ---
    st.markdown("### Medical Director")
    
    col_left, col_right = st.columns(2)
    with col_left:
        st.info("📧 **Email**")
        st.markdown("**dr.vaisakh@rheumacare.com**")
    with col_right:
        st.success("📞 **Phone**")
        st.markdown("**9717096659**")
        
    st.markdown("---")

    # --- Part 2: Facility Services ---
    st.subheader("Facility & Operations Support")
    st.caption("Click 'Call' to view number and log the request to the Supervisor.")
    
    services = get_service_numbers()
    cols = st.columns(3)
    
    for idx, (name, number) in enumerate(services.items()):
        with cols[idx % 3]:
            with st.container(border=True):
                st.write(f"**{name}**")
                if st.button(f"📞 Call", key=f"btn_{name}"):
                    # Log to Sheets
                    try:
                        client = get_google_sheet_client()
                        sheet = client.open_by_url(SHEET_URL)
                        ws = get_or_create_worksheet(sheet, "Service_Logs")
                        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ws.append_row([ts, st.session_state['center'], name, number])
                        st.success(f"Logged! Dial: {number}")
                        st.markdown(f'<a href="tel:{number}">Click to Call</a>', unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Logging failed: {e}")

# --- VIEW: REMINDERS ---
def show_reminders():
    st.header("🔔 Bill & Payment Reminders")
    
    # Load existing reminders for this center
    client = get_google_sheet_client()
    sheet = client.open_by_url(SHEET_URL)
    ws = get_or_create_worksheet(sheet, "Reminders", cols=4)
    
    # Helper to get current value
    all_reminders = ws.get_all_records()
    df_rem = pd.DataFrame(all_reminders)
    
    defaults = {
        "Electricity Bill": None, "Water Bill": None, "Rent": None,
        "SIP": None, "ISP1": None, "ISP2": None
    }
    
    # If data exists, populate defaults
    if not df_rem.empty:
        center_rem = df_rem[df_rem['Center'] == st.session_state['center']]
        for index, row in center_rem.iterrows():
            if row['Type'] in defaults:
                try:
                    defaults[row['Type']] = datetime.strptime(str(row['Due_Date']), "%Y-%m-%d").date()
                except: pass

    with st.form("reminders_form"):
        col1, col2 = st.columns(2)
        new_values = {}
        
        items = list(defaults.keys())
        for i, item in enumerate(items):
            target_col = col1 if i % 2 == 0 else col2
            new_values[item] = target_col.date_input(f"{item} Due Date", value=defaults[item])

        if st.form_submit_button("Update Reminders"):
            ts = datetime.now().strftime("%Y-%m-%d")
            for r_type, r_date in new_values.items():
                if r_date:
                    ws.append_row([st.session_state['center'], r_type, str(r_date), ts])
            
            st.success("Reminders Updated")
            st.cache_data.clear()

# --- VIEW: HOLIDAY LIST (Manager) ---
def show_holiday_manager():
    st.header("📅 Holiday List")
    data = load_data()
    df_h = data.get('Holidays')
    
    if not df_h.empty:
        st.dataframe(df_h, use_container_width=True)
    
    st.divider()
    with st.form("add_holiday"):
        st.write("**Add New Holiday**")
        d = st.date_input("Date")
        n = st.text_input("Holiday Name")
        if st.form_submit_button("Add"):
            client = get_google_sheet_client()
            sheet = client.open_by_url(SHEET_URL)
            ws = get_or_create_worksheet(sheet, "Holidays")
            ws.append_row([str(d), n, st.session_state['center']]) # Added center column
            st.success("Holiday Added")
            st.cache_data.clear()

# --- SUPERVISOR DASHBOARD ---
def show_supervisor_dashboard(data):
    st.title("👨‍💼 Supervisor Dashboard")
    
    tab1, tab2, tab3 = st.tabs(["Daily Logs", "Incident Reports", "Service Call Logs"])
    
    # 1. Daily Logs Consolidated
    with tab1:
        st.subheader("Daily Centre Status")
        date_sel = st.date_input("Select Date", date.today())
        
        df_logs = data.get('Daily_Logs')
        df_users = data.get('Users')
        
        if not df_users.empty:
            all_centers = df_users[df_users['Role'] == 'Centre Manager']['Center_Name'].unique()
        else:
            all_centers = []

        status_rows = []
        
        # Filter logs for selected date
        if not df_logs.empty:
            # Handle string dates from Sheets
            df_logs['Date_Obj'] = pd.to_datetime(df_logs['Timestamp']).dt.date
            day_logs = df_logs[df_logs['Date_Obj'] == date_sel]
        else:
            day_logs = pd.DataFrame()

        for center in all_centers:
            # Find log for this center
            entry = day_logs[day_logs['Center_Name'] == center] if not day_logs.empty else pd.DataFrame()
            
            if not entry.empty:
                row = entry.iloc[0]
                status_rows.append({
                    "Centre": center,
                    "Status": "✅ Reported",
                    "Open": row.get('Open_Time', row.iloc[3] if len(row)>3 else '-'),
                    "Close": row.get('Close_Time', row.iloc[4] if len(row)>4 else '-'),
                    "Shutdown Tmrw": row.get('Shutdown_Tomorrow', row.iloc[5] if len(row)>5 else '-'),
                    "Notes": row.get('Notes', row.iloc[8] if len(row)>8 else '-')
                })
            else:
                status_rows.append({
                    "Centre": center,
                    "Status": "❌ Missing", "Open": "-", "Close": "-", "Shutdown Tmrw": "-", "Notes": "-"
                })
        
        df_status = pd.DataFrame(status_rows)
        
        # Color coding
        def color_missing(val):
            color = '#ffcccc' if val == '❌ Missing' else '#ccffcc'
            return f'background-color: {color}'

        if not df_status.empty:
            st.dataframe(df_status.style.map(color_missing, subset=['Status']), use_container_width=True)

    # 2. Incidents (Last 15)
    with tab2:
        st.subheader("⚠️ Latest Incidents")
        df_inc = data.get('Incidents')
        if not df_inc.empty:
            # Sort by Timestamp (Col 0) desc
            df_inc = df_inc.sort_values(by=df_inc.columns[0], ascending=False).head(15)
            st.dataframe(df_inc, use_container_width=True)
        else:
            st.info("No incidents reported.")

    # 3. Service Logs
    with tab3:
        st.subheader("🔧 Service Call History")
        df_svc = data.get('Service_Logs')
        if not df_svc.empty:
            df_svc = df_svc.sort_values(by=df_svc.columns[0], ascending=False)
            st.dataframe(df_svc, use_container_width=True)
        else:
            st.info("No service calls logged.")

# --- MAIN APP ---
def main():
    # UPDATED PAGE TITLE
    st.set_page_config(page_title="Rheuma CARE Daily", page_icon="🏥", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['role'] = ''
        st.session_state['center'] = ''

    # LOGIN SCREEN
    if not st.session_state['logged_in']:
        left_co, cent_co, last_co = st.columns([1, 2, 1])
        with cent_co:
            st.image(LOGO_URL, width=200)
        
        st.markdown("<h3 style='text-align: center'>Rheuma CARE Login</h3>", unsafe_allow_html=True)
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

    # LOGGED IN INTERFACE
    else:
        with st.sidebar:
            st.image(LOGO_URL, width=150)
            st.title(f"{st.session_state['center']}")
            st.caption(f"Role: {st.session_state['role']}")
            st.divider()
            
            if st.session_state['role'] == "Supervisor":
                menu = "Supervisor Dashboard" # Only one view for now
            else:
                menu = st.radio("Menu", [
                    "Rheuma CARE Daily",  # UPDATED NAME
                    "Incident Reporting", 
                    "Holiday List", 
                    "Contact Us",         # UPDATED NAME
                    "Reminders"
                ])
            
            st.divider()
            if st.button("Log Out"):
                st.session_state['logged_in'] = False
                st.session_state['daily_step'] = 1 # Reset wizard
                st.rerun()

        # ROUTING
        if st.session_state['role'] == "Supervisor":
            data = load_data()
            show_supervisor_dashboard(data)
        else:
            if menu == "Rheuma CARE Daily": show_daily_reporting()
            elif menu == "Incident Reporting": show_incident_reporting()
            elif menu == "Holiday List": show_holiday_manager()
            elif menu == "Contact Us": show_contact_us() # Updated function call
            elif menu == "Reminders": show_reminders()

if __name__ == '__main__':
    main()
