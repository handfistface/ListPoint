from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, BooleanField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from database import Database
from bson.objectid import ObjectId
from PIL import Image
import os
from datetime import timedelta, datetime
import stripe
import uuid
from object_storage import ObjectStorageService
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

csrf = CSRFProtect(app)
db = Database()

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_dict):
        self.id = str(user_dict['_id'])
        self.email = user_dict['email']
        self.username = user_dict['username']
        self.is_admin = user_dict.get('is_admin', False)
        self.roles = user_dict.get('roles', [])
        self.groups = user_dict.get('groups', [])
        self.preferences = user_dict.get('preferences', {'theme': 'dark'})
        self.subscription = user_dict.get('subscription', {
            'is_ad_free': False,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
            'subscription_start': None,
            'subscription_end': None
        })

@login_manager.user_loader
def load_user(user_id):
    user_dict = db.get_user_by_id(user_id)
    if user_dict:
        return User(user_dict)
    return None

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])

class ListForm(FlaskForm):
    name = StringField('List Name', validators=[DataRequired(), Length(min=1, max=100)])
    tags = StringField('Tags (comma-separated)')
    is_public = BooleanField('Make Public')
    is_ethereal = BooleanField('Check List')

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File too large! Maximum size is 500KB. Please choose a smaller image.', 'error')
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def index():
    if current_user.is_authenticated:
        my_lists = db.get_lists_by_owner(current_user.id)
        favorited_lists = db.get_favorited_lists(current_user.id)
        collaborated_lists = db.get_collaborated_lists(current_user.id)
        
        for lst in my_lists:
            lst['is_favorited'] = db.is_favorited(current_user.id, str(lst['_id']))
        
        for lst in favorited_lists:
            owner = db.get_user_by_id(str(lst['owner_id']))
            lst['owner_username'] = owner['username'] if owner else 'Unknown'
            lst['is_favorited'] = True
        
        for lst in collaborated_lists:
            owner = db.get_user_by_id(str(lst['owner_id']))
            lst['owner_username'] = owner['username'] if owner else 'Unknown'
            lst['is_favorited'] = db.is_favorited(current_user.id, str(lst['_id']))
        
        return render_template('index.html', 
                             my_lists=my_lists, 
                             favorited_lists=favorited_lists,
                             collaborated_lists=collaborated_lists,
                             theme=current_user.preferences.get('theme', 'dark'))
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        if db.get_user_by_email(form.email.data):
            flash('Email already registered', 'error')
            return render_template('register.html', form=form)
        
        password_hash = generate_password_hash(form.password.data)
        user_id = db.create_user(form.email.data, form.username.data, password_hash)
        
        user_dict = db.get_user_by_id(str(user_id))
        user = User(user_dict)
        login_user(user)
        
        flash('Account created successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user_dict = db.get_user_by_email(form.email.data)
        if user_dict and check_password_hash(user_dict['password_hash'], form.password.data):
            user = User(user_dict)
            login_user(user)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('landing'))

@app.route('/landing')
def landing():
    adsense_publisher_id = os.getenv('GOOGLE_ADSENSE_PUBLISHER_ID', '')
    return render_template('landing.html', adsense_publisher_id=adsense_publisher_id)

@app.route('/about')
def about():
    theme = current_user.preferences.get('theme', 'dark') if current_user.is_authenticated else 'dark'
    return render_template('about.html', theme=theme)

@app.route('/contact')
def contact():
    theme = current_user.preferences.get('theme', 'dark') if current_user.is_authenticated else 'dark'
    return render_template('contact.html', theme=theme)

