import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
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
    except FileNotFoundError:
        st.error("Error: Could not find secrets. Ensure you have set up the secrets in Streamlit Cloud settings.")
        st.stop()
    except Exception as e:
        st.error(f"An error occurred reading secrets: {e}")
        st.stop()
        
    client = gspread.authorize(creds)
    return client

def check_login(username, password):
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_NAME)
        users_tab = sheet.worksheet("Users")
        users_data = users_tab.get_all_records()
        df_users = pd.DataFrame(users_data)

        user_match = df_users[(df_users['Username'].astype(str).str.strip() == username.strip()) & 
                              (df_users['Password'].astype(str).str.strip() == password.strip())]
        
        if not user_match.empty:
            return True, user_match.iloc[0]['Center_Name']
        else:
            return False, None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return False, None

# --- Main Application Interface ---
def main():
    # Updated Browser Tab Title
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

    # ---------------------------
    # LOGIN SCREEN
    # ---------------------------
    if not st.session_state['logged_in']:
        
        # --- LOGO SECTION ---
        # Using columns to center the logo
        left_co, cent_co, last_co = st.columns([1, 2, 1])
        with cent_co:
            # This requires 'logo.png' to be uploaded to your GitHub repo
            if os.path.exists("logo.png"):
                st.image("logo.png", width=250)
            else:
                st.warning("⚠️ Logo file 'logo.png' not found in repository.")

        # --- UPDATED TITLE ---
        st.title("RheumaCare Clinic Operations Portal")
        st.markdown("### Please log in to start your daily report.")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username_input = st.text_input("Enter Username")
            password_input = st.text_input("Enter Password", type="password")
            st.markdown("") 
            
            if st.button("🔐 LOG IN NOW", type="primary", use_container_width=True):
                if username_input and password_input:
                    with st.spinner("Authenticating..."):
                        is_valid, center_name = check_login(username_input, password_input)
                        if is_valid:
                            st.session_state['logged_in'] = True
                            st.session_state['username'] = username_input
                            st.session_state['center'] = center_name
                            st.rerun() 
                        else:
                            st.error("❌ Incorrect username or password.")
                else:
                     st.warning("Please enter both username and password.")

    # ---------------------------
    # DAILY LOG ENTRY SCREEN
    # ---------------------------
    else:
        # Header showing the new company name
        st.title(f"RheumaCare Daily Log: {st.session_state['center']}")
        st.markdown(f"**Manager:** {st.session_state['username']} | **Date:** {datetime.now().strftime('%d-%m-%Y')}")
        st.markdown("---")

        with st.form("daily_entry_form", clear_on_submit=True):
           
            # POINT 1
            st.markdown("### 1️⃣ Daily Offline DB Backup Completed?")
            p1_backup = st.radio("Select backup status:", ["Yes", "No"], horizontal=True, label_visibility="collapsed", key="p1")
            st.markdown("---")

            # POINT 2
            st.markdown("### 2️⃣ Weekly/Holiday Server Shutdown Protocol Followed?")
            st.info("ℹ️ Note: If today is NOT a defined shutdown day, select 'Yes'.")
            p2_shutdown = st.radio("Select shutdown status:", ["Yes", "No"], horizontal=True, label_visibility="collapsed", key="p2")
            st.markdown("---")

            # POINT 3
            st.markdown("### 3️⃣ Total Patients Encountered Today")
            p3_patients = st.slider("Slide to select count:", min_value=0, max_value=200, value=50, step=1, label_visibility="collapsed", key="p3")
            st.write(f"Selected: **{p3_patients} Patients**")
            st.markdown("---")
            
            # POINT 4
            st.markdown("### 4️⃣ Google Reviews Collected Today")
            review_options = list(range(26))
            p4_reviews = st.selectbox("Select count:", review_options, index=0, label_visibility="collapsed", key="p4")
            st.write(f"Selected: **{p4_reviews} Reviews**")
            st.markdown("---")

            # POINT 5
            st.markdown("### 5️⃣ Daily Operational Notes")
            p5_notes = st.text_area("Enter general observations here (max 250 chars):", height=150, max_chars=250, key="p5")
            st.markdown("---")

            st.markdown("") 

            # SUBMIT BUTTON
            submitted_daily = st.form_submit_button("✅ SUBMIT FINAL DAILY REPORT", type="primary", use_container_width=True)
            
            if submitted_daily:
                with st.spinner("Submitting report..."):
                    try:
                        client = get_google_sheet_client()
                        sheet = client.open(SHEET_NAME)
                        daily_tab = sheet.worksheet("Daily_Logs")
                        
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        row_data = [
                            timestamp,                      # A
                            st.session_state['username'],   # B
                            st.session_state['center'],     # C
                            p1_backup,                      # D
                            p2_shutdown,                    # E
                            p3_patients,                    # F
                            p4_reviews,                     # G
                            p5_notes                        # H
                        ]
                        
                        daily_tab.append_row(row_data)
                        st.balloons() 
                        st.success("🎉 Success! Daily log recorded.")
                        
                    except Exception as e:
                        st.error(f"An unexpected error occurred: {e}")

        st.markdown("---")
        if st.button("⬅️ Log Out"):
            st.session_state['logged_in'] = False
            st.rerun()

if __name__ == '__main__':
    main()
