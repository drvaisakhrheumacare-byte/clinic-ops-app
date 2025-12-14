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

def get_or_create_worksheet(sheet, name, rows=100, cols=25):
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
    
    required_services = [
        "AC Service", "Interior Service", "Electrical Service", "Plumbing Service",
        "CCTV Service", "Network Service", "Desktop Service", "PBX Service",
        "Telephone Service", "Bitvoice Service", "Server Service", "EMR Elixir Service"
    ]
    
    final_contacts = {service: "Not Set" for service in required_services}
    
    if df_contacts is not None and not df_contacts.empty:
        if 'Center' in df_contacts.columns and 'Service_Name' in df_contacts.columns:
            center_specific = df_contacts[df_contacts['Center'] == center_name]
            for index, row in center_specific.iterrows():
                s_name = row['Service_Name']
                s_num = str(row['Phone_Number'])
                if s_name in final_contacts and s_num:
                    final_contacts[s_name] = s_num
                    
    return final_contacts

def is_holiday_tomorrow(center_name):
    data = load_data()
    df_h = data.get('Holidays')
    
    if df_h is None or df_h.empty:
        return False
    if 'Date' not in df_h.columns or 'Center' not in df_h.columns:
        return False
        
    tomorrow = date.today() + timedelta(days=1)
    fmt_dd_mm_yyyy = tomorrow.strftime("%d/%m/%Y") 
    fmt_yyyy_mm_dd = tomorrow.strftime("%Y-%m-%d") 
    
    try:
        match = df_h[
            (df_h['Date'].astype(str).str.strip().isin([fmt_dd_mm_yyyy, fmt_yyyy_mm_dd])) & 
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

    # --- STEP 1: OPERATIONAL BASICS ---
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
        
        is_holiday = is_holiday_tomorrow(st.session_state['center'])
        server_shutdown = False
        if is_holiday:
            tmrw_date = date.today() + timedelta(days=1)
            st.warning(f"⚠️ Tomorrow ({tmrw_date}) is a detected Holiday. Please shut down servers.")
            server_shutdown = st.checkbox("✅ Server Shutdown Completed?")
        
        if st.button("Next ➡️"):
            server_val = "YES" if server_shutdown else "NO"
            if not is_holiday:
                server_val = "N/A"

            st.session_state['daily_data'].update({
                'offline_backup': "YES" if offline_backup else "NO",
                'server_shutdown': server_val
            })
            st.session_state['daily_step'] = 2
            st.rerun()

    # --- STEP 2: FINANCIALS ---
    elif st.session_state['daily_step'] == 2:
        st.subheader("Step 2: Financials")
        
        c1, c2 = st.columns(2)
        with c1:
            cash_dep = st.number_input("Cash Deposit Amount (₹)", min_value=0.0)
            cash_rec = st.number_input("Cash Received Amount (₹)", min_value=0.0)
        with c2:
            upi_amt = st.number_input("UPI Amount (₹)", min_value=0.0)
            card_amt = st.number_input("Card Amount (₹)", min_value=0.0)

        c_back, c_next = st.columns([1,1])
        if c_back.button("⬅️ Back"):
            st.session_state['daily_step'] = 1
            st.rerun()
        if c_next.button("Next ➡️"):
            st.session_state['daily_data'].update({
                'cash_deposit': cash_dep,
                'cash_received': cash_rec,
                'upi_amount': upi_amt,
                'card_amount': card_amt
            })
            st.session_state['daily_step'] = 3
            st.rerun()

    # --- STEP 3: BILLING & CALL METRICS ---
    elif st.session_state['daily_step'] == 3:
        st.subheader("Step 3: Billing & Call Metrics")
        
        st.markdown("**Billing Counters (Nos)**")
        c1, c2, c3, c4 = st.columns(4)
        rec_bill = c1.number_input("Reception", min_value=0)
        phar_bill = c2.number_input("Pharmacy", min_value=0)
        lab_bill = c3.number_input("Lab", min_value=0)
        phys_bill = c4.number_input("Physiotherapy", min_value=0)
        
        st.markdown("---")
        st.markdown("**Patient Management (Nos)**")
        
        col_a, col_b = st.columns(2)
        with col_a:
            rebook = st.number_input("Rebooking Nos", min_value=0)
            tele_fol = st.number_input("Tele Follow-up Nos", min_value=0)
            conf_call = st.number_input("Confirmation Calling Nos", min_value=0)
        
        with col_b:
            def_pat = st.number_input("Default Patients Follow-up", min_value=0)
            can_pat = st.number_input("Cancelled Patients Follow-up", min_value=0)

        c_back, c_next = st.columns([1,1])
        if c_back.button("⬅️ Back"):
            st.session_state['daily_step'] = 2
            st.rerun()
        if c_next.button("Next ➡️"):
            st.session_state['daily_data'].update({
                'bill_recep': rec_bill, 'bill_phar': phar_bill,
                'bill_lab': lab_bill, 'bill_phys': phys_bill,
                'cnt_rebook': rebook, 'cnt_tele': tele_fol,
                'cnt_conf': conf_call, 'cnt_def': def_pat,
                'cnt_can': can_pat
            })
            st.session_state['daily_step'] = 4
            st.rerun()

    # --- STEP 4: FOOTFALL & NOTES ---
    elif st.session_state['daily_step'] == 4:
        st.subheader("Step 4: Footfall & Final Notes")
        
        c1, c2, c3 = st.columns(3)
        tot_pat = c1.number_input("Total Patient Encounters", min_value=0)
        new_pat = c2.number_input("New Patients", min_value=0)
        walk_pat = c3.number_input("Walk-in Patients", min_value=0)
        
        reviews = st.number_input("Google Reviews Count", min_value=0)
        notes = st.text_area("Daily Notes / Handover Issues")
        
        st.info("Please review your data before submitting.")
        
        c_back, c_submit = st.columns([1,1])
        if c_back.button("⬅️ Back"):
            st.session_state['daily_step'] = 3
            st.rerun()
            
        if c_submit.button("✅ Submit Daily Log", type="primary"):
            def _submit():
                client = get_google_sheet_client()
                sheet = client.open_by_url(SHEET_URL)
                ws = get_or_create_worksheet(sheet, "Daily_Logs", cols=25)
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                d = st.session_state['daily_data']
                
                # --- FINAL COLUMN MAPPING (23 Columns) ---
                row_data = [
                    ts,                                         # 1. Timestamp
                    st.session_state['username'],               # 2. Username
                    st.session_state['center'],                 # 3. Center
                    d.get('offline_backup', 'NO'),              # 4. Backup
                    d.get('server_shutdown', 'N/A'),            # 5. Server
                    
                    d.get('cash_deposit', 0.0),                 # 6. Cash Deposit
                    d.get('cash_received', 0.0),                # 7. Cash Received
                    d.get('upi_amount', 0.0),                   # 8. UPI
                    d.get('card_amount', 0.0),                  # 9. Card
                    
                    d.get('bill_recep', 0),                     # 10. Recep Bill
                    d.get('bill_phar', 0),                      # 11. Pharm Bill
                    d.get('bill_lab', 0),                       # 12. Lab Bill
                    d.get('bill_phys', 0),                      # 13. Physio Bill
                    
                    d.get('cnt_rebook', 0),                     # 14. Rebooking
                    d.get('cnt_tele', 0),                       # 15. Tele Followup
                    d.get('cnt_conf', 0),                       # 16. Confirmation
                    d.get('cnt_def', 0),                        # 17. Default
                    d.get('cnt_can', 0),                        # 18. Cancelled
                    
                    tot_pat,                                    # 19. Total Patients
                    new_pat,                                    # 20. New Patients
                    walk_pat,                                   # 21. Walk-in
                    reviews,                                    # 22. Reviews
                    notes                                       # 23. Notes
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
                # Show "Not Set" in grey if no number exists
                if number == "Not Set":
                     st.markdown(f"*{number}*")
                else:
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
                # Saving as DD/MM/YYYY to match user preference
                ws.append_row([d.strftime("%d/%m/%Y"), n, st.session_state['center']])
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
