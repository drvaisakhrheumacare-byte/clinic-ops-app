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
                # Ensure all data is read as string to avoid type confusion
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
    
    # 1. Safety Check: If sheet is empty or headers missing, return False
    if df_h is None or df_h.empty:
        return False
    if 'Date' not in df_h.columns or 'Center' not in df_h.columns:
        return False
        
    # 2. Calculate Tomorrow's Date
    tomorrow = date.today() + timedelta(days=1)
    
    # 3. Generate Format Strings to Match Sheet
    fmt_dd_mm_yyyy = tomorrow.strftime("%d/%m/%Y") # 13/12/2025
    fmt_yyyy_mm_dd = tomorrow.strftime("%Y-%m-%d") # 2025-12-13
    
    # 4. Check against both formats
    try:
        # Convert column to string, strip spaces, and check if it matches either format
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
        
        # Holiday check
        is_holiday = is_holiday_tomorrow(st.session_state['center'])
        
        server_shutdown = False
        if is_holiday:
            st.warning(f"⚠️ Tomorrow ({date.today() +
