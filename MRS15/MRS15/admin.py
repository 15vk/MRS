from flask import Blueprint, render_template, redirect, url_for, session, flash
from .models import User
from . import db

admin = Blueprint('admin', __name__)

@admin.route('/')
def admin_home():
    if 'admin_logged_in' in session:
        users = User.query.all()
        return render_template('admin.html', users=users)
    return redirect(url_for('main.home'))