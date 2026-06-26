from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from sqlalchemy import or_
from wtforms import StringField, PasswordField, TextAreaField, SelectField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError

# Optional email validation pack dependency
try:
    from wtforms.validators import Email
except Exception:
    Email = None
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from dotenv import load_dotenv

try:
    import email_validator  # noqa: F401
    EMAIL_VALIDATOR_INSTALLED = True
except Exception:
    EMAIL_VALIDATOR_INSTALLED = False

# Load environment variables
load_dotenv()

# app = Flask(__name__)
# app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
# app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///tourism.db')
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

database_url = os.getenv('DATABASE_URL')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///tourism.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
@app.route("/debug-db")
def debug_db():
    return app.config['SQLALCHEMY_DATABASE_URI']

STATE_CHOICES = [
    ('', '--Choose State/UT--'),
    ('andhra_pradesh', 'Andhra Pradesh'),
    ('arunachal_pradesh', 'Arunachal Pradesh'),
    ('assam', 'Assam'),
    ('bihar', 'Bihar'),
    ('chhattisgarh', 'Chhattisgarh'),
    ('goa', 'Goa'),
    ('gujarat', 'Gujarat'),
    ('haryana', 'Haryana'),
    ('himachal_pradesh', 'Himachal Pradesh'),
    ('jharkhand', 'Jharkhand'),
    ('karnataka', 'Karnataka'),
    ('kerala', 'Kerala'),
    ('madhya_pradesh', 'Madhya Pradesh'),
    ('maharashtra', 'Maharashtra'),
    ('manipur', 'Manipur'),
    ('meghalaya', 'Meghalaya'),
    ('mizoram', 'Mizoram'),
    ('nagaland', 'Nagaland'),
    ('odisha', 'Odisha'),
    ('punjab', 'Punjab'),
    ('rajasthan', 'Rajasthan'),
    ('sikkim', 'Sikkim'),
    ('tamil_nadu', 'Tamil Nadu'),
    ('telangana', 'Telangana'),
    ('tripura', 'Tripura'),
    ('uttar_pradesh', 'Uttar Pradesh'),
    ('uttarakhand', 'Uttarakhand'),
    ('west_bengal', 'West Bengal'),
    ('andaman_nicobar', 'Andaman & Nicobar Islands'),
    ('chandigarh', 'Chandigarh'),
    ('dadra_nagar_haveli_daman_diu', 'Dadra & Nagar Haveli and Daman & Diu'),
    ('lakshadweep', 'Lakshadweep'),
    ('delhi', 'Delhi'),
    ('puducherry', 'Puducherry'),
    ('ladakh', 'Ladakh')
]
STATE_LABELS = dict(STATE_CHOICES)
WIKIPEDIA_API_URL = 'https://en.wikipedia.org/w/api.php'
PLACE_IMAGE_FALLBACK = '/static/images/travel-fallback.svg'
NOMINATIM_API_URL = 'https://nominatim.openstreetmap.org/search'
OSRM_ROUTE_URL = 'https://router.project-osrm.org/route/v1/driving'
OPENAI_RESPONSES_URL = 'https://api.openai.com/v1/responses'
DEFAULT_ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
DEFAULT_ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
DEFAULT_ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100))
    language = db.Column(db.String(20), default='english')
    state = db.Column(db.String(50))
    contact = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

    # Relationships
    reviews = db.relationship('Review', backref='user', lazy=True)
    favorites = db.relationship('Favorite', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class TouristSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500))
    state = db.Column(db.String(50), nullable=False)
    city = db.Column(db.String(50))
    category = db.Column(db.String(50))  # beach, temple, fort, etc.
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    rating = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    reviews = db.relationship('Review', backref='spot', lazy=True)
    favorites = db.relationship('Favorite', backref='spot', lazy=True)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('tourist_spot.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('tourist_spot.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TransportServiceCompany(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(120), nullable=False)
    transport_type = db.Column(db.String(30), nullable=False)
    service_area = db.Column(db.String(120))
    booking_url = db.Column(db.String(255))
    contact_phone = db.Column(db.String(40))
    contact_email = db.Column(db.String(120))
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Forms
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email_validators = [DataRequired()]
    if Email is not None and EMAIL_VALIDATOR_INSTALLED:
        email_validators.append(Email())
    email = StringField('Email', validators=email_validators)
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    name = StringField('Full Name', validators=[DataRequired()])
    language = SelectField('Language', choices=[('english', 'English'), ('hindi', 'Hindi')])
    state = SelectField('State', choices=STATE_CHOICES, validators=[DataRequired()])
    contact = StringField('Contact', validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists.')

    def validate_email(self, email):
        if not EMAIL_VALIDATOR_INSTALLED:
            email_pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
            if not re.match(email_pattern, email.data or ''):
                raise ValidationError('Please enter a valid email address.')
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ReviewForm(FlaskForm):
    rating = SelectField(
        'Rating',
        choices=[(5, '5 stars'), (4, '4 stars'), (3, '3 stars'), (2, '2 stars'), (1, '1 star')],
        coerce=int,
        validators=[DataRequired()]
    )
    comment = TextAreaField('Comment', validators=[Length(max=500)])
    submit = SubmitField('Submit Review')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def get_average_rating(spot):
    ratings = [review.rating for review in spot.reviews]
    return round(sum(ratings) / len(ratings), 1) if ratings else 0.0


def is_safe_redirect_target(target):
    if not target:
        return False
    parsed = urlsplit(target)
    return not parsed.scheme and not parsed.netloc and target.startswith('/')


def get_state_label(state_key):
    return STATE_LABELS.get(state_key, state_key.replace('_', ' ').title() if state_key else 'Unknown')


def ensure_admin_user():
    if User.query.filter_by(is_admin=True).first():
        return

    admin_user = User.query.filter(
        (User.username == DEFAULT_ADMIN_USERNAME) | (User.email == DEFAULT_ADMIN_EMAIL)
    ).first()

    if admin_user is None:
        admin_user = User(
            username=DEFAULT_ADMIN_USERNAME,
            email=DEFAULT_ADMIN_EMAIL,
            name='Site Admin',
            language='english',
            state='delhi',
            contact='admin',
            is_admin=True
        )
        admin_user.set_password(DEFAULT_ADMIN_PASSWORD)
        db.session.add(admin_user)
    else:
        admin_user.is_admin = True

    db.session.commit()


def fetch_json(url, params):
    query_string = urlencode(params)
    request = Request(
        f'{url}?{query_string}',
        headers={
            'Accept': 'application/json',
            'User-Agent': 'IndiaTourismApp/1.0 (educational project)'
        }
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))


def format_duration(total_minutes):
    total_minutes = max(int(round(total_minutes)), 1)
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f'{hours}h {minutes}m'
    if hours:
        return f'{hours}h'
    return f'{minutes}m'


def format_distance_km(distance_km):
    return f'{distance_km:.0f} km' if distance_km >= 10 else f'{distance_km:.1f} km'


def haversine_km(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2

    earth_radius_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return earth_radius_km * 2 * atan2(sqrt(a), sqrt(1 - a))


def geocode_location(query, limit=1):
    results = fetch_json(NOMINATIM_API_URL, {
        'q': query,
        'format': 'jsonv2',
        'limit': limit,
        'countrycodes': 'in'
    })
    return results or []


def first_geocode_result(query):
    results = geocode_location(query, limit=1)
    if not results:
        return None
    item = results[0]
    return {
        'name': item.get('display_name', query),
        'lat': float(item['lat']),
        'lon': float(item['lon'])
    }


def get_osrm_road_route(start_location, end_location):
    coordinates = f"{start_location['lon']},{start_location['lat']};{end_location['lon']},{end_location['lat']}"
    payload = fetch_json(f'{OSRM_ROUTE_URL}/{coordinates}', {
        'overview': 'false',
        'alternatives': 'false',
        'steps': 'false'
    })
    routes = payload.get('routes', [])
    if not routes:
        return None
    route = routes[0]
    distance_km = route.get('distance', 0) / 1000
    duration_minutes = route.get('duration', 0) / 60
    return {
        'mode': 'Roadways',
        'distance': format_distance_km(distance_km),
        'time': format_duration(duration_minutes),
        'summary': f"Drive from {start_location['name']} to {end_location['name']}"
    }


def build_estimated_route(mode, start_label, end_label, distance_km, speed_kmph, overhead_minutes=0, note='Estimated'):
    duration_minutes = (distance_km / speed_kmph) * 60 + overhead_minutes
    return {
        'mode': mode,
        'distance': format_distance_km(distance_km),
        'time': format_duration(duration_minutes),
        'summary': f'{start_label} to {end_label}',
        'note': note
    }


def build_transport_booking_links(start_point, destination_point):
    route_query = urlencode({'fromCity': start_point, 'toCity': destination_point})
    return {
        'Roadways': {
            'label': 'Book bus or road trip',
            'url': f'https://www.redbus.in/?{route_query}'
        },
        'Railways': {
            'label': 'Book train tickets',
            'url': 'https://www.irctc.co.in/nget/train-search'
        },
        'Aeroplane': {
            'label': 'Search flights',
            'url': f'https://www.makemytrip.com/flights/?{route_query}'
        }
    }


def format_inr(amount):
    return f'Rs. {int(round(amount)):,}'


def build_budget_trip_plan(total_budget, travelers='1', trip_style='any', origin=''):
    try:
        total_budget = max(float(total_budget), 1000)
    except (TypeError, ValueError):
        raise ValueError('Please enter a valid budget amount.')

    try:
        traveler_count = max(int(travelers or 1), 1)
    except (TypeError, ValueError):
        traveler_count = 1

    budget_per_person = total_budget / traveler_count

    style_map = {
        'any': ['heritage', 'nature', 'religious', 'beach'],
        'spiritual': ['religious', 'temple'],
        'heritage': ['heritage', 'history', 'fort', 'palace', 'monument'],
        'nature': ['nature', 'waterfall', 'hill_station', 'wildlife', 'lake'],
        'beach': ['beach'],
        'adventure': ['adventure', 'hill_station', 'wildlife', 'nature']
    }

    if total_budget <= 6000:
        trip_length = '1 day or quick overnight'
        transport = 'Roadways or budget rail'
        stay_share = 0.20
        transport_share = 0.35
        food_share = 0.20
        explore_share = 0.15
        buffer_share = 0.10
        headline = 'A compact getaway works best for this budget.'
    elif total_budget <= 12000:
        trip_length = '2 days / 1 night'
        transport = 'Railways or road trip'
        stay_share = 0.26
        transport_share = 0.30
        food_share = 0.18
        explore_share = 0.16
        buffer_share = 0.10
        headline = 'This budget fits a strong weekend trip.'
    elif total_budget <= 25000:
        trip_length = '3 days / 2 nights'
        transport = 'Comfort rail, road, or budget flight'
        stay_share = 0.30
        transport_share = 0.28
        food_share = 0.17
        explore_share = 0.15
        buffer_share = 0.10
        headline = 'You can plan a fuller mini-vacation with this amount.'
    else:
        trip_length = '4 to 5 days'
        transport = 'Flight plus local road travel'
        stay_share = 0.32
        transport_share = 0.30
        food_share = 0.15
        explore_share = 0.13
        buffer_share = 0.10
        headline = 'This budget gives room for a richer multi-day trip.'

    categories = style_map.get((trip_style or 'any').lower(), style_map['any'])
    filters = [TouristSpot.category.ilike(f'%{category}%') for category in categories]
    suggested_spots = TouristSpot.query.filter(or_(*filters)).order_by(TouristSpot.rating.desc(), TouristSpot.created_at.desc()).limit(6).all()
    if not suggested_spots:
        suggested_spots = TouristSpot.query.order_by(TouristSpot.rating.desc(), TouristSpot.created_at.desc()).limit(6).all()

    recommended_spots = []
    seen_names = set()
    for spot in suggested_spots:
        if spot.name in seen_names:
            continue
        seen_names.add(spot.name)
        recommended_spots.append({
            'name': spot.name,
            'state': get_state_label(spot.state),
            'city': spot.city or get_state_label(spot.state),
            'category': (spot.category or 'destination').replace('_', ' ').title(),
            'description': spot.description,
            'image_url': spot.image_url,
            'id': spot.id
        })
        if len(recommended_spots) == 3:
            break

    trip_style_labels = {
        'any': 'Flexible escape',
        'spiritual': 'Spiritual journey',
        'heritage': 'Heritage circuit',
        'nature': 'Nature break',
        'beach': 'Beach escape',
        'adventure': 'Adventure getaway'
    }

    return {
        'headline': headline,
        'origin': origin,
        'total_budget': format_inr(total_budget),
        'travelers': traveler_count,
        'budget_per_person': format_inr(budget_per_person),
        'trip_length': trip_length,
        'transport': transport,
        'trip_style': trip_style_labels.get((trip_style or 'any').lower(), 'Flexible escape'),
        'allocation': [
            {'label': 'Transport', 'amount': format_inr(total_budget * transport_share)},
            {'label': 'Stay', 'amount': format_inr(total_budget * stay_share)},
            {'label': 'Food', 'amount': format_inr(total_budget * food_share)},
            {'label': 'Sightseeing', 'amount': format_inr(total_budget * explore_share)},
            {'label': 'Buffer', 'amount': format_inr(total_budget * buffer_share)},
        ],
        'recommended_spots': recommended_spots
    }


def build_journey_options(start_point, destination_point, preferred_mode='any', journey_date='', passengers='1'):
    start_location = first_geocode_result(f'{start_point}, India')
    end_location = first_geocode_result(f'{destination_point}, India')
    if not start_location or not end_location:
        raise ValueError('Could not find one of the selected locations.')

    road_route = get_osrm_road_route(start_location, end_location)
    direct_distance_km = haversine_km(
        start_location['lat'],
        start_location['lon'],
        end_location['lat'],
        end_location['lon']
    )

    start_station = first_geocode_result(f'railway station near {start_point}, India') or start_location
    end_station = first_geocode_result(f'railway station near {destination_point}, India') or end_location
    rail_distance_km = haversine_km(
        start_station['lat'],
        start_station['lon'],
        end_station['lat'],
        end_station['lon']
    )
    rail_route = build_estimated_route(
        'Railways',
        start_station['name'],
        end_station['name'],
        rail_distance_km,
        speed_kmph=62,
        overhead_minutes=45,
        note='Estimated using nearby station locations'
    )

    start_airport = first_geocode_result(f'airport near {start_point}, India') or start_location
    end_airport = first_geocode_result(f'airport near {destination_point}, India') or end_location
    air_distance_km = haversine_km(
        start_airport['lat'],
        start_airport['lon'],
        end_airport['lat'],
        end_airport['lon']
    )
    air_route = build_estimated_route(
        'Aeroplane',
        start_airport['name'],
        end_airport['name'],
        air_distance_km,
        speed_kmph=700,
        overhead_minutes=180,
        note='Estimated using nearby airport locations'
    )

    options = []
    if road_route:
        road_route['note'] = 'Live road route from OpenStreetMap routing'
        options.append(road_route)
    options.append(rail_route)
    options.append(air_route)

    booking_links = build_transport_booking_links(start_point, destination_point)
    normalized_mode = (preferred_mode or 'any').strip().lower()
    display_mode_map = {
        'roadways': 'Roadways',
        'railways': 'Railways',
        'aeroplane': 'Aeroplane',
        'any': 'Any available option'
    }

    for option in options:
        option['is_preferred'] = normalized_mode != 'any' and option['mode'].lower() == normalized_mode
        booking = booking_links.get(option['mode'], {})
        option['booking_label'] = booking.get('label', 'Continue')
        option['booking_url'] = booking.get('url', '#')

    return {
        'start': start_location['name'],
        'destination': end_location['name'],
        'direct_distance': format_distance_km(direct_distance_km),
        'options': options,
        'preferred_mode': display_mode_map.get(normalized_mode, 'Any available option'),
        'journey_date': journey_date,
        'passengers': passengers,
        'booking_links': booking_links
    }


def clean_query_terms(text):
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    for phrase in [
        'show me', 'places for', 'place for', 'places to visit', 'place to visit',
        'suggest', 'suggest me', 'help me', 'can you', 'i want', 'tourist',
        'destination', 'destinations', 'query', 'please'
    ]:
        cleaned = cleaned.replace(phrase, ' ')
    return ' '.join(cleaned.split())


def search_wikipedia_general(query_text):
    payload = fetch_json(WIKIPEDIA_API_URL, {
        'action': 'query',
        'format': 'json',
        'generator': 'search',
        'gsrsearch': query_text,
        'gsrlimit': 3,
        'prop': 'extracts|info',
        'inprop': 'url',
        'exintro': 1,
        'explaintext': 1,
        'exchars': 180
    })
    query = payload.get('query', {})
    pages = query.get('pages', {})
    if not pages:
        return []
    ordered_ids = query.get('pageids', [])
    return [pages[page_id] for page_id in ordered_ids if page_id in pages]


def format_place_list(spots):
    return '; '.join(f"{spot.name} in {spot.city or get_state_label(spot.state)}" for spot in spots)


def extract_response_text(response_payload):
    output_items = response_payload.get('output', [])
    texts = []
    for item in output_items:
        for content in item.get('content', []):
            if content.get('type') == 'output_text' and content.get('text'):
                texts.append(content['text'])
    return '\n'.join(texts).strip()


def build_chatbot_context_snippet():
    featured_spots = TouristSpot.query.limit(12).all()
    if not featured_spots:
        return 'No local tourism spots are currently stored.'
    return '; '.join(f"{spot.name} ({get_state_label(spot.state)}) - {spot.category}" for spot in featured_spots)


def get_chat_history():
    history = session.get('chatbot_history', [])
    return history if isinstance(history, list) else []


def save_chat_history(history):
    session['chatbot_history'] = history[-8:]
    session.modified = True


def build_openai_chat_input(history, message):
    chat_input = []
    for item in history[-6:]:
        role = item.get('role')
        content = (item.get('content') or '').strip()
        if role in {'user', 'assistant'} and content:
            chat_input.append({
                'role': role,
                'content': [{'type': 'input_text', 'text': content}]
            })

    chat_input.append({
        'role': 'user',
        'content': [{'type': 'input_text', 'text': message}]
    })
    return chat_input


def get_openai_chatbot_reply(message, history=None):
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    if not api_key:
        return None

    model = os.getenv('OPENAI_MODEL', 'gpt-5.4-mini')
    system_prompt = (
        "You are a helpful tourism assistant inside an India travel website. "
        "Answer clearly, warmly, and directly. Prefer useful travel suggestions, app guidance, and short practical answers. "
        "When the user asks for recommendations, suggest specific places and explain why they fit. "
        "If you do not know an exact live timetable, say it is an estimate instead of inventing facts. "
        "If the user asks for places, recommend specific destinations when possible. "
        "Use this local tourism app context when helpful: "
        f"{build_chatbot_context_snippet()}"
    )

    body = {
        'model': model,
        'instructions': system_prompt,
        'input': build_openai_chat_input(history or [], message),
        'max_output_tokens': 320,
        'text': {
            'verbosity': 'medium'
        }
    }
    request = Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )

    try:
        with urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode('utf-8'))
            reply_text = extract_response_text(payload)
            return reply_text or None
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def get_category_matches(query_text):
    keyword_map = {
        'climbing': ['adventure', 'hill_station', 'nature', 'wildlife'],
        'hiking': ['adventure', 'hill_station', 'nature'],
        'trekking': ['adventure', 'hill_station', 'nature'],
        'adventure': ['adventure', 'hill_station', 'nature', 'wildlife'],
        'mountain': ['hill_station', 'adventure', 'nature'],
        'beach': ['beach'],
        'temple': ['temple', 'religious'],
        'religious': ['religious', 'temple'],
        'fort': ['fort', 'history', 'heritage'],
        'palace': ['palace'],
        'wildlife': ['wildlife', 'nature'],
        'nature': ['nature', 'waterfall', 'lake', 'wildlife'],
        'history': ['heritage', 'history', 'fort', 'monument'],
        'unesco': ['heritage', 'history', 'monument'],
        'family': ['nature', 'beach', 'heritage', 'religious'],
        'honeymoon': ['beach', 'hill_station', 'lake', 'nature'],
        'food': ['city', 'heritage'],
        'spiritual': ['religious', 'temple'],
        'pilgrimage': ['religious', 'temple']
    }

    matched_categories = set()
    for keyword, categories in keyword_map.items():
        if keyword in query_text:
            matched_categories.update(categories)

    if not matched_categories:
        return []

    filters = [TouristSpot.category.ilike(f'%{category}%') for category in matched_categories]
    query = TouristSpot.query.filter(or_(*filters)).limit(5)
    return query.all()


