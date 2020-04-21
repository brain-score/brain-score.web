from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

User = get_user_model()


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
	name = forms.CharField(max_length=200, help_text='Required')
	model_type = forms.ChoiceField(choices=[
		("BaseModel", "BaseModel - to submit a standard machine learning model"),
		("BrainModel", "BrainModel - to change brain-transformation, e.g. layer-mapping, visual degrees etc.")])
	zip_file = forms.FileField(help_text='Required')

	class Meta:
		model = UploadPlaceHolder
		fields = ( 'name', 'zip_file')

class ChangePasswordForm(PasswordChangeForm):
	def __init__(self, *args, **kwargs):
		super(ChangePasswordForm, self).__init__(*args, **kwargs)
		self.fields.pop('old_password')

	class Meta:
		fields=('new_password1', 'new_password2')
