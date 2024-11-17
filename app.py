# app.py
import uuid
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, flash, abort, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crm.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

from datetime import datetime, timedelta
import random  # Для демо-данных


@app.template_filter('currency_rub')
def currency_rub(value):
    """Форматирует число как денежную сумму в рублях"""
    try:
        return "{:,.2f} ₽".format(float(value)).replace(',', ' ')
    except (ValueError, TypeError):
        return "0.00 ₽"


@app.route('/api/profit-data')
@login_required
def profit_data():
    # Создаем демо-данные за последние 30 дней
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    dates = []
    revenue_data = []
    costs_data = []
    profit_data = []

    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.strftime('%d.%m'))
        # Генерируем демо-данные
        revenue = random.uniform(50000, 150000)
        costs = random.uniform(30000, 80000)
        profit = revenue - costs

        revenue_data.append(revenue)
        costs_data.append(costs)
        profit_data.append(profit)

        current_date += timedelta(days=1)

    return {
        'dates': dates,
        'revenue': revenue_data,
        'costs': costs_data,
        'profit': profit_data
    }

# Модели данных
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='customer', lazy=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    deadline = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Form(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    fields = db.relationship('FormField', backref='form', lazy=True, cascade='all, delete-orphan')
    submissions = db.relationship('FormSubmission', backref='form', lazy=True, cascade='all, delete-orphan')

class FormField(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('form.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    field_type = db.Column(db.String(20), nullable=False)  # text, email, tel, date, time, select
    required = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    options = db.Column(db.Text)  # Для select, хранит опции в формате JSON
    placeholder = db.Column(db.String(200))

class FormSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('form.id'), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='new')  # new, processed, completed


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Маршруты аутентификации
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Неверные учетные данные')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# Основные маршруты
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    # Базовая статистика
    customers = Customer.query.count()
    orders = Order.query.count()
    tasks = Task.query.filter_by(status='pending').count()

    # Статистика по заказам
    total_orders_sum = db.session.query(func.sum(Order.amount)).scalar() or 0
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()

    # Статистика по формам
    active_forms = Form.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()

    new_submissions = FormSubmission.query.join(Form).filter(
        Form.user_id == current_user.id,
        FormSubmission.status == 'new'
    ).count()

    recent_submissions = FormSubmission.query.join(Form).filter(
        Form.user_id == current_user.id
    ).order_by(
        FormSubmission.created_at.desc()
    ).limit(5).all()

    return render_template(
        'dashboard.html',
        customers=customers,
        orders=orders,
        tasks=tasks,
        total_orders_sum=total_orders_sum,
        recent_orders=recent_orders,
        active_forms=active_forms,
        new_submissions=new_submissions,
        recent_submissions=recent_submissions
    )


# Маршруты для работы с клиентами
@app.route('/customers')
@login_required
def customers():
    customers_list = Customer.query.all()
    return render_template('customers.html', customers=customers_list)


@app.route('/customer/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        customer = Customer(
            name=request.form['name'],
            email=request.form['email'],
            phone=request.form['phone']
        )
        db.session.add(customer)
        db.session.commit()
        flash('Клиент добавлен успешно')
        return redirect(url_for('customers'))
    return render_template('customer_form.html')


# Маршруты для работы с заказами
@app.route('/orders')
@login_required
def orders():
    orders_list = Order.query.all()
    return render_template('orders.html', orders=orders_list)


@app.route('/order/add', methods=['GET', 'POST'])
@login_required
def add_order():
    if request.method == 'POST':
        order = Order(
            customer_id=request.form['customer_id'],
            description=request.form['description'],
            amount=float(request.form['amount'])
        )
        db.session.add(order)
        db.session.commit()
        flash('Заказ добавлен успешно')
        return redirect(url_for('orders'))
    customers = Customer.query.all()
    return render_template('order_form.html', customers=customers)


# Маршруты для работы с задачами
@app.route('/tasks')
@login_required
def tasks():
    tasks_list = Task.query.all()
    return render_template('tasks.html', tasks=tasks_list)


@app.route('/task/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        task = Task(
            title=request.form['title'],
            description=request.form['description'],
            deadline=datetime.strptime(request.form['deadline'], '%Y-%m-%d'),
            assigned_to=request.form['assigned_to']
        )
        db.session.add(task)
        db.session.commit()
        flash('Задача добавлена успешно')
        return redirect(url_for('tasks'))
    users = User.query.all()
    return render_template('task_form.html', users=users)


@app.route('/forms')
@login_required
def forms():
    user_forms = Form.query.filter_by(user_id=current_user.id).all()
    return render_template('forms/forms.html', forms=user_forms)


@app.route('/forms/create', methods=['GET', 'POST'])
@login_required
def create_form():
    if request.method == 'POST':
        # Генерируем уникальный slug для формы
        slug = str(uuid.uuid4())[:8]

        form = Form(
            user_id=current_user.id,
            name=request.form['name'],
            description=request.form['description'],
            slug=slug
        )
        db.session.add(form)
        db.session.commit()

        # Получаем данные о полях формы из POST запроса
        field_names = request.form.getlist('field_name[]')
        field_types = request.form.getlist('field_type[]')
        field_required = request.form.getlist('field_required[]')
        field_options = request.form.getlist('field_options[]')
        field_placeholders = request.form.getlist('field_placeholder[]')

        for i in range(len(field_names)):
            field = FormField(
                form_id=form.id,
                name=field_names[i],
                field_type=field_types[i],
                required='required' in field_required,
                order=i,
                options=field_options[i] if field_options[i] else None,
                placeholder=field_placeholders[i]
            )
            db.session.add(field)

        db.session.commit()
        flash('Форма успешно создана')
        return redirect(url_for('forms'))

    return render_template('forms/create_form.html')


@app.route('/forms/<slug>')
def public_form(slug):
    form = Form.query.filter_by(slug=slug).first_or_404()
    if not form.is_active:
        abort(404)
    return render_template('forms/public_form.html', form=form)


@app.route('/forms/<slug>/submit', methods=['POST'])
def submit_form(slug):
    form = Form.query.filter_by(slug=slug).first_or_404()
    if not form.is_active:
        abort(404)

    submission_data = {}
    for field in form.fields:
        value = request.form.get(f'field_{field.id}')
        submission_data[field.name] = value

    submission = FormSubmission(
        form_id=form.id,
        data=submission_data
    )
    db.session.add(submission)
    db.session.commit()

    flash('Форма успешно отправлена')
    return redirect(url_for('form_success'))


@app.route('/forms/<slug>/submissions')
@login_required
def form_submissions(slug):
    form = Form.query.filter_by(slug=slug, user_id=current_user.id).first_or_404()
    submissions = FormSubmission.query.filter_by(form_id=form.id).order_by(FormSubmission.created_at.desc()).all()
    return render_template('forms/submissions.html', form=form, submissions=submissions)


@app.route('/forms/submission/<int:submission_id>')
@login_required
def get_submission(submission_id):
    submission = FormSubmission.query.get_or_404(submission_id)
    # Проверяем, принадлежит ли форма текущему пользователю
    if submission.form.user_id != current_user.id:
        abort(403)
    return jsonify({
        'id': submission.id,
        'data': submission.data,
        'created_at': submission.created_at.strftime('%d.%m.%Y %H:%M'),
        'status': submission.status
    })


@app.route('/forms/submission/<int:submission_id>/status', methods=['POST'])
@login_required
def update_submission_status(submission_id):
    submission = FormSubmission.query.get_or_404(submission_id)
    if submission.form.user_id != current_user.id:
        abort(403)

    data = request.get_json()
    submission.status = data.get('status')
    db.session.commit()

    return jsonify({'success': True})


@app.route('/forms/submission/<int:submission_id>', methods=['DELETE'])
@login_required
def delete_submission(submission_id):
    submission = FormSubmission.query.get_or_404(submission_id)
    if submission.form.user_id != current_user.id:
        abort(403)

    db.session.delete(submission)
    db.session.commit()

    return jsonify({'success': True})


@app.route('/forms/<slug>/export')
@login_required
def export_submissions(slug, xlsxwriter=None):
    form = Form.query.filter_by(slug=slug, user_id=current_user.id).first_or_404()
    submissions = FormSubmission.query.filter_by(form_id=form.id).order_by(FormSubmission.created_at.desc()).all()

    # Создаем Excel файл
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()

    # Заголовки
    headers = ['ID', 'Дата'] + [field.name for field in form.fields] + ['Статус']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)

    # Данные
    for row, submission in enumerate(submissions, start=1):
        worksheet.write(row, 0, submission.id)
        worksheet.write(row, 1, submission.created_at.strftime('%d.%m.%Y %H:%M'))

        for col, field in enumerate(form.fields, start=2):
            worksheet.write(row, col, submission.data.get(field.name, ''))

        worksheet.write(row, len(headers) - 1, submission.status)

    workbook.close()
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'submissions_{slug}_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )


@app.route('/form-success')
def form_success():
    return render_template('forms/success.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)