import base64
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from flask import Flask, request, session
from PIL import Image, ImageDraw

app = Flask(__name__)
app.secret_key = "mmrugat-secret-key"

DATA_FILE = "SEATING PLAN MMR PENGHARGAAN 2026 2.csv"
ATTENDANCE_FILE = "attendance_records.csv"

LOGO_UGAT = "Logo-UGAT.png"
CENTER_IMAGE = "LAYOUT SUSUNAN.png"

HOST_PASSWORD = "host123"
REQUIRED_COLS = ["BIL", "NOTEN", "NAMA", "MENU", "MEJA"]


def clean_csv(df_raw):
    df_raw = df_raw.dropna(how="all").reset_index(drop=True)
    df_raw.columns = [str(col).strip().upper() for col in df_raw.columns]

    if all(col in df_raw.columns for col in REQUIRED_COLS):
        df = df_raw.copy()
    else:
        header_row_index = None

        for i in range(len(df_raw)):
            row_values = [str(value).strip().upper() for value in df_raw.iloc[i].tolist()]

            if all(col in row_values for col in REQUIRED_COLS):
                header_row_index = i
                break

        if header_row_index is None:
            return pd.DataFrame()

        headers = [str(value).strip().upper() for value in df_raw.iloc[header_row_index].tolist()]
        df = df_raw.iloc[header_row_index + 1:].copy()
        df.columns = headers

    df = df.loc[:, df.columns.notna()]
    df = df.loc[:, [str(col).strip() != "" for col in df.columns]]
    df = df.loc[:, ~df.columns.astype(str).str.upper().str.startswith("UNNAMED")]
    df = df.dropna(how="all").reset_index(drop=True)
    df.columns = [str(col).strip().upper() for col in df.columns]

    for col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()

    for col in ["BIL", "NOTEN", "MEJA"]:
        if col in df.columns:
            df[col] = df[col].str.replace(".0", "", regex=False)

    if "MEJA" in df.columns:
        df["MEJA"] = df["MEJA"].str.upper()

    return df


def load_data():
    if not Path(DATA_FILE).exists():
        return pd.DataFrame()

    df_raw = pd.read_csv(DATA_FILE, encoding="utf-8")
    return clean_csv(df_raw)


def load_attendance():
    if Path(ATTENDANCE_FILE).exists():
        try:
            df = pd.read_csv(ATTENDANCE_FILE)
            df.columns = [str(col).strip().upper() for col in df.columns]

            for col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()

            if "NOTEN" in df.columns:
                df["NOTEN"] = df["NOTEN"].str.replace(".0", "", regex=False)

            return df
        except Exception:
            pass

    return pd.DataFrame(columns=[
        "BIL", "NOTEN", "NAMA", "MENU", "MEJA",
        "STATUS_KEHADIRAN", "TARIKH_MASA"
    ])


def save_attendance(attendance_df):
    attendance_df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8")


def reset_attendance():
    reset_df = pd.DataFrame(columns=[
        "BIL", "NOTEN", "NAMA", "MENU", "MEJA",
        "STATUS_KEHADIRAN", "TARIKH_MASA"
    ])
    reset_df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8")


def get_base64_image(image_path):
    path = Path(image_path)

    if not path.exists():
        return ""

    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def get_updated_time():
    files = [Path(DATA_FILE), Path(ATTENDANCE_FILE)]
    files = [f for f in files if f.exists()]

    if not files:
        return "Tiada rekod"

    latest_file = max(files, key=lambda x: x.stat().st_mtime)
    latest_time = datetime.fromtimestamp(
        latest_file.stat().st_mtime,
        ZoneInfo("Asia/Kuala_Lumpur")
    )

    return latest_time.strftime("%d/%m/%Y %I:%M:%S %p")


def table_html(df):
    if df.empty:
        return "<div class='warning'>Tiada data.</div>"

    return df.to_html(index=False, escape=False, classes="data-table")


