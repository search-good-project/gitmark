#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
from flask import render_template, redirect, request, flash, url_for, current_app, session
from flask.views import MethodView
from flask_login import login_user, logout_user, login_required, current_user
from flask_principal import Identity, AnonymousIdentity, identity_changed

from . import models, forms, github_auth
from main import models as main_models
from .permissions import admin_permission, su_permission
from utils.misc import send_user_confirm_mail
from gitmark.config import GitmarkSettings

PER_PAGE = GitmarkSettings['pagination']['admin_per_page']
default_user_image = GitmarkSettings['default_user_image']

class LoginView(MethodView):
    template_name = 'accounts/login.html'

    def get(self, form=None):
        if not current_user.is_anonymous:
            return redirect(url_for('main.index'))
        if not form:
            form = forms.LoginForm()
        return render_template(self.template_name, form=form)

    def post(self):
        if request.form.get('login_github'):
            session['oauth_callback_type'] = 'login'
            return github_auth.github_auth()
            # return 'login_github'

        form = forms.LoginForm(obj=request.form)
        if form.validate():
            try:
                user = models.User.objects.get(username=form.username.data)
            except models.User.DoesNotExist:
                user = None

            if user and user.verify_password(form.password.data):
                login_user(user, form.remember_me.data)
                user.last_login = datetime.datetime.now
                user.save()
                identity_changed.send(current_app._get_current_object(), identity=Identity(user.username))
                return redirect(request.args.get('next') or url_for('main.index'))
            flash('Invalid username or password', 'danger')
        return self.get(form=form)

@login_required
def logout():
    logout_user()
    # Remove session keys set by Flask-Principal
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)

    # Tell Flask-Principal the user is anonymous
    identity_changed.send(current_app._get_current_object(), identity=AnonymousIdentity())

    flash('You have been logged out', 'success')
    return redirect(url_for('accounts.login'))

def register(create_su=False):
    if not GitmarkSettings['allow_registration']:
        msg = 'Register is forbidden, please contact administrator'
        return msg

    if create_su and not GitmarkSettings['allow_su_creation']:
        msg = 'Register superuser is forbidden, please contact administrator'
        return msg

    form = forms.RegistrationForm()
    if form.validate_on_submit():
        user = models.User()
        user.username = form.username.data
        user.password = form.password.data
        user.email = form.email.data

        user.display_name = user.username
        user.avatar_url = default_user_image

        if create_su and GitmarkSettings['allow_su_creation']:
            user.is_superuser = True
        user.save()

        return redirect(url_for('main.index'))

    return render_template('accounts/registration.html', form=form)

class RegistrationView(MethodView):
    template_name = 'accounts/registration.html'

    def get(self, form=None, create_su=False):
        if not current_user.is_anonymous:
            return redirect(url_for('main.index'))

        if not GitmarkSettings['allow_registration']:
            msg = 'Register is forbidden, please contact administrator'
            return msg

        if create_su and not GitmarkSettings['allow_su_creation']:
            msg = 'Register superuser is forbidden, please contact administrator'
            return msg

        if not form:
            form = forms.RegistrationForm()

        return render_template(self.template_name, form=form, create_su=create_su)

    def post(self, create_su=False):
        if request.form.get('github'):
            session['oauth_callback_type'] = 'register'
            return github_auth.github_auth()
            # return 'github register'

        form = forms.RegistrationForm(obj=request.form)
        if form.validate():
            user = models.User()
            user.username = form.username.data
            user.password = form.password.data
            user.email = form.email.data

            user.display_name = user.username
            user.avatar_url = default_user_image

            if create_su and GitmarkSettings['allow_su_creation']:
                user.is_superuser = True
            user.save()

            return redirect(url_for('main.index'))
        return self.get(form=form, create_su=create_su)


@login_required
def add_user():
    form = forms.RegistrationForm()
    if form.validate_on_submit():
        user = models.User()
        user.username = form.username.data
        user.password = form.password.data
        user.email = form.email.data

        user.display_name = user.username
        user.avatar_url = default_user_image

        user.save()

        return redirect(url_for('accounts.users'))

    return render_template('accounts/registration.html', form=form)

def get_current_user():
    user = models.User.objects.get(username=current_user.username)
    return user


