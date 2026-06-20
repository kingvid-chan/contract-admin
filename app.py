import os
import uuid
from datetime import datetime

from flask import (Flask, Blueprint, render_template, request, redirect,
                   url_for, flash, send_from_directory, abort, make_response)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, Contract, Attachment


# ---- App Factory -----------------------------------------------------------
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure instance and upload folders exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)

    # Init extensions
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'main.login_form'
    login_manager.login_message = '请先登录后再访问该页面。'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ---- Blueprint ---------------------------------------------------------
    main_bp = Blueprint('main', __name__,
                        url_prefix='/projects/contract-admin',
                        static_folder='static')

    # ---- After-request: Cache-Control: no-cache on all HTML ---------------
    @main_bp.after_request
    def add_cache_headers(response):
        if response.content_type and 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    # ---- Helper: allowed file ----------------------------------------------
    def allowed_file(filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in app.config['ALLOWED_EXTENSIONS']

    # =====================================================================
    #  ROUTES
    # =====================================================================

    # -- Index ------------------------------------------------------------
    @main_bp.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))
        return redirect(url_for('main.login_form'))

    # -- Health Check -----------------------------------------------------
    @main_bp.route('/healthz')
    def healthz():
        return {'status': 'ok', 'version': '0.0.1'}, 200

    # -- Auth: Login -----------------------------------------------------
    @main_bp.route('/login', methods=['GET'])
    def login_form():
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))
        return render_template('login.html')

    @main_bp.route('/login', methods=['POST'])
    def login():
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('用户名和密码不能为空。', 'danger')
            return render_template('login.html'), 400

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash('用户名或密码错误。', 'danger')
            return render_template('login.html'), 401

        login_user(user, remember=bool(request.form.get('remember')))
        flash(f'欢迎回来，{user.username}！', 'success')
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('main.dashboard'))

    # -- Auth: Logout ----------------------------------------------------
    @main_bp.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('您已成功退出登录。', 'info')
        return redirect(url_for('main.login_form'))

    # -- Auth: Register --------------------------------------------------
    @main_bp.route('/register', methods=['GET'])
    def register_form():
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))
        return render_template('register.html')

    @main_bp.route('/register', methods=['POST'])
    def register():
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        errors = []
        if not username or len(username) < 2:
            errors.append('用户名至少需要2个字符。')
        if not password or len(password) < 6:
            errors.append('密码至少需要6个字符。')
        if password != password_confirm:
            errors.append('两次输入的密码不一致。')

        existing = User.query.filter_by(username=username).first()
        if existing:
            errors.append('该用户名已被注册。')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('register.html'), 400

        user = User(username=username, role='user')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('注册成功！请登录。', 'success')
        return redirect(url_for('main.login_form'))

    # -- Dashboard --------------------------------------------------------
    @main_bp.route('/dashboard')
    @login_required
    def dashboard():
        user_count = User.query.count()
        contract_count = Contract.query.count()

        status_counts = {
            'draft': Contract.query.filter_by(status='draft').count(),
            'active': Contract.query.filter_by(status='active').count(),
            'completed': Contract.query.filter_by(status='completed').count(),
            'terminated': Contract.query.filter_by(status='terminated').count(),
        }

        recent_contracts = (Contract.query
                            .order_by(Contract.created_at.desc())
                            .limit(5)
                            .all())

        return render_template('dashboard.html',
                               user_count=user_count,
                               contract_count=contract_count,
                               status_counts=status_counts,
                               recent_contracts=recent_contracts)

    # =====================================================================
    #  USER CRUD
    # =====================================================================

    @main_bp.route('/users')
    @login_required
    def user_list():
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template('users/list.html', users=users)

    @main_bp.route('/users/create', methods=['GET'])
    @login_required
    def user_create_form():
        return render_template('users/form.html', user=None, form_action='create')

    @main_bp.route('/users/create', methods=['POST'])
    @login_required
    def user_create():
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'user')

        errors = []
        if not username or len(username) < 2:
            errors.append('用户名至少需要2个字符。')
        if not password or len(password) < 6:
            errors.append('密码至少需要6个字符。')
        if role not in ('admin', 'user'):
            errors.append('无效的角色。')
        if User.query.filter_by(username=username).first():
            errors.append('用户名已存在。')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('users/form.html', user=None, form_action='create'), 400

        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'用户 {username} 创建成功。', 'success')
        return redirect(url_for('main.user_list'))

    @main_bp.route('/users/<int:id>/edit', methods=['GET'])
    @login_required
    def user_edit_form(id):
        user = db.session.get(User, id)
        if user is None:
            abort(404)
        return render_template('users/form.html', user=user, form_action='edit')

    @main_bp.route('/users/<int:id>/edit', methods=['POST'])
    @login_required
    def user_edit(id):
        user = db.session.get(User, id)
        if user is None:
            abort(404)

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'user')

        errors = []
        if not username or len(username) < 2:
            errors.append('用户名至少需要2个字符。')
        if role not in ('admin', 'user'):
            errors.append('无效的角色。')

        existing = User.query.filter(User.username == username, User.id != id).first()
        if existing:
            errors.append('用户名已被其他用户使用。')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('users/form.html', user=user, form_action='edit'), 400

        user.username = username
        user.role = role
        if password:
            if len(password) < 6:
                flash('密码至少需要6个字符。', 'danger')
                return render_template('users/form.html', user=user, form_action='edit'), 400
            user.set_password(password)

        db.session.commit()
        flash(f'用户 {username} 更新成功。', 'success')
        return redirect(url_for('main.user_list'))

    @main_bp.route('/users/<int:id>/delete', methods=['POST'])
    @login_required
    def user_delete(id):
        user = db.session.get(User, id)
        if user is None:
            abort(404)

        if user.id == current_user.id:
            flash('不能删除自己的账号。', 'danger')
            return redirect(url_for('main.user_list'))

        username = user.username
        db.session.delete(user)
        db.session.commit()
        flash(f'用户 {username} 已删除。', 'success')
        return redirect(url_for('main.user_list'))

    # =====================================================================
    #  CONTRACT CRUD
    # =====================================================================

    @main_bp.route('/contracts')
    @login_required
    def contract_list():
        contracts = (Contract.query
                     .order_by(Contract.updated_at.desc())
                     .all())
        return render_template('contracts/list.html', contracts=contracts)

    @main_bp.route('/contracts/create', methods=['GET'])
    @login_required
    def contract_create_form():
        return render_template('contracts/form.html', contract=None, form_action='create')

    @main_bp.route('/contracts/create', methods=['POST'])
    @login_required
    def contract_create():
        name = request.form.get('name', '').strip()
        contract_number = request.form.get('contract_number', '').strip()
        amount_str = request.form.get('amount', '').strip()
        signing_date_str = request.form.get('signing_date', '').strip()
        status = request.form.get('status', 'draft')

        errors = []
        if not name:
            errors.append('合同名称不能为空。')
        if not contract_number:
            errors.append('合同编号不能为空。')
        if status not in Contract.VALID_STATUSES:
            errors.append('无效的合同状态。')
        if Contract.query.filter_by(contract_number=contract_number).first():
            errors.append('合同编号已存在。')

        amount = None
        if amount_str:
            try:
                amount = float(amount_str)
            except ValueError:
                errors.append('合同金额格式无效。')

        signing_date = None
        if signing_date_str:
            try:
                signing_date = datetime.strptime(signing_date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('签约日期格式无效（应为 YYYY-MM-DD）。')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('contracts/form.html', contract=None, form_action='create'), 400

        contract = Contract(
            name=name,
            contract_number=contract_number,
            amount=amount,
            signing_date=signing_date,
            status=status,
            created_by=current_user.id
        )
        db.session.add(contract)
        db.session.commit()

        flash(f'合同「{name}」创建成功。', 'success')
        return redirect(url_for('main.contract_list'))

    @main_bp.route('/contracts/<int:id>')
    @login_required
    def contract_detail(id):
        contract = db.session.get(Contract, id)
        if contract is None:
            abort(404)
        attachments = contract.attachments.order_by(Attachment.uploaded_at.desc()).all()
        return render_template('contracts/detail.html', contract=contract, attachments=attachments)

    @main_bp.route('/contracts/<int:id>/edit', methods=['GET'])
    @login_required
    def contract_edit_form(id):
        contract = db.session.get(Contract, id)
        if contract is None:
            abort(404)
        return render_template('contracts/form.html', contract=contract, form_action='edit')

    @main_bp.route('/contracts/<int:id>/edit', methods=['POST'])
    @login_required
    def contract_edit(id):
        contract = db.session.get(Contract, id)
        if contract is None:
            abort(404)

        name = request.form.get('name', '').strip()
        contract_number = request.form.get('contract_number', '').strip()
        amount_str = request.form.get('amount', '').strip()
        signing_date_str = request.form.get('signing_date', '').strip()
        status = request.form.get('status', 'draft')

        errors = []
        if not name:
            errors.append('合同名称不能为空。')
        if not contract_number:
            errors.append('合同编号不能为空。')
        if status not in Contract.VALID_STATUSES:
            errors.append('无效的合同状态。')

        existing = Contract.query.filter(
            Contract.contract_number == contract_number,
            Contract.id != id
        ).first()
        if existing:
            errors.append('合同编号已被其他合同使用。')

        amount = None
        if amount_str:
            try:
                amount = float(amount_str)
            except ValueError:
                errors.append('合同金额格式无效。')

        signing_date = None
        if signing_date_str:
            try:
                signing_date = datetime.strptime(signing_date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('签约日期格式无效（应为 YYYY-MM-DD）。')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('contracts/form.html', contract=contract, form_action='edit'), 400

        contract.name = name
        contract.contract_number = contract_number
        contract.amount = amount
        contract.signing_date = signing_date
        contract.status = status
        db.session.commit()

        flash(f'合同「{name}」更新成功。', 'success')
        return redirect(url_for('main.contract_list'))

    @main_bp.route('/contracts/<int:id>/delete', methods=['POST'])
    @login_required
    def contract_delete(id):
        contract = db.session.get(Contract, id)
        if contract is None:
            abort(404)

        # Delete attachment files from disk
        for att in contract.attachments:
            file_full_path = os.path.join(app.config['UPLOAD_FOLDER'], att.file_path)
            if os.path.exists(file_full_path):
                os.remove(file_full_path)

        name = contract.name
        db.session.delete(contract)
        db.session.commit()
        flash(f'合同「{name}」已删除。', 'success')
        return redirect(url_for('main.contract_list'))

    # =====================================================================
    #  ATTACHMENTS
    # =====================================================================

    @main_bp.route('/contracts/<int:id>/attachments/upload', methods=['POST'])
    @login_required
    def attachment_upload(id):
        contract = db.session.get(Contract, id)
        if contract is None:
            abort(404)

        file = request.files.get('attachment')
        if not file or file.filename == '':
            flash('请选择一个文件。', 'danger')
            return redirect(url_for('main.contract_detail', id=id))

        if not allowed_file(file.filename):
            flash('仅支持 .pdf、.doc 和 .docx 格式的文件。', 'danger')
            return redirect(url_for('main.contract_detail', id=id))

        # Check file size (also enforced by MAX_CONTENT_LENGTH)
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > 10 * 1024 * 1024:
            flash('文件大小不能超过 10MB。', 'danger')
            return redirect(url_for('main.contract_detail', id=id))

        # Generate unique filename
        original_name = secure_filename(file.filename)
        ext = os.path.splitext(original_name)[1].lower()
        unique_name = f'{uuid.uuid4().hex}{ext}'

        # Store in uploads/<contract_id>/ directory
        upload_subdir = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
        os.makedirs(upload_subdir, exist_ok=True)

        file_path_rel = os.path.join(str(id), unique_name)
        file_full_path = os.path.join(app.config['UPLOAD_FOLDER'], file_path_rel)
        file.save(file_full_path)

        attachment = Attachment(
            contract_id=id,
            filename=unique_name,
            original_filename=original_name,
            file_path=file_path_rel,
            file_size=size,
            mime_type=file.content_type
        )
        db.session.add(attachment)
        db.session.commit()

        flash(f'附件「{original_name}」上传成功。', 'success')
        return redirect(url_for('main.contract_detail', id=id))

    @main_bp.route('/contracts/<int:id>/attachments/<int:aid>/download')
    @login_required
    def attachment_download(id, aid):
        attachment = Attachment.query.filter_by(id=aid, contract_id=id).first()
        if attachment is None:
            abort(404)

        file_full_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment.file_path)
        if not os.path.exists(file_full_path):
            flash('文件不存在或已被删除。', 'danger')
            return redirect(url_for('main.contract_detail', id=id))

        upload_dir = os.path.dirname(file_full_path)
        return send_from_directory(
            upload_dir,
            attachment.filename,
            download_name=attachment.original_filename,
            as_attachment=True
        )

    @main_bp.route('/contracts/<int:id>/attachments/<int:aid>/view')
    @login_required
    def attachment_view(id, aid):
        attachment = Attachment.query.filter_by(id=aid, contract_id=id).first()
        if attachment is None:
            abort(404)

        file_full_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment.file_path)
        if not os.path.exists(file_full_path):
            flash('文件不存在或已被删除。', 'danger')
            return redirect(url_for('main.contract_detail', id=id))

        upload_dir = os.path.dirname(file_full_path)

        # PDF -> inline, Word -> download (most browsers can't inline Word)
        if attachment.is_pdf():
            return send_from_directory(
                upload_dir,
                attachment.filename,
                mimetype='application/pdf',
                as_attachment=False
            )
        else:
            # Word files: send as attachment since inline is unreliable
            return send_from_directory(
                upload_dir,
                attachment.filename,
                download_name=attachment.original_filename,
                as_attachment=True,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                if attachment.original_filename.lower().endswith('.docx')
                else 'application/msword'
            )

    # -- Error Handlers ---------------------------------------------------
    @main_bp.errorhandler(413)
    def too_large(e):
        flash('上传文件超过最大限制（10MB）。', 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))

    @main_bp.errorhandler(404)
    def not_found(e):
        return render_template('base.html', content='<h2>404 - 页面未找到</h2>'), 404

    # ---- Register blueprint ------------------------------------------------
    app.register_blueprint(main_bp)

    # ---- App-level error handlers ------------------------------------------
    @app.errorhandler(404)
    def app_not_found(e):
        return render_template('base.html', content='<h2>404 - 页面未找到</h2>'), 404

    @app.errorhandler(413)
    def app_too_large(e):
        flash('上传文件超过最大限制（10MB）。', 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))


    return app


# ---- Entry Point -----------------------------------------------------------
if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=5301, debug=True)
else:
    # For gunicorn: `gunicorn app:application`
    application = create_app()
