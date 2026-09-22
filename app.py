import streamlit as st
import pandas as pd
import psycopg2
import bcrypt
from supabase import create_client
from datetime import datetime
import io

# ==========================================
# KONFIGURASI HALAMAN (HARUS PALING ATAS)
# ==========================================
st.set_page_config(page_title="Sistem Informasi Kelompok Bundaran Pancasila", layout="wide", page_icon="🕌")

# ==========================================
# CUSTOM STYLING (TAMPILAN LEBIH MENARIK)
# ==========================================
st.markdown("""
<style>
    /* Kartu metrik dashboard */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #ffffff 0%, #f7f9fc 100%);
        border: 1px solid #e6e9f0;
        border-radius: 14px;
        padding: 18px 16px;
        box-shadow: 0 2px 8px rgba(20, 40, 80, 0.06);
    }
    div[data-testid="stMetric"] label {
        font-weight: 600;
        color: #5b6470;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
        color: #14532d;
    }
    /* Tab styling */
    button[data-baseweb="tab"] {
        font-weight: 600;
    }
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #0f4c3a;
    }
    section[data-testid="stSidebar"] * {
        color: #f2f7f4 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #14532d !important;
    }
    section[data-testid="stSidebar"] button {
        background-color: #b91c1c !important;
        color: white !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# KONEKSI DATABASE (SUPABASE / POSTGRESQL)
# ==========================================
@st.cache_resource
def get_connection():
    return psycopg2.connect(st.secrets["connection"]["url"])

@st.cache_resource
def get_supabase_client():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jemaah 
                 (id SERIAL PRIMARY KEY, nama TEXT, kontak TEXT, kelompok TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keuangan 
                 (id SERIAL PRIMARY KEY, tanggal TEXT, tipe TEXT, kategori TEXT, jumlah INTEGER, amil TEXT, keterangan TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS aset 
                 (id SERIAL PRIMARY KEY, nama_barang TEXT, jumlah INTEGER, kondisi TEXT, lokasi TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kegiatan 
                 (id SERIAL PRIMARY KEY, nama_kegiatan TEXT, tanggal TEXT, lokasi TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS absensi 
                 (id SERIAL PRIMARY KEY, kegiatan_id INTEGER, jemaah_id INTEGER, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, nama_lengkap TEXT, role TEXT DEFAULT 'user')''')
    c.execute('''CREATE TABLE IF NOT EXISTS dokumen 
                 (id SERIAL PRIMARY KEY, nama_file TEXT, url TEXT, kategori TEXT, uploaded_by TEXT, uploaded_at TEXT)''')
    # Kolom tambahan untuk penandaan modul terkait dokumen (aman dijalankan berulang kali)
    c.execute("ALTER TABLE dokumen ADD COLUMN IF NOT EXISTS modul TEXT")
    conn.commit()
    c.close()

init_db()

def run_query(query, params=(), is_select=False):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(query, params)
        if is_select:
            data = c.fetchall()
            cols = [description[0] for description in c.description]
            return pd.DataFrame(data, columns=cols)
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Terjadi kesalahan database: {e}")
    finally:
        c.close()

# ==========================================
# AUTENTIKASI / MULTI-USER
# ==========================================
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

def get_user_count():
    df = run_query("SELECT COUNT(*) as total FROM users", is_select=True)
    if df is not None and not df.empty:
        return int(df['total'].iloc[0])
    return 0

def login_page():
    st.title("🕌 Sistem Informasi Kelompok Bundaran Pancasila")

    if get_user_count() == 0:
        st.info("Belum ada akun terdaftar. Buat akun Admin pertama untuk memulai.")
        with st.form("form_setup_admin"):
            st.write("### Buat Akun Admin Pertama")
            username = st.text_input("Username")
            nama_lengkap = st.text_input("Nama Lengkap")
            password = st.text_input("Password", type="password")
            password2 = st.text_input("Ulangi Password", type="password")
            submit = st.form_submit_button("Buat Akun Admin")
            if submit:
                if not username or not password:
                    st.error("Username dan password wajib diisi.")
                elif password != password2:
                    st.error("Password dan ulangi password tidak sama.")
                else:
                    run_query(
                        "INSERT INTO users (username, password_hash, nama_lengkap, role) VALUES (%s, %s, %s, %s)",
                        (username, hash_password(password), nama_lengkap, "admin")
                    )
                    st.success("Akun admin berhasil dibuat! Silakan login di bawah.")
                    st.rerun()
    else:
        with st.form("form_login"):
            st.write("### Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Masuk")
            if submit:
                df = run_query("SELECT * FROM users WHERE username = %s", (username,), is_select=True)
                if df is not None and not df.empty and verify_password(password, df.iloc[0]['password_hash']):
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = df.iloc[0]['username']
                    st.session_state['nama_lengkap'] = df.iloc[0]['nama_lengkap']
                    st.session_state['role'] = df.iloc[0]['role']
                    st.rerun()
                else:
                    st.error("Username atau password salah.")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    login_page()
    st.stop()

# ==========================================
# SIDEBAR: INFO USER & LOGOUT
# ==========================================
is_admin = st.session_state['role'] == 'admin'
label_role = "Admin" if is_admin else "Umum (Hanya Lihat)"
st.sidebar.write(f"👤 **{st.session_state.get('nama_lengkap') or st.session_state['username']}**")
st.sidebar.caption(f"Level akses: {label_role}")
if st.sidebar.button("Logout"):
    for key in ['logged_in', 'username', 'nama_lengkap', 'role']:
        st.session_state.pop(key, None)
    st.rerun()
st.sidebar.write("---")

# ==========================================
# KONFIGURASI HALAMAN UTAMA
# ==========================================
st.markdown("""
<div style="
    background: linear-gradient(120deg, #14532d 0%, #0f4c3a 60%, #b45309 130%);
    padding: 28px 32px;
    border-radius: 18px;
    margin-bottom: 22px;
    box-shadow: 0 6px 18px rgba(20, 83, 45, 0.25);
">
    <h1 style="color: white; margin: 0; font-size: 1.9rem;">🕌 Sistem Informasi Kelompok Bundaran Pancasila</h1>
    <p style="color: #d9f2e6; margin: 6px 0 0 0; font-size: 0.95rem;">Modul Keuangan, Aset, SDM &amp; Kegiatan Kelompok</p>
</div>
""", unsafe_allow_html=True)

menu_options = ["Dashboard", "Data SDM (Jemaah)", "Keuangan & Kas", "Aset & Inventaris", "Kegiatan & Absensi", "Dokumen", "Unduh Laporan Excel"]
if st.session_state['role'] == 'admin':
    menu_options.append("Kelola Pengguna")

menu = st.sidebar.selectbox("Pilih Modul", menu_options)

df_jemaah = run_query("SELECT * FROM jemaah", is_select=True)
df_keuangan = run_query("SELECT * FROM keuangan", is_select=True)
df_aset = run_query("SELECT * FROM aset", is_select=True)
df_kegiatan = run_query("SELECT * FROM kegiatan", is_select=True)
df_absensi = run_query("SELECT * FROM absensi", is_select=True)

if not df_keuangan.empty:
    masuk = df_keuangan[df_keuangan['tipe'] == 'Masuk']['jumlah'].sum()
    keluar = df_keuangan[df_keuangan['tipe'] == 'Keluar']['jumlah'].sum()
    saldo_total = masuk - keluar
else:
    saldo_total = 0

total_aset = df_aset['jumlah'].sum() if not df_aset.empty else 0

# ==========================================
# 1. MODUL DASHBOARD
# ==========================================
if menu == "Dashboard":
    st.markdown(f"""
    <p style="color:#6b7280; font-size:0.95rem; margin-top:-10px; margin-bottom:18px;">
        Selamat datang kembali, <b>{st.session_state.get('nama_lengkap') or st.session_state['username']}</b> 👋
    </p>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.metric(label="👥 Total Jemaah Terdaftar", value=f"{len(df_jemaah)} Orang")
    col2.metric(label="💰 Saldo Kas Saat Ini", value=f"Rp {saldo_total:,}")
    col3.metric(label="📦 Total Unit Aset Kelompok", value=f"{total_aset} Barang")

    st.write("")
    st.markdown("#### 📈 Aktivitas Terbaru")
    tab1, tab2 = st.tabs(["💵 5 Transaksi Terakhir", "🗓️ Agenda Terdekat"])
    with tab1:
        if not df_keuangan.empty:
            st.dataframe(df_keuangan.tail(5), use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada transaksi keuangan yang dicatat.")
    with tab2:
        if not df_kegiatan.empty:
            st.dataframe(df_kegiatan.tail(5), use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada agenda kegiatan yang dijadwalkan.")

# ==========================================
# 2. MODUL DATA SDM (JEMAAH)
# ==========================================
elif menu == "Data SDM (Jemaah)":
    st.write("### 👥 Pengelolaan Data SDM / Jemaah Kelompok")
    if is_admin:
        with st.form("form_jemaah", clear_on_submit=True):
            st.write("**Tambah Jemaah Baru**")
            nama = st.text_input("Nama Lengkap")
            kontak = st.text_input("Nomor WhatsApp/Kontak")
            kelompok = st.selectbox("Asal Kelompok / Wilayah", ["Kelompok Bundaran Pancasila"])
            submit = st.form_submit_button("Simpan Data Jemaah")
            if submit and nama:
                run_query("INSERT INTO jemaah (nama, kontak, kelompok) VALUES (%s, %s, %s)", (nama, kontak, kelompok))
                st.success(f"Berhasil menambahkan {nama} ke {kelompok}!")
                st.rerun()
    else:
        st.info("Mode Umum: hanya bisa melihat data. Hubungi Admin untuk menambah jemaah baru.")

    st.write("---")
    st.write("#### 🔍 Daftar Anggota Jemaah Aktif")
    filter_kelompok = st.selectbox("Filter berdasarkan Kelompok:", ["Semua", "Kelompok Bundaran Pancasila"])
    if not df_jemaah.empty:
        display_df = df_jemaah if filter_kelompok == "Semua" else df_jemaah[df_jemaah['kelompok'] == filter_kelompok]
        st.dataframe(display_df[['id', 'nama', 'kontak', 'kelompok']], use_container_width=True)
    else:
        st.info("Belum ada data jemaah. Silakan isi form di atas.")

# ==========================================
# 3. MODUL KEUANGAN & KAS
# ==========================================
elif menu == "Keuangan & Kas":
    st.write("### 💰 Pencatatan Transaksi Keuangan")
    if is_admin:
        with st.form("form_keuangan", clear_on_submit=True):
            st.write("**Input Transaksi Baru**")
            col_f1, col_f2 = st.columns(2)
            tipe = col_f1.radio("Jenis Transaksi", ["Masuk", "Keluar"])
            kategori = col_f2.selectbox("Kategori Dana", ["Zakat", "Infaq Rutin", "Kas Pengajian", "Konsumsi", "Bantuan Sosial", "Operasional"])
            jumlah = st.number_input("Jumlah Uang (Rp)", min_value=0, step=1000)
            amil = st.text_input("Nama Pengurus / Amil Pencatat", value=st.session_state.get('nama_lengkap', ''))
            keterangan = st.text_area("Keterangan Tambahan")
            submit_keu = st.form_submit_button("Simpan Transaksi")
            if submit_keu and jumlah > 0 and amil:
                tgl_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M")
                run_query("INSERT INTO keuangan (tanggal, tipe, kategori, jumlah, amil, keterangan) VALUES (%s, %s, %s, %s, %s, %s)",
                          (tgl_sekarang, tipe, kategori, jumlah, amil, keterangan))
                st.success("Transaksi berhasil dicatat ke dalam sistem!")
                st.rerun()
    else:
        st.info("Mode Umum: hanya bisa melihat data. Hubungi Admin untuk mencatat transaksi.")

    st.write("---")
    st.write("#### 📜 Seluruh Riwayat Kas Masuk & Keluar")
    if not df_keuangan.empty:
        st.dataframe(df_keuangan, use_container_width=True)
    else:
        st.info("Belum ada riwayat transaksi keuangan.")

# ==========================================
# 4. MODUL ASET & INVENTARIS
# ==========================================
elif menu == "Aset & Inventaris":
    st.write("### 📦 Inventarisasi Barang & Aset Kelompok")
    if is_admin:
        with st.form("form_aset", clear_on_submit=True):
            st.write("**Tambah Barang / Aset Baru**")
            nama_barang = st.text_input("Nama Barang")
            jumlah = st.number_input("Jumlah Unit/Barang", min_value=1, step=1)
            kondisi = st.selectbox("Kondisi Barang Saat Ini", ["Baik", "Rusak Ringan", "Rusak Berat"])
            lokasi = st.text_input("Lokasi Penyimpanan")
            submit_aset = st.form_submit_button("Simpan Data Aset")
            if submit_aset and nama_barang:
                run_query("INSERT INTO aset (nama_barang, jumlah, kondisi, lokasi) VALUES (%s, %s, %s, %s)", (nama_barang, jumlah, kondisi, lokasi))
                st.success(f"Aset '{nama_barang}' berhasil didaftarkan!")
                st.rerun()
    else:
        st.info("Mode Umum: hanya bisa melihat data. Hubungi Admin untuk menambah aset.")

    st.write("---")
    st.write("#### 📋 Daftar Inventaris Barang")
    if not df_aset.empty:
        st.dataframe(df_aset, use_container_width=True)
    else:
        st.info("Belum ada aset terdaftar.")

# ==========================================
# 5. MODUL KEGIATAN & ABSENSI
# ==========================================
elif menu == "Kegiatan & Absensi":
    st.write("### 📅 Pengelolaan Agenda Rutin & Absensi Jemaah")
    tab_keg1, tab_keg2 = st.tabs(["Buat Agenda Baru", "Isi Absensi Kegiatan"])
    with tab_keg1:
        if is_admin:
            with st.form("form_kegiatan", clear_on_submit=True):
                st.write("**Jadwalkan Kegiatan Baru**")
                nama_kegiatan = st.text_input("Nama Kegiatan / Tema Pengajian")
                tgl_keg = st.date_input("Tanggal Pelaksanaan")
                lokasi_keg = st.text_input("Tempat / Lokasi Pengajian")
                submit_keg = st.form_submit_button("Buat Jadwal")
                if submit_keg and nama_kegiatan:
                    run_query("INSERT INTO kegiatan (nama_kegiatan, tanggal, lokasi) VALUES (%s, %s, %s)", (nama_kegiatan, str(tgl_keg), lokasi_keg))
                    st.success(f"Agenda '{nama_kegiatan}' berhasil dijadwalkan!")
                    st.rerun()
        else:
            st.info("Mode Umum: hanya bisa melihat agenda. Hubungi Admin untuk membuat jadwal baru.")
        st.write("#### 📜 Daftar Agenda Terjadwal")
        if not df_kegiatan.empty:
            st.dataframe(df_kegiatan, use_container_width=True)

    with tab_keg2:
        if df_kegiatan.empty:
            st.warning("Silakan buat agenda kegiatan terlebih dahulu.")
        elif df_jemaah.empty:
            st.warning("Silakan daftarkan jemaah terlebih dahulu.")
        else:
            st.write("**Pencatatan Kehadiran Jemaah**")
            pilihan_keg = {row['id']: f"{row['nama_kegiatan']} ({row['tanggal']})" for _, row in df_kegiatan.iterrows()}
            keg_terpilih = st.selectbox("Pilih Kegiatan Pengajian:", options=list(pilihan_keg.keys()), format_func=lambda x: pilihan_keg[x])
            if is_admin:
                st.write("Centang jemaah yang **Hadir** dalam kegiatan ini:")
                with st.form("form_absensi"):
                    status_kehadiran = {}
                    for _, jemaah in df_jemaah.iterrows():
                        col_j1, col_j2 = st.columns(2)
                        col_j1.write(f"👥 **{jemaah['nama']}**")
                        status_kehadiran[jemaah['id']] = col_j2.checkbox("Hadir", key=f"j_{jemaah['id']}")
                    submit_abs = st.form_submit_button("Simpan Seluruh Absensi")
                    if submit_abs:
                        run_query("DELETE FROM absensi WHERE kegiatan_id = %s", (int(keg_terpilih),))
                        for jemaah_id, hadir in status_kehadiran.items():
                            status = "Hadir" if hadir else "Tidak Hadir"
                            run_query(
                                "INSERT INTO absensi (kegiatan_id, jemaah_id, status) VALUES (%s, %s, %s)",
                                (int(keg_terpilih), int(jemaah_id), status)
                            )
                        st.success("Absensi berhasil disimpan!")
                        st.rerun()
            else:
                st.info("Mode Umum: hanya bisa melihat rekap absensi. Hubungi Admin untuk mengisi absensi.")

            st.write("---")
            st.write("#### 📊 Rekap Absensi Kegiatan Terpilih")
            if not df_absensi.empty:
                rekap = df_absensi[df_absensi['kegiatan_id'] == keg_terpilih].merge(
                    df_jemaah[['id', 'nama']], left_on='jemaah_id', right_on='id', how='left'
                )
                if not rekap.empty:
                    st.dataframe(rekap[['nama', 'status']], use_container_width=True)
                else:
                    st.info("Belum ada absensi tersimpan untuk kegiatan ini.")
            else:
                st.info("Belum ada data absensi.")

# ==========================================
# 6. MODUL DOKUMEN (UPLOAD KE SUPABASE STORAGE)
# ==========================================
elif menu == "Dokumen":
    st.write("### 📁 Upload & Kelola Dokumen")
    MODUL_DOKUMEN = ["Jemaah", "Keuangan", "Aset", "Kegiatan", "Umum"]

    if is_admin:
        with st.form("form_dokumen", clear_on_submit=True):
            st.write("**Upload Dokumen Baru**")
            modul_dok = st.selectbox("Modul Terkait", MODUL_DOKUMEN)
            kategori_dok = st.selectbox("Kategori Dokumen", ["Notulen Rapat", "Bukti Transaksi", "Surat Menyurat", "Foto Kegiatan", "Lainnya"])
            uploaded_file = st.file_uploader("Pilih File", type=["pdf", "jpg", "jpeg", "png", "docx", "xlsx"])
            submit_dok = st.form_submit_button("Upload Dokumen")
            if submit_dok:
                if uploaded_file is None:
                    st.error("Silakan pilih file terlebih dahulu.")
                else:
                    try:
                        supabase = get_supabase_client()
                        file_bytes = uploaded_file.getvalue()
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        safe_name = uploaded_file.name.replace(" ", "_")
                        storage_path = f"{timestamp}_{safe_name}"

                        supabase.storage.from_("dokumen").upload(storage_path, file_bytes)
                        public_url = supabase.storage.from_("dokumen").get_public_url(storage_path)

                        run_query(
                            "INSERT INTO dokumen (nama_file, url, kategori, modul, uploaded_by, uploaded_at) VALUES (%s, %s, %s, %s, %s, %s)",
                            (uploaded_file.name, public_url, kategori_dok, modul_dok, st.session_state['username'], datetime.now().strftime("%Y-%m-%d %H:%M"))
                        )
                        st.success(f"Dokumen '{uploaded_file.name}' berhasil diupload!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal mengupload dokumen: {e}")
    else:
        st.info("Mode Umum: hanya bisa melihat & mengunduh dokumen. Hubungi Admin untuk upload dokumen baru.")

    st.write("---")
    st.write("#### 📋 Daftar Dokumen Tersimpan")
    filter_modul = st.selectbox("Filter Modul", ["Semua"] + MODUL_DOKUMEN)
    df_dokumen = run_query("SELECT * FROM dokumen ORDER BY id DESC", is_select=True)
    if df_dokumen is not None and not df_dokumen.empty:
        if filter_modul != "Semua":
            df_dokumen = df_dokumen[df_dokumen['modul'] == filter_modul]
        if df_dokumen.empty:
            st.info(f"Belum ada dokumen untuk modul '{filter_modul}'.")
        for _, row in df_dokumen.iterrows():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
            col1.write(f"📄 **{row['nama_file']}**")
            col2.write(row.get('modul') or "-")
            col3.write(row['kategori'])
            col4.write(f"oleh {row['uploaded_by']}")
            col5.markdown(f"[Buka/Unduh]({row['url']})")
    else:
        st.info("Belum ada dokumen yang diupload.")

# ==========================================
# 7. MODUL KELOLA PENGGUNA (ADMIN SAJA)
# ==========================================
elif menu == "Kelola Pengguna":
    st.write("### 👤 Kelola Akun Pengguna")
    with st.form("form_user", clear_on_submit=True):
        st.write("**Tambah Pengguna Baru**")
        new_username = st.text_input("Username Baru")
        new_nama = st.text_input("Nama Lengkap")
        new_role = st.selectbox("Peran (Role)", ["user", "admin"], format_func=lambda x: "Umum (Hanya Lihat)" if x == "user" else "Admin (Bisa Edit)")
        new_password = st.text_input("Password", type="password")
        submit_user = st.form_submit_button("Tambah Pengguna")
        if submit_user:
            if not new_username or not new_password:
                st.error("Username dan password wajib diisi.")
            else:
                existing = run_query("SELECT id FROM users WHERE username = %s", (new_username,), is_select=True)
                if existing is not None and not existing.empty:
                    st.error("Username sudah dipakai, silakan pilih username lain.")
                else:
                    run_query(
                        "INSERT INTO users (username, password_hash, nama_lengkap, role) VALUES (%s, %s, %s, %s)",
                        (new_username, hash_password(new_password), new_nama, new_role)
                    )
                    st.success(f"Pengguna '{new_username}' berhasil ditambahkan!")
                    st.rerun()

    st.write("---")
    st.write("#### Daftar Pengguna Terdaftar")
    df_users = run_query("SELECT id, username, nama_lengkap, role FROM users", is_select=True)
    if df_users is not None and not df_users.empty:
        df_users_display = df_users.copy()
        df_users_display['role'] = df_users_display['role'].map({"admin": "Admin", "user": "Umum"}).fillna(df_users_display['role'])
        st.dataframe(df_users_display, use_container_width=True)
    else:
        st.info("Belum ada pengguna terdaftar.")

# ==========================================
# 8. MODUL UNDUH LAPORAN EXCEL
# ==========================================
elif menu == "Unduh Laporan Excel":
    st.write("### 📥 Unduh Laporan Lengkap (Format Excel)")
    st.write("Klik tombol di bawah untuk mengunduh seluruh data sistem dalam satu file Excel (multi-sheet).")

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        (df_jemaah if not df_jemaah.empty else pd.DataFrame(columns=['id', 'nama', 'kontak', 'kelompok'])).to_excel(writer, sheet_name='Jemaah', index=False)
        (df_keuangan if not df_keuangan.empty else pd.DataFrame(columns=['id', 'tanggal', 'tipe', 'kategori', 'jumlah', 'amil', 'keterangan'])).to_excel(writer, sheet_name='Keuangan', index=False)
        (df_aset if not df_aset.empty else pd.DataFrame(columns=['id', 'nama_barang', 'jumlah', 'kondisi', 'lokasi'])).to_excel(writer, sheet_name='Aset', index=False)
        (df_kegiatan if not df_kegiatan.empty else pd.DataFrame(columns=['id', 'nama_kegiatan', 'tanggal', 'lokasi'])).to_excel(writer, sheet_name='Kegiatan', index=False)
        (df_absensi if not df_absensi.empty else pd.DataFrame(columns=['id', 'kegiatan_id', 'jemaah_id', 'status'])).to_excel(writer, sheet_name='Absensi', index=False)

    st.download_button(
        label="⬇️ Unduh Laporan Excel Lengkap",
        data=buffer.getvalue(),
        file_name=f"laporan_pengajian_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.write("---")
    st.write("#### Pratinjau Data Keuangan")
    if not df_keuangan.empty:
        st.dataframe(df_keuangan, use_container_width=True)
    else:
        st.info("Belum ada data keuangan untuk ditampilkan.")