@app.route('/sitemap.xml')
def sitemap():
    pages = []
    ten_days_ago = (datetime.now() - timedelta(days=10)).date().isoformat()
    
    for rule in app.url_map.iter_rules():
        if "GET" in rule.methods and len(rule.arguments) == 0:
            if rule.endpoint not in ['static', 'sitemap', 'robots', 'stripe_webhook', 'objects', 'logout']:
                if not rule.rule.startswith('/api/') and not rule.rule.startswith('/admin/'):
                    pages.append({
                        'loc': url_for(rule.endpoint, _external=True),
                        'lastmod': ten_days_ago,
                        'changefreq': 'weekly',
                        'priority': '1.0' if rule.endpoint == 'index' else '0.8'
                    })
    
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{page["loc"]}</loc>\n'
        sitemap_xml += f'    <lastmod>{page["lastmod"]}</lastmod>\n'
        sitemap_xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        sitemap_xml += f'    <priority>{page["priority"]}</priority>\n'
        sitemap_xml += '  </url>\n'
    
    sitemap_xml += '</urlset>'
    
    return Response(sitemap_xml, mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    robots_txt = f"""User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin/
Disallow: /settings

Sitemap: {url_for('sitemap', _external=True)}
"""
    return Response(robots_txt, mimetype='text/plain')

@app.route('/google76025c41dd521010.html')
def google_verification():
    return Response('google-site-verification: google76025c41dd521010.html', mimetype='text/html')

@app.route('/sitemap.xml/google76025c41dd521010.html')
def google_verification_alt():
    return Response('google-site-verification: google76025c41dd521010.html', mimetype='text/html')

@app.route('/lists/create', methods=['GET', 'POST'])
@login_required
def create_list():
    form = ListForm()
    if form.validate_on_submit():
        tags = [tag.strip() for tag in form.tags.data.split(',') if tag.strip()]
        
        thumbnail_url = ''
        if 'thumbnail' in request.files:
            file = request.files['thumbnail']
            if file and file.filename:
                ext = os.path.splitext(secure_filename(file.filename))[1]
                
                try:
                    img = Image.open(file)
                    img.thumbnail((400, 400))
                    
                    img_io = io.BytesIO()
                    img_format = img.format or 'JPEG'
                    img.save(img_io, format=img_format)
                    img_io.seek(0)
                    
                    storage_service = ObjectStorageService()
                    thumbnail_url = storage_service.upload_thumbnail(img_io, ext)
                except Exception as e:
                    flash(f'Error uploading image: {str(e)}', 'error')
        
        list_id = db.create_list(
            name=form.name.data,
            owner_id=current_user.id,
            thumbnail_url=thumbnail_url,
            is_public=form.is_public.data,
            is_ethereal=form.is_ethereal.data,
            tags=tags
        )
        
        flash('List created successfully!', 'success')
        return redirect(url_for('view_list', list_id=str(list_id)))
    
    return render_template('create_list.html', form=form, theme=current_user.preferences.get('theme', 'dark'))

@app.route('/lists/<list_id>')
def view_list(list_id):
    list_doc = db.get_list_by_id(list_id)
    if not list_doc:
        flash('List not found', 'error')
        return redirect(url_for('index'))
    
    is_owner = current_user.is_authenticated and str(list_doc['owner_id']) == current_user.id
    is_collaborator = current_user.is_authenticated and db.is_collaborator(current_user.id, list_id)
    
    if not list_doc['is_public'] and not is_owner and not is_collaborator:
        flash('This list is private', 'error')
        return redirect(url_for('index'))
    
    owner = db.get_user_by_id(str(list_doc['owner_id']))
    list_doc['owner_username'] = owner['username'] if owner else 'Unknown'
    
    is_favorited = False
    if current_user.is_authenticated:
        is_favorited = db.is_favorited(current_user.id, list_id)
    
    theme = current_user.preferences.get('theme', 'dark') if current_user.is_authenticated else 'dark'
    adsense_publisher_id = os.getenv('GOOGLE_ADSENSE_PUBLISHER_ID', '')
    
    return render_template('view_list.html', 
                         current_list=list_doc, 
                         is_owner=is_owner,
                         is_collaborator=is_collaborator,
                         is_favorited=is_favorited,
                         theme=theme,
                         adsense_publisher_id=adsense_publisher_id)

@app.route('/lists/<list_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_list(list_id):
    list_doc = db.get_list_by_id(list_id)
    if not list_doc or str(list_doc['owner_id']) != current_user.id:
        flash('List not found or access denied', 'error')
        return redirect(url_for('index'))
    
    form = ListForm()
    if form.validate_on_submit():
        tags = [tag.strip() for tag in form.tags.data.split(',') if tag.strip()]
        
        update_data = {
            'name': form.name.data,
            'tags': tags,
            'is_public': form.is_public.data
        }
        
        if 'thumbnail' in request.files:
            file = request.files['thumbnail']
            if file and file.filename:
                ext = os.path.splitext(secure_filename(file.filename))[1]
                
                try:
                    img = Image.open(file)
                    img.thumbnail((400, 400))
                    
                    img_io = io.BytesIO()
                    img_format = img.format or 'JPEG'
                    img.save(img_io, format=img_format)
                    img_io.seek(0)
                    
                    storage_service = ObjectStorageService()
                    update_data['thumbnail_url'] = storage_service.upload_thumbnail(img_io, ext)
                except Exception as e:
                    flash(f'Error uploading image: {str(e)}', 'error')
        
        db.update_list(list_id, **update_data)
        flash('List updated successfully!', 'success')
        return redirect(url_for('view_list', list_id=list_id))
    
    form.name.data = list_doc['name']
    form.tags.data = ', '.join(list_doc.get('tags', []))
    form.is_public.data = list_doc['is_public']
    form.is_ethereal.data = list_doc.get('is_ethereal', False)
    
    collaborators_info = []
    for collab_id in list_doc.get('collaborators', []):
        user = db.get_user_by_id(str(collab_id))
        if user:
            collaborators_info.append({
                '_id': str(user['_id']),
                'username': user['username']
            })
    
    return render_template('edit_list.html', 
                         form=form, 
                         current_list=list_doc, 
                         collaborators=collaborators_info,
                         theme=current_user.preferences.get('theme', 'dark'))

@app.route('/lists/<list_id>/delete', methods=['POST'])
@login_required
def delete_list(list_id):
    list_doc = db.get_list_by_id(list_id)
    if list_doc and str(list_doc['owner_id']) == current_user.id:
        db.delete_list(list_id)
        flash('List deleted successfully', 'success')
    else:
        flash('List not found or access denied', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/lists/<list_id>/items', methods=['POST'])
@login_required
def add_item(list_id):
    list_doc = db.get_list_by_id(list_id)
    is_owner = list_doc and str(list_doc['owner_id']) == current_user.id
    is_collaborator = list_doc and db.is_collaborator(current_user.id, list_id)
    
    if not list_doc or (not is_owner and not is_collaborator):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    data = request.get_json()
    item_text = data.get('text', '').strip()
    
    if not item_text:
        return jsonify({'success': False, 'message': 'Item text is required'}), 400
    
    success, message, item_id = db.add_item_to_list(list_id, item_text)
    
    if success:
        db.update_autocomplete_cache(current_user.id, item_text)
    
    return jsonify({'success': success, 'message': message, 'item_id': item_id})

@app.route('/api/lists/<list_id>/items/<item_id>', methods=['DELETE'])
@login_required
def delete_item(list_id, item_id):
    list_doc = db.get_list_by_id(list_id)
    is_owner = list_doc and str(list_doc['owner_id']) == current_user.id
    is_collaborator = list_doc and db.is_collaborator(current_user.id, list_id)
    
    if not list_doc or (not is_owner and not is_collaborator):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    db.remove_item_from_list(list_id, item_id)
    return jsonify({'success': True})

@app.route('/api/lists/<list_id>/restore', methods=['POST'])
@login_required
def restore_list(list_id):
    list_doc = db.get_list_by_id(list_id)
    if not list_doc or str(list_doc['owner_id']) != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    data = request.get_json() or {}
    reset_checked_only = data.get('reset_checked_only', False)
    success = db.restore_ethereal_list(list_id, reset_checked_only)
    return jsonify({'success': success, 'message': 'List restored successfully' if success else 'Failed to restore list'})

@app.route('/api/lists/<list_id>/items/<item_id>/toggle', methods=['POST'])
def toggle_item(list_id, item_id):
    list_doc = db.get_list_by_id(list_id)
    if not list_doc:
        return jsonify({'success': False, 'message': 'List not found'}), 404
    
    is_owner = current_user.is_authenticated and str(list_doc['owner_id']) == current_user.id
    is_collaborator = current_user.is_authenticated and db.is_collaborator(current_user.id, list_id)
    
    if not list_doc['is_public'] and not is_owner and not is_collaborator:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    success, message = db.toggle_item_checked(list_id, item_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/lists/<list_id>/items/<item_id>/quantity', methods=['POST'])
@login_required
def adjust_quantity(list_id, item_id):
    list_doc = db.get_list_by_id(list_id)
    is_owner = list_doc and str(list_doc['owner_id']) == current_user.id
    is_collaborator = list_doc and db.is_collaborator(current_user.id, list_id)
    
    if not list_doc or (not is_owner and not is_collaborator):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    data = request.get_json()
    delta = data.get('delta', 0)
    
    success, message = db.adjust_item_quantity(list_id, item_id, delta)
    
    list_doc = db.get_list_by_id(list_id)
    new_quantity = 1
    for item in list_doc.get('items', []):
        if str(item['_id']) == str(item_id):
            new_quantity = item.get('quantity', 1)
            break
    
    return jsonify({'success': success, 'message': message, 'quantity': new_quantity})

@app.route('/api/lists/<list_id>/items/<item_id>', methods=['PUT'])
@login_required
def update_item(list_id, item_id):
    list_doc = db.get_list_by_id(list_id)
    is_owner = list_doc and str(list_doc['owner_id']) == current_user.id
    is_collaborator = list_doc and db.is_collaborator(current_user.id, list_id)
    
    if not list_doc or (not is_owner and not is_collaborator):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    data = request.get_json()
    new_text = data.get('text', '').strip()
    
    if not new_text:
        return jsonify({'success': False, 'message': 'Item text is required'}), 400
    
    success, message, old_text = db.update_item_text(list_id, item_id, new_text)
    
    if success:
        db.update_autocomplete_cache(current_user.id, new_text)
    
    return jsonify({'success': success, 'message': message, 'old_text': old_text})

@app.route('/api/lists/<list_id>/original/items/<item_id>', methods=['PUT'])
@login_required
def update_item_in_original(list_id, item_id):
    list_doc = db.get_list_by_id(list_id)
    if not list_doc or str(list_doc['owner_id']) != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    data = request.get_json()
    new_text = data.get('text', '').strip()
    
    if not new_text:
        return jsonify({'success': False, 'message': 'Item text is required'}), 400
    
    success, message, old_text = db.update_item_text_in_original(list_id, item_id, new_text)
    
    if success:
        db.update_autocomplete_cache(current_user.id, new_text)
    
    return jsonify({'success': success, 'message': message, 'old_text': old_text})

@app.route('/api/lists/<list_id>/original/items', methods=['POST'])
@login_required
def add_item_to_original(list_id):
    list_doc = db.get_list_by_id(list_id)
    if not list_doc or str(list_doc['owner_id']) != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    data = request.get_json()
    item_text = data.get('text', '').strip()
    
    if not item_text:
        return jsonify({'success': False, 'message': 'Item text is required'}), 400
    
    success, message, item_id = db.add_item_to_original(list_id, item_text)
    
    if success:
        db.update_autocomplete_cache(current_user.id, item_text)
    
    return jsonify({'success': success, 'message': message, 'item_id': item_id})

@app.route('/api/lists/<list_id>/original/items/<item_id>', methods=['DELETE'])
@login_required
def delete_item_from_original(list_id, item_id):
    list_doc = db.get_list_by_id(list_id)
    if not list_doc or str(list_doc['owner_id']) != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    success = db.remove_item_from_original(list_id, item_id)
    return jsonify({'success': success})

@app.route('/api/autocomplete')
@login_required
def autocomplete():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    suggestions = db.get_autocomplete_suggestions(current_user.id, query)
    return jsonify(suggestions)

@app.route('/api/theme', methods=['POST'])
@login_required
def update_theme():
    data = request.get_json()
    theme = data.get('theme', 'dark')
    db.update_user_theme(current_user.id, theme)
    return jsonify({'success': True})

@app.route('/explore')
def explore():
    search_query = request.args.get('q', '')
    tags_param = request.args.get('tags', '')
    tags = [tag.strip() for tag in tags_param.split(',') if tag.strip()]
    
    public_lists = db.get_public_lists(search_query, tags if tags else None)
    
    for lst in public_lists:
        owner = db.get_user_by_id(str(lst['owner_id']))
        lst['owner_username'] = owner['username'] if owner else 'Unknown'
        if current_user.is_authenticated:
            lst['is_favorited'] = db.is_favorited(current_user.id, str(lst['_id']))
        else:
            lst['is_favorited'] = False
    
    theme = current_user.preferences.get('theme', 'dark') if current_user.is_authenticated else 'dark'
    
    return render_template('explore.html', 
                         lists=public_lists, 
                         search_query=search_query,
                         theme=theme)

@app.route('/api/favorite/<list_id>', methods=['POST'])
@login_required
def toggle_favorite(list_id):
    is_favorited = db.is_favorited(current_user.id, list_id)
    
    if is_favorited:
        db.remove_favorite(current_user.id, list_id)
        return jsonify({'success': True, 'favorited': False})
    else:
        success = db.add_favorite(current_user.id, list_id)
        return jsonify({'success': success, 'favorited': True})

@app.route('/create-subscription-session', methods=['POST'])
@login_required
def create_subscription_session():
    try:
        domain = os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')
        
        user_dict = db.get_user_by_id(current_user.id)
        stripe_customer_id = user_dict.get('subscription', {}).get('stripe_customer_id')
        
        if not stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={'user_id': current_user.id}
            )
            stripe_customer_id = customer.id
            db.update_user_subscription(
                current_user.id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=None,
                is_ad_free=False
            )
        
        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Ad-Free Subscription',
                        'description': 'Remove all ads from List Point',
                    },
                    'unit_amount': 500,
                    'recurring': {
                        'interval': 'month',
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f'https://{domain}/subscription-success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'https://{domain}/settings',
        )
        
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        flash(f'Error creating subscription: {str(e)}', 'error')
        return redirect(url_for('settings'))

@app.route('/subscription-success')
@login_required
def subscription_success():
    session_id = request.args.get('session_id')
    
    if session_id:
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            subscription_id = checkout_session.subscription
            
            db.update_user_subscription(
                current_user.id,
                stripe_customer_id=checkout_session.customer,
                stripe_subscription_id=subscription_id,
                is_ad_free=True,
                subscription_start=datetime.utcnow()
            )
            
            flash('Subscription activated! Ads have been removed.', 'success')
        except Exception as e:
            flash(f'Error processing subscription: {str(e)}', 'error')
    
    return redirect(url_for('settings'))

@app.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    try:
        user_dict = db.get_user_by_id(current_user.id)
        subscription_id = user_dict.get('subscription', {}).get('stripe_subscription_id')
        
        if subscription_id:
            stripe.Subscription.delete(subscription_id)
            db.cancel_user_subscription(current_user.id)
            flash('Subscription cancelled successfully.', 'success')
        else:
            flash('No active subscription found.', 'error')
    except Exception as e:
        flash(f'Error cancelling subscription: {str(e)}', 'error')
    
    return redirect(url_for('settings'))

@app.route('/customer-portal', methods=['POST'])
@login_required
def customer_portal():
    try:
        user_dict = db.get_user_by_id(current_user.id)
        stripe_customer_id = user_dict.get('subscription', {}).get('stripe_customer_id')
        
        if not stripe_customer_id:
            flash('No subscription found.', 'error')
            return redirect(url_for('settings'))
        
        domain = os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')
        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=f'https://{domain}/settings',
        )
        
        return redirect(session.url, code=303)
    except Exception as e:
        flash(f'Error accessing customer portal: {str(e)}', 'error')
        return redirect(url_for('settings'))

@app.route('/stripe-webhook', methods=['POST'])
@csrf.exempt
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET', '')
        )
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400
    
    if event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        user_dict = db.get_user_by_stripe_customer_id(customer_id)
        if user_dict:
            db.cancel_user_subscription(str(user_dict['_id']))
    
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        user_dict = db.get_user_by_stripe_customer_id(customer_id)
        if user_dict:
            is_active = subscription['status'] in ['active', 'trialing']
            if not is_active:
                db.cancel_user_subscription(str(user_dict['_id']))
    
    return jsonify({'status': 'success'}), 200

