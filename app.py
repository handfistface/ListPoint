from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
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
from datetime import timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

csrf = CSRFProtect(app)
db = Database()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_dict):
        self.id = str(user_dict['_id'])
        self.email = user_dict['email']
        self.username = user_dict['username']
        self.preferences = user_dict.get('preferences', {'theme': 'dark'})

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
    is_ethereal = BooleanField('Ethereal List')

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/')
def index():
    if current_user.is_authenticated:
        my_lists = db.get_lists_by_owner(current_user.id)
        favorited_lists = db.get_favorited_lists(current_user.id)
        
        for lst in my_lists:
            lst['is_favorited'] = False
        
        for lst in favorited_lists:
            owner = db.get_user_by_id(str(lst['owner_id']))
            lst['owner_username'] = owner['username'] if owner else 'Unknown'
            lst['is_favorited'] = True
        
        return render_template('index.html', 
                             my_lists=my_lists, 
                             favorited_lists=favorited_lists,
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
    return render_template('landing.html')

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
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{current_user.id}_{filename}")
                
                try:
                    img = Image.open(file)
                    img.thumbnail((400, 400))
                    img.save(filepath)
                    thumbnail_url = f'/static/uploads/{current_user.id}_{filename}'
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
    
    if not list_doc['is_public'] and not is_owner:
        flash('This list is private', 'error')
        return redirect(url_for('index'))
    
    owner = db.get_user_by_id(str(list_doc['owner_id']))
    list_doc['owner_username'] = owner['username'] if owner else 'Unknown'
    
    is_favorited = False
    if current_user.is_authenticated:
        is_favorited = db.is_favorited(current_user.id, list_id)
    
    theme = current_user.preferences.get('theme', 'dark') if current_user.is_authenticated else 'dark'
    
    return render_template('view_list.html', 
                         current_list=list_doc, 
                         is_owner=is_owner,
                         is_favorited=is_favorited,
                         theme=theme)

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
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{current_user.id}_{filename}")
                
                try:
                    img = Image.open(file)
                    img.thumbnail((400, 400))
                    img.save(filepath)
                    update_data['thumbnail_url'] = f'/static/uploads/{current_user.id}_{filename}'
                except Exception as e:
                    flash(f'Error uploading image: {str(e)}', 'error')
        
        db.update_list(list_id, **update_data)
        flash('List updated successfully!', 'success')
        return redirect(url_for('view_list', list_id=list_id))
    
    form.name.data = list_doc['name']
    form.tags.data = ', '.join(list_doc.get('tags', []))
    form.is_public.data = list_doc['is_public']
    form.is_ethereal.data = list_doc.get('is_ethereal', False)
    
    return render_template('edit_list.html', form=form, current_list=list_doc, theme=current_user.preferences.get('theme', 'dark'))

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
    if not list_doc or str(list_doc['owner_id']) != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    data = request.get_json()
    item_text = data.get('text', '').strip()
    
    if not item_text:
        return jsonify({'success': False, 'message': 'Item text is required'}), 400
    
    success, message = db.add_item_to_list(list_id, item_text)
    
    if success:
        db.update_autocomplete_cache(current_user.id, item_text)
    
    return jsonify({'success': success, 'message': message})

@app.route('/api/lists/<list_id>/items/<item_id>', methods=['DELETE'])
@login_required
def delete_item(list_id, item_id):
    list_doc = db.get_list_by_id(list_id)
    if not list_doc or str(list_doc['owner_id']) != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    db.remove_item_from_list(list_id, item_id)
    return jsonify({'success': True})

@app.route('/api/lists/<list_id>/restore', methods=['POST'])
@login_required
def restore_list(list_id):
    list_doc = db.get_list_by_id(list_id)
    if not list_doc or str(list_doc['owner_id']) != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    success = db.restore_ethereal_list(list_id)
    return jsonify({'success': success, 'message': 'List restored successfully' if success else 'Failed to restore list'})

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

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
