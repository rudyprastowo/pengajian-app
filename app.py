import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import io

# ==========================================
# KONEKSI DATABASE (SUPABASE / POSTGRESQL)
# ==========================================
@st.cache_resource
def get_connection():
    return psycopg2.connect(st.secrets["connection"]["url"])

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
# KONFIGURASI HALAMAN UTAMA
# ==========================================
st.set_page_config(page_title="Sistem Pengajian Kelompok", layout="wide")
st.title("🕌 Sistem Informasi & Pengelolaan Pengajian")
st.subheader("Modul Keuangan, Aset, SDM & Kegiatan")

menu = st.sidebar.selectbox("Pilih Modul", ["Dashboard", "Data SDM (Jemaah)", "Keuangan & Kas", "Aset & Inventaris", "Kegiatan & Absensi", "Unduh Laporan Excel"])

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
    st.write("### Selamat Datang di Pusat Kendali Pengajian")
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Total Jemaah Terdaftar", value=f"{len(df_jemaah)} Orang")
    col2.metric(label="Saldo Kas Saat Ini", value=f"Rp {saldo_total:,}")
    col3.metric(label="Total Unit Aset Kelompok", value=f"{total_aset} Barang")
    st.write("---")
    st.write("#### 📈 Ringkasan Aktivitas Terbaru")
    tab1, tab2 = st.tabs(["5 Transaksi Terakhir", "Agenda Terdekat"])
    with tab1:
        if not df_keuangan.empty:
            st.dataframe(df_keuangan.tail(5), use_container_width=True)
        else:
            st.info("Belum ada transaksi keuangan yang dicatat.")
    with tab2:
        if not df_kegiatan.empty:
            st.dataframe(df_kegiatan.tail(5), use_container_width=True)
        else:
            st.info("Belum ada agenda kegiatan yang dijadwalkan.")

# ==========================================
# 2. MODUL DATA SDM (JEMAAH)
# ==========================================
elif menu == "Data SDM (Jemaah)":
    st.write("### 👥 Pengelolaan Data SDM / Jemaah Kelompok")
    with st.form("form_jemaah", clear_on_submit=True):
        st.write("**Tambah Jemaah Baru**")
        nama = st.text_input("Nama Lengkap")
        kontak = st.text_input("Nomor WhatsApp/Kontak")
        kelompok = st.selectbox("Asal Kelompok / Wilayah", ["Kelompok Bundaran Pancalia"])
        submit = st.form_submit_button("Simpan Data Jemaah")
        if submit and nama:
            run_query("INSERT INTO jemaah (nama, kontak, kelompok) VALUES (%s, %s, %s)", (nama, kontak, kelompok))
            st.success(f"Berhasil menambahkan {nama} ke {kelompok}!")
            st.rerun()

    st.write("---")
    st.write("#### 🔍 Daftar Anggota Jemaah Aktif")
    filter_kelompok = st.selectbox("Filter berdasarkan Kelompok:", ["Semua", "Kelompok Bundaran Pancalia"])
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
    with st.form("form_keuangan", clear_on_submit=True):
        st.write("**Input Transaksi Baru (Multi-User Entry)**")
        col_f1, col_f2 = st.columns(2)
        tipe = col_f1.radio("Jenis Transaksi", ["Masuk", "Keluar"])
        kategori = col_f2.selectbox("Kategori Dana", ["Zakat", "Infaq Rutin", "Kas Pengajian", "Konsumsi", "Bantuan Sosial", "Operasional"])
        jumlah = st.number_input("Jumlah Uang (Rp)", min_value=0, step=1000)
        amil = st.text_input("Nama Pengurus / Amil Pencatat")
        keterangan = st.text_area("Keterangan Tambahan")
        submit_keu = st.form_submit_button("Simpan Transaksi")
        if submit_keu and jumlah > 0 and amil:
            tgl_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M")
            run_query("INSERT INTO keuangan (tanggal, tipe, kategori, jumlah, amil, keterangan) VALUES (%s, %s, %s, %s, %s, %s)",
                      (tgl_sekarang, tipe, kategori, jumlah, amil, keterangan))
            st.success("Transaksi berhasil dicatat ke dalam sistem!")
            st.rerun()

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
# 6. MODUL UNDUH LAPORAN EXCEL
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