def generate_seat_map():
    seat_map = {}

    row_y = {
        "FL": 28,
        "FR": 84,
        "EL": 112,
        "ER": 168,
        "DL": 196,
        "DR": 252,
        "CL": 308,
        "CR": 364,
        "BL": 392,
        "BR": 448,
        "AL": 476,
        "AR": 532,
    }

    start_x = 70
    gap_x = 50

    for prefix, y in row_y.items():
        for seat_no in range(20, 0, -1):
            x = start_x + (20 - seat_no) * gap_x
            seat_id = f"{prefix}{seat_no}"

            seat_map[seat_id] = {
                "x": x,
                "y": y,
                "w": 30,
                "h": 18
            }

    right_side_positions = {
        "18": (1155, 42),
        "16": (1155, 70),
        "14": (1155, 98),
        "12": (1155, 126),
        "10": (1155, 154),
        "8": (1155, 182),
        "6": (1155, 210),
        "4": (1155, 238),
        "2": (1155, 266),
        "1": (1155, 294),
        "3": (1155, 322),
        "5": (1155, 350),
        "7": (1155, 378),
        "9": (1155, 406),
        "11": (1155, 434),
        "13": (1155, 462),
        "15": (1155, 490),
        "17": (1155, 518),
    }

    for meja, (x, y) in right_side_positions.items():
        seat_map[meja] = {
            "x": x,
            "y": y,
            "w": 24,
            "h": 18
        }

    return seat_map


