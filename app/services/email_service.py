# app/services/email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings


class EmailService:

    @staticmethod
    def send_loan_form_link(
        to_email: str,
        to_name: str,
        form_url: str,
        contact_ref: str,
        expire_minutes: int = 5,  # changed from expire_hours to expire_minutes
    ) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Complete Your Loan Application"
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = to_email

            html = f"""
            <html>
            <body style="font-family:'Segoe UI',sans-serif;
                         background:#f8fafc;padding:32px;color:#1e293b;">

              <div style="max-width:520px;margin:0 auto;background:#fff;
                          border-radius:12px;padding:32px;
                          border:1px solid #e2e8f0;">

                <h2 style="color:#0891b2;margin-bottom:4px;">
                  Loan Application Form
                </h2>
                <p style="color:#64748b;font-size:13px;margin-top:0;">
                  Reference: {contact_ref}
                </p>

                <p>Hello <strong>{to_name}</strong>,</p>

                <p style="color:#475569;">
                  Your personalised loan application form is ready.
                  Please click the button below to fill in your details.
                </p>

                <div style="text-align:center;margin:28px 0;">
                  <a href="{form_url}"
                     style="display:inline-block;padding:14px 32px;
                            background:#0891b2;color:#fff;
                            border-radius:8px;text-decoration:none;
                            font-weight:700;font-size:15px;">
                    Fill Loan Application
                  </a>
                </div>

                <p style="font-size:12px;color:#94a3b8;">
                  Or copy this link into your browser:<br/>
                  <span style="color:#0891b2;word-break:break-all;">
                    {form_url}
                  </span>
                </p>

                <div style="background:#fff7ed;border:1px solid #fed7aa;
                            border-radius:8px;padding:12px 16px;
                            margin-top:16px;">
                  <p style="margin:0;font-size:12px;color:#c2410c;">
                    This link will expire in
                    <strong>{expire_minutes} minutes</strong>.
                    Please complete your application before it expires.
                  </p>
                </div>

                <hr style="border:none;border-top:1px solid #e2e8f0;
                           margin:24px 0;"/>
                <p style="font-size:11px;color:#cbd5e1;text-align:center;">
                  If you did not request this, please ignore this email.
                </p>

              </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())

            return True

        except Exception as e:
            print(f"[EmailService] Failed to send to {to_email}: {e}")
            return False


    @staticmethod
    def send_password_reset_link(
        to_email: str,
        to_name: str,
        reset_url: str,
        expire_minutes: int = 60
    ) -> bool:

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Reset Your Password"
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = to_email

            html = f"""
            <html>
            <body style="font-family:'Segoe UI',sans-serif;
                         background:#f8fafc;padding:32px;color:#1e293b;">

              <div style="max-width:520px;margin:0 auto;background:#fff;
                          border-radius:12px;padding:32px;
                          border:1px solid #e2e8f0;">

                <h2 style="color:#0369a1;">Password Reset</h2>

                <p>Hello <strong>{to_name}</strong>,</p>

                <p>Click the button below to reset your password.</p>

                <div style="text-align:center;margin:28px 0;">
                  <a href="{reset_url}"
                     style="display:inline-block;padding:14px 32px;
                            background:#0369a1;color:#fff;
                            border-radius:8px;text-decoration:none;
                            font-weight:700;">
                    Reset Password
                  </a>
                </div>

                <p style="font-size:12px;color:#64748b;">
                  This link expires in <strong>{expire_minutes} minutes</strong>.
                </p>

              </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())

            return True

        except Exception as e:
            print(f"[EmailService] Failed to send reset email: {e}")
            return False