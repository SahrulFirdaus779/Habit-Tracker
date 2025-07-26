import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import io
from fpdf import FPDF
import plotly.express as px
import sqlite3

# --- KONFIGURASI DASAR ---
st.set_page_config(layout="wide", page_title="LetsTracker")
DB_FILE = "letstracker.db"
# --- PERUBAHAN: Menambahkan placeholder ---
PARTICIPANTS = ["Pilih Nama..."] + ["Sahrul", "Umam", "Fatih", "Fahmi", "El", "Taqi", "Bang Abror", "Bang Habib", "Bang Yafie", "Bang Yudo"]
HABITS = {
    "Juz 30 (Hafalan/Murajaah)": "daily", "Hadis Arbain 1-25": "daily", "Tilawah 1/2 Juz": "daily",
    "Al-Matsurat (Pagi/Sore)": "daily", "Qiyamulail": "weekly", "Olahraga": "weekly", "Shaum Sunnah": "monthly"
}
EXTRA_COLS = ["Catatan"]
TARGETS = {"Qiyamulail": 2, "Olahraga": 3, "Shaum Sunnah": 3}

# --- FUNGSI DATABASE (SQLite) ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    habit_cols = ", ".join([f'"{habit}" INTEGER DEFAULT 0' for habit in HABITS.keys()])
    c.execute(f'CREATE TABLE IF NOT EXISTS progress (Tanggal TEXT, User TEXT, {habit_cols}, Catatan TEXT, PRIMARY KEY (Tanggal, User))')
    conn.commit()
    conn.close()

@st.cache_data(ttl=60)
def load_data(username):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM progress WHERE User = ?", conn, params=(username,))
    conn.close()
    if not df.empty and 'Tanggal' in df.columns:
        df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
        df.dropna(subset=['Tanggal'], inplace=True)
        for col in list(HABITS.keys()) + EXTRA_COLS:
            if col not in df.columns: df[col] = 0 if col != 'Catatan' else ''
        df['Catatan'] = df['Catatan'].fillna('')
    return df

@st.cache_data(ttl=60)
def load_all_user_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM progress", conn)
    conn.close()
    if not df.empty and 'Tanggal' in df.columns:
        df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
        df.dropna(subset=['Tanggal'], inplace=True)
    return df