@app.route('/api/users/<user_id>')
@login_required
def get_user(user_id):
    user = db.get_user_by_id(user_id)
    if user:
        return jsonify({'username': user['username'], '_id': str(user['_id'])})
    return jsonify({'error': 'User not found'}), 404

@app.route('/api/search_users')
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'users': []})
    
    users = db.search_users_by_username(query, limit=5)
    return jsonify({'users': users})

@app.route('/api/lists/<list_id>/collaborators', methods=['POST'])
@login_required
@csrf.exempt
def add_collaborator(list_id):
    try:
        list_doc = db.get_list_by_id(list_id)
        if not list_doc or str(list_doc['owner_id']) != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        data = request.get_json()
        username = data.get('username', '').strip()
        
        if not username:
            return jsonify({'success': False, 'message': 'Username is required'}), 400
        
        user = db.get_user_by_username(username)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        success, message = db.add_collaborator(list_id, str(user['_id']))
        if success:
            return jsonify({'success': True, 'message': message, 'user': {'username': user['username'], '_id': str(user['_id'])}})
        else:
            return jsonify({'success': False, 'message': message}), 400
    except Exception as e:
        print(f"Error adding collaborator: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/lists/<list_id>/collaborators/<user_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def remove_collaborator(list_id, user_id):
    list_doc = db.get_list_by_id(list_id)
    if not list_doc or str(list_doc['owner_id']) != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    success, message = db.remove_collaborator(list_id, user_id)
    return jsonify({'success': success, 'message': message})

@app.route('/settings')
@login_required
def settings():
    user_dict = db.get_user_by_id(current_user.id)
    subscription = user_dict.get('subscription', {})
    
    subscription_info = None
    if subscription.get('stripe_subscription_id'):
        try:
            stripe_sub = stripe.Subscription.retrieve(subscription['stripe_subscription_id'])
            subscription_info = {
                'status': stripe_sub.status,
                'current_period_end': datetime.fromtimestamp(stripe_sub.current_period_end),
                'cancel_at_period_end': stripe_sub.cancel_at_period_end
            }
        except:
            subscription_info = None
    
    theme = current_user.preferences.get('theme', 'dark')
    return render_template('settings.html', 
                         subscription=subscription,
                         subscription_info=subscription_info,
                         theme=theme)

@app.route('/objects/<path:object_path>')
def serve_object(object_path):
    try:
        storage_service = ObjectStorageService()
        file_data = storage_service.get_object_file(f'/objects/{object_path}')
        response = Response()
        return storage_service.download_object(file_data, response)
    except FileNotFoundError:
        return 'Object not found', 404
    except Exception as e:
        print(f"Error serving object: {str(e)}")
        return 'Internal server error', 500

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    users = db.get_all_users()
    theme = current_user.preferences.get('theme', 'dark')
    return render_template('admin_users.html', users=users, theme=theme)

@app.route('/admin/user/<user_id>')
@login_required
def admin_user_detail(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    user_dict = db.get_user_by_id(user_id)
    if not user_dict:
        flash('User not found', 'error')
        return redirect(url_for('admin_users'))
    
    user_dict.pop('password_hash', None)
    theme = current_user.preferences.get('theme', 'dark')
    return render_template('admin_user_detail.html', user=user_dict, theme=theme)

@app.route('/admin/user/<user_id>/edit', methods=['POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    field = request.json.get('field')
    value = request.json.get('value')
    
    if field == 'password_hash':
        return jsonify({'success': False, 'message': 'Cannot edit password directly'}), 400
    
    success = db.update_user_field(user_id, field, value)
    return jsonify({'success': success})

@app.route('/admin/user/<user_id>/role', methods=['POST'])
@login_required
def manage_user_role(user_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    action = request.json.get('action')
    role = request.json.get('role')
    
    if action == 'add':
        success = db.add_user_role(user_id, role)
    elif action == 'remove':
        success = db.remove_user_role(user_id, role)
    else:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400
    
    return jsonify({'success': success})

@app.route('/admin/user/<user_id>/group', methods=['POST'])
@login_required
def manage_user_group(user_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    action = request.json.get('action')
    group = request.json.get('group')
    
    if action == 'add':
        success = db.add_user_group(user_id, group)
    elif action == 'remove':
        success = db.remove_user_group(user_id, group)
    else:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400
    
    return jsonify({'success': success})

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