def detect_state_key_from_text(query_text):
    normalized_text = query_text.lower().replace('-', ' ')
    for state_key, state_label in STATE_LABELS.items():
        if not state_key:
            continue
        state_name = state_label.lower()
        if state_name in normalized_text or state_key.replace('_', ' ') in normalized_text:
            return state_key
    return None


def format_spot_lines(spots, intro):
    lines = [intro]
    for spot in spots:
        category = (spot.category or 'destination').replace('_', ' ').title()
        state_label = get_state_label(spot.state)
        location = spot.city or state_label
        summary = (spot.description or '').strip()
        summary = summary[:110].rstrip() + '...' if len(summary) > 110 else summary
        lines.append(f"- {spot.name} ({location}, {state_label}) - {category}. {summary}")
    return '\n'.join(lines)


def find_spot_matches(query_text, limit=5):
    cleaned_query = clean_query_terms(query_text)
    search_terms = [term for term in cleaned_query.split() if len(term) > 2]
    if not search_terms:
        search_terms = [cleaned_query] if cleaned_query else []

    filters = []
    for term in search_terms[:5]:
        filters.extend([
            TouristSpot.name.ilike(f'%{term}%'),
            TouristSpot.city.ilike(f'%{term}%'),
            TouristSpot.category.ilike(f'%{term}%'),
            TouristSpot.description.ilike(f'%{term}%')
        ])

    if not filters:
        return []

    return TouristSpot.query.filter(or_(*filters)).limit(limit).all()


