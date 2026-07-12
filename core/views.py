import random
import io
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse

from .models import User, OTPRecord, PrescriptionAnalysis
from .ai_service import extract_text_from_pdf, gemini_request
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if User.objects.filter(email=email).exists() or User.objects.filter(username=username).exists():
            messages.error(request, "Username or email already exists.")
            return render(request, 'core/register.html')

        otp = str(random.randint(100000, 999999))
        OTPRecord.objects.update_or_create(
            email=email,
            defaults={
                'otp': otp,
                'username_temp': username,
                'password_temp': password
            }
        )

        send_mail(
            "Medical AI Verification OTP",
            f"Your verification OTP is {otp}",
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=False,
        )

        request.session['verify_email'] = email
        return redirect('verify_otp')

    return render(request, 'core/register.html')

def verify_otp_view(request):
    email = request.session.get('verify_email')
    if not email:
        return redirect('register')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        try:
            record = OTPRecord.objects.get(email=email)
            if record.otp == entered_otp:
                user = User.objects.create_user(
                    username=record.username_temp,
                    email=email,
                    password=record.password_temp,
                    is_verified=True
                )
                record.delete()
                del request.session['verify_email']
                messages.success(request, "Account created successfully. Please log in.")
                return redirect('login')
            else:
                messages.error(request, "Wrong OTP")
        except OTPRecord.DoesNotExist:
            messages.error(request, "Session expired or invalid email.")
            return redirect('register')

    return render(request, 'core/verify_otp.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # We need to find the user by email, but authenticate takes username.
        # Since we set USERNAME_FIELD = 'email' in our custom model, we pass email as username.
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid email or password.")
            
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required(login_url='login')
def dashboard_view(request):
    clean_prescription = ""
    ai_analysis = ""
    
    if request.method == 'POST':
        file = request.FILES.get('prescription')
        if file:
            # We save it temporarily using the model
            analysis = PrescriptionAnalysis(user=request.user, file_upload=file)
            analysis.save()
            
            filepath = analysis.file_upload.path
            try:
                if filepath.lower().endswith(".pdf"):
                    input_data = extract_text_from_pdf(filepath)
                else:
                    input_data = Image.open(filepath)
                
                output = gemini_request(input_data)
                
                # Clean up any asterisks here in Python instead of in the template
                output = output.replace('*', '')
                
                if "AI ANALYSIS:" in output:
                    clean_prescription = output.split("AI ANALYSIS:")[0]
                    ai_analysis = output.split("AI ANALYSIS:")[1]
                else:
                    clean_prescription = output
                    ai_analysis = output
                
                analysis.clean_prescription = clean_prescription
                analysis.ai_analysis = ai_analysis
                analysis.save()
            except Exception as e:
                ai_analysis = "Error processing file: " + str(e)
                clean_prescription = "Error"
                
    history = PrescriptionAnalysis.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'core/dashboard.html', {
        'clean_prescription': clean_prescription,
        'ai_analysis': ai_analysis,
        'history': history
    })

@login_required(login_url='login')
def download_pdf(request, analysis_id):
    try:
        analysis = PrescriptionAnalysis.objects.get(id=analysis_id, user=request.user)
    except PrescriptionAnalysis.DoesNotExist:
        return HttpResponse("Analysis not found.", status=404)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Title
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 750, "Medical Prescription AI Analysis")
    
    p.setFont("Helvetica", 10)
    p.drawString(50, 730, f"Date: {analysis.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    y = 700
    
    # Text wrapping helper
    def draw_wrapped_text(text_block, y_start):
        y_pos = y_start
        p.setFont("Helvetica", 10)
        lines = text_block.split('\n')
        for line in lines:
            words = line.split(' ')
            current_line = ""
            for word in words:
                if p.stringWidth(current_line + word, "Helvetica", 10) < 500:
                    current_line += word + " "
                else:
                    p.drawString(50, y_pos, current_line)
                    y_pos -= 15
                    current_line = word + " "
                    if y_pos < 50:
                        p.showPage()
                        p.setFont("Helvetica", 10)
                        y_pos = 750
            if current_line:
                p.drawString(50, y_pos, current_line)
                y_pos -= 15
                if y_pos < 50:
                    p.showPage()
                    p.setFont("Helvetica", 10)
                    y_pos = 750
        return y_pos

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Clean Prescription:")
    y -= 20
    y = draw_wrapped_text(analysis.clean_prescription, y)
    
    y -= 30
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "AI Analysis:")
    y -= 20
    draw_wrapped_text(analysis.ai_analysis, y)

    p.showPage()
    p.save()

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="prescription_analysis_{analysis.id}.pdf"'
    return response
