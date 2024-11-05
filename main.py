from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'CMS'  # Consider using environment variables for secrets
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/cms'
db = SQLAlchemy(app)

# Initialize LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.session_protection = 'strong'

# ----------------------- MODELS -----------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50))
    email = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(1000), nullable=False)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10), nullable=False)  
    phone = db.Column(db.String(15), nullable=False)   
    age = db.Column(db.Integer, nullable=False)
    address = db.Column(db.Text, nullable=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    patient = db.relationship('Patient', backref=db.backref('appointments', lazy=True))
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    disease_description = db.Column(db.Text, nullable=False)

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=False)
    
    # Correct relationship to Appointment
    appointment = db.relationship('Appointment', backref=db.backref('prescriptions', lazy=True))
    
    prescription = db.Column(db.Text, nullable=False)

# Create all tables if not already present
with app.app_context():
    db.create_all()

# ----------------------- LOGIN MANAGEMENT -----------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role = request.form.get('role')
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email address.', 'danger')
            return redirect(url_for('signup'))

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists. Please log in.', 'warning')
            return redirect(url_for('login'))

        encpassword = generate_password_hash(password)
        new_user = User(role=role, email=email, username=username, password=encpassword)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('Error creating account. Please try again.', 'danger')

    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    patient_count = Patient.query.count()
    appointment_count = Appointment.query.count()
    return render_template('dashboard.html', patient_count=patient_count, appointment_count=appointment_count)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

# ----------------------- APPOINTMENT MANAGEMENT -----------------------
@app.route('/schedule-appointment', methods=['GET', 'POST'])
@login_required
def schedule_appointment():
    if request.method == 'POST':
        # Check if the existing patient is selected or new patient details are provided
        patient_id = request.form.get('patient_id')
        new_patient_name = request.form.get('new_patient_name')
        new_patient_gender = request.form.get('new_patient_gender')
        new_patient_phone = request.form.get('new_patient_phone')
        new_patient_age = request.form.get('new_patient_age')
        new_patient_address = request.form.get('new_patient_address')

        appointment_date_str = request.form.get('appointment_date')
        appointment_time_str = request.form.get('appointment_time')
        disease_description = request.form.get('disease_description')

        # Validate form inputs
        if not appointment_date_str or not appointment_time_str or not disease_description:
            flash("All fields are required!", "warning")
            return redirect(url_for('schedule_appointment'))

        # Check if new patient details are provided or an existing patient is selected
        if patient_id:
            # Use the selected existing patient
            patient = Patient.query.get(patient_id)
        elif new_patient_name and new_patient_phone and new_patient_age:
            # Create a new patient record
            new_patient = Patient(
                name=new_patient_name,
                gender=new_patient_gender,
                phone=new_patient_phone,
                age=new_patient_age,
                address=new_patient_address
            )
            try:
                db.session.add(new_patient)
                db.session.commit()
                patient = new_patient  # Use the new patient for the appointment
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding new patient: {str(e)}", "danger")
                return redirect(url_for('schedule_appointment'))
        else:
            flash("Please select an existing patient or fill in the new patient details.", "warning")
            return redirect(url_for('schedule_appointment'))

        # Validate appointment date and time format
        try:
            appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(appointment_time_str, '%H:%M').time()
        except ValueError:
            flash("Invalid date or time format. Please use YYYY-MM-DD for date and HH:MM for time.", "warning")
            return redirect(url_for('schedule_appointment'))

        # Create and save the appointment
        new_appointment = Appointment(
            patient_id=patient.id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            disease_description=disease_description
        )

        try:
            db.session.add(new_appointment)
            db.session.commit()
            flash("Appointment scheduled successfully!", "success")
            return redirect(url_for('print_appointment', appointment_id=new_appointment.id))  # Redirect to print appointment
        except Exception as e:
            db.session.rollback()
            flash(f"Error scheduling appointment: {str(e)}", "danger")

        return redirect(url_for('view_appointments'))

    # Get list of patients for the dropdown
    patients = Patient.query.all()
    return render_template('schedule_appointment.html', patients=patients)


@app.route('/print-appointment/<int:appointment_id>')
def print_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    patient = Patient.query.get(appointment.patient_id)
    return render_template('print_appointment.html', appointment=appointment, patient=patient)

