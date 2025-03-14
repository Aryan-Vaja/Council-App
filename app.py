import streamlit as st
import psycopg2
import bcrypt
import pandas as pd
from datetime import datetime
import os
import streamlit_js_eval as js

# Connect to PostgreSQL Database
def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="council_db",
        user="postgres",  
        password="Sunshine04" 
    )
    return conn

# Define folder to save images
IMAGE_UPLOAD_FOLDER = "uploaded_images"
if not os.path.exists(IMAGE_UPLOAD_FOLDER):
    os.makedirs(IMAGE_UPLOAD_FOLDER)

def submit_issue():
    st.title("📢 Report an Issue")

    issue_type = st.selectbox(
        'Select Issue Type:', 
        ['Pothole', 'Graffiti', 'Streetlight Issue', 'Anti-Social Behaviour', 'Fly-Tipping', 'Blocked Drains', 'Other']
    )

    # Camera input for mobile-friendly image capture
    uploaded_file = st.camera_input("📸 Take a Photo or Upload")

    # Get live GPS location
    location_data = js.get_geolocation()

    latitude, longitude = None, None
    if location_data:
        latitude, longitude = location_data["coords"]["latitude"], location_data["coords"]["longitude"]
        st.success(f"✅ Location detected: {latitude}, {longitude}")
        st.map(pd.DataFrame({"lat": [latitude], "lon": [longitude]}))
    else:
        st.warning("⚠️ Allow location access for automatic detection.")

    # Submit button
    if st.button("✅ Submit Issue", use_container_width=True):
        if uploaded_file and latitude and longitude:
            # Save the image
            file_path = os.path.join(IMAGE_UPLOAD_FOLDER, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Save issue details to database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO issues (issue_type, description, latitude, longitude, status, image_path) VALUES (%s, %s, %s, %s, %s, %s)', 
                (issue_type, "No description provided (image included)", latitude, longitude, 'Pending', file_path)
            )
            conn.commit()
            conn.close()
            st.success("✅ Issue submitted successfully!")
        else:
            st.error("❌ Please allow location access and upload an image.")

# Hash password
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

# Check password
def check_password(stored_hash, password):
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

# Staff login
def staff_login():
    st.title("🔑 Staff Login")
    
    username = st.text_input("👤 Username")
    password = st.text_input("🔒 Password", type='password')

    if st.button("Login", use_container_width=True):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM staff_members WHERE username = %s', (username,))
        staff_member = cursor.fetchone()
        conn.close()

        if staff_member and check_password(staff_member[2], password):  
            st.session_state.logged_in = True
            st.session_state.staff_id = staff_member[0]
            st.session_state.username = username
            st.success(f"✅ Welcome {username}")
            st.rerun()  
        else:
            st.error("❌ Invalid username or password")

# Manage issues (Staff)
def manage_issues():
    st.title("⚙️ Manage Issues")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT issue_id, issue_type, latitude, longitude, status, image_path FROM issues WHERE status != %s', ('Resolved',))
    issues = cursor.fetchall()
    conn.close()

    if issues:
        for issue in issues:
            st.subheader(f"Issue ID: {issue[0]}")
            st.text(f"📌 Issue Type: {issue[1]}")
            st.text(f"📍 Status: {issue[4]}")

            # Show image
            if issue[5]:  
                st.image(issue[5], caption="Uploaded Image", use_column_width=True)

            # Show map
            if issue[2] and issue[3]:  
                st.map(pd.DataFrame({"lat": [issue[2]], "lon": [issue[3]]}))

            # Assign an engineer
            engineer_name = st.text_input(f"👷 Assign Engineer (ID: {issue[0]})", key=f"engineer_{issue[0]}")
            if st.button(f"✔ Assign Engineer", key=f"assign_{issue[0]}", use_container_width=True):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE issues SET assigned_engineer = %s WHERE issue_id = %s', 
                               (engineer_name, issue[0]))
                conn.commit()
                conn.close()
                st.success(f"✅ Issue ID {issue[0]} assigned to {engineer_name}.")

            # Close issue
            if issue[4] != "Resolved":
                if st.button(f"✔ Close Issue", key=f"close_{issue[0]}", use_container_width=True):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE issues SET status = %s, resolved_at = %s WHERE issue_id = %s', 
                                   ('Resolved', datetime.now(), issue[0]))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Issue ID {issue[0]} closed successfully!")
    else:
        st.text("No issues to manage.")

# Analytics
def analytics():
    st.title("📊 Analytics")

    conn = get_db_connection()

    # Count issues per type
    query = '''
    SELECT issue_type, COUNT(*) as count
    FROM issues
    GROUP BY issue_type
    '''
    df = pd.read_sql(query, conn)

    if not df.empty:
        st.write("📊 Issues by Type")
        st.bar_chart(df.set_index('issue_type')['count'])

    # Average resolution time
    query = '''
    SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 86400) as avg_resolution_time
    FROM issues
    WHERE status = 'Resolved' AND resolved_at IS NOT NULL
    '''
    avg_time = pd.read_sql(query, conn)
    conn.close()

    if not avg_time.empty and avg_time['avg_resolution_time'][0] is not None:
        st.write(f"⏳ Average Resolution Time: {avg_time['avg_resolution_time'][0]:.2f} days")
    else:
        st.write("No resolved issues to calculate average resolution time.")

# Main App Logic
def main():
    st.set_page_config(page_title="📍 Issue Reporter", layout="centered")

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        choice = st.selectbox("🔍 Choose Action", ["Report an Issue", "Staff Login"])
        if choice == "Report an Issue":
            submit_issue()
        elif choice == "Staff Login":
            staff_login()
    else:
        choice = st.selectbox("🔧 Staff Actions", ["Manage Issues", "Analytics", "Logout"])
        if choice == "Manage Issues":
            manage_issues()
        elif choice == "Analytics":
            analytics()
        elif choice == "Logout":
            st.session_state.logged_in = False
            st.success("✅ Logged out successfully.")

# Run the Streamlit App
if __name__ == '__main__':
    main()