def get_state_recommendations(state_key, limit=5):
    return TouristSpot.query.filter_by(state=state_key).order_by(TouristSpot.rating.desc(), TouristSpot.created_at.desc()).limit(limit).all()


def build_local_explore_reply(message, history=None):
    text = (message or '').strip()
    lowered = text.lower()
    history = history or []
    previous_user_text = ''
    for item in reversed(history):
        if item.get('role') == 'user':
            previous_user_text = (item.get('content') or '').lower()
            break

    if not text:
        return (
            "Ask me anything about this tourism site or Indian travel.\n"
            "Try: best places in Goa, places for climbing, spiritual places in Uttar Pradesh, or how admin login works."
        )

    if any(word in lowered for word in ['hello', 'hi', 'hey']):
        return (
            "Hello! I can help with trip ideas, religious places, beaches, climbing, family trips, admin access, "
            "registration, and the journey planner. Tell me your interest and state if you have one."
        )

    if any(phrase in lowered for phrase in ['what can you do', 'help me', 'how can you help']):
        return (
            "I can suggest places by interest, state, or city, explain how to register and log in, guide admin access, "
            "and help you use the journey planner for road, rail, and air estimates."
        )

    if 'register' in lowered or 'sign up' in lowered or 'signup' in lowered:
        return (
            "To register, open the Register page, fill in username, email, password, name, state, and contact, then submit. "
            "After that you can log in, save favorites, post reviews, and use more site features."
        )

    if 'login' in lowered or 'log in' in lowered or 'sign in' in lowered:
        return "Use the Login page with your username and password. After login, you can open your dashboard, favorites, reviews, or admin panel if your account is an admin."

    if 'admin' in lowered:
        return "Admin access uses the normal login page. Log in with an admin account, then open the Admin link in the top navigation or go directly to /admin."

    if any(word in lowered for word in ['journey', 'route', 'travel time', 'roadway', 'railway', 'aeroplane', 'flight']):
        return (
            "Open Start Your Journey, enter the starting point and destination, and submit the form. "
            "The page will show road distance plus estimated road, rail, and air travel times."
        )

    if 'favorite' in lowered:
        return "After login, open any destination page and use the favorite option. Your saved places appear on the dashboard."

    if 'review' in lowered or 'rating' in lowered:
        return "After login, open a destination page and submit a rating with your comment in the review section."

    if lowered in {'more', 'more places', 'show more', 'another', 'another one'} and previous_user_text:
        lowered = f'{previous_user_text} more'

    detected_state_key = detect_state_key_from_text(lowered)
    category_matches = get_category_matches(lowered)
    state_matches = get_state_recommendations(detected_state_key) if detected_state_key else []

    if detected_state_key and category_matches:
        filtered = [spot for spot in category_matches if spot.state == detected_state_key][:4]
        if filtered:
            return format_spot_lines(
                filtered,
                f"These {clean_query_terms(text) or 'travel'} suggestions fit {get_state_label(detected_state_key)}:"
            )

    if category_matches:
        return format_spot_lines(category_matches[:4], "These places match your travel style:")

    if state_matches:
        intro = f"Top places I can suggest in {get_state_label(detected_state_key)}:"
        if any(word in lowered for word in ['best', 'famous', 'popular', 'must visit']):
            intro = f"Popular places in {get_state_label(detected_state_key)}:"
        return format_spot_lines(state_matches[:4], intro)

    direct_matches = find_spot_matches(text, limit=4)
    if direct_matches:
        return format_spot_lines(direct_matches, "I found these matching destinations in the app:")

    cleaned_query = clean_query_terms(text)
    if cleaned_query:
        try:
            wikipedia_results = search_wikipedia_general(f'{cleaned_query} tourism India')
            if wikipedia_results:
                lines = ["I found these broader travel suggestions from the internet:"]
                for result in wikipedia_results[:3]:
                    title = result.get('title', 'Travel result')
                    description = result.get('extract') or 'Travel-related result from the internet.'
                    lines.append(f"- {title}: {description}")
                lines.append("If you want, ask me for a state, city, beach, temple, climbing, family trip, or spiritual destination and I will narrow it down.")
                return '\n'.join(lines)
        except Exception:
            pass

    return (
        "I can give better answers if you tell me the kind of trip or the place.\n"
        "Try: places for climbing in Himachal Pradesh, famous temples in Uttar Pradesh, best beaches in Goa, or family trip ideas in Rajasthan."
    )


