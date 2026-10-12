from datetime import date, datetime
import hashlib
import mysql.connector
import pandas as pd
import streamlit as st
import base64
import certifi
import razorpay


# Page Config
st.set_page_config(
    page_title="Youva Pahal - Free Coaching & E-Learning Centre", page_icon="🎓", layout="wide"
)

MY_NAME = "DILEEP KUMAR RATHAUR"

# ============== RAZORPAY CONFIGURATION ====================
RAZORPAY_KEY_ID = "YOUR_RAZORPAY_KEY_ID"
RAZORPAY_KEY_SECRET = "YOUR_RAZORPAY_SECRET"
# ===============================================================




# --- CUSTOM CSS to more effective UI ---
st.markdown("""
    <style>
    .logo {
        width: 150px;
        height: 150px;
        border-radius: 50%;
        border: 4px solid #1f77b4;
       
    }
    .main-header {
        font-size: 2.2rem;
        color: #1f77b4;
        font-weight: 700;
    }
    .card {
        background-color: #2d3748;
        color: #ffffff;
        padding: 22px;
        border-radius: 12px;
        border: 1px solid #4a5568;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
        height: 400px;
    }
    .card h4, .card p {
        color: #ffffff !important;
    }
    .notes_card {
            background-color: #2d3748;
            color: white;
            padding: 22px;
            border-radius: 12px;
            border: 1px solid #4a5568;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
            height: 250px;
        }

    .badge-free {
        background-color: #d1fae5;
        color: #065f46;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-paid {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    </style>
""", unsafe_allow_html=True)


# --- TIDB CLOUD DATABASE CONNECTION SETUP ---
def get_db_connection():
    db_config = st.secrets["tidb"]
    return mysql.connector.connect(
        host=db_config["host"],
        port=int(db_config["port"]),
        user=db_config["user"],
        password=db_config["password"],
        database=db_config["database"],
        ssl_ca=certifi.where(),
        ssl_verify_cert=True
    )


def init_db():
  try:
    conn = get_db_connection()
    cursor = conn.cursor()
  except Exception as e:
    st.error(f"TiDB Cloud Connection Error: {e}")
    return

  # 1. Users Table
  cursor.execute("""
      CREATE TABLE IF NOT EXISTS users (
          id INT AUTO_INCREMENT PRIMARY KEY,
          username VARCHAR(255) UNIQUE NOT NULL,
          password VARCHAR(255) NOT NULL,
          role VARCHAR(50) NOT NULL,
          name VARCHAR(255),
          is_admin BOOLEAN DEFAULT FALSE
      )
  """)
  
  #  Create default admin if not exists
  admin_config=st.secrets["admin"]
  cursor.execute(f"SELECT COUNT(*) FROM users WHERE username = '{admin_config['ADMIN_USERNAME']}'")
  
  if cursor.fetchone()[0] == 0:  # yah fetch kiye gaye result se pahle record(row or tuple) ke 0th index ke element ko return karega
    hashed_admin_pw = hashlib.sha256(admin_config["ADMIN_PASSWORD"].encode()).hexdigest()   # hashlib is builtin python library that uses sha256 algorithm to encript the password, encode string ko byte me convert kr deta hai , hexadecimal encripted bytes ko readable hexadecimal string me badal deta hai.
    cursor.execute("""
            INSERT INTO users (username, password, role, name, is_admin) 
            VALUES (%s, %s, 'Admin', 'Administrator', TRUE)
        """, (admin_config['ADMIN_USERNAME'], hashed_admin_pw))

  
  # 2. Batches Table (For Free Coaching Classes)
  cursor.execute("""
      CREATE TABLE IF NOT EXISTS batches (
          id INT AUTO_INCREMENT PRIMARY KEY,
          title VARCHAR(255) NOT NULL,
          description TEXT,
          batch_time VARCHAR(255),
          fees VARCHAR(50) DEFAULT 'Free',
          video_link TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
  """)

  # 3. Notes Table (For Digital Library / Study Notes PDF Store)
  cursor.execute("""
      CREATE TABLE IF NOT EXISTS notes (
          id INT AUTO_INCREMENT PRIMARY KEY,
          title VARCHAR(255) NOT NULL,
          description TEXT,
          price DECIMAL(10,2) DEFAULT 0.00,
          file_content LONGBLOB,
          file_name VARCHAR(255),
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
  """)

  # 4. Enrollments Table (PURCHASES and sales)
  cursor.execute("""
      CREATE TABLE IF NOT EXISTS enrollments (
          id INT AUTO_INCREMENT PRIMARY KEY,
          student_name VARCHAR(255),
          email VARCHAR(255),
          batch_name VARCHAR(255),
          purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
  """)

  # 5. Students Record Table
  cursor.execute("""
      CREATE TABLE IF NOT EXISTS students (
          roll_no VARCHAR(50) PRIMARY KEY,
          name VARCHAR(255) NOT NULL,
          fathers_name VARCHAR(255) NOT NULL,
          dob VARCHAR(50) NOT NULL,
          email VARCHAR(255) NOT NULL,
          gender VARCHAR(50) NOT NULL,
          class VARCHAR(50) NOT NULL,
          section VARCHAR(50) NOT NULL,
          contact VARCHAR(50) NOT NULL,
          address TEXT
      )
  """)

  # 6. Paid Purchases Table for Notes
  cursor.execute("""
      CREATE TABLE IF NOT EXISTS purchases (
          id INT AUTO_INCREMENT PRIMARY KEY,
          user_id INT,
          note_id INT,
          purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (user_id) REFERENCES users(id),
          FOREIGN KEY (note_id) REFERENCES notes(id)
      )
  """)

  # 7. Public Posts 
  cursor.execute("""
      CREATE TABLE IF NOT EXISTS public_posts (
          id INT AUTO_INCREMENT PRIMARY KEY,
          title VARCHAR(255),
          content TEXT,
          category VARCHAR(100),
          status VARCHAR(50),
          image LONGBLOB,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
  """)

  # 8. Attendance Table
  cursor.execute("""
      CREATE TABLE IF NOT EXISTS attendance (
          id INT AUTO_INCREMENT PRIMARY KEY,
          roll_no VARCHAR(50),
          student_name VARCHAR(255),
          class VARCHAR(50),
          date VARCHAR(50),
          status VARCHAR(50)
      )
  """)

  # Default batches if empty
  cursor.execute("SELECT COUNT(*) FROM batches")
  if cursor.fetchone()[0] == 0:
    cursor.executemany(
        "INSERT INTO batches (title, description, batch_time, fees) VALUES (%s, %s, %s, %s)",
        [
            ("Basic Mathematics (Nursery - 4th)", "Fundamental mathematical concepts for young students completely free of cost.", "Morning (8:00 AM - 9:00 AM)", "Free"),
            ("Junior English & Grammar (5th - 8th)", "Building strong English communication and grammar foundations.", "Evening (4:00 PM - 5:00 PM)", "Free"),
            ("General Science Basics", "Interactive science learning sessions for underprivileged children.", "Weekend (10:00 AM - 11:30 AM)", "Free"),
        ],
    )

  conn.commit()
  cursor.close()
  conn.close()



