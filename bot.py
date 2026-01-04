import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Google Sheets setup
SHEET_ID = "1yPXXNyXGNFV_s9kEF6N-bco60lpiPdOTcjnnb0Pwtow"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Column mapping (1-indexed for gspread)
COL_CRITICAL = 1  # A - Critical/Non-Crit (formula)
COL_GM = 2  # B - GM Service (formula)
COL_D = 4  # D - Oxygen Support (formula)
COL_DISPO = 6  # F - Disposition
COL_WARD_BED = 8  # H - Ward-Bed
COL_PATIENT = 9  # I - Patient Entry
COL_JRIC = 10  # J - JRIC Name
COL_CWI = 11  # K - Current Working Impression

# Conversation states
(GM_SERVICE, LAST_NAME, O2_SUPPORT, COVID_STATUS, CASE_NUMBER, 
 PASSCODE, WARD, BED, JRIC, SPECIAL_CATS, DISPO_TYPE, CWI,
 DISPO_SELECT, DISPO_PATIENT, SERVICE_REPORT, GALAWARDS_INPUTS, SEARCH_QUERY) = range(17)

# Special categories mapping
SPECIAL_CATS_MAP = {
    '🕊': 'pending mort',
    '🏥': 'hospitalist',
    '💦': 'dialytic/possible HD',
    '🐀': 'Lepto',
    '🚨': 'Advanced airway (ET/BIPAP/HFNC)',
    '🫀': 'ACS',
    '🪼': 'DKA/HHS',
    '✨': 'New',
    '📺': 'TB',
    '😱': 'Shock',
    '🔪': 'Surgical',
    '🦶': 'DFI',
    '🦠': 'COVID',
    '🌊': 'Overflow'
}

DISPO_OPTIONS = [
    "OLD", "ADMITTED", "HOME", "TOS IN", "TRANS IN FROM ICU",
    "MORT", "TOS OUT", "TRANS OUT TO ICU", "HAMA/HPR", "THOC", "ABSCOND"
]

def get_sheet():
    """Initialize and return Google Sheets client"""
    try:
        # Check if credentials are in environment variable (for Railway/cloud deployment)
        if os.environ.get('GOOGLE_CREDENTIALS_BASE64'):
            import json
            import base64
            # Decode base64 credentials
            creds_json = base64.b64decode(os.environ.get('GOOGLE_CREDENTIALS_BASE64')).decode('utf-8')
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        elif os.environ.get('GOOGLE_CREDENTIALS'):
            import json
            creds_dict = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            # Use credentials.json file (for local deployment)
            creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID)
        return sheet.worksheet('Template [Edit Here ONLY]')
    except Exception as e:
        print(f"Error initializing Google Sheets: {e}")
        raise

def get_all_patients():
    """Get all patient data from the sheet"""
    try:
        ws = get_sheet()
        all_values = ws.get_all_values()
        
        # Skip header row (assuming row 1 is header)
        patients = []
        for idx, row in enumerate(all_values[1:], start=2):
            # Make sure row has enough columns and patient data exists
            if len(row) > COL_PATIENT and row[COL_PATIENT-1] and str(row[COL_PATIENT-1]).strip():
                patients.append({
                    'row': idx,
                    'critical': row[COL_CRITICAL-1] if len(row) >= COL_CRITICAL and row[COL_CRITICAL-1] else '',
                    'gm_service': row[COL_GM-1] if len(row) >= COL_GM and row[COL_GM-1] else '',
                    'o2_support': row[COL_D-1] if len(row) >= COL_D and row[COL_D-1] else '',
                    'dispo': row[COL_DISPO-1] if len(row) >= COL_DISPO and row[COL_DISPO-1] else '',
                    'ward_bed': row[COL_WARD_BED-1] if len(row) >= COL_WARD_BED and row[COL_WARD_BED-1] else '',
                    'patient': str(row[COL_PATIENT-1]).strip(),
                    'jric': row[COL_JRIC-1] if len(row) >= COL_JRIC and row[COL_JRIC-1] else '',
                    'cwi': row[COL_CWI-1] if len(row) >= COL_CWI and row[COL_CWI-1] else ''
                })
        
        return patients
    except Exception as e:
        print(f"Error in get_all_patients: {e}")
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text(
        "Welcome to Patient Census Bot! 🏥\n\n"
        "Available commands:\n"
        "/add - Add a new patient\n"
        "/dispo - Update patient disposition\n"
        "/search - Search for a patient\n"
        "/servicereport - Generate service report\n"
        "/galawardsreport - Generate Gala Wards report\n"
        "/cancel - Cancel current operation"
    )