def chatbot_reply(message, history=None):
    openai_reply = get_openai_chatbot_reply(message, history=history)
    if openai_reply:
        return openai_reply
    return build_local_explore_reply(message, history=history)


def normalize_state_label(state_value):
    if not state_value:
        return ''
    return STATE_LABELS.get(state_value, state_value.replace('_', ' ').title())


def search_wikipedia_places(state_value, district=''):
    state_label = normalize_state_label(state_value)
    district_label = district.strip()
    location_label = f'{district_label}, {state_label}, India' if district_label else f'{state_label}, India'
    search_terms = [
        f'tourist attractions in {location_label}',
        f'places to visit in {location_label}',
        f'tourism in {location_label}'
    ]

    for term in search_terms:
        payload = fetch_json(WIKIPEDIA_API_URL, {
            'action': 'query',
            'format': 'json',
            'generator': 'search',
            'gsrsearch': term,
            'gsrlimit': 12,
            'prop': 'pageimages|extracts|pageterms|info',
            'inprop': 'url',
            'piprop': 'thumbnail',
            'pithumbsize': 900,
            'exintro': 1,
            'explaintext': 1,
            'exchars': 220,
            'wbptterms': 'description'
        })

        query = payload.get('query', {})
        pages = query.get('pages', {})
        if not pages:
            continue

        ordered_ids = query.get('pageids', [])
        ordered_pages = [pages[page_id] for page_id in ordered_ids if page_id in pages]
        if not ordered_pages:
            ordered_pages = sorted(pages.values(), key=lambda page: page.get('title', ''))

        places = []
        for page in ordered_pages:
            terms_data = page.get('terms', {}).get('description', [])
            description = terms_data[0] if terms_data else page.get('extract') or 'Live result from Wikipedia'
            places.append({
                'id': page.get('pageid'),
                'name': page.get('title'),
                'description': description,
                'image': page.get('thumbnail', {}).get('source', PLACE_IMAGE_FALLBACK),
                'url': page.get('fullurl', ''),
                'source': 'internet'
            })
        if places:
            return places

    return []