if "db_initialized" not in st.session_state:
  init_db()
  st.session_state.db_initialized = True

# --- CACHED DATA FETCH FUNCTIONS ---
@st.cache_data(ttl=60)
def fetch_all_batches():
  conn = get_db_connection()
  cursor = conn.cursor(dictionary=True)
  cursor.execute("SELECT * FROM batches")
  result = cursor.fetchall()
  cursor.close()
  conn.close()
  return pd.DataFrame(result)

@st.cache_data(ttl=60)
def fetch_all_notes():
  conn = get_db_connection()
  cursor = conn.cursor(dictionary=True)
  cursor.execute("SELECT * FROM notes")
  result = cursor.fetchall()
  cursor.close()
  conn.close()
  return pd.DataFrame(result)

@st.cache_data(ttl=60)
def fetch_all_students():
  conn = get_db_connection()
  cursor = conn.cursor(dictionary=True)
  cursor.execute("SELECT * FROM students")
  result = cursor.fetchall()
  cursor.close()
  conn.close()
  return pd.DataFrame(result)



# Session States settings
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
if "user_id" not in st.session_state:
  st.session_state.user_id = None
if "username" not in st.session_state:
  st.session_state.username = ""
if "role" not in st.session_state:
  st.session_state.role = ""
if "is_admin" not in st.session_state:
  st.session_state.is_admin = False
if "page" not in st.session_state:
  st.session_state.page = "Home"


# --- SIDEBAR NAVIGATION & AUTH ---
st.sidebar.title("🧭 Navigation")

if st.sidebar.button("🏠 Home & E-Learning Store"):
  st.session_state.page = "Home"
  st.rerun()

if st.session_state.logged_in:
  st.sidebar.success(f"Logged in: {st.session_state.username}")
  if st.session_state.is_admin:
    if st.sidebar.button("🛠️ Admin Dashboard"):
      st.session_state.page = "Admin"
      st.rerun()
  if st.sidebar.button("📂 My Purchased Library & History"):
    st.session_state.page = "Library"
    st.rerun()
  if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.is_admin = False
    st.session_state.page = "Home"
    st.rerun()
else:
  st.sidebar.info("Browsing as Guest")
  if st.sidebar.button("🔑 User Login / Register"):
    st.session_state.page = "Auth"
    st.rerun()
  if st.sidebar.button("🔒 Admin Portal Login"):
    st.session_state.page = "Admin_Login"
    st.rerun()

st.sidebar.markdown("---")