@app.route('/view-appointments')
def view_appointments():
    appointments = Appointment.query.all()
    # If you need to access the patient data, you can prepare a dictionary
    appointment_details = [
        {
            'appointment': appointment,
            'patient': appointment.patient  # Fetch the associated patient
        }
        for appointment in appointments
    ]
    return render_template('view_appointments.html', appointment_details=appointment_details)

from flask import session

@app.route('/patient-details/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def patient_details(patient_id):
    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('patient_records'))

    if request.method == 'POST':
        patient.name = request.form.get('patient_name')
        patient.gender = request.form.get('gender')  # Add this line
        patient.phone = request.form.get('phone')    # Add this line
        patient.age = request.form.get('age')
        patient.address = request.form.get('address')
        try:
            db.session.commit()
            flash('Patient details updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()  # Rollback in case of an error
            flash(f"Error updating patient details: {str(e)}", 'danger')
        
        return redirect(url_for('patient_records'))



    # Check if the user is a doctor
    is_doctor = session.get('user_role') == 'doctor'  # Adjust according to your auth implementation

    # Choose the appropriate template
    template = 'patient_details_doctor.html' if is_doctor else 'patient_details.html'

    prescriptions = [p for appointment in patient.appointments for p in appointment.prescriptions]
    return render_template(template, patient=patient, prescriptions=prescriptions)


@app.route('/delete_patient/<int:patient_id>', methods=['POST'])
@login_required
def delete_patient(patient_id):
    patient = db.session.get(Patient, patient_id)
    
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('patient_records'))
    
    try:
        db.session.delete(patient)
        db.session.commit()
        flash('Patient deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()  # Rollback on error
        flash(f'Error deleting patient: {str(e)}', 'danger')

    return redirect(url_for('patient_records'))



@app.route('/patient-records')
@login_required
def patient_records():
    patients = Patient.query.all()  # Fetch all patients from the database
    return render_template('patient_records.html', patients=patients)

@app.route('/manage-patients', methods=['GET', 'POST'])
@login_required
def manage_patients():
    if current_user.role != 'doctor':
        return redirect(url_for('dashboard'))
    
    patient = None  # Initialize patient variable
    if request.method == 'POST':
        patient_name = request.form.get('patient_name')
        patient = Patient.query.filter_by(name=patient_name).first()
        if patient:
            return render_template('patient_details_doctor.html', patient=patient)  # Pass patient instance
        else:
            flash('Patient not found.', 'danger')
    
    return render_template('manage_patients.html')



@app.route('/add_prescription/<int:patient_id>', methods=['POST'])
@login_required
def add_prescription(patient_id):
    # Get the form data
    appointment_date_str = request.form.get('appointment_date')
    prescription_text = request.form.get('prescription')

    # Check for empty fields
    if not appointment_date_str or not prescription_text:
        flash("All fields are required!", "warning")
        return redirect(url_for('patient_details_doctor', patient_id=patient_id))

    # Validate appointment date format
    try:
        appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Invalid appointment date format. Please use YYYY-MM-DD.", "warning")
        return redirect(url_for('patient_details_doctor', patient_id=patient_id))

    # Find the appointment
    appointment = Appointment.query.filter_by(patient_id=patient_id, appointment_date=appointment_date).first()

    # Check if the appointment exists
    if not appointment:
        flash("Appointment not found for the selected date.", "danger")
        return redirect(url_for('patient_details_doctor', patient_id=patient_id))

    # Create and save the new prescription
    try:
        new_prescription = Prescription(appointment_id=appointment.id, prescription=prescription_text)
        db.session.add(new_prescription)
        db.session.commit()
        flash("Prescription added successfully!", "success")
    except Exception as e:
        db.session.rollback()  # Rollback on error
        flash(f"Error adding prescription: {str(e)}", "danger")

    # Redirect back to the patient details for the doctor
    return redirect(url_for('patient_details_doctor', patient_id=patient_id))

@app.route('/patient-details-doctor/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def patient_details_doctor(patient_id):
    # Your logic for handling patient details for doctors
    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('view_appointments'))

    prescriptions = [p for appointment in patient.appointments for p in appointment.prescriptions]
    return render_template('patient_details_doctor.html', patient=patient, prescriptions=prescriptions)



@app.route('/print-prescription/<int:prescription_id>')
@login_required
def print_prescription(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    appointment = prescription.appointment
    patient = appointment.patient

    return render_template(
        'print_prescription.html', 
        prescription=prescription, 
        appointment=appointment, 
        patient=patient
    )

# ----------------------- RUN APPLICATION -----------------------
if __name__ == '__main__':
    app.run(debug=True)