class Users(MethodView):
    decorators = [login_required, admin_permission.require(401)]
    template_name = 'accounts/users.html'
    def get(self):
        roles_raw = models.ROLES
        # roles = [role[1] for role in roles_raw]
        roles = ['superuser']
        roles.extend([role[1] for role in roles_raw])
        current_role = request.args.get('current_role')

        users = models.User.objects.all()
        if current_role:
            users = users.filter(role=current_role) if not current_role == 'superuser' else users.filter(is_superuser=True)

        try:
            cur_page = int(request.args.get('page', 1))
        except ValueError:
            cur_page = 1
        total_page = len(users)//PER_PAGE+1 if len(users)%PER_PAGE >0 else len(users)//PER_PAGE
        if cur_page > total_page:
            cur_page = total_page
        users = users.paginate(page=cur_page, per_page=PER_PAGE)

        data = {
            'users': users,
            'roles': roles,
            'current_role': current_role
        }
        return render_template(self.template_name, **data)

class User(MethodView):
    decorators = [login_required, admin_permission.require(401)]
    template_name = 'accounts/user.html'

    def get_context(self, username, form=None):
        user = models.User.objects.get_or_404(username=username)
        if not form:
            # user = models.User.objects.get_or_404(username=username)
            form = forms.UserForm(obj=user)
        data = {'form':form, 'user':user}
        return data

    def get(self, username, form=None):
        data = self.get_context(username, form)
        return render_template(self.template_name, **data)

    def post(self, username):
        form = forms.UserForm(obj=request.form)
        if form.validate():
            user = models.User.objects.get_or_404(username=username)
            if user.email != form.email.data:
                user.is_email_confirmed = False
            user.email = form.email.data
            # print 'is superuser:', request.form.get('is_superuser1')
            # user.is_active = (request.form.get('is_active')!=None)
            user.is_superuser = (request.form.get('is_superuser')!=None)
            user.is_email_confirmed = (request.form.get('is_email_confirmed')!=None)
            user.role = form.role.data
            user.save()
            flash('Succeed to update user details', 'success')
            return redirect(url_for('accounts.edit_user', username=username))
        return self.get(username, form)

    def delete(self, username):
        user = models.User.objects.get_or_404(username=username)
        user.delete()

        if request.args.get('ajax'):
            return 'success'

        msg = 'Succeed to delete user'

        flash(msg, 'success')
        return redirect(url_for('accounts.users'))

class SuUsers(MethodView):
    decorators = [login_required, su_permission.require(401)]
    template_name = 'accounts/su_users.html'
    def get(self):
        users = models.User.objects.all()
        return render_template(self.template_name, users=users)

class SuUser(MethodView):
    decorators = [login_required, admin_permission.require(401)]
    template_name = 'accounts/user.html'

    def get_context(self, username, form=None):
        if not form:
            user = models.User.objects.get_or_404(username=username)
            user.weibo = user.social_networks['weibo'].get('url')
            user.weixin = user.social_networks['weixin'].get('url')
            user.twitter = user.social_networks['twitter'].get('url')
            user.github = user.social_networks['github'].get('url')
            user.facebook = user.social_networks['facebook'].get('url')
            user.linkedin = user.social_networks['linkedin'].get('url')

            form = forms.SuUserForm(obj=user)
        data = {'form':form}
        return data

    def get(self, username, form=None):
        data = self.get_context(username, form)
        return render_template(self.template_name, **data)

    def post(self, username):
        form = forms.SuUserForm(obj=request.form)
        if form.validate():
            user = models.User.objects.get_or_404(username=username)

            user.email = form.email.data
            user.is_email_confirmed = form.is_email_confirmed.data

            user.display_name = form.display_name.data
            user.biography = form.biography.data
            user.homepage_url = form.homepage_url.data or None
            user.social_networks['weibo']['url'] = form.weibo.data or None
            user.social_networks['weixin']['url'] = form.weixin.data or None
            user.social_networks['twitter']['url'] = form.twitter.data or None
            user.social_networks['github']['url'] = form.github.data or None
            user.social_networks['facebook']['url'] = form.facebook.data or None
            user.social_networks['linkedin']['url'] = form.linkedin.data or None
            user.save()

            msg = 'Succeed to update user profile'
            flash(msg, 'success')

            return redirect(url_for('accounts.su_edit_user', username=user.username))

        return self.get(form)