def search_wikipedia_districts(state_value, query_text):
    state_label = normalize_state_label(state_value)
    query_text = query_text.strip()
    if not state_label or not query_text:
        return []

    search_terms = [
        f'{query_text} district in {state_label} India',
        f'{query_text} {state_label} district India'
    ]

    suggestions = []
    seen = set()
    for term in search_terms:
        payload = fetch_json(WIKIPEDIA_API_URL, {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': term,
            'srlimit': 8
        })
        for result in payload.get('query', {}).get('search', []):
            title = result.get('title', '').strip()
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            suggestions.append(title)
        if suggestions:
            break

    return suggestions


@app.context_processor
def inject_template_helpers():
    return {
        'state_labels': STATE_LABELS,
        'get_state_label': get_state_label,
        'get_average_rating': get_average_rating
    }

# Initialize database and populate with sample data
def init_db():
    with app.app_context():
        db.create_all()
        ensure_admin_user()

        # Check if data already exists
        if TouristSpot.query.count() == 0:
            # Real famous spots (more complete images per request)
            spots_data = [
                # Goa
                {"name": "Baga Beach", "description": "Popular beach known for water sports and nightlife", "state": "goa", "city": "North Goa", "category": "beach", "image_url": "https://images.unsplash.com/photo-1483683804023-6ccdb62f86ef?w=800&h=600&fit=crop"},
                {"name": "Fort Aguada", "description": "Historic 17th century Portuguese fort overlooking the sea", "state": "goa", "city": "Sinquerim", "category": "fort", "image_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&h=600&fit=crop"},
                {"name": "Dudhsagar Falls", "description": "Spectacular waterfall on the Goa-Karnataka border", "state": "goa", "city": "Sanguem", "category": "waterfall", "image_url": "https://images.unsplash.com/photo-1422452228503-a65068227500?w=800&h=600&fit=crop"},
                {"name": "Basilica of Bom Jesus", "description": "UNESCO World Heritage site and Baroque church", "state": "goa", "city": "Old Goa", "category": "religious", "image_url": "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?w=800&h=600&fit=crop"},

                # Rajasthan
                {"name": "Hawa Mahal", "description": "Iconic pink palace with 953 jharokhas in Jaipur", "state": "rajasthan", "city": "Jaipur", "category": "palace", "image_url": "https://images.unsplash.com/photo-1535346569550-3b06d1704335?w=800&h=600&fit=crop"},
                {"name": "Amber Fort", "description": "UNESCO-affiliated hilltop fort with mirror rooms", "state": "rajasthan", "city": "Jaipur", "category": "fort", "image_url": "https://res.cloudinary.com/dgfrkgl9j/image/upload/w_800,h_600,c_fill/1280px-20191219_Fort_Amber_2C_Amer_2C_Jaipur_0955_9481_uf201w.jpg"},
                {"name": "Jaisalmer Fort", "description": "Golden sandstone fort in the Thar Desert", "state": "rajasthan", "city": "Jaisalmer", "category": "fort", "image_url": "https://images.unsplash.com/photo-1530317414848-6838df9d7d18?w=800&h=600&fit=crop"},
                {"name": "City Palace, Udaipur", "description": "Lakefront palace complex with royal galleries", "state": "rajasthan", "city": "Udaipur", "category": "palace", "image_url": "https://images.unsplash.com/photo-1518856975173-81b1b7088a2c?w=800&h=600&fit=crop"},
                {"name": "Mehrangarh Fort", "description": "Massive hilltop fort with panoramic views of Jodhpur", "state": "rajasthan", "city": "Jodhpur", "category": "fort", "image_url": "https://images.unsplash.com/photo-1589987607627-9b4c5b0e5474?w=800&h=600&fit=crop"},

                {"name": "Umaid Bhawan Palace", "description": "Luxury palace and heritage hotel, one of the world's largest private residences", "state": "rajasthan", "city": "Jodhpur", "category": "palace", "image_url": "https://images.unsplash.com/photo-1599661046827-dacff0d2b1dc?w=800&h=600&fit=crop"},

                {"name": "Lake Pichola", "description": "Scenic artificial lake with boat rides and palace views", "state": "rajasthan", "city": "Udaipur", "category": "lake", "image_url": "https://images.unsplash.com/photo-1609947017136-9daf32a5eb16?w=800&h=600&fit=crop"},

                {"name": "Ranthambore National Park", "description": "Famous wildlife reserve known for Bengal tigers", "state": "rajasthan", "city": "Sawai Madhopur", "category": "wildlife", "image_url": "https://images.unsplash.com/photo-1549366021-9f761d450615?w=800&h=600&fit=crop"},

                {"name": "Pushkar Lake", "description": "Sacred lake surrounded by ghats and temples", "state": "rajasthan", "city": "Pushkar", "category": "religious", "image_url": "https://images.unsplash.com/photo-1582555172866-f73bb12a2ab3?w=800&h=600&fit=crop"},

                {"name": "Brahma Temple", "description": "One of the very few temples dedicated to Lord Brahma", "state": "rajasthan", "city": "Pushkar", "category": "temple", "image_url": "https://images.unsplash.com/photo-1603262110263-fb0112e7cc33?w=800&h=600&fit=crop"},

                {"name": "Chittorgarh Fort", "description": "Largest fort in India and a UNESCO World Heritage Site", "state": "rajasthan", "city": "Chittorgarh", "category": "fort", "image_url": "https://images.unsplash.com/photo-1593696140826-c58b021acf8b?w=800&h=600&fit=crop"},

                {"name": "Kumbhalgarh Fort", "description": "Famous for its massive wall, second longest in the world", "state": "rajasthan", "city": "Rajsamand", "category": "fort", "image_url": "https://images.unsplash.com/photo-1626621341517-bbf3d4f1cd5e?w=800&h=600&fit=crop"},

                {"name": "Mount Abu", "description": "Only hill station of Rajasthan with cool climate and scenic views", "state": "rajasthan", "city": "Mount Abu", "category": "hill_station", "image_url": "https://images.unsplash.com/photo-1590128167107-7c6e6f3e8f50?w=800&h=600&fit=crop"},

                {"name": "Dilwara Temples", "description": "Famous Jain temples known for intricate marble carvings", "state": "rajasthan", "city": "Mount Abu", "category": "temple", "image_url": "https://images.unsplash.com/photo-1629883289233-6c3d61bb64b0?w=800&h=600&fit=crop"},

                {"name": "Bikaner Camel Festival", "description": "Unique cultural festival celebrating camels and desert life", "state": "rajasthan", "city": "Bikaner", "category": "festival", "image_url": "https://images.unsplash.com/photo-1575478337745-3f3e3e7a5f8b?w=800&h=600&fit=crop"},

                {"name": "Junagarh Fort", "description": "Impressive fort complex not built on a hill unlike others", "state": "rajasthan", "city": "Bikaner", "category": "fort", "image_url": "https://res.cloudinary.com/dgfrkgl9j/image/upload/w_800,h_600,c_fill/India_Bikaner_Junagarh_Fort_kwgsfj.jpg"},

                
                

                # Maharashtra
                {"name": "Gateway of India", "description": "Iconic waterfront arch in Mumbai", "state": "maharashtra", "city": "Mumbai", "category": "monument", "image_url": "https://images.unsplash.com/photo-1567200239477-5376acf26a93?w=800&h=600&fit=crop"},
                {"name": "Ajanta Caves", "description": "Ancient rock-cut Buddhist cave temples", "state": "maharashtra", "city": "Aurangabad", "category": "heritage", "image_url": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=800&h=600&fit=crop"},
                {"name": "Marine Drive", "description": "Scenic sea-facing boulevard in Mumbai", "state": "maharashtra", "city": "Mumbai", "category": "landmark", "image_url": "https://images.unsplash.com/photo-1556761175-4b46a572b786?w=800&h=600&fit=crop"},
                {"name": "Ellora Caves", "description": "UNESCO world heritage rock-cut cave temples", "state": "maharashtra", "city": "Aurangabad", "category": "heritage", "image_url": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800&h=600&fit=crop"},

                # Uttar Pradesh
                {"name": "Taj Mahal", "description": "World's most beautiful monument in Agra", "state": "uttar_pradesh", "city": "Agra", "category": "monument", "image_url": "https://images.unsplash.com/photo-1564507592333-c60657eea523?w=800&h=600&fit=crop"},
                {"name": "Varanasi Ghats", "description": "Spiritual riverfront steps along the Ganges", "state": "uttar_pradesh", "city": "Varanasi", "category": "religious", "image_url": "https://images.unsplash.com/photo-1475513223960-0c3b3b1a9e7f?w=800&h=600&fit=crop"},
                {"name": "Bara Imambara", "description": "Historic Indo-Islamic monument in Lucknow", "state": "uttar_pradesh", "city": "Lucknow", "category": "heritage", "image_url": "https://images.unsplash.com/photo-1595618061177-36d8a4f9d522?w=800&h=600&fit=crop"},
                {"name": "Fatehpur Sikri", "description": "UNESCO walled city near Agra", "state": "uttar_pradesh", "city": "Fatehpur Sikri", "category": "heritage", "image_url": "https://images.unsplash.com/photo-1531882001842-36f08b0be541?w=800&h=600&fit=crop"},

                # Karnataka
                {"name": "Mysore Palace", "description": "Grand royal palace in Mysore lit up at night", "state": "karnataka", "city": "Mysore", "category": "palace", "image_url": "https://images.unsplash.com/photo-1574992915442-9927803f8d5b?w=800&h=600&fit=crop"},
                {"name": "Hampi", "description": "Ruins of the Vijayanagara Empire on the Tungabhadra", "state": "karnataka", "city": "Hampi", "category": "historic", "image_url": "https://images.unsplash.com/photo-1524253482453-3fed8d2fe12b?w=800&h=600&fit=crop"},
                {"name": "Coorg", "description": "Lush coffee and spice plantations in Coorg", "state": "karnataka", "city": "Coorg", "category": "nature", "image_url": "https://images.unsplash.com/photo-1546293036-36bbd30f42d1?w=800&h=600&fit=crop"},
                {"name": "Jog Falls", "description": "Tall plunge waterfall in the Western Ghats", "state": "karnataka", "city": "Shimoga", "category": "waterfall", "image_url": "https://images.unsplash.com/photo-1504303996922-d2c017c48cf8?w=800&h=600&fit=crop"},

                # Remaining states and UT (one landmark each)
                {"name": "Dudhsagar Falls", "description": "Riverside waterfall in Goa", "state": "goa", "city": "Sanguem", "category": "waterfall", "image_url": "https://images.unsplash.com/photo-1422452228503-a65068227500?w=800&h=600&fit=crop"},
                {"name": "Sundarbans", "description": "Largest mangrove forest in West Bengal", "state": "west_bengal", "city": "Sundarbans", "category": "wildlife", "image_url": "https://images.unsplash.com/photo-1517232115160-ff93364542dd?w=800&h=600&fit=crop"},
                {"name": "Amber Fort", "description": "Fort palace in Jaipur", "state": "rajasthan", "city": "Jaipur", "category": "history", "image_url": "https://images.unsplash.com/photo-1485903350308-5880fa9ce818?w=800&h=600&fit=crop"},
                {"name": "Kedarnath Temple", "description": "High-altitude pilgrimage site", "state": "uttarakhand", "city": "Kedarnath", "category": "religious", "image_url": "https://images.unsplash.com/photo-1577758694112-e12177a1c1f6?w=800&h=600&fit=crop"},
                {"name": "Nagarhole National Park", "description": "Wildlife sanctuary in Karnataka", "state": "karnataka", "city": "Kushalnagar", "category": "wildlife", "image_url": "https://images.unsplash.com/photo-1516339901601-2e1b0fdb3947?w=800&h=600&fit=crop"},
                {"name": "Cherrapunjee", "description": "Wettest place on earth in Meghalaya", "state": "meghalaya", "city": "Cherrapunjee", "category": "nature", "image_url": "https://images.unsplash.com/photo-1516569423085-677ed0dc22aa?w=800&h=600&fit=crop"},
                {"name": "Sikkim Rumtek Monastery", "description": "Important Buddhist monastery", "state": "sikkim", "city": "Gangtok", "category": "religious", "image_url": "https://images.unsplash.com/photo-1546467761-e4f5d2a81d26?w=800&h=600&fit=crop"},
                {"name": "Konark Sun Temple", "description": "Sun Temple UNESCO World Heritage site", "state": "odisha", "city": "Konark", "category": "heritage", "image_url": "https://images.unsplash.com/photo-1558466590-0928f8c77ea1?w=800&h=600&fit=crop"},
                {"name": "Sundar Ban", "description": "Mangrove forest with tigers", "state": "west_bengal", "city": "Sundarbans", "category": "wildlife", "image_url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=800&h=600&fit=crop"},
                {"name": "Rann of Kutch", "description": "Seasonal salt marsh in Gujarat", "state": "gujarat", "city": "Kutch", "category": "nature", "image_url": "https://images.unsplash.com/photo-1523861756950-3298d6a569bf?w=800&h=600&fit=crop"},
                {"name": "Nanda Devi", "description": "Second highest mountain in India", "state": "uttarakhand", "city": "Chamoli", "category": "adventure", "image_url": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=800&h=600&fit=crop"},
                {"name": "Jama Masjid", "description": "Iconic mosque in Old Delhi", "state": "delhi", "city": "Delhi", "category": "religious", "image_url": "https://images.unsplash.com/photo-1518914155859-280f3f012e08?w=800&h=600&fit=crop"},
                {"name": "Baba House", "description": "Historic house in Ahmedabad", "state": "gujarat", "city": "Ahmedabad", "category": "culture", "image_url": "https://images.unsplash.com/photo-1558980664-10dfc0f6657a?w=800&h=600&fit=crop"},
                # UTs
                {"name": "Havelock Beach", "description": "Pristine beaches in Andaman & Nicobar", "state": "andaman_nicobar", "city": "Havelock", "category": "beach", "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&h=600&fit=crop"},
                {"name": "Chandni Chowk", "description": "Famous marketplace in NCT Delhi", "state": "delhi", "city": "New Delhi", "category": "shopping", "image_url": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=800&h=600&fit=crop"},
                {"name": "Mall Road", "description": "Himalayan shopping street in Chandigarh", "state": "chandigarh", "city": "Chandigarh", "category": "urban", "image_url": "https://images.unsplash.com/photo-1482513755317-610b5e1b0135?w=800&h=600&fit=crop"},
                {"name": "Gandhi Memorial", "description": "Historic site in Ahmedabad", "state": "dadra_nagar_haveli_daman_diu", "city": "Daman", "category": "history", "image_url": "https://images.unsplash.com/photo-1475443332791-2ed1b46eb5a3?w=800&h=600&fit=crop"},
                {"name": "Promenade Beach", "description": "Serene waterfront in Puducherry", "state": "puducherry", "city": "Pondicherry", "category": "beach", "image_url": "https://images.unsplash.com/photo-1525186402429-c8f7a0e802f4?w=800&h=600&fit=crop"},
                {"name": "Agatti Island", "description": "Tropical island in Lakshadweep", "state": "lakshadweep", "city": "Agatti", "category": "island", "image_url": "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=800&h=600&fit=crop"},
                {"name": "Pangong Lake", "description": "Stunning blue lake in Ladakh", "state": "ladakh", "city": "Pangong", "category": "nature", "image_url": "https://images.unsplash.com/photo-1516455590571-18256e5bb9ff?w=800&h=600&fit=crop"},
            ]

            for spot_data in spots_data:
                spot = TouristSpot(**spot_data)
                db.session.add(spot)

            db.session.commit()

# Routes
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template("index.html")

@app.route('/dashboard')
@login_required
def dashboard():
    user_favorites = Favorite.query.filter_by(user_id=current_user.id).all()
    favorite_spots = [fav.spot for fav in user_favorites]
    return render_template("dashboard.html", favorites=favorite_spots)

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin:
        flash('Admin access is required to open that page.', 'warning')
        return redirect(url_for('dashboard'))
    db.create_all()
    if request.method == 'POST':
        action = (request.form.get('action') or '').strip()
        if action == 'add_transport_company':
            company_name = (request.form.get('company_name') or '').strip()
            transport_type = (request.form.get('transport_type') or '').strip().lower()
            service_area = (request.form.get('service_area') or '').strip()
            booking_url = (request.form.get('booking_url') or '').strip()
            contact_phone = (request.form.get('contact_phone') or '').strip()
            contact_email = (request.form.get('contact_email') or '').strip()
            description = (request.form.get('description') or '').strip()

            if not company_name or transport_type not in {'roadways', 'railways', 'aeroplane'}:
                flash('Please enter a company name and choose a valid transport type.', 'error')
                return redirect(url_for('admin'))

            new_company = TransportServiceCompany(
                company_name=company_name,
                transport_type=transport_type,
                service_area=service_area,
                booking_url=booking_url,
                contact_phone=contact_phone,
                contact_email=contact_email,
                description=description,
                created_by=current_user.id
            )
            db.session.add(new_company)
            db.session.commit()
            flash('Transport service company added successfully.', 'success')
            return redirect(url_for('admin'))

    users = User.query.order_by(User.created_at.desc()).all()
    spots = TouristSpot.query.order_by(TouristSpot.created_at.desc()).all()
    reviews_count = Review.query.count()
    transport_companies = TransportServiceCompany.query.order_by(TransportServiceCompany.created_at.desc()).all()
    return render_template(
        "admin.html",
        users=users,
        spots=spots,
        transport_companies=transport_companies,
        user_count=len(users),
        destination_count=len(spots),
        reviews_count=reviews_count,
        transport_company_count=len(transport_companies)
    )

@app.route('/explore')
def explore():
    return render_template("explore.html")

@app.route('/api/spots/<state>')
def get_spots(state):
    spots = TouristSpot.query.filter_by(state=state.lower()).all()
    spots_data = []
    for spot in spots:
        # Calculate average rating
        reviews = Review.query.filter_by(spot_id=spot.id).all()
        avg_rating = sum(review.rating for review in reviews) / len(reviews) if reviews else 0

        spots_data.append({
            "id": spot.id,
            "name": spot.name,
            "description": spot.description,
            "image": spot.image_url,
            "category": spot.category,
            "rating": round(avg_rating, 1),
            "review_count": len(reviews)
        })

    return jsonify({"places": spots_data})

@app.route('/spot/<int:spot_id>')
def spot_detail(spot_id):
    spot = TouristSpot.query.get_or_404(spot_id)
    reviews = Review.query.filter_by(spot_id=spot_id).order_by(Review.created_at.desc()).all()
    review_form = ReviewForm()

    # Check if user has favorited this spot
    is_favorite = False
    if current_user.is_authenticated:
        favorite = Favorite.query.filter_by(user_id=current_user.id, spot_id=spot_id).first()
        is_favorite = favorite is not None

    return render_template(
        "spot_detail.html",
        spot=spot,
        reviews=reviews,
        is_favorite=is_favorite,
        form=review_form,
        average_rating=get_average_rating(spot)
    )

@app.route('/add_favorite/<int:spot_id>', methods=['POST'])
@login_required
def add_favorite(spot_id):
    spot = TouristSpot.query.get_or_404(spot_id)
    existing_favorite = Favorite.query.filter_by(user_id=current_user.id, spot_id=spot_id).first()

    if existing_favorite:
        db.session.delete(existing_favorite)
        flash('Removed from favorites!', 'info')
    else:
        favorite = Favorite(user_id=current_user.id, spot_id=spot_id)
        db.session.add(favorite)
        flash('Added to favorites!', 'success')

    db.session.commit()
    return redirect(url_for('spot_detail', spot_id=spot_id))

@app.route('/add_review/<int:spot_id>', methods=['POST'])
@login_required
def add_review(spot_id):
    form = ReviewForm()
    if form.validate_on_submit():
        # Check if user already reviewed this spot
        existing_review = Review.query.filter_by(user_id=current_user.id, spot_id=spot_id).first()
        if existing_review:
            existing_review.rating = int(form.rating.data)
            existing_review.comment = form.comment.data
            flash('Review updated!', 'success')
        else:
            review = Review(
                user_id=current_user.id,
                spot_id=spot_id,
                rating=int(form.rating.data),
                comment=form.comment.data
            )
            db.session.add(review)
            flash('Review added!', 'success')

        db.session.commit()

    return redirect(url_for('spot_detail', spot_id=spot_id))

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            name=form.name.data,
            language=form.language.data,
            state=form.state.data,
            contact=form.contact.data
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            if is_safe_redirect_target(next_page):
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/journey', methods=['GET', 'POST'])
def journey():
    budget_plan = None
    if request.method == 'POST':
        action = (request.form.get('action') or 'route_planner').strip()
        start_point = request.form.get('starting_point', '').strip()
        destination_point = request.form.get('city', '').strip()
        transport_mode = request.form.get('transport_mode', 'any').strip().lower()
        journey_date = request.form.get('journey_date', '').strip()
        passengers = request.form.get('passengers', '1').strip()
        budget_amount = request.form.get('budget_amount', '').strip()
        budget_origin = request.form.get('budget_origin', '').strip()
        budget_travelers = request.form.get('budget_travelers', '1').strip()
        budget_style = request.form.get('budget_style', 'any').strip().lower()

        if action == 'budget_trip':
            if not budget_amount:
                flash('Please enter your budget amount first.', 'warning')
            else:
                try:
                    budget_plan = build_budget_trip_plan(
                        budget_amount,
                        travelers=budget_travelers,
                        trip_style=budget_style,
                        origin=budget_origin
                    )
                except Exception as error:
                    flash(f'Unable to build a budget plan right now: {error}', 'error')
        else:
            if not start_point or not destination_point:
                flash('Please select both starting point and destination point.', 'warning')
                return render_template(
                    'journey.html',
                    start_point=start_point,
                    destination_point=destination_point,
                    transport_mode=transport_mode,
                    journey_date=journey_date,
                    passengers=passengers,
                    budget_amount=budget_amount,
                    budget_origin=budget_origin,
                    budget_travelers=budget_travelers,
                    budget_style=budget_style
                )

            try:
                journey_result = build_journey_options(
                    start_point,
                    destination_point,
                    preferred_mode=transport_mode,
                    journey_date=journey_date,
                    passengers=passengers
                )
                return render_template(
                    'journey.html',
                    start_point=start_point,
                    destination_point=destination_point,
                    transport_mode=transport_mode,
                    journey_date=journey_date,
                    passengers=passengers,
                    budget_amount=budget_amount,
                    budget_origin=budget_origin,
                    budget_travelers=budget_travelers,
                    budget_style=budget_style,
                    journey_result=journey_result
                )
            except Exception as error:
                flash(f'Unable to fetch route details right now: {error}', 'error')

        return render_template(
            'journey.html',
            start_point=start_point,
            destination_point=destination_point,
            transport_mode=transport_mode,
            journey_date=journey_date,
            passengers=passengers,
            budget_amount=budget_amount,
            budget_origin=budget_origin,
            budget_travelers=budget_travelers,
            budget_style=budget_style,
            budget_plan=budget_plan
        )

    return render_template('journey.html')

@app.route('/search', methods=['POST'])
def search():
    if not current_user.is_authenticated:
        flash('Please login to search for places.', 'warning')
        return redirect(url_for('login'))

    city = request.form.get('city', '').lower().strip()

    # Find spots by city or state
    spots = TouristSpot.query.filter(
        (TouristSpot.state.ilike(f'%{city}%')) |
        (TouristSpot.city.ilike(f'%{city}%')) |
        (TouristSpot.name.ilike(f'%{city}%'))
    ).all()

    return render_template("search_results.html", city=city, spots=spots)

# API Routes for AJAX
@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').lower().strip()
    if not query:
        return jsonify([])

    spots = TouristSpot.query.filter(
        (TouristSpot.name.ilike(f'%{query}%')) |
        (TouristSpot.state.ilike(f'%{query}%')) |
        (TouristSpot.city.ilike(f'%{query}%'))
    ).limit(10).all()

    results = []
    for spot in spots:
        results.append({
            'id': spot.id,
            'name': spot.name,
            'state': spot.state,
            'image': spot.image_url
        })

    return jsonify(results)


@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    payload = request.get_json(silent=True) or {}
    message = (payload.get('message') or '').strip()
    history = get_chat_history()
    try:
        reply = chatbot_reply(message, history=history)
        if message and reply:
            history.extend([
                {'role': 'user', 'content': message},
                {'role': 'assistant', 'content': reply}
            ])
            save_chat_history(history)
        return jsonify({'reply': reply, 'history_count': len(get_chat_history())})
    except Exception as error:
        return jsonify({'reply': f'Sorry, I could not answer that right now. {error}'}), 500


@app.route('/api/internet/district-search')
def internet_district_search():
    state = request.args.get('state', '').strip()
    query = request.args.get('q', '').strip()
    if not state or len(query) < 2:
        return jsonify({'districts': []})

    try:
        districts = search_wikipedia_districts(state, query)
        return jsonify({'districts': districts})
    except Exception as error:
        return jsonify({'districts': [], 'error': str(error)}), 502


@app.route('/api/internet/places')
def internet_places():
    state = request.args.get('state', '').strip()
    district = request.args.get('district', '').strip()
    if not state:
        return jsonify({'places': [], 'error': 'State is required.'}), 400

    try:
        places = search_wikipedia_places(state, district)
        return jsonify({
            'places': places,
            'state': normalize_state_label(state),
            'district': district,
            'source': 'Wikipedia'
        })
    except Exception as error:
        return jsonify({'places': [], 'error': str(error)}), 502

@app.route('/favicon.ico')
def favicon():
    # Inline SVG favicon for Amandeep and Manas
    svg = '''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <rect width="100%" height="100%" fill="#1C87D2" rx="12" />
  <text x="50%" y="53%" font-family="Poppins, sans-serif" font-size="32" fill="#fff" font-weight="700" text-anchor="middle" dominant-baseline="middle">A+M</text>
</svg>
'''
    return Response(svg, mimetype='image/svg+xml', headers={'Cache-Control': 'public, max-age=86400'})

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# Initialize database for both local and Render
with app.app_context():
    init_db()

@app.route('/debug-db')
def debug_db():
    return app.config['SQLALCHEMY_DATABASE_URI']

if __name__ == '__main__':
    app.run()