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
    'placeholder:text-[#a0a09e] focus:outline-none focus:border-[#5d674f] transition-colors'
)

SELECT_CLASS = (
    'w-full bg-transparent border-b border-[#dcdacd] py-2 pb-3 text-base text-[#1a1a1a] '
    'focus:outline-none focus:border-[#5d674f] transition-colors'
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
                widget.attrs.setdefault('class', 'w-4 h-4 accent-[#5d674f]')
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
        self.fields['email'].widget.attrs['placeholder'] = 'voce@email.com'
        self.fields['password1'].label = 'Senha'
        self.fields['password2'].label = 'Confirme a senha'
        self.fields['password1'].widget.attrs['placeholder'] = 'Mínimo de 8 caracteres'
        self.fields['password2'].widget.attrs['placeholder'] = 'Repita a senha'


class EmailAuthenticationForm(StyledFormMixin, AuthenticationForm):
    """Login form. The username field holds the email, since it is the USERNAME_FIELD."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'E-mail'
        self.fields['username'].widget = forms.EmailInput(
            attrs={'class': TEXT_INPUT_CLASS, 'placeholder': 'voce@email.com', 'autofocus': True}
        )
        self.fields['password'].label = 'Senha'
        self.fields['password'].widget.attrs['placeholder'] = 'Sua senha'


class StyledPasswordResetForm(StyledFormMixin, PasswordResetForm):
    """Asks for the email that will receive the reset link."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'E-mail'
        self.fields['email'].widget.attrs['placeholder'] = 'voce@email.com'


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    """Sets the new password after the link is confirmed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Nova senha'
        self.fields['new_password2'].label = 'Confirme a nova senha'


class ProfileForm(StyledFormMixin, forms.ModelForm):
    """Biometric data and reminder channel."""

    class Meta:
        model = Profile
        fields = ['birth_date', 'sex', 'height_cm', 'target_weight_kg', 'phone', 'notification_channel']
        widgets = {'birth_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['birth_date'].input_formats = ['%Y-%m-%d']
        self.fields['height_cm'].widget.attrs['placeholder'] = 'Ex.: 178'
        self.fields['target_weight_kg'].widget.attrs['placeholder'] = 'Ex.: 78.5'
        self.fields['phone'].widget.attrs['placeholder'] = '(00) 00000-0000'


class UserForm(StyledFormMixin, forms.ModelForm):
    """Name and email of the account itself."""

    class Meta:
        model = User
        fields = ['full_name', 'email']
        labels = {'full_name': 'Nome completo', 'email': 'E-mail'}
