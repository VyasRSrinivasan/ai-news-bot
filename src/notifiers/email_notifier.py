"""
Email notification module using Gmail SMTP
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime
from ..logger import setup_logger


logger = setup_logger(__name__)


class EmailNotifier:
    """Send email notifications with AI news digest using Gmail SMTP"""

    def __init__(
        self,
        gmail_address: Optional[str] = None,
        gmail_app_password: Optional[str] = None,
        email_to: Optional[str] = None,
    ):
        """
        Initialize EmailNotifier with Gmail SMTP.

        Args:
            gmail_address: Your Gmail address
            gmail_app_password: App Password from Google Account settings
              (NOT your regular Gmail password - see README for setup instructions)
            email_to: Recipient email address

        All parameters default to environment variables if not provided.
        """
        self.gmail_address = gmail_address or os.getenv("GMAIL_ADDRESS")
        self.gmail_app_password = gmail_app_password or os.getenv("GMAIL_APP_PASSWORD")
        self.email_to = email_to or os.getenv("EMAIL_TO")

        # Gmail SMTP settings
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

        if not all([self.gmail_address, self.gmail_app_password, self.email_to]):
            logger.warning(
                "Gmail notifier not fully configured. "
                "Required: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_TO"
            )
        else:
            logger.info(f"EmailNotifier initialized with Gmail SMTP (from: {self.gmail_address})")

    def send(self, content: str, subject: Optional[str] = None, language: str = "en") -> bool:
        """
        Send email notification with news digest.

        Args:
            content: Email body content (news digest)
            subject: Email subject. If None, uses default with current date
            language: Language code to include in subject (e.g., 'en', 'zh', 'ja')

        Returns:
            True if email sent successfully, False otherwise
        """
        # Create default subject if not provided
        if subject is None:
            today = datetime.now().strftime("%Y-%m-%d")
            lang_suffix = f" [{language.upper()}]" if language != "en" else ""
            subject = f"AI News Digest - {today}{lang_suffix}"

        if not all([self.gmail_address, self.gmail_app_password, self.email_to]):
            logger.error("Gmail notifier is not fully configured. Skipping email send.")
            return False

        try:
            # Create HTML email content
            html_content = self._create_html_email(content, subject)

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.gmail_address
            msg["To"] = self.email_to

            # Attach plain text and HTML versions
            part1 = MIMEText(content, "plain", "utf-8")
            part2 = MIMEText(html_content, "html", "utf-8")
            msg.attach(part1)
            msg.attach(part2)

            logger.info(f"Sending email via Gmail SMTP to {self.email_to}")

            # Connect and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.gmail_address, self.gmail_app_password)
                server.sendmail(self.gmail_address, self.email_to, msg.as_string())

            logger.info("Email sent successfully via Gmail SMTP")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(
                f"Gmail authentication failed: {str(e)}. "
                "Make sure you're using an App Password, not your regular Gmail password. "
                "See README for setup instructions."
            )
            return False
        except Exception as e:
            logger.error(f"Failed to send email via Gmail: {str(e)}", exc_info=True)
            return False

    def _create_html_email(self, content: str, subject: str) -> str:
        """
        Create HTML version of email with proper formatting.

        Args:
            content: Markdown formatted content
            subject: Email subject

        Returns:
            HTML formatted email
        """
        try:
            import markdown
            from markdown.extensions import nl2br, tables, fenced_code

            # Convert markdown to HTML with extensions
            html_content = markdown.markdown(
                content,
                extensions=[
                    'nl2br',      # Convert newlines to <br>
                    'tables',     # Support for tables
                    'fenced_code',# Support for code blocks
                    'sane_lists', # Better list handling
                ]
            )
        except ImportError:
            logger.warning("markdown library not installed, using basic HTML formatting")
            # Fallback to basic HTML escaping and line break conversion
            import html
            html_content = html.escape(content).replace('\n', '<br>\n')

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', Helvetica, Arial, sans-serif;
                    line-height: 1.8;
                    color: #24292e;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f6f8fa;
                }}
                .container {{
                    background-color: #ffffff;
                    border-radius: 8px;
                    padding: 40px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }}
                .title {{
                    color: #0366d6;
                    font-size: 32px;
                    font-weight: 700;
                    margin-bottom: 20px;
                    padding-bottom: 15px;
                    border-bottom: 4px solid #0366d6;
                    text-align: center;
                }}
                .content {{
                    margin-top: 30px;
                }}
                .content h1 {{
                    color: #0366d6;
                    font-size: 28px;
                    font-weight: 700;
                    margin-top: 40px;
                    margin-bottom: 20px;
                    padding-bottom: 12px;
                    border-bottom: 3px solid #0366d6;
                }}
                .content h2 {{
                    color: #2c3e50;
                    font-size: 22px;
                    font-weight: 600;
                    margin-top: 35px;
                    margin-bottom: 18px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #e1e4e8;
                }}
                .content h3 {{
                    color: #24292e;
                    font-size: 18px;
                    font-weight: 600;
                    margin-top: 28px;
                    margin-bottom: 15px;
                    padding-left: 12px;
                    border-left: 4px solid #0366d6;
                }}
                .content h4 {{
                    color: #586069;
                    font-size: 16px;
                    font-weight: 600;
                    margin-top: 20px;
                    margin-bottom: 12px;
                }}
                .content p {{
                    margin: 15px 0;
                    line-height: 1.8;
                    color: #24292e;
                }}
                .content ul, .content ol {{
                    margin: 15px 0;
                    padding-left: 30px;
                }}
                .content li {{
                    margin: 10px 0;
                    line-height: 1.8;
                }}
                .content strong {{
                    font-weight: 600;
                    color: #0366d6;
                }}
                .content em {{
                    font-style: italic;
                    color: #586069;
                }}
                .content code {{
                    background-color: #f6f8fa;
                    padding: 3px 6px;
                    border-radius: 3px;
                    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
                    font-size: 0.9em;
                    color: #d73a49;
                }}
                .content pre {{
                    background-color: #f6f8fa;
                    padding: 16px;
                    border-radius: 6px;
                    overflow-x: auto;
                    border: 1px solid #e1e4e8;
                }}
                .content pre code {{
                    background-color: transparent;
                    padding: 0;
                    color: #24292e;
                }}
                .content blockquote {{
                    margin: 20px 0;
                    padding: 10px 20px;
                    border-left: 4px solid #dfe2e5;
                    background-color: #f6f8fa;
                    color: #586069;
                }}
                .content hr {{
                    border: none;
                    border-top: 2px solid #e1e4e8;
                    margin: 30px 0;
                }}
                .content a {{
                    color: #0366d6;
                    text-decoration: none;
                    border-bottom: 1px solid transparent;
                    transition: border-bottom 0.2s;
                }}
                .content a:hover {{
                    border-bottom: 1px solid #0366d6;
                }}
                .content table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 20px 0;
                }}
                .content th, .content td {{
                    border: 1px solid #e1e4e8;
                    padding: 10px 15px;
                    text-align: left;
                }}
                .content th {{
                    background-color: #f6f8fa;
                    font-weight: 600;
                }}
                .footer {{
                    margin-top: 50px;
                    padding-top: 25px;
                    border-top: 2px solid #e1e4e8;
                    text-align: center;
                    font-size: 14px;
                    color: #586069;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="title">{subject}</div>
                <div class="content">
                    {html_content}
                </div>
            </div>
            <div class="footer">
                <p>This email was automatically generated by AI News Bot</p>
                <p>Powered by AI • <a href="https://github.com/giftedunicorn/ai-news-bot" style="color: #0366d6;">View on GitHub</a></p>
            </div>
        </body>
        </html>
        """
        return html

    def send_digest(self, digest: dict, language: str = "en") -> bool:
        """
        Send an HTML email rendered from a structured JSON digest.

        Args:
            digest: Dict produced by Summarizer.summarize() with keys:
                    date, headline, categories (list of {name, stories}).
            language: Language code used to suffix the subject line.

        Returns:
            True if email sent successfully, False otherwise.
        """
        import html as html_mod

        date = html_mod.escape(digest.get("date", ""))
        lang_suffix = f" [{language.upper()}]" if language != "en" else ""
        subject = f"AI News Digest \u2014 {date}{lang_suffix}"

        if not all([self.gmail_address, self.gmail_app_password, self.email_to]):
            logger.error("Gmail notifier is not fully configured. Skipping email send.")
            return False

        try:
            html_body = self._render_digest_html(digest, subject)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.gmail_address
            msg["To"] = self.email_to

            # Plain-text fallback
            plain = f"{subject}\n\n{digest.get('headline', '')}\n\nRead the HTML version for full details."
            msg.attach(MIMEText(plain, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.gmail_address, self.gmail_app_password)
                server.sendmail(self.gmail_address, self.email_to, msg.as_string())

            logger.info("Digest email sent successfully via Gmail SMTP")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send digest email: {e}", exc_info=True)
            return False

    def _render_digest_html(self, digest: dict, subject: str) -> str:
        """Render a JSON digest dict into a styled HTML email body."""
        import html as html_mod

        _IMPORTANCE_COLOR = {"high": "#d73a49", "medium": "#e36209", "low": "#6f42c1"}
        _IMPORTANCE_LABEL = {"high": "High", "medium": "Medium", "low": "Low"}

        date = html_mod.escape(digest.get("date", ""))
        headline = html_mod.escape(digest.get("headline", ""))
        categories = digest.get("categories", [])

        categories_html = ""
        for cat in categories:
            cat_name = html_mod.escape(cat.get("name", ""))
            categories_html += f'<div class="category"><h2>{cat_name}</h2>'
            for story in cat.get("stories", []):
                title = html_mod.escape(story.get("title", ""))
                summary = html_mod.escape(story.get("summary", ""))
                source = html_mod.escape(story.get("source", ""))
                url = html_mod.escape(story.get("url", "#"))
                importance = story.get("importance", "medium").lower()
                imp_color = _IMPORTANCE_COLOR.get(importance, "#6f42c1")
                imp_label = _IMPORTANCE_LABEL.get(importance, importance.capitalize())
                categories_html += f"""
                <div class="story">
                  <h3><a href="{url}">{title}</a></h3>
                  <p class="summary">{summary}</p>
                  <p class="meta">
                    <span class="importance" style="color:{imp_color}">{imp_label}</span>
                    &mdash; {source}
                  </p>
                </div>"""
            categories_html += "</div>"

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
      background: #f6f8fa; color: #24292e; margin: 0; padding: 20px;
    }}
    .container {{
      background: #fff; border-radius: 8px; max-width: 800px;
      margin: 0 auto; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,.1);
    }}
    .header {{ border-bottom: 3px solid #0366d6; margin-bottom: 30px; padding-bottom: 20px; }}
    .header h1 {{ color: #0366d6; font-size: 28px; margin: 0 0 8px; }}
    .header .date {{ color: #586069; font-size: 14px; margin: 0 0 12px; }}
    .header .headline {{ font-size: 16px; font-style: italic; color: #24292e; margin: 0; }}
    .category {{ margin: 30px 0; }}
    .category h2 {{
      color: #0366d6; font-size: 20px; border-bottom: 2px solid #e1e4e8;
      padding-bottom: 8px; margin-bottom: 16px;
    }}
    .story {{ margin: 0 0 24px; padding: 16px; background: #f6f8fa; border-radius: 6px; }}
    .story h3 {{ font-size: 16px; margin: 0 0 8px; }}
    .story h3 a {{ color: #0366d6; text-decoration: none; }}
    .story h3 a:hover {{ text-decoration: underline; }}
    .summary {{ font-size: 14px; line-height: 1.7; margin: 0 0 8px; }}
    .meta {{ font-size: 12px; color: #586069; margin: 0; }}
    .importance {{ font-weight: 600; }}
    .footer {{
      margin-top: 40px; padding-top: 20px; border-top: 1px solid #e1e4e8;
      text-align: center; font-size: 13px; color: #586069;
    }}
    .footer a {{ color: #0366d6; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>AI News Digest</h1>
      <p class="date">{date}</p>
      <p class="headline">{headline}</p>
    </div>
    {categories_html}
    <div class="footer">
      <p>Generated by <a href="https://github.com/giftedunicorn/ai-news-bot">AI News Bot</a></p>
    </div>
  </div>
</body>
</html>"""