# ============ ADD PATIENT HANDLERS ============

async def add_patient_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the add patient conversation"""
    await update.message.reply_text("Please enter the GM service number (e.g., 1, 2, 3, etc.):")
    return GM_SERVICE

async def gm_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service_num = update.message.text.strip()
    # Add GM prefix if not included
    if not service_num.upper().startswith('GM'):
        service_num = f"GM{service_num}"
    context.user_data['gm_service'] = service_num
    await update.message.reply_text("Enter patient's Last Name:")
    return LAST_NAME

async def last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_name'] = update.message.text.strip()
    await update.message.reply_text("Enter Oxygen Support:")
    return O2_SUPPORT

async def o2_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['o2_support'] = update.message.text.strip()
    await update.message.reply_text("Enter COVID Status:")
    return COVID_STATUS

async def covid_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['covid_status'] = update.message.text.strip()
    await update.message.reply_text("Enter Case Number:")
    return CASE_NUMBER

async def case_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['case_number'] = update.message.text.strip()
    await update.message.reply_text("Enter Passcode:")
    return PASSCODE

async def passcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['passcode'] = update.message.text.strip()
    await update.message.reply_text("Enter Ward:")
    return WARD

async def ward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ward'] = update.message.text.strip()
    await update.message.reply_text("Enter Bed:")
    return BED

async def bed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bed'] = update.message.text.strip()
    await update.message.reply_text("Enter JRIC:")
    return JRIC

async def jric(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['jric'] = update.message.text.strip()
    
    # Ask for disposition type
    keyboard = [
        [InlineKeyboardButton("ADMITTED", callback_data="dtype_ADMITTED")],
        [InlineKeyboardButton("TOS IN", callback_data="dtype_TOS IN")],
        [InlineKeyboardButton("TRANS IN FROM ICU", callback_data="dtype_TRANS IN FROM ICU")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Select the patient type:",
        reply_markup=reply_markup
    )
    return DISPO_TYPE

async def dispo_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    dispo_type = query.data.replace("dtype_", "")
    context.user_data['dispo_type'] = dispo_type
    
    await query.edit_message_text(f"Patient type set to: {dispo_type}\n\nEnter Current Working Impression:")
    return CWI

async def cwi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cwi'] = update.message.text.strip()
    context.user_data['special_cats'] = []
    
    # Create inline keyboard for special categories
    keyboard = []
    for emoji, desc in SPECIAL_CATS_MAP.items():
        keyboard.append([InlineKeyboardButton(f"{emoji} - {desc}", callback_data=emoji)])
    keyboard.append([InlineKeyboardButton("✅ Done", callback_data="done")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Select Special Categories (you can select multiple):",
        reply_markup=reply_markup
    )
    return SPECIAL_CATS

async def special_cats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "done":
        # Format the patient entry
        data = context.user_data
        special_cats_str = ' '.join(data.get('special_cats', []))
        
        patient_entry = (
            f"{data['gm_service']}/{data['last_name']} "
            f"({data['o2_support']}/{data['covid_status']}) - "
            f"{data['case_number']}/{data['passcode']} - "
            f"{data['ward']}-{data['bed']} [{data['jric']}] {special_cats_str}"
        ).strip()
        
        # Add to Google Sheet
        try:
            ws = get_sheet()
            # Find the next empty row
            all_values = ws.get_all_values()
            next_row = len(all_values) + 1
            
            # Check if we need to add more rows
            if next_row > ws.row_count:
                rows_to_add = 50  # Add 50 rows at a time
                ws.add_rows(rows_to_add)
            
            # Column A: Critical/Non-Crit formula
            formula_a = f'=IF(I{next_row}="", "", IF(OR(ISNUMBER(SEARCH("🚨", I{next_row})), ISNUMBER(SEARCH("😱", I{next_row}))), "Critical", "Non-Crit"))'
            
            # Column B: Extract GM service formula
            formula_b = f'=IF(I{next_row}="","",LEFT(I{next_row},3))'
            
            # Column D: Extract O2 support formula
            formula_d = f'=IF(REGEXMATCH(I{next_row}, "\\(?(RA|NC|FM|TM|NRM|HFNC|BIPAP|ET)/"), REGEXEXTRACT(I{next_row}, "\\(?(RA|NC|FM|TM|NRM|HFNC|BIPAP|ET)"), "")'
            
            # Update all cells
            ws.update_cell(next_row, COL_CRITICAL, formula_a)
            ws.update_cell(next_row, COL_GM, formula_b)
            ws.update_cell(next_row, COL_D, formula_d)
            ws.update_cell(next_row, COL_DISPO, data['dispo_type'])
            ws.update_cell(next_row, COL_WARD_BED, f"{data['ward']}-{data['bed']}")
            ws.update_cell(next_row, COL_PATIENT, patient_entry)
            ws.update_cell(next_row, COL_JRIC, data['jric'])
            ws.update_cell(next_row, COL_CWI, data['cwi'])
            
            await query.edit_message_text(f"✅ Patient added successfully!\n\n{patient_entry}\n\nDisposition: {data['dispo_type']}\nCWI: {data['cwi']}")
        except Exception as e:
            await query.edit_message_text(f"❌ Error adding patient: {str(e)}")
        
        context.user_data.clear()
        return ConversationHandler.END
    else:
        # Toggle special category
        if query.data in context.user_data['special_cats']:
            context.user_data['special_cats'].remove(query.data)
        else:
            context.user_data['special_cats'].append(query.data)
        
        # Update keyboard to show selected items
        keyboard = []
        for emoji, desc in SPECIAL_CATS_MAP.items():
            selected = "✓ " if emoji in context.user_data['special_cats'] else ""
            keyboard.append([InlineKeyboardButton(f"{selected}{emoji} - {desc}", callback_data=emoji)])
        keyboard.append([InlineKeyboardButton("✅ Done", callback_data="done")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)
        
        return SPECIAL_CATS

# ============ DISPOSITION HANDLERS ============

async def dispo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start disposition update - first select patient"""
    try:
        patients = get_all_patients()
        
        if not patients:
            await update.message.reply_text("No patients found in the sheet.")
            return ConversationHandler.END
        
        # Create keyboard with patient list
        keyboard = []
        for p in patients:
            # Show last name from patient entry
            display = p['patient'][:50] + "..." if len(p['patient']) > 50 else p['patient']
            keyboard.append([InlineKeyboardButton(display, callback_data=f"patient_{p['row']}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['patients'] = patients
        
        await update.message.reply_text(
            "Select a patient to update disposition:",
            reply_markup=reply_markup
        )
        return DISPO_PATIENT
    except Exception as e:
        await update.message.reply_text(f"Error loading patients: {str(e)}")
        return ConversationHandler.END

async def dispo_patient_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle patient selection for disposition"""
    query = update.callback_query
    await query.answer()
    
    row_num = int(query.data.replace("patient_", ""))
    context.user_data['selected_row'] = row_num
    
    # Show disposition options
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"dispo_{opt}")] for opt in DISPO_OPTIONS]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Select the disposition status:",
        reply_markup=reply_markup
    )
    return DISPO_SELECT

async def dispo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle disposition selection"""
    query = update.callback_query
    await query.answer()
    
    dispo = query.data.replace("dispo_", "")
    row_num = context.user_data.get('selected_row')
    
    try:
        ws = get_sheet()
        ws.update_cell(row_num, COL_DISPO, dispo)
        
        await query.edit_message_text(f"✅ Disposition updated to: {dispo}")
    except Exception as e:
        await query.edit_message_text(f"❌ Error updating disposition: {str(e)}")
    
    context.user_data.clear()
    return ConversationHandler.END

# ============ SEARCH HANDLERS ============

async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start search conversation"""
    await update.message.reply_text(
        "🔍 Search for a patient\n\n"
        "Enter search term (name, case number, ward, bed, JRIC, or any keyword):"
    )
    return SEARCH_QUERY

async def search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process search query"""
    query = update.message.text.strip()
    
    try:
        patients = get_all_patients()
        
        if not patients:
            await update.message.reply_text("No patients found in the sheet.")
            return ConversationHandler.END
        
        # Detect search type
        query_lower = query.lower()
        
        # Check if searching by GM service (e.g., GM1, GM2)
        if query_lower.startswith('gm') and len(query) <= 4:
            await search_by_gm_service(update, patients, query.upper())
            return ConversationHandler.END
        
        # Check if searching by JRIC
        jric_matches = [p for p in patients if p['jric'].lower() == query_lower]
        if jric_matches:
            await search_by_jric(update, jric_matches, query)
            return ConversationHandler.END
        
        # Search for individual patient (by name or case number)
        patient_matches = []
        for p in patients:
            # Search in patient string
            if query_lower in p['patient'].lower():
                patient_matches.append(p)
        
        if len(patient_matches) == 1:
            # Single patient match - show detailed view
            await search_single_patient(update, patient_matches[0])
        elif len(patient_matches) > 1:
            # Multiple matches - show list
            response = f"🔍 Found {len(patient_matches)} patient(s) matching '{query}':\n\n"
            for idx, p in enumerate(patient_matches[:15], 1):
                # Extract code from patient string
                code = extract_code(p['patient'])
                response += f"{idx}. {code}\n"
                if p['cwi']:
                    response += f"   {p['cwi']}\n"
                response += "\n"
            
            if len(patient_matches) > 15:
                response += f"... and {len(patient_matches) - 15} more results."
            
            await update.message.reply_text(response)
        else:
            await update.message.reply_text(f"No patients found matching: {query}")
        
    except Exception as e:
        await update.message.reply_text(f"Error during search: {str(e)}")
    
    return ConversationHandler.END

def extract_code(patient_str):
    """Extract the full patient entry from column I"""
    # Return the full patient string instead of just case number/passcode
    return patient_str

async def search_by_jric(update: Update, patients, jric_name):
    """Search by JRIC and display formatted results"""
    total_patients = len(patients)
    crit_patients = sum(1 for p in patients if p['critical'] == 'Critical')
    
    response = f"{jric_name} ({total_patients} | {crit_patients})\n"
    
    for p in patients:
        code = extract_code(p['patient'])
        response += f"{code}\n"
    
    await update.message.reply_text(response)

async def search_single_patient(update: Update, patient):
    """Display single patient details"""
    code = extract_code(patient['patient'])
    cwi = patient['cwi'] if patient['cwi'] else "No assessment available"
    
    response = f"{code}\n{cwi}"
    
    await update.message.reply_text(response)

async def search_by_gm_service(update: Update, patients, service):
    """Search by GM service and display formatted results"""
    service_patients = [p for p in patients if p['gm_service'] == service]
    
    if not service_patients:
        await update.message.reply_text(f"No patients found for {service}")
        return
    
    total_patients = len(service_patients)
    crit_patients = sum(1 for p in service_patients if p['critical'] == 'Critical')
    
    response = f"{service} ({total_patients} | {crit_patients})\n\n"
    
    # Group by JRIC
    jric_groups = {}
    for p in service_patients:
        jric = p['jric'] if p['jric'] else 'No JRIC'
        if jric not in jric_groups:
            jric_groups[jric] = []
        jric_groups[jric].append(p)
    
    # Display grouped by JRIC
    for jric, pts in sorted(jric_groups.items()):
        response += f"[{jric}]\n"
        for p in pts:
            code = extract_code(p['patient'])
            response += f"{code}\n"
        response += "\n"
    
    await update.message.reply_text(response)

# ============ SERVICE REPORT HANDLERS ============

async def service_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate service report"""
    await update.message.reply_text("Enter the GM service for the report (e.g., GM1):")
    return SERVICE_REPORT

async def generate_service_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = update.message.text.strip()
    
    try:
        patients = get_all_patients()
        
        if not patients:
            await update.message.reply_text("No patients found in the sheet.")
            return ConversationHandler.END
        
        service_patients = [p for p in patients if p['gm_service'] == service]
        
        if not service_patients:
            await update.message.reply_text(f"No patients found for service: {service}")
            return ConversationHandler.END
        
        # Count dispositions
        old_count = sum(1 for p in service_patients if p['dispo'] == 'OLD')
        
        # Count advanced airway patients (🚨 emoji in patient string)
        advanced_airway = [p for p in service_patients if '🚨' in p['patient']]
        
        # Group by JRIC
        jric_groups = {}
        for p in service_patients:
            # Extract JRIC from patient string (between [ ])
            patient_str = p['patient']
            jric_start = patient_str.find('[')
            jric_end = patient_str.find(']', jric_start) if jric_start != -1 else -1
            
            if jric_start != -1 and jric_end != -1 and jric_end > jric_start:
                jric = patient_str[jric_start+1:jric_end]
                if jric not in jric_groups:
                    jric_groups[jric] = []
                jric_groups[jric].append(p)
        
        # Count admissions/discharges
        admitted = sum(1 for p in service_patients if p['dispo'] == 'ADMITTED')
        trans_in_icu = sum(1 for p in service_patients if p['dispo'] == 'TRANS IN FROM ICU')
        tos_in = sum(1 for p in service_patients if p['dispo'] == 'TOS IN')
        
        home = sum(1 for p in service_patients if p['dispo'] == 'HOME')
        hama = sum(1 for p in service_patients if p['dispo'] == 'HAMA/HPR')
        trans_out_icu = sum(1 for p in service_patients if p['dispo'] == 'TRANS OUT TO ICU')
        mort = sum(1 for p in service_patients if p['dispo'] == 'MORT')
        thoc = sum(1 for p in service_patients if p['dispo'] == 'THOC')
        abscond = sum(1 for p in service_patients if p['dispo'] == 'ABSCOND')
        
        # Calculate total
        additions = admitted + trans_in_icu + tos_in
        subtractions = home + hama + trans_out_icu + mort + thoc + abscond
        total = old_count + additions - subtractions
        
        # Build report
        report = f"GM{service} WARD CENSUS\n"
        report += f"DATE {datetime.now().strftime('%m/%d/%y')}\n"
        report += f"RECEIVED: {old_count}\n\n"
        
        # JRIC groups
        for jric, pts in jric_groups.items():
            advanced_in_jric = sum(1 for p in pts if '🚨' in p['patient'])
            report += f"{jric} ({len(pts)} | {advanced_in_jric})\n"
            
            # List patient codes
            for p in pts:
                # Extract case number/passcode
                patient_str = p['patient']
                dash_parts = patient_str.split(' - ')
                if len(dash_parts) >= 2:
                    code = dash_parts[1].split(' - ')[0]
                    report += f"{code}\n"
            report += "\n"
        
        report += f"{service} = {old_count} + {additions} - {subtractions} = {total}"
        
        await update.message.reply_text(f"```\n{report}\n```", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Error generating report: {str(e)}")
    
    return ConversationHandler.END

# ============ GALA WARDS REPORT HANDLERS ============

async def galawards_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Gala Wards report"""
    await update.message.reply_text("Enter Admitting service:")
    context.user_data['gala_step'] = 'service'
    return GALAWARDS_INPUTS

async def galawards_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get('gala_step')
    
    if step == 'service':
        context.user_data['admitting_service'] = update.message.text.strip()
        context.user_data['gala_step'] = 'sapod'
        await update.message.reply_text("Enter SAPOD:")
    elif step == 'sapod':
        context.user_data['sapod'] = update.message.text.strip()
        context.user_data['gala_step'] = 'napod'
        await update.message.reply_text("Enter NAPOD:")
    elif step == 'napod':
        context.user_data['napod'] = update.message.text.strip()
        context.user_data['gala_step'] = 'wapod'
        await update.message.reply_text("Enter WAPOD:")
    elif step == 'wapod':
        context.user_data['wapod'] = update.message.text.strip()
        context.user_data['gala_step'] = 'apod'
        await update.message.reply_text("Enter APOD:")
    elif step == 'apod':
        context.user_data['apod'] = update.message.text.strip()
        
        # Generate report
        try:
            report = generate_galawards_report(context.user_data)
            await update.message.reply_text(f"```\n{report}\n```", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"Error generating report: {str(e)}")
        
        context.user_data.clear()
        return ConversationHandler.END
    
    return GALAWARDS_INPUTS

def generate_galawards_report(data):
    """Generate the Gala Wards report"""
    patients = get_all_patients()
    
    # Count OLD patients
    old_total = sum(1 for p in patients if p['dispo'] == 'OLD')
    
    # Helper function to extract last name from patient string
    def get_last_name(patient_str):
        # Format: GM#/LastName (...)
        parts = patient_str.split('/')
        if len(parts) >= 2:
            name_part = parts[1].split('(')[0].strip()
            return name_part
        return ""
    
    # Process each GM service
    services = ['GM1', 'GM2', 'GM3', 'GM4', 'GM5', 'GM6']
    
    report = "SERVICE AND WARD CENSUS\n"
    report += f"Admitting service: {data['admitting_service']}\n"
    report += f"Date of Duty: {datetime.now().strftime('%m/%d/%y')}\n\n"
    report += f"SAPOD: {data['sapod']}\n"
    report += f"NAPOD: {data['napod']}\n"
    report += f"WAPOD: {data['wapod']}\n"
    report += f"APOD: {data['apod']}\n\n"
    report += f"Received: {old_total}\n\n"
    
    # ADMISSIONS
    admitted_total = sum(1 for p in patients if p['dispo'] == 'ADMITTED')
    report += f"ADMISSIONS: {admitted_total}\n"
    for service in services:
        service_admitted = [p for p in patients if p['gm_service'] == service and p['dispo'] == 'ADMITTED']
        if service_admitted:
            names = ', '.join([get_last_name(p['patient']) for p in service_admitted])
            report += f"{service}: {len(service_admitted)} ({names})\n"
    report += "\n"
    
    # DISCHARGES
    home_total = sum(1 for p in patients if p['dispo'] == 'HOME')
    report += f"DISCHARGES: {home_total}\n"
    for service in services:
        service_home = [p for p in patients if p['gm_service'] == service and p['dispo'] == 'HOME']
        if service_home:
            names = ', '.join([get_last_name(p['patient']) for p in service_home])
            report += f"{service}: {len(service_home)} ({names})\n"
    report += "\n"
    
    # TOS IN
    tos_in_patients = [p for p in patients if p['dispo'] == 'TOS IN']
    report += f"TOS IN: {len(tos_in_patients)}\n"
    for service in services:
        service_tos = [p for p in tos_in_patients if p['gm_service'] == service]
        if service_tos:
            names = ', '.join([get_last_name(p['patient']) for p in service_tos])
            report += f"{service}: {names}\n"
    report += "\n"
    
    # TRANS IN FROM ICU
    trans_in_patients = [p for p in patients if p['dispo'] == 'TRANS IN FROM ICU']
    report += f"TRANS IN FROM ICU: {len(trans_in_patients)}\n"
    for service in services:
        service_trans = [p for p in trans_in_patients if p['gm_service'] == service]
        if service_trans:
            names = ', '.join([get_last_name(p['patient']) for p in service_trans])
            report += f"{service}: {names}\n"
    report += "\n"
    
    # MORT
    mort_patients = [p for p in patients if p['dispo'] == 'MORT']
    report += f"MORT: {len(mort_patients)}\n"
    for service in services:
        service_mort = [p for p in mort_patients if p['gm_service'] == service]
        if service_mort:
            names = ', '.join([get_last_name(p['patient']) for p in service_mort])
            report += f"{service}: {names}\n"
    report += "\n"
    
    # TOS OUT
    tos_out_patients = [p for p in patients if p['dispo'] == 'TOS OUT']
    report += f"TOS OUT: {len(tos_out_patients)}\n"
    for p in tos_out_patients:
        report += f"{p['gm_service']}: {get_last_name(p['patient'])}\n"
    report += "\n"
    
    # TRANS OUT TO ICU
    trans_out_patients = [p for p in patients if p['dispo'] == 'TRANS OUT TO ICU']
    report += f"TRANS OUT TO ICU: {len(trans_out_patients)}"
    for p in trans_out_patients:
        report += f" ({p['gm_service']}/{get_last_name(p['patient'])})"
    report += "\n"
    
    # HAMA
    hama_patients = [p for p in patients if p['dispo'] == 'HAMA/HPR']
    report += f"HAMA: {len(hama_patients)}"
    for p in hama_patients:
        report += f" ({p['gm_service']}/{get_last_name(p['patient'])})"
    report += "\n"
    
    # THOC
    thoc_patients = [p for p in patients if p['dispo'] == 'THOC']
    report += f"THOC: {len(thoc_patients)}"
    for p in thoc_patients:
        report += f" ({p['gm_service']}/{get_last_name(p['patient'])})"
    report += "\n"
    
    # ABSCOND
    abscond_patients = [p for p in patients if p['dispo'] == 'ABSCOND']
    report += f"ABSCOND: {len(abscond_patients)}"
    for p in abscond_patients:
        report += f" ({p['gm_service']}/{get_last_name(p['patient'])})"
    report += "\n\n"
    
    # SERVICE CENSUS
    report += "SERVICE CENSUS\n"
    total_all = 0
    for service in services:
        service_patients = [p for p in patients if p['gm_service'] == service]
        old_count = sum(1 for p in service_patients if p['dispo'] == 'OLD')
        additions = sum(1 for p in service_patients if p['dispo'] in ['ADMITTED', 'TOS IN', 'TRANS IN FROM ICU'])
        subtractions = sum(1 for p in service_patients if p['dispo'] in ['HOME', 'TOS OUT', 'TRANS OUT TO ICU', 'HAMA/HPR', 'THOC', 'ABSCOND', 'MORT'])
        total = old_count + additions - subtractions
        total_all += total
        
        report += f"{service}: {old_count} + {additions} - {subtractions} = {total}\n"
    
    report += f"\nTOTAL: {total_all}"
    
    return report

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current operation"""
    context.user_data.clear()
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

def main():
    """Main function to run the bot"""
    # Replace with your bot token
    TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    application = Application.builder().token(TOKEN).build()
    
    # Add patient conversation handler
    add_conv = ConversationHandler(
        entry_points=[CommandHandler('add', add_patient_start)],
        states={
            GM_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, gm_service)],
            LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, last_name)],
            O2_SUPPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, o2_support)],
            COVID_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, covid_status)],
            CASE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, case_number)],
            PASSCODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, passcode)],
            WARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ward)],
            BED: [MessageHandler(filters.TEXT & ~filters.COMMAND, bed)],
            JRIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, jric)],
            DISPO_TYPE: [CallbackQueryHandler(dispo_type_callback, pattern=r'^dtype_')],
            CWI: [MessageHandler(filters.TEXT & ~filters.COMMAND, cwi)],
            SPECIAL_CATS: [CallbackQueryHandler(special_cats_callback)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Disposition conversation handler
    dispo_conv = ConversationHandler(
        entry_points=[CommandHandler('dispo', dispo_start)],
        states={
            DISPO_PATIENT: [CallbackQueryHandler(dispo_patient_callback, pattern=r'^patient_')],
            DISPO_SELECT: [CallbackQueryHandler(dispo_callback, pattern=r'^dispo_')],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Service report conversation handler
    service_conv = ConversationHandler(
        entry_points=[CommandHandler('servicereport', service_report_start)],
        states={
            SERVICE_REPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_service_report)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Gala Wards report conversation handler
    gala_conv = ConversationHandler(
        entry_points=[CommandHandler('galawardsreport', galawards_start)],
        states={
            GALAWARDS_INPUTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, galawards_inputs)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Search conversation handler
    search_conv = ConversationHandler(
        entry_points=[CommandHandler('search', search_start)],
        states={
            SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_query)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(add_conv)
    application.add_handler(dispo_conv)
    application.add_handler(service_conv)
    application.add_handler(gala_conv)
    application.add_handler(search_conv)
    
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