class Profile(MethodView):
    decorators = [login_required]
    template_name = 'accounts/settings.html'

    def get(self, form=None):
        if not form:
            user = current_user
            user.weibo = user.social_networks['weibo'].get('url')
            user.weixin = user.social_networks['weixin'].get('url')
            user.twitter = user.social_networks['twitter'].get('url')
            # user.github = user.social_networks['github'].get('url')
            user.facebook = user.social_networks['facebook'].get('url')
            user.linkedin = user.social_networks['linkedin'].get('url')
            form = forms.ProfileForm(obj=user)
        data = {'form': form}
        return render_template(self.template_name, **data)

    def post(self):
        form = forms.ProfileForm(obj=request.form)
        if form.validate():
            # user = get_current_user()
            user = current_user
            # if user.email != form.email.data:
            #     user.email = form.email.data
            #     user.is_email_confirmed = False

            user.display_name = form.display_name.data
            user.biography = form.biography.data
            user.homepage_url = form.homepage_url.data or None
            user.avatar_url = form.avatar_url.data or None
            user.social_networks['weibo']['url'] = form.weibo.data or None
            user.social_networks['weixin']['url'] = form.weixin.data or None
            user.social_networks['twitter']['url'] = form.twitter.data or None
            # user.social_networks['github']['url'] = form.github.data or None
            user.social_networks['facebook']['url'] = form.facebook.data or None
            user.social_networks['linkedin']['url'] = form.linkedin.data or None
            user.save()

            msg = 'Succeed to update user profile'
            flash(msg, 'success')

            return redirect(url_for('accounts.settings'))

        return self.get(form)

class Password(MethodView):
    decorators = [login_required]
    template_name = 'accounts/password.html'

    def get(self, password_form=None, password_form2=None, user_form=None):
        if not password_form:
            password_form = forms.PasswordForm()
        if not password_form2:
            password_form2 = forms.PasswordForm2()
        if not user_form:
            user_form = forms.UsernameForm(obj=current_user)

        data = {}
        data['password_form'] = password_form
        data['password_form2'] = password_form2
        data['user_form'] = user_form
        data['user'] = current_user

        email_resend_flag = False
        if current_user.confirm_email_sent_time and (datetime.datetime.now()-current_user.confirm_email_sent_time).seconds < 3600:
            email_resend_flag = True

        # now = datetime.datetime.now()
        # print current_user.confirm_email_sent_time, now, now-current_user.confirm_email_sent_time

        data['email_resend_flag'] = email_resend_flag

        return render_template(self.template_name, **data)

    def post(self):
        password_form = None
        password_form2 = None
        user_form = None

        if request.form.get('local'):
            password_form = forms.PasswordForm(obj=request.form)
            if password_form.validate():
                current_user.password = password_form.new_password.data
                current_user.save()
                msg = 'Succeed to update password'
                flash(msg, 'success')

                return redirect(url_for('accounts.password'))

        if request.form.get('github'):
            password_form2 = forms.PasswordForm2(obj=request.form)
            if password_form2.validate():
                session['oauth_callback_type'] = 'reset_password'
                verified = github_auth.github_auth()
                if verified:
                    current_user.password = password_form2.new_password.data
                    current_user.save()
                    msg = 'Succeed to update password'
                    flash(msg, 'success')

                    return redirect(url_for('accounts.password'))

        if request.form.get('user_form'):
            user_form = forms.UsernameForm(obj=request.form)
            if user_form.validate():
                if current_user.username != user_form.username.data:
                    # old_name = current_user.username
                    repos = main_models.Repo.objects(starred_users=current_user.username)
                    repos.modify(add_to_set__starred_users=user_form.username.data)
                    repos.modify(pop__starred_users=current_user.username)

                    collections = main_models.Collection.objects(owner=current_user.username)
                    collections.modify(set__owner=user_form.username.data)

                    current_user.username = user_form.username.data

                if user_form.email.data != current_user.email:
                    current_user.email = user_form.email.data
                    current_user.is_email_confirmed = False

                current_user.save()

                msg = 'Succeed to update account'
                flash(msg, 'success')

                return redirect(url_for('accounts.password'))

        if request.form.get('email'):
            if current_user.email:
                token = current_user.generate_confirmation_token()
                send_user_confirm_mail(current_user.email, current_user, token)
                current_user.confirm_email_sent_time = datetime.datetime.now()
                current_user.save()
                flash('Confirmation message has been sent, please check your email to confirm your account')
                # return 'sending confirm email'
            else:
                flash('Set your email first!', 'danger')

        return self.get(password_form=password_form, password_form2=password_form2, user_form=user_form)

class ConfirmEmail(MethodView):
    decorators = [login_required]

    def get(self, token):
        if current_user.is_email_confirmed:
            return redirect(url_for('accounts.password'))

        if current_user.confirm_email(token):
            flash('Your email has been confirmed', 'success')
        else:
            flash('The confirmation link is invalid or has expired', 'danger')

        return redirect(url_for('accounts.password'))
