import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta
import time
import random

# --- Configuration ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1vqZT4ul1kJXilVdK0Avw0U2frZPGvnlHZEWOFzqCnag/edit"
LOGO_URL = "https://raw.githubusercontent.com/drvaisakhrheumacare-byte/clinic-ops-app/main/logo.png"
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# --- Helper Functions ---

def retry_api_call(func, retries=3, delay=2):
    """Retries a function if API quota is exceeded."""
    for i in range(retries):
        try:
            return func()
        except Exception as e:
            if "429" in str(e) or "Quota exceeded" in str(e):
                wait_time = delay * (2 ** i) + random.uniform(0, 1)
                st.warning(f"⚠️ High traffic. Retrying in {int(wait_time)}s...")
                time.sleep(wait_time)
            else:
                raise e
    raise Exception("API Quota Exceeded. Please try again later.")

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
    for hour in range(start_hour, end_hour + 1):
        for minute in [0, 30]:
            t = datetime.strptime(f"{hour}:{minute}", "%H:%M")
            times.append(t.strftime("%I:%M %p"))
    return times

# --- DATA LOADER (OPTIMIZED) ---
@st.cache_data(ttl=300)
def load_data():
    client = get_google_sheet_client()
    
    def _fetch():
        sheet = client.open_by_url(SHEET_URL)
        data = {}
        tabs = ["Daily_Logs", "Users", "Incidents", "Service_Logs", "Reminders", "Holidays", "Service_Contacts"]
        
        for tab in tabs:
            try:
                ws = sheet.worksheet(tab)
                df = pd.DataFrame(ws.get_all_records())
                data[tab] = df
            except:
                data[tab] = pd.DataFrame()
        return data

    return retry_api_call(_fetch)

# --- AUTH & LOGIC ---

def check_login(username, password):
    data = load_data()
    df_users = data.get('Users')
    
    if df_users is None or df_users.empty:
        return False, None, None

    # Check Username & Password
    try:
        user_match = df_users[(df_users['Username'].astype(str).str.strip() == username.strip()) & 
                              (df_users['Password'].astype(str).str.strip() == password.strip())]
        
        if not user_match.empty:
            return True, user_match.iloc[0]['Center_Name'], user_match.iloc[0]['Role']
        else:
            return False, None, None
    except KeyError:
        st.error("Sheet Error: 'Users' tab missing headers (Username, Password, Role, Center_Name).")
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
    
    if df_contacts is not None and not df_contacts.empty:
        if 'Center' in df_contacts.columns and 'Service_Name' in df_contacts.columns:
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
    
    # --- CRITICAL FIX: SAFETY CHECK ---
    # If the sheet is empty or missing columns, return False (Not a holiday)
    if df_h is None or df_h.empty:
        return False
        
    if 'Date' not in df_h.columns or 'Center' not in df_h.columns:
        # Columns missing, cannot check
        return False
    # ----------------------------------
        
    tomorrow = date.today() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    
    try:
        match = df_h[
            (df_h['Date'].astype(str) == tomorrow_str) & 
            (df_h['Center'] == center_name)
        ]
        return not match.empty
    except:
        return False

# --- VIEW FUNCTIONS ---