def generate_highlighted_layout(group_df):
    path = Path(CENTER_IMAGE)

    if not path.exists():
        return "", []

    image = Image.open(path).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    seat_map = generate_seat_map()

    meja_list = (
        group_df["MEJA"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
    )

    missing_meja = []

    for meja in meja_list:
        if meja in seat_map:
            info = seat_map[meja]

            x = info["x"]
            y = info["y"]
            w = info["w"]
            h = info["h"]

            draw.rectangle(
                [x - w // 2, y - h // 2, x + w // 2, y + h // 2],
                fill=(255, 0, 0, 90),
                outline=(255, 0, 0, 255),
                width=4
            )
        else:
            missing_meja.append(meja)

    highlighted = Image.alpha_composite(image, overlay)
    temp_file = "highlighted_layout.png"
    highlighted.convert("RGB").save(temp_file)

    return get_base64_image(temp_file), missing_meja


def submit_attendance_for_search(search_no):
    df = load_data()
    attendance_df = load_attendance()

    result_df = df[
        df["NOTEN"].astype(str).str.contains(search_no, case=False, na=False)
    ].copy()

    if result_df.empty:
        return "<div class='warning'>Tiada rekod dijumpai untuk nombor tentera tersebut.</div>"

    bil_value = str(result_df.iloc[0]["BIL"]).strip()
    group_df = df[df["BIL"].astype(str).str.strip() == bil_value].copy()

    hadir_noten = []

    if not attendance_df.empty and "NOTEN" in attendance_df.columns:
        hadir_noten = attendance_df["NOTEN"].astype(str).str.strip().tolist()

    new_records = []

    for _, row in group_df.iterrows():
        noten = str(row["NOTEN"]).strip()

        if noten not in hadir_noten:
            new_records.append({
                "BIL": row["BIL"],
                "NOTEN": row["NOTEN"],
                "NAMA": row["NAMA"],
                "MENU": row["MENU"],
                "MEJA": row["MEJA"],
                "STATUS_KEHADIRAN": "HADIR",
                "TARIKH_MASA": datetime.now(
                    ZoneInfo("Asia/Kuala_Lumpur")
                ).strftime("%Y-%m-%d %H:%M:%S")
            })

    if new_records:
        attendance_df = pd.concat(
            [attendance_df, pd.DataFrame(new_records)],
            ignore_index=True
        )
        save_attendance(attendance_df)
        return "<div class='success'>Kehadiran berjaya direkodkan.</div>"

    return "<div class='info'>Semua dalam BIL ini telah ditandakan hadir.</div>"


def build_sidebar(message="", search_no=""):
    host_logged_in = session.get("host_logged_in", False)

    if not host_logged_in:
        return f"""
        <aside class="sidebar">
            <h2>Host Panel</h2>

            {message}

            <div class="side-card">
                <h3>Host Login</h3>

                <form method="POST">
                    <label>Kata Laluan Host</label>
                    <input type="password" name="password" placeholder="Masukkan kata laluan">
                    <button type="submit" name="action" value="host_login">
                        Login Host
                    </button>
                </form>
            </div>
        </aside>
        """

    submit_html = ""

    if search_no:
        submit_html = f"""
      result_content = f"""
<div class="card">
    <div class="success">Rekod dijumpai. BIL: {bil_value}</div>

    <h2>Maklumat Kehadiran</h2>
    <div class="table-wrap">
        {table_html(group_df[display_cols])}
    </div>

    {layout_html}
    {missing_html}

    <div class="info">Last Updated: {get_updated_time()}</div>

    {message_status}
</div>
"""

    return f"""
    <aside class="sidebar">
        <h2>Host Panel</h2>

        {message}

        <div class="side-card">
            <h3>Status Host</h3>
            <div class="success">Anda login sebagai host.</div>

            <form method="POST">
                <button type="submit" name="action" value="host_logout">
                    Logout Host
                </button>
            </form>
        </div>

        <div class="side-card">
            <h3>Upload CSV Baru</h3>

            <form method="POST" enctype="multipart/form-data">
                <input type="file" name="csv_file" accept=".csv">
                <button type="submit" name="action" value="upload_csv">
                    Upload CSV & Reset Kehadiran
                </button>
            </form>
        </div>

        {submit_html}

        <div class="side-card">
            <h3>Admin</h3>
            <a class="side-link" href="/admin">Lihat Live Attendance</a>
            <a class="side-link" href="/">Kembali ke Carian</a>
        </div>
    </aside>
    """


def html_page(content, sidebar_message="", search_no=""):
    logo = get_base64_image(LOGO_UGAT)

    if logo:
        logo_html = f'<img src="data:image/png;base64,{logo}" class="logo">'
    else:
        logo_html = '<div class="logo-text">⚓</div>'

    sidebar = build_sidebar(sidebar_message, search_no)

    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>MMR KPA (GAJI)</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #070b16;
            color: white;
        }}

        .menu-btn {{
            position: fixed;
            top: 16px;
            left: 16px;
            z-index: 10000;
            background: #2563eb;
            color: white;
            border: none;
            width: 48px;
            height: 48px;
            border-radius: 12px;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 8px 24px rgba(0,0,0,0.35);
        }}

        .layout {{
            display: flex;
            min-height: 100vh;
        }}

        .sidebar {{
            width: 300px;
            background: #020617;
            border-right: 1px solid #1e3a5f;
            padding: 80px 20px 20px 20px;
            position: fixed;
            top: 0;
            left: 0;
            height: 100vh;
            overflow-y: auto;
            transition: transform 0.3s ease;
            z-index: 9999;
        }}

        .layout.sidebar-closed .sidebar {{
            transform: translateX(-100%);
        }}

        .main {{
            flex: 1;
            padding: 24px;
            margin-left: 300px;
            transition: margin-left 0.3s ease;
        }}

        .layout.sidebar-closed .main {{
            margin-left: 0;
        }}

        .sidebar h2 {{
            color: #38bdf8;
            margin-top: 0;
        }}

        .side-card {{
            background: #0d1320;
            border: 1px solid #1e3a5f;
            padding: 16px;
            border-radius: 16px;
            margin-bottom: 18px;
        }}

        .side-card h3 {{
            margin-top: 0;
            color: white;
        }}

        .side-link {{
            display: block;
            color: white;
            text-decoration: none;
            background: #1d4ed8;
            padding: 12px;
            border-radius: 10px;
            margin-top: 10px;
            text-align: center;
            font-weight: bold;
        }}

        .side-note {{
            color: #94a3b8;
            font-size: 13px;
        }}

        .container {{
            max-width: 950px;
            margin: auto;
        }}

        .header {{
            display: flex;
            align-items: center;
            gap: 18px;
            background: linear-gradient(90deg, #020617, #111827);
            padding: 22px;
            border-radius: 18px;
            border: 1px solid #1e3a5f;
            margin-bottom: 24px;
        }}

        .logo {{
            width: 70px;
            height: 70px;
            object-fit: contain;
        }}

        .logo-text {{
            font-size: 55px;
        }}

        h1 {{
            margin: 0;
            font-size: 28px;
            line-height: 1.25;
        }}

        h2 {{
            color: #38bdf8;
            margin-top: 0;
        }}

        .card {{
            background: #0d1320;
            border: 1px solid #1e3a5f;
            padding: 22px;
            border-radius: 18px;
            margin-bottom: 22px;
        }}

        label {{
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }}

        input {{
            width: 100%;
            padding: 15px;
            border-radius: 12px;
            border: 1px solid #334155;
            background: #111827;
            color: white;
            font-size: 16px;
            margin-bottom: 14px;
        }}

        input[type="file"] {{
            padding: 12px;
        }}

        button {{
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 12px;
            background: #2563eb;
            color: white;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }}

        button:hover {{
            background: #1d4ed8;
        }}

        .success {{
            background: #14532d;
            border: 1px solid #22c55e;
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 18px;
        }}

        .warning {{
            background: #422006;
            border: 1px solid #f59e0b;
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 18px;
        }}

        .info {{
            background: #102a43;
            border: 1px solid #38bdf8;
            color: #60a5fa;
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 18px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            font-size: 14px;
        }}

        th, td {{
            padding: 10px;
            border: 1px solid #334155;
            text-align: left;
        }}

        th {{
            background: #1e3a8a;
        }}

        td {{
            background: #0f172a;
        }}

        .table-wrap {{
            overflow-x: auto;
        }}

        .layout-img {{
            width: 100%;
            border-radius: 14px;
            border: 1px solid #334155;
            margin-top: 12px;
        }}

        @media (max-width: 850px) {{
            .sidebar {{
                width: 320px;
                max-width: 88vw;
            }}

            .main {{
                margin-left: 0;
                padding: 80px 14px 14px 14px;
            }}

            .layout:not(.sidebar-closed) .main {{
                filter: brightness(0.7);
            }}

            h1 {{
                font-size: 21px;
            }}

            .header {{
                padding: 16px;
            }}

            .logo {{
                width: 55px;
                height: 55px;
            }}

            table {{
                font-size: 12px;
            }}
        }}
    </style>
</head>

<body>
    <button class="menu-btn" onclick="toggleSidebar()">☰</button>

    <div class="layout sidebar-closed" id="layout">
        {sidebar}

        <main class="main">
            <div class="container">
                <div class="header">
                    {logo_html}
                    <div>
                        <h1>Majlis Makan Malam Rejimental Penghargaan Brigedier Jeneral Dato' Zamzuri bin Harun</h1>
                    </div>
                </div>

                {content}
            </div>
        </main>
    </div>

    <script>
        function toggleSidebar() {{
            document.getElementById("layout").classList.toggle("sidebar-closed");
        }}
    </script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    sidebar_message = ""
    result_content = ""
    search_no = ""

    action = request.form.get("action", "")

    if request.method == "POST":
        if action == "host_login":
            password = request.form.get("password", "").strip()

            if password == HOST_PASSWORD:
                session["host_logged_in"] = True
                sidebar_message = "<div class='success'>Login host berjaya.</div>"
            else:
                sidebar_message = "<div class='warning'>Kata laluan host salah.</div>"

        elif action == "host_logout":
            session["host_logged_in"] = False
            sidebar_message = "<div class='info'>Host telah logout.</div>"

        elif action == "upload_csv":
            if not session.get("host_logged_in", False):
                sidebar_message = "<div class='warning'>Sila login host dahulu.</div>"
            else:
                uploaded_file = request.files.get("csv_file")

                if not uploaded_file or uploaded_file.filename == "":
                    sidebar_message = "<div class='warning'>Sila pilih fail CSV.</div>"
                else:
                    try:
                        df_raw = pd.read_csv(uploaded_file, encoding="utf-8")
                        new_df = clean_csv(df_raw)

                        missing_cols = [col for col in REQUIRED_COLS if col not in new_df.columns]

                        if missing_cols:
                            sidebar_message = f"""
                            <div class='warning'>
                                CSV baru tidak lengkap.<br>
                                Kolum tiada: {missing_cols}
                            </div>
                            """
                        else:
                            new_df.to_csv(DATA_FILE, index=False, encoding="utf-8")
                            reset_attendance()

                            sidebar_message = """
                            <div class='success'>
                                CSV baru berjaya dimuat naik.<br>
                                Rekod kehadiran telah direset.
                            </div>
                            """

                    except Exception as e:
                        sidebar_message = f"<div class='warning'>Fail tidak dapat dibaca: {e}</div>"

        elif action == "submit":
            search_no = request.form.get("search_no", "").strip()

            if not session.get("host_logged_in", False):
                sidebar_message = "<div class='warning'>Sila login host dahulu.</div>"
            elif not search_no:
                sidebar_message = "<div class='warning'>Cari No Tentera dahulu.</div>"
            else:
                sidebar_message = submit_attendance_for_search(search_no)

    df = load_data()
    attendance_df = load_attendance()

    if df.empty:
        content = f"""
        <div class="warning">
            Fail CSV tidak dijumpai atau format CSV salah.<br>
            Pastikan file ini wujud: <b>{DATA_FILE}</b>
        </div>
        """
        return html_page(content, sidebar_message, search_no)

    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]

    if missing_cols:
        content = f"""
        <div class="warning">
            Kolum berikut tiada dalam CSV: <b>{missing_cols}</b>
        </div>
        """
        return html_page(content, sidebar_message, search_no)

    if request.method == "POST" and action in ["search", "submit"]:
        if not search_no:
            search_no = request.form.get("search_no", "").strip()

        result_df = df[
            df["NOTEN"].astype(str).str.contains(search_no, case=False, na=False)
        ].copy()

        if result_df.empty:
            result_content = """
            <div class="warning">Tiada rekod dijumpai untuk nombor tentera tersebut.</div>
            """
        else:
            bil_value = str(result_df.iloc[0]["BIL"]).strip()
            group_df = df[df["BIL"].astype(str).str.strip() == bil_value].copy()

            attendance_df = load_attendance()

            hadir_noten = []
            if not attendance_df.empty and "NOTEN" in attendance_df.columns:
                hadir_noten = attendance_df["NOTEN"].astype(str).str.strip().tolist()

            sudah_hadir_semua = True

            for _, row in group_df.iterrows():
                noten = str(row["NOTEN"]).strip()
                if noten not in hadir_noten:
                    sudah_hadir_semua = False

            message_status = (
                "<div class='success'>✅ TELAH HADIR</div>"
                if sudah_hadir_semua
                else "<div class='warning'>❌ BELUM HADIR</div>"
            )

            display_cols = ["BIL", "NOTEN", "NAMA", "MENU", "MEJA"]

            if "CATATAN" in group_df.columns:
                display_cols.append("CATATAN")

            layout_base64, missing_meja = generate_highlighted_layout(group_df)

            if layout_base64:
                layout_html = f"""
                <h2>Pelan Kedudukan Dewan</h2>
                <img src="data:image/png;base64,{layout_base64}" class="layout-img">
                """
            else:
                layout_html = f"""
                <div class="warning">
                    Fail gambar layout tidak dijumpai: <b>{CENTER_IMAGE}</b>
                </div>
                """

            missing_html = ""
            if missing_meja:
                missing_html = f"""
                <div class="warning">
                    Meja ini belum ada coordinate dalam layout: {", ".join(missing_meja)}
                </div>
                """

  result_content = f"""
<div class="card">
    <div class="success">Rekod dijumpai. BIL: {bil_value}</div>

    <h2>Maklumat Kehadiran</h2>
    <div class="table-wrap">
        {table_html(group_df[display_cols])}
    </div>

    {layout_html}
    {missing_html}

    <div class="info">Last Updated: {get_updated_time()}</div>

    {message_status}

    <!-- Submit Kehadiran button appears here, after Host Login -->
    <div class="side-card">
        <h3>Submit Kehadiran</h3>
        <form method="POST">
            <input type="hidden" name="search_no" value="{search_no}">
            <button type="submit" name="action" value="submit">
                Submit / Tandakan Kehadiran
            </button>
        </form>
    </div>
</div>
"""

    content = f"""
    <div class="card">
        <h2>Carian Nombor Tentera</h2>

        <form method="POST">
            <label>Masukkan No Tentera</label>
            <input name="search_no" maxlength="10" placeholder="Contoh: 3004463" value="{search_no}">
            <button type="submit" name="action" value="search">Cari Kehadiran</button>
        </form>
    </div>

    {result_content}
    """

    return html_page(content, sidebar_message, search_no)


@app.route("/admin")
def admin():
    df = load_data()
    attendance_df = load_attendance()

    hadir_noten = []

    if not attendance_df.empty and "NOTEN" in attendance_df.columns:
        hadir_noten = attendance_df["NOTEN"].astype(str).str.strip().tolist()

    if not df.empty:
        belum_hadir_df = df[
            ~df["NOTEN"].astype(str).str.strip().isin(hadir_noten)
        ].copy()
    else:
        belum_hadir_df = pd.DataFrame()

    total_semua = len(df)
    total_hadir = len(attendance_df)
    total_belum = len(belum_hadir_df)

    belum_cols = ["BIL", "NOTEN", "NAMA", "MENU", "MEJA"]

    if not belum_hadir_df.empty and "CATATAN" in belum_hadir_df.columns:
        belum_cols.append("CATATAN")

    content = f"""
    <div class="card">
        <h2>📋 Live Attendance / Kehadiran Semasa</h2>

        <div class="info">Jumlah Keseluruhan: {total_semua}</div>
        <div class="success">Jumlah Telah Hadir: {total_hadir}</div>
        <div class="warning">Jumlah Belum Hadir: {total_belum}</div>

        <h2>✅ Telah Hadir</h2>
        <div class="table-wrap">
            {table_html(attendance_df)}
        </div>

        <h2>❌ Belum Hadir</h2>
        <div class="table-wrap">
            {table_html(belum_hadir_df[belum_cols]) if not belum_hadir_df.empty else "<div class='success'>Semua telah hadir.</div>"}
        </div>
    </div>
    """

    return html_page(content)


if __name__ == "__main__":
    app.run(debug=True)