# ==========================================
# 1. HOME & E-LEARNING STOREFRONT
# ==========================================
def show_home():
  st.markdown('<img src="https://img.freepik.com/premium-vector/coaching-center-logo_1169041-70.jpg?w=2000" class="logo">', unsafe_allow_html=True)
  st.markdown('<p class="main-header">🌟 Youva Pahal - Free Coaching Institute & Notes Portal</p>', unsafe_allow_html=True)
  st.markdown("### *Empowering Underprivileged Children Through Free Education Up to Class 8th*")

  st.image(
      "https://images.unsplash.com/photo-1523240795612-9a054b0db644?q=80&w=1200&auto=format&fit=crop",
      caption="Education is a right, not a privilege",
      use_container_width=True,
  )

  # Coaching Address Section
  st.markdown("---")
  st.markdown("## 📍 Coaching Institute Address & Location")
  st.markdown("""
        <div style="padding: 15px; border-radius: 10px; background-color: #f8f9fa; border-left: 5px solid #1f77b4; border: 1px solid #e0e0e0;">
            <p style="margin: 0; font-size: 16px; color: #333333;">
                <b>Village Bari, Post Shahajana</b><br>
                Pihani, Hardoi, Uttar Pradesh – <b>241407</b>
            </p>
        </div>
    """, unsafe_allow_html=True)


  # About insitute Section
  st.markdown("---")  # to draw a horizontal line separator
  st.markdown("## 📖 About Our Free Coaching Institute")   # equals to h2 heading
  st.markdown("""
    Our coaching institute is dedicated to providing **100% free education** to children from underprivileged and needy families who are unable to afford quality learning due to financial constraints. 
    This noble initiative is founded and managed by **Ramesh Singh** with the mission to build a brighter future, instil confidence, and provide strong foundational learning for every child.
    
    * **Target Group:** Students from Nursery up to **Class 8th**
    * **Founder & Director:** Ramesh Singh
    * **Fee Structure:** Completely Free (No charges)
    * **Mission:** Ensuring that no child is left behind due to a lack of resources.
    """)  # '''...''' for string, and **..** for bold text, *..* for italic text, * for bulet points

  
  # Active Public Posts & Announcements
  conn = get_db_connection()
  cursor = conn.cursor(dictionary=True)
  cursor.execute("SELECT title, content, category, image FROM public_posts WHERE status = 'Active'")
  active_posts = cursor.fetchall()
  cursor.close()
  conn.close()

  if active_posts:
    st.markdown("---")
    st.header("📢 Latest Announcements & Active Batches")
    for post in active_posts:
      title, content, category, img_blob = post["title"], post["content"], post["category"], post["image"]
      with st.container():
        cols_p = st.columns([2, 1] if img_blob else [1])
        with cols_p[0]:
          st.markdown(f"### 📌 [{category}] {title}")
          st.write(content)
        if img_blob and len(cols_p) > 1:
          with cols_p[1]:
            st.image(img_blob, caption=title, use_container_width=True)
        st.markdown("---")

 
  # SECTION 1: COACHING BATCHES
  st.header("🎓 Free Coaching Batches")
  batches_df = fetch_all_batches()

  enrolled_batch_names = []
  if st.session_state.logged_in and st.session_state.username:
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT batch_name FROM enrollments WHERE email = %s", (st.session_state.username,))
    enrolled_batch_names = [row['batch_name'] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

  if not batches_df.empty:
    cols = st.columns(3)
    for index, row in batches_df.iterrows():
      b_id = row["id"]
      b_name = row["title"]
      b_time = row["batch_time"] if row["batch_time"] else "Flexible"
      b_fees = row["fees"] if row["fees"] else "Free"
      b_desc = row["description"]

      with cols[index % 3]:
        st.markdown(f"""
            <div class="card">
                <h4>{b_name}</h4>
                <p><b>🕒 Timing:</b> {b_time}</p>
                <p><span class="badge-free">💰 {b_fees}</span></p>
                <p style="color: #555;"><i>{b_desc}</i></p>
            </div>
        """, unsafe_allow_html=True)

        if row.get("video_link"):
          st.markdown(f"[🎥 Watch Class Preview]({row['video_link']})")

        if b_name in enrolled_batch_names:
          st.success("✅ Enrolled in Batch")
        else:
          if st.button("Enroll Free", key=f"free_enroll_batch_{b_id}"):
            if not st.session_state.logged_in:
              st.warning("Please login first to enroll!")
              st.session_state.page = "Auth"
              st.rerun()
            else:
              conn = get_db_connection()
              cursor = conn.cursor()
              try:
                cursor.execute(
                    "INSERT INTO enrollments (student_name, email, batch_name) VALUES (%s, %s, %s)",
                    (st.session_state.username, st.session_state.username, b_name),
                )
                conn.commit()
                st.success("Successfully Enrolled!")
                st.rerun()
              except Exception:
                st.info("Already enrolled in this batch.")
              finally:
                cursor.close()
                conn.close()


  # SECTION 2: STUDY NOTES STORE
  st.markdown("---")
  st.header("📚 Premium & Free Study Notes Library")
  notes_df = fetch_all_notes()

  purchased_note_ids = []
  if st.session_state.logged_in and st.session_state.user_id:
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT note_id FROM purchases WHERE user_id = %s", (st.session_state.user_id,))
    purchased_note_ids = [row['note_id'] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

  if not notes_df.empty:
    cols_n = st.columns(3)
    for index, row in notes_df.iterrows():
      n_id = row["id"]
      n_title = row["title"]
      n_desc = row["description"]
      n_price = float(row["price"]) if row["price"] else 0.00
      price_badge = f'<span class="badge-free">Free</span>' if n_price == 0 else f'<span class="badge-paid">₹{n_price}</span>'

      with cols_n[index % 3]:
        st.markdown(f"""
            <div class="notes_card">
                <h4>{n_title}</h4>
                <p>{price_badge}</p>
                <p style="color: #555;"><i>{n_desc}</i></p>
            </div>
        """, unsafe_allow_html=True)

        if n_id in purchased_note_ids or n_price == 0.00:
          st.success("✅ Unlocked")
          conn = get_db_connection()
          cursor = conn.cursor(dictionary=True)
          cursor.execute("SELECT file_content, file_name FROM notes WHERE id = %s", (n_id,))
          res = cursor.fetchone()
          cursor.close()
          conn.close()
          if res and res['file_content']:
            st.download_button(
                label="📥 Download PDF Notes",
                data=res['file_content'],
                file_name=res['file_name'] if res['file_name'] else "notes.pdf",
                mime="application/pdf",
                key=f"store_dl_note_{n_id}"
            )
          elif n_price == 0.00 and n_id not in purchased_note_ids:
            if st.button("Access Free Notes", key=f"unlock_free_note_{n_id}"):
              if not st.session_state.logged_in:
                st.warning("Please login first!")
                st.session_state.page = "Auth"
                st.rerun()
              else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO purchases (user_id, note_id) VALUES (%s, %s)", (st.session_state.user_id, n_id))
                conn.commit()
                cursor.close()
                conn.close()
                st.success("Unlocked successfully!")
                st.rerun()
        else:
          if not st.session_state.logged_in:
            if st.button(f"Pay ₹{n_price} to Unlock", key=f"pay_note_unlogged_{n_id}"):
              st.warning("Please login first!")
              st.session_state.page = "Auth"
              st.rerun()
          else:
            try:
              client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
              amount_paise = int(n_price * 100)
              order = client.order.create({"amount": amount_paise, "currency": "INR", "payment_capture": 1})
              order_id = order['id']
            except Exception:
              order_id = None

            if order_id:
              razorpay_html = f"""
              <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
              <button id="rzp-button-{n_id}" style="background-color:#4f46e5;color:white;padding:10px 20px;border:none;border-radius:5px;font-weight:bold;cursor:pointer;width:100%;">Pay ₹{n_price} Now</button>
              <script>
              var options = {{
                  "key": "{RAZORPAY_KEY_ID}",
                  "amount": "{amount_paise}",
                  "currency": "INR",
                  "name": "{MY_NAME}",
                  "description": "{n_title}",
                  "order_id": "{order_id}",
                  "handler": function (response){{
                      alert('Payment Successful! Payment ID: ' + response.razorpay_payment_id);
                      window.location.reload();
                  }},
                  "theme": {{ "color": "#4f46e5" }}
              }};
              var rzp1 = new Razorpay(options);
              document.getElementById('rzp-button-{n_id}').onclick = function(e){{
                  rzp1.open();
                  e.preventDefault();
              }}
              </script>
              """
              st.components.v1.html(razorpay_html, height=60)

            if st.button(f"🔄 Verify Payment / Unlock Notes", key=f"verify_pay_note_{n_id}"):
              with st.spinner("Verifying purchase..."):
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                  cursor.execute("INSERT INTO purchases (user_id, note_id) VALUES (%s, %s)", (st.session_state.user_id, n_id))
                  conn.commit()
                  st.success("Payment verified! Notes unlocked successfully.")
                  st.rerun()
                except Exception:
                  st.info("Already unlocked.")
                finally:
                  cursor.close()
                  conn.close()



  # ==========================================
  # PROFESSIONAL CIRCULAR FOOTER (STRICTLY FOR PUBLIC PAGE ONLY)
  # ==========================================
  st.markdown("<br><br>", unsafe_allow_html=True)
  st.markdown("---")

  def get_img_b64(path):
    try:
      with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()
    except Exception:
      return ""

  img_data = get_img_b64("image_bdace0.png")

  st.markdown(f"""
      <div style="display: flex; align-items: center; justify-content: center; gap: 20px; padding: 15px; background: rgba(255, 255, 255, 0.03); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1); flex-wrap: wrap;">
          <div>
              <img src="data:image/png;base64,{img_data}" style="width: 95px; height: 95px; border-radius: 50%; object-fit: cover; border: 3px solid #1f77b4; box-shadow: 0px 4px 10px rgba(0,0,0,0.4);">
          </div>
          <div>
              <p style="margin: 0 0 6px 0; font-size: 17px; font-weight: bold; color: #ffffff;">
                  Website Developed by: Dileep Kumar Rathaur
              </p>
              <p style="margin: 0; font-size: 14px; color: #cccccc; line-height: 1.8;">
                  📞 <b>Mobile:</b> 8874549203 &nbsp;|&nbsp; 
                  📸 <b>Instagram:</b> <a href="https://instagram.com/royal_dk700" target="_blank" style="color: #4dabf7; text-decoration: none;">@royal_dk700</a><br>
                  🐙 <b>GitHub:</b> <a href="https://github.com/" target="_blank" style="color: #4dabf7; text-decoration: none;">GitHub</a> &nbsp;|&nbsp; 
                  💼 <b>LinkedIn:</b> <a href="https://linkedin.com/" target="_blank" style="color: #4dabf7; text-decoration: none;">LinkedIn</a>
              </p>
          </div>
      </div>
      <p style='text-align: center; font-size: 13px; color: #888888; margin-top: 15px;'>
          © 2026 Youva Pahal Free Coaching Centre | All Rights Reserved.
      </p>
  """, unsafe_allow_html=True)




# ==========================================
# 2. USER AUTHENTICATION
# ==========================================
def auth_page():
  st.title("🔐 Login or Register Account")
  tab1, tab2 = st.tabs(["Login", "Register"])

  with tab1:
    st.subheader("Login to your account")
    username = st.text_input("Username / Email", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    
    if st.button("Login", key="login_btn"):
      with st.spinner("Authenticating..."):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, hashed_pw))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
          st.session_state.logged_in = True
          st.session_state.user_id = user['id']
          st.session_state.username = user['username']
          st.session_state.role = user['role']
          st.session_state.is_admin = bool(user['is_admin'])
          st.success("Login Successful!")
          st.session_state.page = "Home"
          st.rerun()
        else:
          st.error("Invalid Username or Password")

  with tab2:
    st.subheader("Create a new account")
    r_name = st.text_input("Full Name", key="reg_name")
    new_user = st.text_input("Choose Username / Email", key="reg_user")
    new_pass = st.text_input("Choose Password", type="password", key="reg_pass")
    
    if st.button("Register & Login Instantly", key="reg_btn"):
      if new_user and new_pass:
        with st.spinner("Creating account..."):
          conn = get_db_connection()
          cursor = conn.cursor()
          try:
            hashed_pw = hashlib.sha256(new_pass.encode()).hexdigest()
            cursor.execute("INSERT INTO users (username, password, role, name, is_admin) VALUES (%s, %s, 'Student', %s, FALSE)", 
                           (new_user, hashed_pw, r_name))
            conn.commit()
            
            cursor.execute("SELECT id, username, role, is_admin FROM users WHERE username = %s", (new_user,))
            created_user = cursor.fetchone()
            
            if created_user:
              st.session_state.logged_in = True
              st.session_state.user_id = created_user[0]
              st.session_state.username = created_user[1]
              st.session_state.role = created_user[2]
              st.session_state.is_admin = bool(created_user[3])
              st.success("Registration successful! Automatically logged in.")
              st.session_state.page = "Home"
              st.rerun()
          except mysql.connector.Error:
            st.error("Username already exists.")
          finally:
            cursor.close()
            conn.close()
      else:
        st.warning("Please fill all fields.")

# ==========================================
# 3. ADMIN LOGIN
# ==========================================
def admin_login_page():
  st.title("🔒 Admin Portal Access")
  admin_user = st.text_input("Admin Username", key="adm_u")
  admin_pass = st.text_input("Admin Password", type="password", key="adm_p")
  
  if st.button("Access Admin Panel"):
    with st.spinner("Verifying admin credentials..."):
      conn = get_db_connection()
      cursor = conn.cursor(dictionary=True)
      hashed_pw = hashlib.sha256(admin_pass.encode()).hexdigest()
      cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s AND is_admin = 1", (admin_user, hashed_pw))
      admin = cursor.fetchone()
      cursor.close()
      conn.close()
      
      if admin:
        st.session_state.logged_in = True
        st.session_state.user_id = admin['id']
        st.session_state.username = admin['username']
        st.session_state.role = admin['role']
        st.session_state.is_admin = True
        st.session_state.page = "Admin"
        st.success("Admin access granted!")
        st.rerun()
      else:
        st.error("Invalid Admin credentials!")

# ==========================================
# 4. ADMIN PANEL (Combined Dashboard)
# ==========================================
def admin_panel():
  if not st.session_state.is_admin:
    st.error("Access Denied!")
    return

  st.title("🛠 Admin Dashboard - Institute & E-Learning Management")
  st.info(f"Welcome Admin: **{st.session_state.username}**")

  # Using radio button in sidebar so all options are fully visible and neatly organized without dropdown truncation
  menu = st.sidebar.radio(
      "🛠️ Admin Management Menu",
      [
          "Manage Students Records",
          "Search Students",
          "Manage Batches",
          "Manage Notes & Pricing",
          "View Purchases & Sales",
          "Manage Public Posts",
          "Manage Attendance",
      ],
  )

  if menu == "Manage Students Records":
    st.subheader("📋 Student Records Database")
    df = fetch_all_students()

    selected_roll = ""
    selected_data = None

    if not df.empty:
      df.columns = [
          "Roll No", "Name", "Father's Name", "D.O.B", "Email",
          "Gender", "Class", "Section", "Contact", "Address",
      ]
      event = st.dataframe(df, use_container_width=True, on_select="rerun", selection_mode="single-row")
      if event.selection.rows:
        selected_row = df.iloc[event.selection.rows[0]]
        selected_roll = selected_row["Roll No"]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE roll_no = %s", (selected_roll,))
        selected_data = cursor.fetchone()
        cursor.close()
        conn.close()
    else:
      st.info("No student records found yet.")

    st.markdown("---")
    st.subheader("✏️ Add / Update Student Form" + (f" (Selected: {selected_roll})" if selected_roll else ""))

    def_roll = selected_data[0] if selected_data else ""
    def_name = selected_data[1] if selected_data else ""
    def_fname = selected_data[2] if selected_data else ""
    def_dob = selected_data[3] if selected_data else ""
    def_email = selected_data[4] if selected_data else ""
    def_gender = selected_data[5] if selected_data else "Male"
    def_cls = selected_data[6] if selected_data else ""
    def_sec = selected_data[7] if selected_data else ""
    def_contact = selected_data[8] if selected_data else ""
    def_addr = selected_data[9] if selected_data else ""

    gender_options = ["Male", "Female", "Other"]
    gender_index = gender_options.index(def_gender) if def_gender in gender_options else 0

    with st.form("admin_student_form"):
      c1, c2, c3 = st.columns(3)
      with c1:
        roll = st.text_input("Roll No", value=def_roll)
        name = st.text_input("Name", value=def_name)
        fathers_name = st.text_input("Father's Name", value=def_fname)
      with c2:
        dob = st.text_input("D.O.B (DD/MM/YYYY)", value=def_dob)
        email = st.text_input("Email", value=def_email)
        gender = st.selectbox("Gender", gender_options, index=gender_index)
      with c3:
        cls = st.text_input("Class", value=def_cls)
        section = st.text_input("Section", value=def_sec)
        contact = st.text_input("Contact", value=def_contact)

      address = st.text_area("Address", value=def_addr)

      b1, b2, b3 = st.columns(3)
      with b1:
        add_b = st.form_submit_button("➕ Add Student")
      with b2:
        up_b = st.form_submit_button("🔄 Update Student")
      with b3:
        del_b = st.form_submit_button("🗑️ Delete Student")

      if add_b:
        if roll and name:
          with st.spinner("Adding student..."):
            conn = get_db_connection()
            try:
              cursor = conn.cursor()
              cursor.execute(
                  "INSERT INTO students VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (roll, name, fathers_name, dob, email, gender, cls, section, contact, address),
              )
              default_pass = contact if contact else "123456"
              hashed_pass = hashlib.sha256(default_pass.encode()).hexdigest()
              
              cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s", (email,))
              if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO users (username, password, role, name, is_admin) VALUES (%s, %s, 'Student', %s, FALSE)",
                    (email, hashed_pass, name),
                )
              conn.commit()
              cursor.close()
              conn.close()
              st.cache_data.clear()
              st.success(f"Student added! Login Email: {email}, Password: {default_pass}")
              st.rerun()
            except Exception as err:
              st.error(f"Error: Roll No or Email already exists! ({err})")
        else:
          st.warning("Fill required fields.")

      if up_b:
        if roll:
          with st.spinner("Updating student..."):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE students SET name=%s, fathers_name=%s, dob=%s, email=%s,
                gender=%s, class=%s, section=%s, contact=%s, address=%s WHERE roll_no=%s""",
                (name, fathers_name, dob, email, gender, cls, section, contact, address, roll),
            )
            conn.commit()
            cursor.close()
            conn.close()
            st.cache_data.clear()
            st.success("Updated successfully!")
            st.rerun()

      if del_b:
        if roll:
          with st.spinner("Deleting student..."):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM students WHERE roll_no=%s", (roll,))
            conn.commit()
            cursor.close()
            conn.close()
            st.cache_data.clear()
            st.success("Deleted successfully!")
            st.rerun()

  elif menu == "Search Students":
    st.subheader("🔍 Advanced Student Search Filter")
    search_by = st.selectbox("Search By", ["Roll No", "Name", "Class", "Section"])
    search_query = st.text_input("Search keyword enter karein")

    if st.button("Search"):
      with st.spinner("Searching..."):
        col_map = {"Roll No": "roll_no", "Name": "name", "Class": "class", "Section": "section"}
        db_col = col_map[search_by]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM students WHERE {db_col} LIKE %s", ("%" + search_query + "%",))
        results = cursor.fetchall()
        cursor.close()
        conn.close()

      if results:
        df = pd.DataFrame(results)
        df.columns = ["Roll No", "Name", "Father's Name", "D.O.B", "Email", "Gender", "Class", "Section", "Contact", "Address"]
        st.success(f"Total {len(results)} matching record(s) found:")
        st.dataframe(df, use_container_width=True)
      else:
        st.warning("No matching records found.")

  elif menu == "Manage Batches":
    st.subheader("🎓 Manage Coaching Batches")
    with st.form("batch_add_form"):
      b_title = st.text_input("Batch Title (e.g., Mathematics Class 6th)")
      b_desc = st.text_area("Batch Description")
      b_time = st.text_input("Batch Timing / Schedule (e.g., Morning 8:00 AM)")
      b_fees = st.text_input("Fee Label", value="Free")
      b_video = st.text_input("Intro / Video Preview Link (Optional)")

      if st.form_submit_button("Publish Batch"):
        if b_title:
          with st.spinner("Publishing batch..."):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO batches (title, description, batch_time, fees, video_link)
                VALUES (%s, %s, %s, %s, %s)
            """, (b_title, b_desc, b_time, b_fees, b_video))
            conn.commit()
            cursor.close()
            conn.close()
            st.cache_data.clear()
            st.success("Batch published successfully!")
            st.rerun()
        else:
          st.error("Please provide a batch title.")

    st.markdown("---")
    st.subheader("📋 Existing Batches List")
    batches_df = fetch_all_batches()
    if not batches_df.empty:
      for idx, row in batches_df.iterrows():
        col1, col2 = st.columns([4, 1])
        with col1:
          st.write(f"**{row['title']}** | Timing: *{row['batch_time']}* | Fee: *{row['fees']}*")
        with col2:
          if st.button("🗑️ Delete", key=f"del_batch_{row['id']}"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM batches WHERE id = %s", (row['id'],))
            conn.commit()
            cursor.close()
            conn.close()
            st.cache_data.clear()
            st.success("Deleted!")
            st.rerun()

  elif menu == "Manage Notes & Pricing":
    st.subheader("📚 Upload PDF Study Notes & Manage Pricing")
    with st.form("notes_add_form"):
      n_title = st.text_input("Notes Title")
      n_desc = st.text_area("Description")
      n_price = st.number_input("Price (INR) - 0 for Free", min_value=0.0, format="%.2f")
      n_file = st.file_uploader("Upload PDF File", type=["pdf"])

      if st.form_submit_button("Publish Notes"):
        if n_title and n_file:
          with st.spinner("Uploading notes..."):
            file_bytes = n_file.read()
            file_name = n_file.name

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notes (title, description, price, file_content, file_name)
                VALUES (%s, %s, %s, %s, %s)
            """, (n_title, n_desc, n_price, file_bytes, file_name))
            conn.commit()
            cursor.close()
            conn.close()
            st.cache_data.clear()
            st.success("Notes published successfully!")
            st.rerun()
        else:
          st.error("Please provide a title and upload a PDF file.")

    st.markdown("---")
    st.subheader("💲 Update Existing Notes Pricing")
    notes_df = fetch_all_notes()
    if not notes_df.empty:
      for note in notes_df.to_dict(orient="records"):
        with st.expander(f"{note['title']} (Current Price: ₹{note['price']})"):
          new_price = st.number_input("New Price", value=float(note['price']), key=f"note_price_{note['id']}")
          col_a, col_b = st.columns(2)
          with col_a:
            if st.button("Update Price", key=f"upd_note_{note['id']}"):
              conn = get_db_connection()
              cursor = conn.cursor()
              cursor.execute("UPDATE notes SET price = %s WHERE id = %s", (new_price, note['id']))
              conn.commit()
              cursor.close()
              conn.close()
              st.cache_data.clear()
              st.success("Price updated!")
              st.rerun()
          with col_b:
            if st.button("🗑️ Delete Note", key=f"del_note_{note['id']}"):
              conn = get_db_connection()
              cursor = conn.cursor()
              cursor.execute("DELETE FROM notes WHERE id = %s", (note['id'],))
              conn.commit()
              cursor.close()
              conn.close()
              st.cache_data.clear()
              st.success("Deleted note!")
              st.rerun()

  elif menu == "View Purchases & Sales":
    st.subheader("🛍️ Study Notes Purchases & Sales Report")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.id, u.username, n.title, n.price, p.purchase_date 
        FROM purchases p
        JOIN users u ON p.user_id = u.id
        JOIN notes n ON p.note_id = n.id
        ORDER BY p.purchase_date DESC
    """)
    res_sales = cursor.fetchall()
    cursor.close()
    conn.close()

    if res_sales:
      st.dataframe(pd.DataFrame(res_sales), use_container_width=True)
    else:
      st.info("No paid sales recorded yet.")

  elif menu == "Manage Public Posts":
    st.subheader("📢 Manage Public Posts & Batches (with Image Support)")

    with st.expander("➕ Add New Public Post / Batch with Thumbnail/Image", expanded=True):
      with st.form("add_post_form"):
        p_title = st.text_input("Title")
        p_content = st.text_area("Details / Description")
        p_category = st.selectbox("Category", ["Batch", "Announcement", "Notice"])
        p_status = st.selectbox("Status", ["Active", "Expired/Timeout"])
        p_image_file = st.file_uploader("Upload Thumbnail / Poster Image (Optional)", type=["jpg", "png", "jpeg"])

        if st.form_submit_button("Publish"):
          if p_title and p_content:
            with st.spinner("Publishing post..."):
              image_bytes = p_image_file.read() if p_image_file is not None else None
              conn = get_db_connection()
              cursor = conn.cursor()
              cursor.execute(
                  "INSERT INTO public_posts (title, content, category, status, image) VALUES (%s, %s, %s, %s, %s)",
                  (p_title, p_content, p_category, p_status, image_bytes),
              )
              conn.commit()
              cursor.close()
              conn.close()
              st.success("Successfully published!")
              st.rerun()

    st.markdown("---")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, title, content, category, status FROM public_posts ORDER BY id DESC")
    df_posts = pd.DataFrame(cursor.fetchall())
    cursor.close()
    conn.close()

    if not df_posts.empty:
      for index, row in df_posts.iterrows():
        with st.container():
          col1, col2, col3 = st.columns([3, 1, 1])
          with col1:
            st.markdown(f"**[{row['category']}] {row['title']}** (Status: `{row['status']}`)")
            st.write(row["content"])
          with col2:
            new_status = st.selectbox("Status", ["Active", "Expired/Timeout"], index=0 if row["status"] == "Active" else 1, key=f"status_{row['id']}")
            if st.button("Update", key=f"up_btn_{row['id']}"):
              conn = get_db_connection()
              cursor = conn.cursor()
              cursor.execute("UPDATE public_posts SET status = %s WHERE id = %s", (new_status, row["id"]))
              conn.commit()
              cursor.close()
              conn.close()
              st.success("Updated!")
              st.rerun()
          with col3:
            if st.button("🗑️ Delete", key=f"del_post_{row['id']}"):
              conn = get_db_connection()
              cursor = conn.cursor()
              cursor.execute("DELETE FROM public_posts WHERE id = %s", (row["id"],))
              conn.commit()
              cursor.close()
              conn.close()
              st.success("Deleted!")
              st.rerun()
          st.divider()

  elif menu == "Manage Attendance":
    st.subheader("📊 Online Attendance Management System")
    tab_mark, tab_report = st.tabs(["📝 Mark Attendance", "📈 View Attendance Reports"])

    with tab_mark:
      conn = get_db_connection()
      cursor = conn.cursor(dictionary=True)
      cursor.execute("SELECT DISTINCT class FROM students")
      classes_df = pd.DataFrame(cursor.fetchall())
      cursor.close()
      conn.close()

      if not classes_df.empty:
        class_list = classes_df["class"].tolist()
        selected_class = st.selectbox("Select Class / Batch", class_list, key="att_class")
        selected_date = st.date_input("Attendance Date", value=date.today(), key="att_date")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT roll_no, name FROM students WHERE class = %s", (selected_class,))
        students_in_class = pd.DataFrame(cursor.fetchall())
        cursor.close()
        conn.close()

        if not students_in_class.empty:
          with st.form("attendance_form"):
            attendance_status = {}
            for idx, s_row in students_in_class.iterrows():
              r_no = s_row["roll_no"]
              s_name = s_row["name"]
              c1, c2, c3 = st.columns([1, 2, 1])
              c1.write(f"`{r_no}`")
              c2.write(f"**{s_name}**")
              status = c3.radio("Status", ["Present", "Absent"], key=f"status_{r_no}", horizontal=True, label_visibility="collapsed")
              attendance_status[r_no] = (s_name, status)

            if st.form_submit_button("💾 Save Attendance"):
              with st.spinner("Saving attendance..."):
                date_str = str(selected_date)
                conn = get_db_connection()
                cursor = conn.cursor()
                for r_no, (s_name, status) in attendance_status.items():
                  cursor.execute("DELETE FROM attendance WHERE roll_no = %s AND class = %s AND date = %s", (r_no, selected_class, date_str))
                  cursor.execute("INSERT INTO attendance (roll_no, student_name, class, date, status) VALUES (%s, %s, %s, %s, %s)", (r_no, s_name, selected_class, date_str, status))
                conn.commit()
                cursor.close()
                conn.close()
                st.success("Attendance saved successfully!")
    with tab_report:
      conn = get_db_connection()
      cursor = conn.cursor(dictionary=True)
      cursor.execute("SELECT * FROM attendance")
      att_df = pd.DataFrame(cursor.fetchall())
      cursor.close()
      conn.close()
      if not att_df.empty:
        st.dataframe(att_df, use_container_width=True)
      else:
        st.info("No attendance records found.")

