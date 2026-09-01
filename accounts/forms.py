"""Authentication and profile forms.

Widget classes come straight from the Soluna design system: underlined inputs on a
transparent background, olive focus ring, pill shaped selects.
"""

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    BaseUserCreationForm,
    PasswordResetForm,
    SetPasswordForm,
)

from .models import Profile, User

TEXT_INPUT_CLASS = (
    'w-full bg-transparent border-b border-[#dcdacd] py-2 pb-3 text-base text-[#1a1a1a] '
    'placeholder:text-[#686865] focus:border-[#5d674f] focus-visible:outline-none '
    'focus-visible:ring-2 focus-visible:ring-[#5d674f]/30 focus-visible:ring-offset-2 '
    'focus-visible:ring-offset-[#f5f4f0] transition-colors'
)

SELECT_CLASS = (
    'w-full bg-transparent border-b border-[#dcdacd] py-2 pb-3 text-base text-[#1a1a1a] '
    'focus:border-[#5d674f] focus-visible:outline-none focus-visible:ring-2 '
    'focus-visible:ring-[#5d674f]/30 focus-visible:ring-offset-2 '
    'focus-visible:ring-offset-[#f5f4f0] transition-colors'
)


class StyledFormMixin:
    """Applies the design system classes to every widget of the form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault('class', SELECT_CLASS)
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault(
                    'class',
                    'w-5 h-5 accent-[#5d674f] focus-visible:outline-none '
                    'focus-visible:ring-2 focus-visible:ring-[#5d674f] focus-visible:ring-offset-2',
                )
            else:
                widget.attrs.setdefault('class', TEXT_INPUT_CLASS)


class SignupForm(StyledFormMixin, BaseUserCreationForm):
    """Account creation: email, name and password."""

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ['full_name', 'email']
        labels = {'full_name': 'Nome completo', 'email': 'E-mail'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['full_name'].widget.attrs['placeholder'] = 'Como você quer ser chamado'
        self.fields['full_name'].widget.attrs['autocomplete'] = 'name'
        self.fields['email'].widget.attrs['placeholder'] = 'voce@email.com'
        self.fields['email'].widget.attrs['autocomplete'] = 'email'
        self.fields['password1'].label = 'Senha'
        self.fields['password2'].label = 'Confirme a senha'
        self.fields['password1'].widget.attrs['placeholder'] = 'Mínimo de 8 caracteres'
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['placeholder'] = 'Repita a senha'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'


class EmailAuthenticationForm(StyledFormMixin, AuthenticationForm):
    """Login form. The username field holds the email, since it is the USERNAME_FIELD."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'E-mail'
        self.fields['username'].widget = forms.EmailInput(
            attrs={
                'class': TEXT_INPUT_CLASS,
                'placeholder': 'voce@email.com',
                'autocomplete': 'email',
                'autofocus': True,
            }
        )
        self.fields['password'].label = 'Senha'
        # pr-12 abre espaço para o botão de revelar a senha (partials/_password_field.html).
        self.fields['password'].widget.attrs['class'] = TEXT_INPUT_CLASS + ' pr-12'
        self.fields['password'].widget.attrs['placeholder'] = 'Sua senha'
        self.fields['password'].widget.attrs['autocomplete'] = 'current-password'


class StyledPasswordResetForm(StyledFormMixin, PasswordResetForm):
    """Asks for the email that will receive the reset link."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'E-mail'
        self.fields['email'].widget.attrs['placeholder'] = 'voce@email.com'
        self.fields['email'].widget.attrs['autocomplete'] = 'email'


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    """Sets the new password after the link is confirmed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Nova senha'
        self.fields['new_password2'].label = 'Confirme a nova senha'
        self.fields['new_password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['new_password2'].widget.attrs['autocomplete'] = 'new-password'


class ProfileForm(StyledFormMixin, forms.ModelForm):
    """Biometric data and reminder channel."""

    class Meta:
        model = Profile
        fields = ['birth_date', 'sex', 'height_cm', 'target_weight_kg', 'phone', 'notification_channel']
        widgets = {'birth_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['birth_date'].input_formats = ['%Y-%m-%d']
        self.fields['birth_date'].widget.attrs['autocomplete'] = 'bday'
        self.fields['height_cm'].widget.attrs['placeholder'] = 'Ex.: 178'
        self.fields['target_weight_kg'].widget.attrs['placeholder'] = 'Ex.: 78.5'
        self.fields['phone'].widget.attrs['placeholder'] = '(00) 00000-0000'
        self.fields['phone'].widget.attrs['autocomplete'] = 'tel'


class UserForm(StyledFormMixin, forms.ModelForm):
    """Name and email of the account itself."""

    class Meta:
        model = User
        fields = ['full_name', 'email']
        labels = {'full_name': 'Nome completo', 'email': 'E-mail'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['full_name'].widget.attrs['autocomplete'] = 'name'
        self.fields['email'].widget.attrs['autocomplete'] = 'email'
