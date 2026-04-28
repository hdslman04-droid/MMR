import base64
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from flask import Flask, request, session
from PIL import Image, ImageDraw

app = Flask(__name__)
app.secret_key = "mmrugat-secret-key"

# Konfigurasi Fail
DATA_FILE = "SEATING PLAN MMR PENGHARGAAN 2026 2.csv"
ATTENDANCE_FILE = "attendance_records.csv"
LOGO_UGAT = "Logo-UGAT.png"
CENTER_IMAGE = "LAYOUT SUSUNAN.png"

HOST_PASSWORD = "host123"
REQUIRED_COLS = ["BIL", "NOTEN", "NAMA", "MENU", "MEJA"]

# --- FUNGSI PEMPROSESAN DATA ---

def clean_csv(df_raw):
    df_raw = df_raw.dropna(how="all").reset_index(drop=True)
    df_raw.columns = [str(col).strip().upper() for col in df_raw.columns]

    if not all(col in df_raw.columns for col in REQUIRED_COLS):
        header_row_index = None
        for i in range(len(df_raw)):
            row_values = [str(value).strip().upper() for value in df_raw.iloc[i].tolist()]
            if all(col in row_values for col in REQUIRED_COLS):
                header_row_index = i
                break
        
        if header_row_index is not None:
            headers = [str(value).strip().upper() for value in df_raw.iloc[header_row_index].tolist()]
            df = df_raw.iloc[header_row_index + 1:].copy()
            df.columns = headers
        else:
            return pd.DataFrame()
    else:
        df = df_raw.copy()

    df = df.loc[:, df.columns.notna()]
    df = df.dropna(how="all").reset_index(drop=True)
    df.columns = [str(col).strip().upper() for col in df.columns]

    for col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()
        if col in ["BIL", "NOTEN", "MEJA"]:
            df[col] = df[col].str.replace(".0", "", regex=False)
    
    return df

def load_data():
    if not Path(DATA_FILE).exists(): return pd.DataFrame()
    try:
        df_raw = pd.read_csv(DATA_FILE, encoding="utf-8")
        return clean_csv(df_raw)
    except:
        return pd.DataFrame()

def load_attendance():
    if Path(ATTENDANCE_FILE).exists():
        try:
            df = pd.read_csv(ATTENDANCE_FILE)
            df.columns = [str(col).strip().upper() for col in df.columns]
            for col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()
            return df
        except: pass
    return pd.DataFrame(columns=REQUIRED_COLS + ["STATUS_KEHADIRAN", "TARIKH_MASA"])

def save_attendance(attendance_df):
    attendance_df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8")

def reset_attendance():
    pd.DataFrame(columns=REQUIRED_COLS + ["STATUS_KEHADIRAN", "TARIKH_MASA"]).to_csv(ATTENDANCE_FILE, index=False)

def get_base64_image(image_path):
    path = Path(image_path)
    if not path.exists(): return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def get_updated_time():
    files = [f for f in [Path(DATA_FILE), Path(ATTENDANCE_FILE)] if f.exists()]
    if not files: return "Tiada rekod"
    latest_file = max(files, key=lambda x: x.stat().st_mtime)
    latest_time = datetime.fromtimestamp(latest_file.stat().st_mtime, ZoneInfo("Asia/Kuala_Lumpur"))
    return latest_time.strftime("%d/%m/%Y %I:%M:%S %p")

# --- FUNGSI GRAFIK & LAYOUT ---

