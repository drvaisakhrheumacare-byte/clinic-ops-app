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
LOGO_URL = "https://raw.githubusercontent.com/drvaisakhrheumacare-byte/clinic-ops-app/main/logo.png"
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
    tabs = ["Daily_Logs", "Users", "Incidents", "Service_Logs", "Reminders", "Holidays", "Service_Contacts"]
    
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

# Get contacts specifically for the logged-in center
def get_center_service_numbers(center_name):
    data = load_data()
    df_contacts = data.get('Service_Contacts')
    
    default_contacts = {
        "AC Service": "+919800000001", "Interior Service": "+919800000002",
        "Electrical Service": "+919800000003", "Plumbing Service": "+919800000004",
        "CCTV Service": "+919800000005", "Network Service": "+919800000006",
        "Desktop Service": "+919800000007", "PBX Service": "+919800000008",
        "Telephone Service": "+919800000009", "Bitvoice Service": "+919800000010",
        "Server Service": "+919800000011", "EMR Elixir Service": "+919800000012",
    }
    
    if not df_contacts.empty:
        # Filter for this center
        center_specific = df_contacts[df_contacts['Center'] == center_name]
        if not center_specific.empty:
            for index, row in center_specific.iterrows():
                service_name = row['Service_Name']
                number = row['Phone_Number']
                if service_name and number:
                    default_contacts[service_name] = str(number)
                    
    return default_contacts

# --- VIEW: GAMIFIED DAILY REPORTING (QUIZ STYLE) ---
def show_daily_reporting():
    # 1. Removed "Growth" from header
    st.header(f"📝 Daily Log: {st.session_state['center']}")
    
    if 'daily_step' not in st.session_state: st.session_state['daily_step'] = 1
    if 'daily_data' not in st.session_state: st.session_state['daily_data'] = {}

    # Wizard Step 1: Time & Server Status
    if st.session_state['daily_step'] == 1:
        st.subheader("Step 1: Operational Basics")
        
        c1, c2 = st.columns(2)
        open_time = c1.time_input("Centre Open Time", value=None)
        close_time = c2.time_input("Centre Close Time", value=None)
        
        st.markdown("---")
        st.write(" **End of Day Checks:**")
        
        # Restored Item: Offline Backup
        offline_backup = st.checkbox("✅ Offline Backup Taken?")
        
        # Restored Item: Server Shutdown
        server_shutdown = st.checkbox("✅ Server Shutdown Completed?")
        
        # Restored Item: Holiday Check
        holiday_tmrw = st.checkbox("🗓️ Is Centre Closed Tomorrow?")

        if st.button("Next ➡️"):
            st.session_state['daily_data'].update({
                'open': str(open_time),
                'close': str(close_time),
                'offline_backup': "YES" if offline_backup else "NO",
                'server_shutdown': "YES" if server_shutdown else "NO",
                'holiday_tmrw': "YES" if holiday_tmrw else "NO"
            })
            st.session_state['daily_step'] = 2
            st.rerun()

    # Wizard Step 2: Patient Flow & Revenue
    elif st.session_state['daily_step'] == 2:
        st.subheader("Step 2: Patient & Cash Metrics")
        
        c1, c2 = st.columns(2)
        
        # Restored Items
        with c1:
            total_patients = st.number_input("Total Patient Count", min_value=0)
            new_patients = st.number_input("New Patients Count", min_value=0)
            walk_in = st.number_input("Walk-in Patients Count", min_value=0)
            
        with c2:
            rebooking = st.number_input("Rebooking Count", min_value=0)
            reviews = st.number_input("Google Reviews Count", min_value=0)
            cash = st.number_input("Cash Deposit Amount (₹)", min_value=0.0)

        c_back, c_next = st.columns([1,1])
        if c_back.button("⬅️ Back"):
            st.session_state['daily_step'] = 1
            st.rerun()
            
        if c_next.button("Next ➡️"):
            st.session_state['daily_data'].update({
                'total_patients': total_patients,
                'new_patients': new_patients,
                'walk_in': walk_in,
                'rebooking': rebooking,
                'reviews': reviews,
                'cash': cash
            })
            st.session_state['daily_step'] = 3
            st.rerun()

    # Wizard Step 3: Notes & Submit
    elif st.session_state['daily_step'] == 3:
        st.subheader("Step 3: Final Notes")
        
        # Restored Item: Daily Notes
        notes = st.text_area("Daily Notes / Handover Issues")
        
        st.info("Please review your data before submitting.")
        st.write(f"**Patients:** {st.session_state['daily_data'].get('total_patients')} | **Cash:** ₹{st.session_state['daily_data'].get('cash')}")

        c_back, c_submit = st.columns([1,1])
        if c_back.button("⬅️ Back"):
            st.session_state['daily_step'] = 2
            st.rerun()
            
        if c_submit.button("✅ Submit Daily Log", type="primary"):
            try:
                client = get_google_sheet_client()
                sheet = client.open_by_url(SHEET_URL)
                ws = get_or_create_worksheet(sheet, "Daily_Logs")
                
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                d = st.session_state['daily_data']
                
                # Full Data Row
                row_data = [
                    ts, st.session_state['username'], st.session_state['center'],
                    d['open'], d['close'], d['offline_backup'], d['server_shutdown'], d['holiday_tmrw'],
                    d['total_patients'], d['new_patients'], d['walk_in'], d['rebooking'], d['reviews'],
                    d['cash'], notes
                ]
                
                ws.append_row(row_data)
                st.cache_data.clear()
                st.success("Daily log saved successfully! Great job! 🎉")
                time.sleep(2)
                st.session_state['daily_step'] = 1
                st.session_state['daily_data'] = {}
                st.rerun()
                
            except Exception as e:
                st.error(f"Error saving data: {e}")

