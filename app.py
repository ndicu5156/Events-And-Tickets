from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import qrcode

app = Flask(__name__)

# Configurations
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key_here'

# Initialize the database
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=True)
    nostr_key = db.Column(db.String(150), unique=True, nullable=True)

    def __repr__(self):
        return f'<User {self.email or self.nostr_key}>'

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    location = db.Column(db.String(150), nullable=True)
    tickets_available = db.Column(db.Integer, nullable=False)
    lightning_address = db.Column(db.String(150), nullable=False)

    def __repr__(self):
        return f'<Event {self.title}>'

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    purchase_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref='tickets')
    event = db.relationship('Event', backref='tickets')

    def __repr__(self):
        return f'<Ticket {self.id} for Event {self.event_id}>'

# Routes
@app.route('/')
def index():
    events = Event.query.all()
    return render_template('index.html', events=events)

@app.route('/event/<int:event_id>', methods=['GET'])
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('event_details.html', event=event)

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        try:
            # Extract form data
            title = request.form['title']
            description = request.form['description']
            date = datetime.strptime(request.form['date'], '%Y-%m-%d')
            location = request.form['location']
            tickets_available = int(request.form['tickets_available'])
            lightning_address = request.form['lightning_address']

            # Create and save event
            event = Event(
                title=title,
                description=description,
                date=date,
                location=location,
                tickets_available=tickets_available,
                lightning_address=lightning_address,
            )
            db.session.add(event)
            db.session.commit()
            flash('Event created successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating event: {e}', 'error')
            print(f"Error: {e}")  # Log the error for debugging
            return redirect(url_for('create_event'))
    return render_template('create_event.html')


@app.route('/purchase_ticket/<int:event_id>', methods=['GET', 'POST'])
def purchase_ticket(event_id):
    event = Event.query.get_or_404(event_id)

    if request.method == 'POST':
        nostr_key = request.form.get('nostr_key')
        email = request.form.get('email')

        user = User.query.filter((User.nostr_key == nostr_key) | (User.email == email)).first()
        if not user:
            user = User(nostr_key=nostr_key, email=email)
            db.session.add(user)
            db.session.commit()

        ticket = Ticket(user_id=user.id, event_id=event.id)
        db.session.add(ticket)
        db.session.commit()

        # Generate QR code for the payment request
        payment_request = f"Payment for ticket ID {ticket.id} to {event.lightning_address}"
        qr_img_path = generate_qr_code(payment_request)

        return render_template('purchase_ticket.html', event=event, qr_img_path=qr_img_path)

    return render_template('purchase_ticket.html', event=event)

def generate_qr_code(payment_request):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(payment_request)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    qr_img_path = 'static/payment_qr.png'
    img.save(qr_img_path)
    return qr_img_path

@app.route('/generate_qr/<payment_request>', methods=['GET'])
def generate_qr(payment_request):
    qr_img_path = generate_qr_code(payment_request)
    return send_file(qr_img_path, mimetype='image/png')

@app.route('/dashboard')
def dashboard():
    user_tickets = Ticket.query.all()
    return render_template('dashboard.html', tickets=user_tickets)

# Main
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