def generate_seat_map():
    seat_map = {}
    row_y = {"FL": 28, "FR": 84, "EL": 112, "ER": 168, "DL": 196, "DR": 252, "CL": 308, "CR": 364, "BL": 392, "BR": 448, "AL": 476, "AR": 532}
    start_x, gap_x = 70, 50
    for prefix, y in row_y.items():
        for seat_no in range(20, 0, -1):
            x = start_x + (20 - seat_no) * gap_x
            seat_map[f"{prefix}{seat_no}"] = {"x": x, "y": y, "w": 30, "h": 18}
    
    right_side = {"18":(1155,42),"16":(1155,70),"14":(1155,98),"12":(1155,126),"10":(1155,154),"8":(1155,182),"6":(1155,210),"4":(1155,238),"2":(1155,266),"1":(1155,294),"3":(1155,322),"5":(1155,350),"7":(1155,378),"9":(1155,406),"11":(1155,434),"13":(1155,462),"15":(1155,490),"17":(1155,518)}
    for meja, (x, y) in right_side.items():
        seat_map[meja] = {"x": x, "y": y, "w": 24, "h": 18}
    return seat_map

def generate_highlighted_layout(group_df):
    path = Path(CENTER_IMAGE)
    if not path.exists(): return "", []
    image = Image.open(path).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    seat_map = generate_seat_map()
    meja_list = group_df["MEJA"].dropna().astype(str).str.strip().str.upper().unique()
    missing_meja = []
    for meja in meja_list:
        if meja in seat_map:
            info = seat_map[meja]
            draw.rectangle([info["x"]-info["w"]//2, info["y"]-info["h"]//2, info["x"]+info["w"]//2, info["y"]+info["h"]//2], fill=(255, 0, 0, 90), outline=(255, 0, 0, 255), width=4)
        else: missing_meja.append(meja)
    highlighted = Image.alpha_composite(image, overlay)
    temp_file = "highlighted_layout.png"
    highlighted.convert("RGB").save(temp_file)
    return get_base64_image(temp_file), missing_meja

# --- LOGIK SISTEM ---

def submit_attendance_for_search(search_no):
    df = load_data()
    attendance_df = load_attendance()
    result_df = df[df["NOTEN"].astype(str).str.contains(search_no, case=False, na=False)].copy()
    if result_df.empty: return "<div class='warning'>Tiada rekod dijumpai.</div>"
    
    bil_value = str(result_df.iloc[0]["BIL"]).strip()
    group_df = df[df["BIL"].astype(str).str.strip() == bil_value].copy()
    hadir_noten = attendance_df["NOTEN"].astype(str).str.strip().tolist() if not attendance_df.empty else []
    
    new_records = []
    for _, row in group_df.iterrows():
        if str(row["NOTEN"]).strip() not in hadir_noten:
            new_records.append({**row.to_dict(), "STATUS_KEHADIRAN": "HADIR", "TARIKH_MASA": datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).strftime("%Y-%m-%d %H:%M:%S")})
    
    if new_records:
        attendance_df = pd.concat([attendance_df, pd.DataFrame(new_records)], ignore_index=True)
        save_attendance(attendance_df)
        return "<div class='success'>Kehadiran berjaya direkodkan.</div>"
    return "<div class='info'>Semua dalam BIL ini telah hadir.</div>"

# --- HTML TEMPLATE ---

def html_page(content, sidebar_message="", search_no=""):
    logo = get_base64_image(LOGO_UGAT)
    logo_html = f'<img src="data:image/png;base64,{logo}" class="logo">' if logo else '<div class="logo-text">⚓</div>'
    host_status = session.get("host_logged_in", False)
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>MMR KPA (GAJI)</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ margin: 0; font-family: Arial, sans-serif; background: #070b16; color: white; }}
        .menu-btn {{ position: fixed; top: 16px; left: 16px; z-index: 10000; background: #2563eb; color: white; border: none; width: 48px; height: 48px; border-radius: 12px; font-size: 24px; cursor: pointer; }}
        .layout {{ display: flex; min-height: 100vh; }}
        .sidebar {{ width: 300px; background: #020617; border-right: 1px solid #1e3a5f; padding: 80px 20px 20px; position: fixed; height: 100vh; transition: 0.3s; z-index: 9999; }}
        .layout.sidebar-closed .sidebar {{ transform: translateX(-100%); }}
        .main {{ flex: 1; padding: 24px; margin-left: 300px; transition: 0.3s; }}
        .layout.sidebar-closed .main {{ margin-left: 0; }}
        .header {{ display: flex; align-items: center; gap: 18px; background: linear-gradient(90deg, #020617, #111827); padding: 22px; border-radius: 18px; border: 1px solid #1e3a5f; margin-bottom: 24px; }}
        .logo {{ width: 75px; height: 75px; object-fit: contain; }}
        h1 {{ margin: 0; font-size: 22px; line-height: 1.4; color: white; }}
        .card {{ background: #0d1320; border: 1px solid #1e3a5f; padding: 22px; border-radius: 18px; margin-bottom: 22px; }}
        .search-label {{ color: #38bdf8; font-weight: bold; display: block; margin-bottom: 10px; font-size: 14px; }}
        input {{ width: 100%; padding: 15px; border-radius: 12px; border: 1px solid #334155; background: #111827; color: white; font-size: 16px; margin-bottom: 14px; }}
        button {{ width: 100%; padding: 15px; border: none; border-radius: 12px; background: #2563eb; color: white; font-weight: bold; cursor: pointer; }}
        .btn-submit-main {{ background: #059669 !important; margin-top: 15px; }}
        .success {{ background: #14532d; border: 1px solid #22c55e; padding: 15px; border-radius: 12px; margin-bottom: 18px; }}
        .warning {{ background: #422006; border: 1px solid #f59e0b; padding: 15px; border-radius: 12px; margin-bottom: 18px; }}
        .info {{ background: #102a43; border: 1px solid #38bdf8; color: #60a5fa; padding: 15px; border-radius: 12px; margin-bottom: 18px; }}
        .table-wrap {{ overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        th, td {{ padding: 10px; border: 1px solid #334155; text-align: left; }}
        th {{ background: #1e3a8a; }}
        td {{ background: #0f172a; }}
        .layout-section {{ margin-top: 60px; padding-top: 30px; border-top: 1px dashed #1e3a5f; }}
        .layout-img {{ width: 100%; border-radius: 14px; border: 1px solid #334155; }}
        .side-card {{ background: #0d1320; border: 1px solid #1e3a5f; padding: 16px; border-radius: 16px; margin-bottom: 18px; }}
        @media (max-width: 850px) {{ .sidebar {{ width: 85%; }} .main {{ margin-left: 0; padding-top: 80px; }} h1 {{ font-size: 18px; }} }}
    </style>
</head>
<body>
    <button class="menu-btn" onclick="toggleSidebar()">☰</button>
    <div class="layout sidebar-closed" id="layout">
        <aside class="sidebar">
            <h2>Host Panel</h2>
            {sidebar_message}
            <div class="side-card">
                <h3>{'Host Terlog Masuk' if host_status else 'Host Login'}</h3>
                <form method="POST">
                    {'<button type="submit" name="action" value="host_logout">Logout Host</button>' if host_status else 
                    '<input type="password" name="password" placeholder="Password"><button type="submit" name="action" value="host_login">Login Host</button>'}
                </form>
            </div>
            {f'<div class="side-card"><h3>Admin</h3><a style="color:white;text-decoration:none;display:block;background:#1d4ed8;padding:10px;border-radius:8px;text-align:center" href="/admin">Live Attendance</a></div>' if host_status else ''}
        </aside>
        <main class="main">
            <div class="header">
                {logo_html}
                <div>
                    <h1>Majlis Makan Malam Rejimental Penghargaan<br>Brigedier Jeneral Dato' Zamzuri bin Harun</h1>
                </div>
            </div>
            {content}
        </main>
    </div>
    <script>function toggleSidebar() {{ document.getElementById("layout").classList.toggle("sidebar-closed"); }}</script>
</body>
</html>
"""

# --- ROUTES ---

@app.route("/", methods=["GET", "POST"])
def home():
    sidebar_message, result_content, search_no = "", "", ""
    action = request.form.get("action", "")

    if request.method == "POST":
        if action == "host_login":
            if request.form.get("password") == HOST_PASSWORD:
                session["host_logged_in"] = True
                sidebar_message = "<div class='success'>Login Berjaya.</div>"
            else: sidebar_message = "<div class='warning'>Password Salah.</div>"
        elif action == "host_logout":
            session["host_logged_in"] = False
        elif action == "submit":
            search_no = request.form.get("search_no", "").strip()
            if session.get("host_logged_in"):
                sidebar_message = submit_attendance_for_search(search_no)

    df = load_data()
    if df.empty:
        return html_page("<div class='warning'>Fail CSV tidak dijumpai.</div>", sidebar_message)

    if request.method == "POST" and action in ["search", "submit"]:
        search_no = request.form.get("search_no", "").strip()
        result_df = df[df["NOTEN"].astype(str).str.contains(search_no, case=False, na=False)].copy()

        if result_df.empty:
            result_content = "<div class='warning'>Tiada rekod dijumpai untuk nombor tentera tersebut.</div>"
        else:
            bil_val = str(result_df.iloc[0]["BIL"]).strip()
            group_df = df[df["BIL"].astype(str).str.strip() == bil_val].copy()
            attendance_df = load_attendance()
            hadir_list = attendance_df["NOTEN"].astype(str).tolist() if not attendance_df.empty else []
            sudah_hadir = all(str(r["NOTEN"]).strip() in hadir_list for _, r in group_df.iterrows())

            quick_btn = f"""<form method="POST"><input type="hidden" name="search_no" value="{search_no}"><button type="submit" name="action" value="submit" class="btn-submit-main">Tandakan Kehadiran (BIL: {bil_val})</button></form>""" if session.get("host_logged_in") and not sudah_hadir else ""
            
            layout_b64, missing = generate_highlighted_layout(group_df)
            layout_html = f'<div class="layout-section"><h2>Pelan Kedudukan Dewan</h2><img src="data:image/png;base64,{layout_b64}" class="layout-img"></div>' if layout_b64 else ""

            result_content = f"""
            <div class="card">
                <h2>Maklumat Kedudukan</h2>
                <div class="table-wrap">{group_df[REQUIRED_COLS].to_html(index=False, classes="data-table")}</div>
                {quick_btn}
                <div class="info" style="margin-top:15px;">Kemaskini Terakhir: {get_updated_time()}</div>
                {"<div class='success'>✅ TELAH HADIR</div>" if sudah_hadir else "<div class='warning'>❌ BELUM HADIR</div>"}
                {layout_html}
            </div>
            """

    content = f"""
    <div class="card">
        <form method="POST">
            <label class="search-label">MASUKKAN NOMBOR TENTERA</label>
            <input name="search_no" placeholder="Contoh: 3004463" value="{search_no}">
            <button type="submit" name="action" value="search">Cari Kehadiran</button>
        </form>
    </div>
    {result_content}
    """
    return html_page(content, sidebar_message, search_no)

@app.route("/admin")
def admin():
    if not session.get("host_logged_in"): return "Akses Ditolak"
    df, att_df = load_data(), load_attendance()
    hadir_noten = att_df["NOTEN"].tolist() if not att_df.empty else []
    belum_df = df[~df["NOTEN"].isin(hadir_noten)] if not df.empty else pd.DataFrame()
    
    content = f"""
    <div class="card">
        <h2>📋 Ringkasan Kehadiran</h2>
        <div class="info">Jumlah Keseluruhan: {len(df)}</div>
        <div class="success">Telah Hadir: {len(att_df)}</div>
        <div class="warning">Belum Hadir: {len(belum_df)}</div>
        <h2>✅ Senarai Hadir</h2>
        <div class="table-wrap">{att_df.to_html(index=False)}</div>
    </div>
    """
    return html_page(content)

if __name__ == "__main__":
    app.run(debug=True)