# --- VIEW: GAMIFIED INCIDENT REPORTING ---
def show_incident_reporting():
    st.header(f"⚠️ Incident Reporting")
    
    incident_structure = {
        "Facility": ["AC Not Cooling", "Water Leakage", "Power Failure", "Furniture Broken"],
        "IT & Network": ["Internet Down", "Printer Issue", "PC Slow/Crash", "Software Error"],
        "Medical Equipment": ["BP Apparatus", "Weighing Scale", "X-Ray Issue"],
        "Staffing": ["Staff Absent", "Late Arrival", "Uniform Issue"]
    }

    if 'inc_step' not in st.session_state: st.session_state['inc_step'] = 1
    if 'inc_data' not in st.session_state: st.session_state['inc_data'] = {}

    if st.session_state['inc_step'] == 1:
        st.subheader("Step 1: Which area is affected?")
        cat = st.radio("Select Category", list(incident_structure.keys()))
        if st.button("Next"):
            st.session_state['inc_data']['category'] = cat
            st.session_state['inc_step'] = 2
            st.rerun()

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
                st.session_state['inc_step'] = 1
                st.session_state['inc_data'] = {}
            except Exception as e:
                st.error(f"Error: {e}")

# --- VIEW: CONTACT US (UPDATED) ---
def show_contact_us():
    st.header("📞 Contact Us")
    
    # 2. Changed Title to Growth Manager
    st.markdown("### Growth Manager")
    
    col_left, col_right = st.columns(2)
    with col_left:
        st.info("📧 **Email**")
        st.markdown("**dr.vaisakh@rheumacare.com**")
    with col_right:
        st.success("📞 **Phone**")
        st.markdown("**9717096659**")
        
    st.markdown("---")

    # 3. Dynamic Facility Services
    st.subheader("Facility & Operations Support")
    st.caption("These contacts are specific to your centre.")
    
    # Fetch contacts dynamically for the logged-in center
    services = get_center_service_numbers(st.session_state['center'])
    
    cols = st.columns(3)
    
    for idx, (name, number) in enumerate(services.items()):
        with cols[idx % 3]:
            with st.container(border=True):
                st.write(f"**{name}**")
                if st.button(f"📞 Call", key=f"btn_{name}"):
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
    client = get_google_sheet_client()
    sheet = client.open_by_url(SHEET_URL)
    ws = get_or_create_worksheet(sheet, "Reminders", cols=4)
    
    all_reminders = ws.get_all_records()
    df_rem = pd.DataFrame(all_reminders)
    
    defaults = {
        "Electricity Bill": None, "Water Bill": None, "Rent": None,
        "SIP": None, "ISP1": None, "ISP2": None
    }
    
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

# --- VIEW: HOLIDAY LIST ---
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
            ws.append_row([str(d), n, st.session_state['center']])
            st.success("Holiday Added")
            st.cache_data.clear()

