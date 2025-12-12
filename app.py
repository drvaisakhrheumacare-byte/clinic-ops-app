import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta
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

# --- TIME GENERATORS ---
def generate_time_options(start_hour, end_hour):
    times = []
    # Loop from start hour to end hour
    for hour in range(start_hour, end_hour + 1):
        for minute in [0, 30]:  # 30 min intervals
            # Standard AM/PM formatting
            t = datetime.strptime(f"{hour}:{minute}", "%H:%M")
            times.append(t.strftime("%I:%M %p"))
    return times

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
        center_specific = df_contacts[df_contacts['Center'] == center_name]
        if not center_specific.empty:
            for index, row in center_specific.iterrows():
                service_name = row['Service_Name']
                number = row['Phone_Number']
                if service_name and number:
                    default_contacts[service_name] = str(number)
                    
    return default_contacts

def is_holiday_tomorrow(center_name):
    data = load_data()
    df_h = data.get('Holidays')
    
    if df_h.empty:
        return False
        
    tomorrow = date.today() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    
    # Check if tomorrow is in holidays for this center
    # Assuming Holiday Sheet has columns: Date, Name, Center
    # We check if Date matches AND Center matches
    match = df_h[
        (df_h['Date'].astype(str) == tomorrow_str) & 
        (df_h['Center'] == center_name)
    ]
    
    return not match.empty

# --- VIEW: GAMIFIED DAILY REPORTING ---
def show_daily_reporting():
    st.header(f"📝 Daily Log: {st.session_state['center']}")
    
    if 'daily_step' not in st.session_state: st.session_state['daily_step'] = 1
    if 'daily_data' not in st.session_state: st.session_state['daily_data'] = {}

    # Wizard Step 1: Time & Server Status
    if st.session_state['daily_step'] == 1:
        st.subheader("Step 1: Operational Basics")
        
        c1, c2 = st.columns(2)
        
        # 1. Custom Time Ranges
        # Open: 7 AM (7) to 8 PM (20)
        open_options = generate_time_options(7, 20)
        # Close: 11 AM (11) to 10 PM (22)
        close_options = generate_time_options(11, 22)
        
        open_time = c1.selectbox("Centre Open Time", open_options, index=0)
        close_time = c2.selectbox("Centre Close Time", close_options, index=len(close_options)-1) # Default to late
        
        st.markdown("---")
        st.write(" **End of Day Checks:**")
        
        offline_backup = st.checkbox("✅ Offline Backup Taken?")
        
        # 2. Automated Holiday Check
        is_holiday = is_holiday_tomorrow(st.session_state['center'])
        
        server_shutdown = False
        if is_holiday:
            st.warning(f"⚠️ Tomorrow is a detected Holiday. Please shut down servers.")
            # Only ask if holiday detected
            server_shutdown = st.checkbox("✅ Server Shutdown Completed?")
        
        if st.button("Next ➡️"):
            st.session_state['daily_data'].update({
                'open': str(open_time),
                'close': str(close_time),
                'offline_backup': "YES" if offline_backup else "NO",
                'server_shutdown': "YES" if server_shutdown else "NO" if is_holiday else "N/A",
                'holiday_tmrw': "YES" if is_holiday else "NO" # Auto calculated
            })
            st.session_state['daily_step'] = 2
            st.rerun()

    # Wizard Step 2: Patient Flow & Revenue
    elif st.session_state['daily_step'] == 2:
        st.subheader("Step 2: Patient & Cash Metrics")
        
        c1, c2 = st.columns(2)
        
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

# --- VIEW: CONTACT US ---
def show_contact_us():
    st.header("📞 Contact Us")
    st.markdown("### Growth Manager")
    
    col_left, col_right = st.columns(2)
    with col_left:
        st.info("📧 **Email**")