# ==========================================
# 5. USER PURCHASED LIBRARY & HISTORY
# ==========================================
def user_library():
  if not st.session_state.logged_in:
    st.error("Please login to view your library.")
    return

  st.title("📂 My Purchased Library & Enrolled Batches")

  conn = get_db_connection()
  cursor = conn.cursor(dictionary=True)
  cursor.execute("""
      SELECT n.id, n.title, n.description, n.file_content, n.file_name 
      FROM purchases p
      JOIN notes n ON p.note_id = n.id
      WHERE p.user_id = %s
  """, (st.session_state.user_id,))
  my_notes = cursor.fetchall()
  cursor.close()
  conn.close()

  if my_notes:
    st.subheader("📥 Downloadable Study Notes")
    for note in my_notes:
      st.markdown(f"### 📖 {note['title']}")
      st.write(note['description'])
      if note['file_content']:
        st.download_button(
            label="📥 Download PDF Notes",
            data=note['file_content'],
            file_name=note['file_name'] if note['file_name'] else "notes.pdf",
            mime="application/pdf",
            key=f"lib_dl_note_{note['id']}"
        )
      st.divider()
  else:
    st.info("Aapne abhi tak koi study notes nahi kharida/unlock kiya hai.")

  # Show Batch Enrollments
  conn = get_db_connection()
  cursor = conn.cursor(dictionary=True)
  cursor.execute("SELECT batch_name, purchase_date FROM enrollments WHERE email = %s", (st.session_state.username,))
  enrolled_batches = cursor.fetchall()
  cursor.close()
  conn.close()

  if enrolled_batches:
    st.subheader("🎓 Enrolled Coaching Batches History")
    st.dataframe(pd.DataFrame(enrolled_batches), use_container_width=True)


 


# ==========================================
# MAIN ROUTER
# ==========================================
if st.session_state.page == "Home":
  show_home()
elif st.session_state.page == "Auth":
  auth_page()
elif st.session_state.page == "Admin_Login":
  admin_login_page()
elif st.session_state.page == "Admin":
  admin_panel()
elif st.session_state.page == "Library":
  user_library()


 