def show_daily_reporting():
    st.header(f"📝 Daily Log: {st.session_state['center']}")
    
    if 'daily_step' not in st.session_state: st.session_state['daily_step'] = 1
    if 'daily_data' not in st.session_state: st.session_state['daily_data'] = {}

    # Wizard Step 1: Time & Server Status
    if st.session_state['daily_step'] == 1:
        st.subheader("Step 1: Operational Basics")
        
        c1, c2 = st.columns(2)
        open_options = generate_time_options(7, 20)
        close_options = generate_time_options(11, 22)
        
        open_time = c1.selectbox("Centre Open Time", open_options, index=0)
        close_time = c2.selectbox("Centre Close Time", close_options, index=len(close_options)-1)
        
        st.markdown("---")
        st.write(" **End of Day Checks:**")
        
        offline_backup = st.checkbox("✅ Offline Backup Taken?")
        
        # Holiday check (Safe Version)
        is_holiday = is_holiday_tomorrow(st.session_state['center'])
        
        server_shutdown = False
        if is_holiday:
            st.warning(f"⚠️ Tomorrow is a detected Holiday. Please shut down servers.")
            server_shutdown = st.checkbox("✅ Server Shutdown Completed?")
        
        if st.button("Next ➡️"):
            st.session_state['daily_data'].update({
                'open': str(open_time),
                'close': str(close_time),
                'offline_backup': "YES" if offline_backup else "NO",
                'server_shutdown': "YES" if server_shutdown else "NO" if is_holiday else "N/A",
                'holiday_tmrw': "YES" if is_holiday else "NO"
            })
            st.session_state['daily_step'] = 2
            st.rerun()

    # Wizard Step 2: Metrics
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
                'total_patients': total_patients, 'new_patients': new_patients,
                'walk_in': walk_in, 'rebooking': rebooking,
                'reviews': reviews, 'cash': cash
            })
            st.session_state['daily_step'] = 3
            st.rerun()

    # Wizard Step 3: Notes & Submit
    elif st.session_state['daily_step'] == 3:
        st.subheader("Step 3: Final Notes")
        notes = st.text_area("Daily Notes / Handover Issues")
        st.info("Please review your data before submitting.")
        
        c_back, c_submit = st.columns([1,1])
        if c_back.button("⬅️ Back"):
            st.session_state['daily_step'] = 2
            st.rerun()
            
        if c_submit.button("✅ Submit Daily Log", type="primary"):
            def _submit():
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

            try:
                retry_api_call(_submit)
                st.cache_data.clear()
                st.success("Daily log saved successfully! 🎉")
                time.sleep(2)
                st.session_state['daily_step'] = 1
                st.session_state['daily_data'] = {}
                st.rerun()
            except Exception as e:
                st.error(f"Error saving data: {e}")

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
            def _report():
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

            try:
                retry_api_call(_report)
                st.cache_data.clear()
                st.success("Incident Reported!")
                st.session_state['inc_step'] = 1
                st.session_state['inc_data'] = {}
            except Exception as e:
                st.error(f"Error: {e}")

