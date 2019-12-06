from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class SignupForm(UserCreationForm):
    email = forms.EmailField(max_length=200, help_text='Required')

    def save(self, commit=True):
	    user = super(SignupForm, self).save(commit=False)
	    user.email = self.cleaned_data['email']
	    user.set_password(self.cleaned_data["password1"])
	    if commit:
	        user.save()
	    return user

    class Meta:
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
	model_type = forms.ChoiceField(choices=[("BaseModel", "BaseModel"), ("BrainModel", "BrainModel")])
	zip_file = forms.FileField(help_text='Required')


	class Meta:
		model = UploadPlaceHolder
		fields = ( 'name', 'zip_file')