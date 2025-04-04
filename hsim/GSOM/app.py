import streamlit as st
import pandas as pd
import hashlib
from st_aggrid import AgGrid, GridOptionsBuilder

# Temporary in-memory database for user credentials
user_database = {
    "admin": {"password": hashlib.sha256("lorenzo123".encode()).hexdigest(), "email": "lorenzo@example.com"},  # Default admin user
    "": {"password": hashlib.sha256("".encode()).hexdigest(), "email": "lorenzo@example.com"}  # Default admin user
}
reset_requests = {}  # Temporary in-memory storage for password reset requests

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def run_simulation(data):
    st.write("Running simulation on the uploaded data...")
    st.write(data.describe())

def load_default_table():
    try:
        return pd.read_excel("c:/Users/Lorenzo/GitHub/hsim/hsim/GSOM/GSOM_original.xlsx", sheet_name=None)  # Load all sheets as a dictionary
    except Exception as e:
        st.error(f"Error loading default table: {e}")
        return {}

def main():
    st.title("Streamlit App with Authentication")

    # Initialize session state variables
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.mode = "Login"  # Modes: "Login", "Register", "Forgot Password", "Main"
    if "saved_files" not in st.session_state:
        st.session_state.saved_files = {}
    if "editable_table" not in st.session_state:
        st.session_state.editable_table = load_default_table()  # Ensure default table is loaded

    # Authentication logic
    if not st.session_state.logged_in:
        if st.session_state.mode == "Login":
            st.sidebar.subheader("Login")  # Moved to sidebar
            username = st.sidebar.text_input("Username", key="login_username")  # Moved to sidebar
            password = st.sidebar.text_input("Password", type="password", key="login_password")  # Moved to sidebar
            if st.sidebar.button("Login"):  # Moved to sidebar
                if username in user_database and user_database[username]["password"] == hash_password(password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.sidebar.success(f"Welcome, {username}!")  # Updated to sidebar
                    st.sidebar.empty()  # Close the sidebar after login
                    st.rerun()
                else:
                    st.sidebar.error("Invalid username or password.")  # Updated to sidebar
            if st.sidebar.button("Register"):  # Moved to sidebar
                st.session_state.mode = "Register"  # Explicitly set mode
                st.rerun()  # Force rerun to reflect mode change
            if st.sidebar.button("Forgot Password"):  # Moved to sidebar
                st.session_state.mode = "Forgot Password"
                st.rerun()  # Force rerun to reflect mode change

        elif st.session_state.mode == "Register":
            st.sidebar.subheader("Register")  # Moved to sidebar
            reg_username = st.sidebar.text_input("Username", key="reg_username")  # Moved to sidebar
            reg_email = st.sidebar.text_input("Email", key="reg_email")  # Moved to sidebar
            reg_password = st.sidebar.text_input("Password", type="password", key="reg_password")  # Moved to sidebar
            reg_password_confirm = st.sidebar.text_input("Confirm Password", type="password", key="reg_password_confirm")  # Moved to sidebar
            if st.sidebar.button("Submit Registration"):  # Moved to sidebar
                if reg_username and reg_email and reg_password and reg_password_confirm:
                    if reg_password != reg_password_confirm:
                        st.sidebar.error("Passwords do not match.")  # Updated to sidebar
                    elif reg_username in user_database:
                        st.sidebar.warning("Username already exists. Please choose another.")  # Updated to sidebar
                    else:
                        user_database[reg_username] = {"password": hash_password(reg_password), "email": reg_email}
                        st.sidebar.success(f"User '{reg_username}' registered successfully!")  # Updated to sidebar
                        st.session_state.mode = "Login"
                else:
                    st.sidebar.error("Please fill in all fields.")  # Updated to sidebar
            if st.sidebar.button("Back to Login"):  # Moved to sidebar
                st.session_state.mode = "Login"
                st.rerun()  # Force rerun to reflect mode change

        elif st.session_state.mode == "Forgot Password":
            st.sidebar.subheader("Forgot Password")  # Moved to sidebar
            reset_username = st.sidebar.text_input("Username", key="reset_username")  # Moved to sidebar
            reset_email = st.sidebar.text_input("Registered Email", key="reset_email")  # Moved to sidebar
            if st.sidebar.button("Submit Reset"):  # Moved to sidebar
                if reset_username in user_database and user_database[reset_username]["email"] == reset_email:
                    reset_code = "RESET123"  # Dummy reset code
                    reset_requests[reset_username] = reset_code
                    st.sidebar.success(f"Password reset requested. Use code: {reset_code}")  # Updated to sidebar
                    st.session_state.mode = "Login"
                else:
                    st.sidebar.error("Username and email do not match our records.")  # Updated to sidebar
            if st.sidebar.button("Back to Login"):  # Moved to sidebar
                st.session_state.mode = "Login"
                st.rerun()  # Force rerun to reflect mode change

    # Main application logic after successful login
    if st.session_state.logged_in:
        st.sidebar.header(f"Welcome, {st.session_state.username}!")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.mode = "Login"
            st.sidebar.success("Logged out successfully.")
            st.rerun()

        # Tabs for navigation
        tab1, tab2, tab3 = st.tabs(["Simulation", "Saved Files", "Dashboard"])

        with tab1:
            # Simulation section
            if st.session_state.editable_table:
                visible_sheets = {name: data for name, data in st.session_state.editable_table.items() if not name.endswith("_in")}
                sheet_tabs = st.tabs(list(visible_sheets.keys()))
                for sheet_name, tab in zip(visible_sheets.keys(), sheet_tabs):
                    with tab:
                        sheet_data = visible_sheets[sheet_name]
                        sheet_data.columns = sheet_data.columns.map(str)  # Convert column names to strings
                        gb = GridOptionsBuilder.from_dataframe(sheet_data)
                        gb.configure_default_column(editable=True)
                        grid_options = gb.build()
                        grid_response = AgGrid(sheet_data, gridOptions=grid_options, update_mode="value_changed")
                        st.session_state.editable_table[sheet_name] = grid_response["data"]  # Save changes to session state

            # Save workbook button
            workbook_name = st.text_input("Enter a name to save the workbook", key="workbook_name", placeholder="Enter workbook name")
            if st.button("Save Workbook"):
                if workbook_name:
                    if workbook_name in st.session_state.saved_files:
                        st.error(f"A workbook with the name '{workbook_name}' already exists.")
                    else:
                        st.session_state.saved_files[workbook_name] = st.session_state.editable_table.copy()  # Save a copy of the workbook
                        st.success(f"Workbook '{workbook_name}' saved successfully!")
                        st.rerun()  # Refresh the app to reflect changes in the "Saved Files" tab
                else:
                    st.error("Please enter a name for the workbook.")

            # File upload section
            uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx", "xls"])
            if uploaded_file:
                try:
                    st.session_state.editable_table = pd.read_excel(uploaded_file, sheet_name=None)  # Load all sheets
                    st.success("File uploaded successfully!")
                except Exception as e:
                    st.error(f"Error reading the Excel file: {e}")

            # Run simulation button
            if st.button("Run Simulation"):
                for sheet_name, sheet_data in st.session_state.editable_table.items():
                    st.write(f"Running simulation on sheet: {sheet_name}")
                    run_simulation(sheet_data)

        with tab2:
            # Manage previously saved files
            st.subheader("Saved Files")
            if st.session_state.saved_files:
                saved_files = list(st.session_state.saved_files.keys())
                selected_file = st.selectbox("Select a workbook to manage", saved_files)
                if st.button("Load Workbook"):
                    st.session_state.editable_table = st.session_state.saved_files[selected_file].copy()  # Load a copy of the workbook
                    st.success(f"Workbook '{selected_file}' loaded successfully!")
                    st.rerun()  # Trigger rerun after loading
                if st.button("Rename Workbook"):
                    new_name = st.text_input("Enter a new name for the workbook", key="rename_workbook", placeholder="Enter new name")
                    if new_name:
                        if new_name in st.session_state.saved_files:
                            st.error(f"A workbook with the name '{new_name}' already exists.")
                        else:
                            st.session_state.saved_files[new_name] = st.session_state.saved_files.pop(selected_file)
                            st.success(f"Workbook renamed to '{new_name}'.")
                            st.rerun()  # Trigger rerun after renaming
                if st.button("Delete Workbook"):
                    del st.session_state.saved_files[selected_file]
                    st.success(f"Workbook '{selected_file}' deleted.")
                    st.rerun()  # Trigger rerun after deletion
            else:
                st.info("No saved workbooks available.")

        with tab3:
            # Dashboard section
            st.write("This is the dashboard where you can display analytics or other information.")
            # Placeholder for dashboard content
            st.write("Coming soon!")

if __name__ == "__main__":
    main()