def show_contact_us():
    st.header("📞 Contact Us")
    st.markdown("### Growth Manager")
    
    col_left, col_right = st.columns(2)
    with col_left:
        st.info("📧 **Email**")
        st.markdown("**dr.vaisakh@rheumacare.com**")
    with col_right:
        st.success("📞 **Phone**")
        st.markdown("**9717096659**")
    st.markdown("---")

    st.subheader("Facility & Operations Support")
    st.caption("These contacts are specific to your centre.")
    services = get_center_service_numbers(st.session_state['center'])
    cols = st.columns(3)
    for idx, (name, number) in enumerate(services.items()):
        with cols[idx % 3]:
            with st.container(border=True):
                st.write(f"**{name}**")
                if st.button(f"📞 Call", key=f"btn_{name}"):
                    def _log_call():
                        client = get_google_sheet_client()
                        sheet = client.open_by_url(SHEET_URL)
                        ws = get_or_create_worksheet(sheet, "Service_Logs")
                        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ws.append_row([ts, st.session_state['center'], name, number])
                    try:
                        retry_api_call(_log_call)
                        st.success(f"Logged! Dial: {number}")
                        st.markdown(f'<a href="tel:{number}">Click to Call</a>', unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Logging failed: {e}")

def show_reminders():
    st.header("🔔 Bill & Payment Reminders")
    data = load_data()
    df_rem = data.get('Reminders')
    
    defaults = {
        "Electricity Bill": None, "Water Bill": None, "Rent": None,
        "SIP": None, "ISP1": None, "ISP2": None
    }
    
    if df_rem is not None and not df_rem.empty:
        if 'Center' in df_rem.columns and 'Type' in df_rem.columns:
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
            def _update():
                client = get_google_sheet_client()
                sheet = client.open_by_url(SHEET_URL)
                ws = get_or_create_worksheet(sheet, "Reminders", cols=4)
                ts = datetime.now().strftime("%Y-%m-%d")
                for r_type, r_date in new_values.items():
                    if r_date:
                        ws.append_row([st.session_state['center'], r_type, str(r_date), ts])
            try:
                retry_api_call(_update)
                st.success("Reminders Updated")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Error: {e}")

def show_holiday_manager():
    st.header("📅 Holiday List")
    data = load_data()
    df_h = data.get('Holidays')
    if df_h is not None and not df_h.empty:
        st.dataframe(df_h, use_container_width=True)
    
    st.divider()
    with st.form("add_holiday"):
        st.write("**Add New Holiday**")
        d = st.date_input("Date")
        n = st.text_input("Holiday Name")
        if st.form_submit_button("Add"):
            def _add():
                client = get_google_sheet_client()
                sheet = client.open_by_url(SHEET_URL)
                ws = get_or_create_worksheet(sheet, "Holidays")
                ws.append_row([str(d), n, st.session_state['center']])
            try:
                retry_api_call(_add)
                st.success("Holiday Added")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Error: {e}")

def show_supervisor_dashboard(data):
    st.title("👨‍💼 Supervisor Dashboard")
    tab1, tab2, tab3, tab4 = st.tabs(["Daily Logs", "Incidents", "Service Call Logs", "Manage Contacts"])
    
    with tab1:
        st.subheader("Daily Centre Status")
        date_sel = st.date_input("Select Date", date.today())
        df_logs = data.get('Daily_Logs')
        df_users = data.get('Users')
        
        all_centers = df_users[df_users['Role'] == 'Centre Manager']['Center_Name'].unique() if (df_users is not None and not df_users.empty) else []
        status_rows = []
        if df_logs is not None and not df_logs.empty:
            df_logs['Date_Obj'] = pd.to_datetime(df_logs['Timestamp']).dt.date
            day_logs = df_logs[df_logs['Date_Obj'] == date_sel]
        else:
            day_logs = pd.DataFrame()

        for center in all_centers:
            entry = day_logs[day_logs['Center_Name'] == center] if not day_logs.empty else pd.DataFrame()
            if not entry.empty:
                status_rows.append({"Centre": center, "Status": "✅ Reported"})
            else:
                status_rows.append({"Centre": center, "Status": "❌ Missing"})
        
        df_status = pd.DataFrame(status_rows)
        if not df_status.empty:
            st.dataframe(df_status, use_container_width=True)

    with tab2:
        df_inc = data.get('Incidents')
        if df_inc is not None and not df_inc.empty:
            df_inc = df_inc.sort_values(by=df_inc.columns[0], ascending=False).head(15)
            st.dataframe(df_inc, use_container_width=True)
    
    with tab3:
        df_svc = data.get('Service_Logs')
        if df_svc is not None and not df_svc.empty:
            df_svc = df_svc.sort_values(by=df_svc.columns[0], ascending=False)
            st.dataframe(df_svc, use_container_width=True)
            
    with tab4:
        st.subheader("📞 Manage Centre Contacts")
        df_users = data.get('Users')
        available_centers = df_users['Center_Name'].unique().tolist() if (df_users is not None and not df_users.empty) else []
        
        with st.form("add_contact_form"):
            s_center = st.selectbox("Select Center", available_centers)
            s_service = st.selectbox("Service Type", [
                "AC Service", "Interior Service", "Electrical Service", "Plumbing Service", 
                "CCTV Service", "Network Service", "Desktop Service", "PBX Service", 
                "Telephone Service", "Bitvoice Service", "Server Service", "EMR Elixir Service"
            ])
            s_number = st.text_input("Phone Number (+91...)")
            
            if st.form_submit_button("Save Contact"):
                if s_number:
                    def _save_contact():
                        client = get_google_sheet_client()
                        sheet = client.open_by_url(SHEET_URL)
                        ws = get_or_create_worksheet(sheet, "Service_Contacts", cols=3)
                        ws.append_row([s_center, s_service, s_number])
                    try:
                        retry_api_call(_save_contact)
                        st.success(f"Contact Updated!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Error: {e}")

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
                try:
                    is_valid, center, role = check_login(username, password)
                    if is_valid:
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = username
                        st.session_state['center'] = center
                        st.session_state['role'] = role
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
                except Exception as e:
                    st.error(f"Login failed (API Error). Try again. {e}")
    else:
        with st.sidebar:
            st.image(LOGO_URL, width=150)
            st.title(f"{st.session_state['center']}")
            st.caption(f"Role: {st.session_state['role']}")
            st.divider()
            
            if st.session_state['role'] == "Supervisor":
                menu = "Supervisor Dashboard"
            else:
                menu = st.radio("Menu", [
                    "Rheuma CARE Daily", "Incident Reporting", 
                    "Holiday List", "Reminders", "Contact Us"
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
