from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

class OTPRecord(models.Model):
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    username_temp = models.CharField(max_length=150)
    password_temp = models.CharField(max_length=128)

    def __str__(self):
        return f"{self.email} - {self.otp}"

class PrescriptionAnalysis(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analyses')
    file_upload = models.FileField(upload_to='prescriptions/')
    clean_prescription = models.TextField(blank=True, default='')
    ai_analysis = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analysis for {self.user.email} on {self.created_at.strftime('%Y-%m-%d')}"
