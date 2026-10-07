# app/services/document_email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings


class DocumentEmailService:

    @staticmethod
    def send_upload_link(
        to_email:    str,
        to_name:     str,
        upload_url:  str,
        loan_ref:    str,
        banker_note: str | None,
        bank_name:   str | None,
    ) -> bool:
        """Send secure document upload link to customer."""
        try:
            msg            = MIMEMultipart("alternative")
            msg["Subject"] = f"Documents Required — Loan {loan_ref}"
            msg["From"]    = settings.EMAIL_FROM
            msg["To"]      = to_email

            note_section = ""
            if banker_note:
                note_section = f"""
                <div style="background:#fff7ed;border:1px solid #fed7aa;
                            border-radius:8px;padding:14px 16px;margin:20px 0;">
                  <p style="margin:0 0 6px;font-size:12px;font-weight:700;color:#c2410c;">
                    Documents Requested by {bank_name or 'Bank'}:
                  </p>
                  <p style="margin:0;font-size:13px;color:#92400e;">
                    {banker_note}
                  </p>
                </div>
                """

            html = f"""
            <html>
            <body style="font-family:'Segoe UI',sans-serif;
                         background:#f8fafc;padding:32px;color:#1e293b;">

              <div style="max-width:520px;margin:0 auto;background:#fff;
                          border-radius:12px;padding:32px;
                          border:1px solid #e2e8f0;">

                <h2 style="color:#0891b2;margin-bottom:4px;">
                  Additional Documents Required
                </h2>
                <p style="color:#64748b;font-size:13px;margin-top:0;">
                  Loan Reference: <strong>{loan_ref}</strong>
                </p>

                <p>Hello <strong>{to_name}</strong>,</p>

                <p style="color:#475569;">
                  Your loan application is under review at
                  <strong>{bank_name or 'the bank'}</strong>.
                  The bank has requested additional documents to proceed.
                </p>

                {note_section}

                <p style="color:#475569;">
                  Please click the button below to securely upload
                  your documents. This link is valid for
                  <strong>48 hours</strong>.
                </p>

                <div style="text-align:center;margin:28px 0;">
                  <a href="{upload_url}"
                     style="display:inline-block;padding:14px 32px;
                            background:#0891b2;color:#fff;
                            border-radius:8px;text-decoration:none;
                            font-weight:700;font-size:15px;">
                    Upload Documents
                  </a>
                </div>

                <p style="font-size:12px;color:#94a3b8;">
                  Or copy this link into your browser:<br/>
                  <span style="color:#0891b2;word-break:break-all;">
                    {upload_url}
                  </span>
                </p>

                <div style="background:#f0fdf4;border:1px solid #bbf7d0;
                            border-radius:8px;padding:12px 16px;
                            margin-top:16px;">
                  <p style="margin:0;font-size:12px;color:#166534;">
                    ✓ Accepted formats: PDF, JPG, PNG<br/>
                    ✓ Max file size: 10MB per file<br/>
                    ✓ Your documents are securely encrypted
                  </p>
                </div>

                <div style="background:#fef2f2;border:1px solid #fecaca;
                            border-radius:8px;padding:12px 16px;
                            margin-top:12px;">
                  <p style="margin:0;font-size:12px;color:#991b1b;">
                    ⚠ This link expires in <strong>48 hours</strong>.
                    Please upload your documents before it expires.
                  </p>
                </div>

                <hr style="border:none;border-top:1px solid #e2e8f0;
                           margin:24px 0;"/>
                <p style="font-size:11px;color:#cbd5e1;text-align:center;">
                  If you did not apply for a loan with us, please ignore
                  this email.
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
            print(f"[DocumentEmailService] Failed to send to {to_email}: {e}")
            return False

    @staticmethod
    def send_banker_notification(
        to_email:    str,
        banker_name: str,
        loan_ref:    str,
        customer_name: str,
        doc_count:   int,
    ) -> bool:
        """Notify banker that customer has uploaded documents."""
        try:
            msg            = MIMEMultipart("alternative")
            msg["Subject"] = f"Documents Uploaded — Loan {loan_ref}"
            msg["From"]    = settings.EMAIL_FROM
            msg["To"]      = to_email

            html = f"""
            <html>
            <body style="font-family:'Segoe UI',sans-serif;
                         background:#f8fafc;padding:32px;color:#1e293b;">

              <div style="max-width:520px;margin:0 auto;background:#fff;
                          border-radius:12px;padding:32px;
                          border:1px solid #e2e8f0;">

                <h2 style="color:#22c55e;margin-bottom:4px;">
                  Documents Uploaded ✓
                </h2>
                <p style="color:#64748b;font-size:13px;margin-top:0;">
                  Loan Reference: <strong>{loan_ref}</strong>
                </p>

                <p>Hello <strong>{banker_name}</strong>,</p>

                <p style="color:#475569;">
                  Good news! <strong>{customer_name}</strong> has uploaded
                  <strong>{doc_count} document(s)</strong> for loan
                  <strong>{loan_ref}</strong>.
                </p>

                <div style="background:#f0fdf4;border:1px solid #bbf7d0;
                            border-radius:8px;padding:14px 16px;
                            margin:20px 0;">
                  <p style="margin:0;font-size:13px;color:#166534;font-weight:700;">
                    Loan stage has been automatically updated to:<br/>
                    <span style="font-size:15px;">docs_review_complete</span>
                  </p>
                </div>

                <p style="color:#475569;">
                  Please log in to your bank dashboard to review
                  the uploaded documents and proceed with the
                  loan application.
                </p>

                <hr style="border:none;border-top:1px solid #e2e8f0;
                           margin:24px 0;"/>
                <p style="font-size:11px;color:#cbd5e1;text-align:center;">
                  T-Home Fintech — Automated Notification
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
            print(f"[DocumentEmailService] Banker notify failed: {e}")
            return False