# --- SUPERVISOR DASHBOARD ---
def show_supervisor_dashboard(data):
    st.title("👨‍💼 Supervisor Dashboard")
    
    # 4. Added "Manage Contacts" tab
    tab1, tab2, tab3, tab4 = st.tabs(["Daily Logs", "Incident Reports", "Service Call Logs", "Manage Contacts"])
    
    # Tab 1: Daily Logs
    with tab1:
        st.subheader("Daily Centre Status")
        date_sel = st.date_input("Select Date", date.today())
        
        df_logs = data.get('Daily_Logs')
        df_users = data.get('Users')
        
        all_centers = df_users[df_users['Role'] == 'Centre Manager']['Center_Name'].unique() if not df_users.empty else []
        status_rows = []
        
        if not df_logs.empty:
            df_logs['Date_Obj'] = pd.to_datetime(df_logs['Timestamp']).dt.date
            day_logs = df_logs[df_logs['Date_Obj'] == date_sel]
        else:
            day_logs = pd.DataFrame()

        for center in all_centers:
            entry = day_logs[day_logs['Center_Name'] == center] if not day_logs.empty else pd.DataFrame()
            if not entry.empty:
                # We show basic status here
                status_rows.append({"Centre": center, "Status": "✅ Reported"})
            else:
                status_rows.append({"Centre": center, "Status": "❌ Missing"})
        
        df_status = pd.DataFrame(status_rows)
        if not df_status.empty:
            st.dataframe(df_status, use_container_width=True)

    # Tab 2: Incidents
    with tab2:
        st.subheader("⚠️ Latest Incidents")
        df_inc = data.get('Incidents')
        if not df_inc.empty:
            df_inc = df_inc.sort_values(by=df_inc.columns[0], ascending=False).head(15)
            st.dataframe(df_inc, use_container_width=True)
        else:
            st.info("No incidents reported.")

    # Tab 3: Service Logs
    with tab3:
        st.subheader("🔧 Service Call History")
        df_svc = data.get('Service_Logs')
        if not df_svc.empty:
            df_svc = df_svc.sort_values(by=df_svc.columns[0], ascending=False)
            st.dataframe(df_svc, use_container_width=True)
        else:
            st.info("No service calls logged.")
            
    # Tab 4: Manage Service Contacts (New Feature)
    with tab4:
        st.subheader("📞 Manage Centre Contacts")
        st.info("Add or Update service numbers for specific centers here.")
        
        df_users = data.get('Users')
        available_centers = df_users['Center_Name'].unique().tolist() if not df_users.empty else []
        
        with st.form("add_contact_form"):
            s_center = st.selectbox("Select Center", available_centers)
            s_service = st.selectbox("Service Type", [
                "AC Service", "Interior Service", "Electrical Service", 
                "Plumbing Service", "CCTV Service", "Network Service",
                "Desktop Service", "PBX Service", "Telephone Service", 
                "Bitvoice Service", "Server Service", "EMR Elixir Service"
            ])
            s_number = st.text_input("Phone Number (+91...)")
            
            if st.form_submit_button("Save Contact"):
                if s_number:
                    client = get_google_sheet_client()
                    sheet = client.open_by_url(SHEET_URL)
                    ws = get_or_create_worksheet(sheet, "Service_Contacts", cols=3)
                    # Append new mapping
                    ws.append_row([s_center, s_service, s_number])
                    st.success(f"Contact for {s_service} at {s_center} updated!")
                    st.cache_data.clear()

# --- MAIN APP ---
def main():
    st.set_page_config(page_title="Rheuma CARE Daily", page_icon="🏥", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['role'] = ''
        st.session_state['center'] = ''

    if not st.session_state['logged_in']:
        left_co, cent_co, last_co = st.columns([1, 2, 1])
        with cent_co:
            st.image(LOGO_URL, width=200)
            
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
    else:
        with st.sidebar:
            st.image(LOGO_URL, width=150)
            st.title(f"{st.session_state['center']}")
            st.caption(f"Role: {st.session_state['role']}")
            st.divider()
            
            if st.session_state['role'] == "Supervisor":
                menu = "Supervisor Dashboard"
            else:
                # 2. Reordered Menu
                menu = st.radio("Menu", [
                    "Rheuma CARE Daily",
                    "Incident Reporting", 
                    "Holiday List", 
                    "Reminders",
                    "Contact Us" # Moved to Last
                ])
            
            st.divider()
            if st.button("Log Out"):
                st.session_state['logged_in'] = False
                st.session_state['daily_step'] = 1 
                st.rerun()

        if st.session_state['role'] == "Supervisor":
            data = load_data()
            show_supervisor_dashboard(data)
        else:
            if menu == "Rheuma CARE Daily": show_daily_reporting()
            elif menu == "Incident Reporting": show_incident_reporting()
            elif menu == "Holiday List": show_holiday_manager()
            elif menu == "Reminders": show_reminders()
            elif menu == "Contact Us": show_contact_us()

if __name__ == '__main__':
    main()