def upsert_data(date, user, data_dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    cols = ["Tanggal", "User"] + list(HABITS.keys()) + EXTRA_COLS
    values = [date.strftime('%Y-%m-%d'), user] + [data_dict.get(h, 0) for h in HABITS.keys()] + [data_dict.get('Catatan', '')]
    placeholders = ", ".join(["?"] * len(cols))
    quoted_cols = ", ".join([f'"{col}"' for col in cols])
    c.execute(f"INSERT OR REPLACE INTO progress ({quoted_cols}) VALUES ({placeholders})", values)
    conn.commit()
    conn.close()

def delete_data(date, user):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM progress WHERE Tanggal = ? AND User = ?", (date.strftime('%Y-%m-%d'), user))
    conn.commit()
    conn.close()

# --- FUNGSI BANTUAN LAINNYA ---
def calculate_streaks(df):
    if df.empty: return {}
    streaks = {}
    daily_habits = {k for k, v in HABITS.items() if v == 'daily'}
    df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
    df.dropna(subset=['Tanggal'], inplace=True)
    if df.empty: return {h: 0 for h in daily_habits}
    df_sorted = df.sort_values(by="Tanggal", ascending=False).reset_index(drop=True)
    today = datetime.now().date()
    last_entry_date = df_sorted.loc[0, 'Tanggal'].date()
    if last_entry_date < today - timedelta(days=1): return {h: 0 for h in daily_habits}
    for habit in daily_habits:
        streak_count, expected_date = 0, last_entry_date
        if df_sorted.loc[0].get(habit, 0) == 1:
            for _, row in df_sorted.iterrows():
                if row.get(habit, 0) == 1 and row['Tanggal'].date() == expected_date:
                    streak_count += 1
                    expected_date -= timedelta(days=1)
                else: break
        streaks[habit] = streak_count
    return streaks

def df_to_pdf(df, title="Laporan Progress"):
    # (Fungsi ini tidak berubah)
    return b''

def display_progress_summary(df_period, period_title="", target_days=7):
    st.header(f"Ringkasan Progress {period_title}")
    if df_period.empty:
        st.info("Tidak ada data untuk periode ini.")
        return
    progress_data, total_actual, total_target = [], df_period[list(HABITS.keys())].sum().sum(), 0.0
    for habit, type in HABITS.items():
        actual = df_period[habit].sum()
        target = 0.0
        if type == 'daily': target = float(target_days)
        elif type == 'weekly': target = TARGETS[habit] * (target_days / 7.0)
        elif type == 'monthly': target = TARGETS[habit] * (target_days / 30.0)
        total_target += target
        percentage = (actual / target * 100) if target > 0 else 0
        progress_data.append({"Ibadah": habit, "Capaian (%)": percentage})
    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("Capaian per Ibadah (%)")
        df_progress = pd.DataFrame(progress_data)
        fig_bar = px.bar(df_progress, x="Capaian (%)", y="Ibadah", orientation='h', text="Capaian (%)", color="Ibadah", color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_bar.update_traces(texttemplate='%{x:.0f}%')
        fig_bar.update_layout(xaxis_range=[0, 100], yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_{period_title}")
    with col2:
        st.subheader("Progress Keseluruhan")
        remaining = max(0, total_target - total_actual)
        pie_fig = px.pie(pd.DataFrame({"Status": ["Selesai", "Belum"], "Jumlah": [total_actual, remaining]}), values="Jumlah", names="Status", hole=0.4, color_discrete_map={"Selesai": "mediumseagreen", "Belum": "lightgray"})
        st.plotly_chart(pie_fig, use_container_width=True, key=f"pie_{period_title}")

# --- UI UTAMA ---
init_db()
st.title("🕌 LetsTracker - Habit Tracker Ibadah")

if 'edit_date' not in st.session_state: st.session_state.edit_date = None
if 'confirm_delete_date' not in st.session_state: st.session_state.confirm_delete_date = None
if 'show_success' not in st.session_state: st.session_state.show_success = False

with st.sidebar:
    st.header("👤 Pengguna")
    # --- PERUBAHAN: Menggunakan placeholder ---
    username = st.selectbox("Pilih Nama Peserta", options=PARTICIPANTS, index=0)
    
    # --- PERUBAHAN: Hanya tampilkan sisa sidebar jika nama sudah dipilih ---
    if username != "Pilih Nama...":
        st.header("🗓️ Pilih Tanggal Input")
        selected_date_input = st.date_input("Pilih tanggal untuk diisi", value=datetime.now().date())

# --- PERUBAHAN: Hanya jalankan aplikasi utama jika nama sudah dipilih ---
if username == "Pilih Nama...":
    st.info("👈 Silakan pilih nama Anda di sidebar untuk memulai.")
    st.stop()

df = load_data(username)

main_tabs = st.tabs(["📝 Input Jurnal", "📊 Laporan & Progress", "⚙️ Manajemen Data", "📥 Unduh Laporan"])

with main_tabs[0]:
    if st.session_state.show_success:
        st.success("✨ Jurnal berhasil disimpan!")
        st.session_state.show_success = False
    st.header(f"Input Jurnal untuk: {selected_date_input.strftime('%A, %d %B %Y')}")
    date_obj = pd.to_datetime(selected_date_input)
    is_existing_entry = False
    if not df.empty:
        df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
        if selected_date_input in df['Tanggal'].dt.date.values:
            is_existing_entry = True
    if is_existing_entry:
        daily_data = df[df['Tanggal'].dt.date == selected_date_input].iloc[0].to_dict()
        st.info("Data untuk tanggal ini sudah ada. Menyimpan akan menimpa data lama.")
        button_label = "✅ Timpa & Simpan Jurnal"
    else:
        daily_data = {}
        button_label = "✅ Simpan Jurnal Baru"
    with st.form(key="daily_journal_form"):
        cols = st.columns(2)
        for i, habit in enumerate(HABITS.keys()):
            daily_data[habit] = cols[i % 2].checkbox(habit, value=bool(daily_data.get(habit, 0)))
        daily_data['Catatan'] = st.text_area("Catatan Harian (opsional)...", value=daily_data.get('Catatan', ''))
        if st.form_submit_button(button_label):
            data_to_save = {habit: 1 if daily_data.get(habit, False) else 0 for habit in HABITS}
            data_to_save['Catatan'] = daily_data.get('Catatan', '')
            upsert_data(date_obj, username, data_to_save)
            st.session_state.show_success = True
            st.cache_data.clear()
            st.rerun()

with main_tabs[1]:
    st.header(f"Laporan & Progress untuk {username}")
    st.subheader("🔥 Runtutan (Streak) Ibadah Harian")
    streaks = calculate_streaks(df)
    if streaks:
        daily_habit_names = [k for k, v in HABITS.items() if v == 'daily']
        streak_cols = st.columns(len(daily_habit_names))
        for i, habit in enumerate(daily_habit_names):
            streak_cols[i].metric(habit, f"{streaks.get(habit, 0)} hari")
    st.markdown("---")
    report_tabs = st.tabs(["Ringkasan", "🏆 Leaderboard", "Analisis Kustom"])
    today = datetime.now().date()
    with report_tabs[0]:
        if df.empty:
            st.info("Belum ada data untuk ditampilkan.")
        else:
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
            start_of_week = today - timedelta(days=today.weekday())
            display_progress_summary(df[df['Tanggal'].dt.date >= start_of_week], "Pekan Ini", target_days=7)
            st.markdown("---")
            start_of_month = today.replace(day=1)
            days_in_month = (start_of_month.replace(month=start_of_month.month % 12 + 1, day=1) - timedelta(days=1)).day
            display_progress_summary(df[df['Tanggal'].dt.date >= start_of_month], "Bulan Ini", target_days=days_in_month)
    with report_tabs[1]:
        st.header("🏆 Papan Peringkat Peserta")
        all_users_df = load_all_user_data()
        if all_users_df.empty:
            st.warning("Belum ada data dari peserta manapun untuk ditampilkan.")
        else:
            all_users_df['Tanggal'] = pd.to_datetime(all_users_df['Tanggal'], errors='coerce')
            st.subheader("Peringkat Pekan Ini")
            start_of_week = today - timedelta(days=today.weekday())
            weekly_data_all = all_users_df[all_users_df['Tanggal'].dt.date >= start_of_week]
            leaderboard_weekly = []
            if not weekly_data_all.empty:
                for user, group in weekly_data_all.groupby('User'):
                    total_actual = sum(group[habit].sum() for habit in HABITS)
                    total_target = sum(TARGETS.get(h, 7) for h, t in HABITS.items() if t != 'monthly')
                    percentage = (total_actual / total_target * 100) if total_target > 0 else 0
                    leaderboard_weekly.append({"Peserta": user, "Progress (%)": round(percentage, 2)})
                lb_df_w = pd.DataFrame(leaderboard_weekly).sort_values("Progress (%)", ascending=False).reset_index(drop=True)
                lb_df_w.index += 1
                col1, col2 = st.columns([1, 2])
                with col1: st.dataframe(lb_df_w, use_container_width=True)
                with col2:
                    fig_lb_w = px.bar(lb_df_w, x="Progress (%)", y="Peserta", orientation='h', title="Visualisasi Peringkat Pekanan", text='Progress (%)', color="Peserta")
                    fig_lb_w.update_layout(yaxis={'categoryorder':'total descending'}, xaxis_range=[0,100], showlegend=False)
                    st.plotly_chart(fig_lb_w, use_container_width=True)
            else: st.info("Belum ada data pekan ini untuk leaderboard.")
            st.markdown("---")
            st.subheader("Peringkat Bulan Ini")
            start_of_month = today.replace(day=1)
            monthly_data_all = all_users_df[all_users_df['Tanggal'].dt.date >= start_of_month]
            leaderboard_monthly = []
            if not monthly_data_all.empty:
                days_passed, num_weeks_passed = today.day, today.day / 7
                for user, group in monthly_data_all.groupby('User'):
                    total_actual = sum(group[habit].sum() for habit in HABITS)
                    total_target = 0
                    for habit, type in HABITS.items():
                        if type == "daily": total_target += days_passed
                        elif type == "weekly": total_target += TARGETS[habit] * num_weeks_passed
                        elif type == "monthly": total_target += TARGETS[habit]
                    percentage = (total_actual / total_target * 100) if total_target > 0 else 0
                    leaderboard_monthly.append({"Peserta": user, "Progress (%)": round(percentage, 2)})
                lb_df_m = pd.DataFrame(leaderboard_monthly).sort_values("Progress (%)", ascending=False).reset_index(drop=True)
                lb_df_m.index += 1
                col1_m, col2_m = st.columns([1, 2])
                with col1_m: st.dataframe(lb_df_m, use_container_width=True)
                with col2_m:
                    fig_lb_m = px.bar(lb_df_m, x="Progress (%)", y="Peserta", orientation='h', title="Visualisasi Peringkat Bulanan", text='Progress (%)', color="Peserta")
                    fig_lb_m.update_layout(yaxis={'categoryorder':'total descending'}, xaxis_range=[0,100], showlegend=False)
                    st.plotly_chart(fig_lb_m, use_container_width=True)
            else: st.info("Belum ada data bulan ini untuk leaderboard.")
    with report_tabs[2]:
        st.header("Analisis Performa Ibadah")
        if df.empty:
            st.warning("Tidak ada data untuk dianalisis.")
        else:
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
            col1, col2 = st.columns(2)
            start_date = col1.date_input("Tanggal Mulai", today.replace(day=1), key="custom_start")
            end_date = col2.date_input("Tanggal Akhir", today, key="custom_end")
            if start_date > end_date:
                st.error("Tanggal Mulai tidak boleh melebihi Tanggal Akhir.")
            else:
                filtered_df = df[(df['Tanggal'].dt.date >= start_date) & (df['Tanggal'].dt.date <= end_date)]
                if filtered_df.empty:
                    st.warning("Tidak ada data pada rentang tanggal yang dipilih.")
                else:
                    st.markdown("---")
                    st.subheader("Wawasan Performa")
                    habit_counts = filtered_df[HABITS.keys()].sum().sort_values(ascending=False)
                    if not habit_counts.empty:
                        col_stats1, col_stats2 = st.columns(2)
                        col_stats1.metric("Ibadah Paling Sering Dilakukan", habit_counts.index[0], f"{int(habit_counts.iloc[0])} kali")
                        col_stats2.metric("Ibadah Paling Jarang Dilakukan", habit_counts.index[-1], f"{int(habit_counts.iloc[-1])} kali")
                    st.subheader("Grafik Total Pelaksanaan Ibadah")
                    fig_bar_custom = px.bar(x=habit_counts.values, y=habit_counts.index, orientation='h', title="Total Pelaksanaan Ibadah", color=habit_counts.index, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_bar_custom.update_layout(showlegend=False, yaxis_title="Ibadah", xaxis_title="Jumlah Pelaksanaan", yaxis={'categoryorder':'total descending'})
                    st.plotly_chart(fig_bar_custom, use_container_width=True)

with main_tabs[2]:
    st.header(f"Manajemen Data Jurnal - {username}")
    if not df.empty:
        df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
    if st.session_state.edit_date is not None:
        edit_date_obj = st.session_state.edit_date
        st.subheader(f"Mengedit Jurnal untuk: {edit_date_obj.strftime('%A, %d %B %Y')}")
        data_to_edit = df[df['Tanggal'] == edit_date_obj].iloc[0].to_dict()
        with st.form(key="edit_form"):
            for habit in HABITS:
                data_to_edit[habit] = st.checkbox(habit, value=bool(data_to_edit.get(habit, 0)))
            data_to_edit['Catatan'] = st.text_area("Catatan", value=data_to_edit.get('Catatan', ''))
            c1,c2 = st.columns(2)
            if c1.form_submit_button("💾 Simpan Perubahan", type="primary"):
                upsert_data(edit_date_obj, username, data_to_edit)
                st.success("✨ Perubahan berhasil disimpan!")
                st.session_state.edit_date = None
                st.cache_data.clear()
                st.rerun()
            if c2.form_submit_button("❌ Batal"):
                st.session_state.edit_date = None
                st.rerun()
    elif st.session_state.confirm_delete_date is not None:
        confirm_date_obj = st.session_state.confirm_delete_date
        st.warning(f"**Konfirmasi Hapus**: Yakin ingin menghapus data tanggal **{confirm_date_obj.strftime('%d %B %Y')}**?")
        c1, c2, _ = st.columns([1,1,4])
        if c1.button("✅ Ya, Hapus", type="primary"):
            delete_data(confirm_date_obj, username)
            st.session_state.confirm_delete_date = None
            st.cache_data.clear()
            st.success("Data berhasil dihapus.")
            st.rerun()
        if c2.button("❌ Batal"):
            st.session_state.confirm_delete_date = None
            st.rerun()
    else:
        st.subheader("Daftar Jurnal Tersimpan")
        if not df.empty:
            for _, row in df.sort_values(by="Tanggal", ascending=False).iterrows():
                with st.expander(f"**{row['Tanggal'].strftime('%A, %d %B %Y')}**"):
                    for habit in HABITS:
                        st.markdown(f"- **{habit}**: {'✅' if row.get(habit, 0) == 1 else '❌'}")
                    if pd.notna(row.get('Catatan')) and row.get('Catatan'):
                        st.info(f"**Catatan**: {row['Catatan']}")
                    c1, c2 = st.columns([1,1])
                    if c1.button("✏️ Edit", key=f"edit_{row['Tanggal']}"):
                        st.session_state.edit_date = row['Tanggal']
                        st.rerun()
                    if c2.button("🗑️ Hapus", key=f"del_{row['Tanggal']}"):
                        st.session_state.confirm_delete_date = row['Tanggal']
                        st.rerun()
        else:
            st.warning("Belum ada data jurnal untuk dikelola.")

with main_tabs[3]:
    st.header(f"Unduh Laporan Progress - {username}")
    if df.empty:
        st.warning("Tidak ada data untuk diunduh.")
    else:
        df_display = df.copy()
        df_display['Tanggal'] = pd.to_datetime(df_display['Tanggal']).dt.strftime('%Y-%m-%d')
        if 'User' in df_display.columns:
            df_display = df_display.drop(columns=['User'])
        st.dataframe(df_display.sort_values("Tanggal", ascending=False))
        c1, c2 = st.columns(2)
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f'Progress_{username}')
        c1.download_button("📥 Unduh Semua Data (Excel)", output_excel.getvalue(), f"semua_progress_{username}.xlsx")
        pdf_data = df_to_pdf(df, f"Laporan Lengkap - {username}")
        c2.download_button("📄 Unduh Semua Data (PDF)", pdf_data, f"semua_progress_{username}.pdf")