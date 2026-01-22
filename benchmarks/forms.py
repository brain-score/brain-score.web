from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from django.forms.widgets import CheckboxInput
from django.utils.safestring import mark_safe

User = get_user_model()


class ToggleSwitchWidget(CheckboxInput):
    def render(self, name: str, value, attrs=None, renderer=None) -> str:  # noqa: ARG002
        checked = value if value is not None else False
        aria_pressed = "true" if checked else "false"
        checkbox_checked = "checked" if checked else ""

        initial_label = "Public" if checked else "Private"
        label_color = "#45C676" if checked else "#6b7280"

        return mark_safe(f'''
            <div class="toggle-wrapper">
                <input type="checkbox" name="{name}" id="id_{name}"
                       {checkbox_checked} style="display: none;">
                <button type="button" class="toggle-switch"
                        aria-pressed="{aria_pressed}"
                        onclick="var cb = document.getElementById('id_{name}');
                                 var label = document.getElementById('id_{name}_label');
                                 var pressed = this.getAttribute('aria-pressed') === 'true';
                                 this.setAttribute('aria-pressed', !pressed);
                                 cb.checked = !pressed;
                                 label.textContent = !pressed ? 'Public' : 'Private';
                                 label.style.color = !pressed ? '#45C676' : '#6b7280';">
                    <span class="knob"></span>
                </button>
                <span id="id_{name}_label" style="font-family: 'Open Sans', sans-serif; font-size: 13px; font-weight: 200; color: {label_color};">
                    {initial_label}
                </span>
            </div>
        ''')


class SignupForm(UserCreationForm):
    email = forms.EmailField(max_length=200, help_text='Required')

    def save(self, commit=True):
        user = super(SignupForm, self).save(commit=False)
        # Uses the email from this custom form password1 from the UserCreation Form it extends from.
        user.email = self.cleaned_data['email']
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            return user

    class Meta:
        # Uses the password1 and password2 fields from the UserCreation Form
        model = User
        fields = ('email',)


class LoginForm(AuthenticationForm):
    class Meta:
        model = User
        fields = ('email', 'password')


class UploadPlaceHolder(forms.Form):
    zip_file = forms.FileField(help_text='Required')
    config_file = forms.FileField(help_text='Required')


class UploadFileForm(forms.Form):
    zip_file = forms.FileField(label="", help_text='Required')
    public = forms.BooleanField(
        label='Model Score Visibility (modifiable):',
        required=False,
        initial=True,
        widget=ToggleSwitchWidget(),
        help_text='Toggle if you want the results of your submitted models included in the '
                  'public ranking.',
    )

    class Meta:
        model = UploadPlaceHolder
        fields = ('zip_file', 'public', 'competition')


class ChangePasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super(ChangePasswordForm, self).__init__(*args, **kwargs)
        self.fields.pop('old_password')

    class Meta:
        fields = ('new_password1', 'new_password2')
