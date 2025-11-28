from django.db import models

class ChatSession(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # later: ip, country, city, email, etc.
    
    # NEW: tracking fields
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    user_agent = models.TextField(blank=True)

    # NEW: simple session analytics
    user_message_count = models.IntegerField(default=0)
    bot_message_count = models.IntegerField(default=0)
    lead_count = models.IntegerField(default=0)
    gated_lead_count = models.IntegerField(default=0)

    first_message_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Session {self.id} ({self.created_at})"


class Message(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.role}] {self.text[:40]}"

class Lead(models.Model):
    LEAD_TYPE_CHOICES = (
        ("contact", "Contact Request"),      # “Talk to someone”
        ("gated_info", "Gated Info Access"), # Pricing/PDFs etc. later
    )

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField()
    lead_type = models.CharField(max_length=50, choices=LEAD_TYPE_CHOICES, default="contact")
    message = models.TextField(blank=True)  # free-text context/intent
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} ({self.lead_type})"
