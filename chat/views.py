import os
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import ChatSession, Message, Lead
from .serializers import ChatSessionSerializer
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
from openai import OpenAI
import requests
from django.utils import timezone
from django.db.models import Count, Sum, Max, Min
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models.functions import TruncDate
from datetime import timedelta

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


SYSTEM_PROMPT = """
You are the AI concierge for Dotswitch CX (dotswitch.space).

Your job:
- Answer questions about Dotswitch CX clearly and briefly.
- Use ONLY the knowledge base below for specific facts (what we do, services, product, pricing).
- If something is not covered, stay high-level and suggest reaching out via email/chat, do NOT invent details.

KNOWLEDGE BASE
---------------

1. What is Dotswitch CX?
- Dotswitch CX is a boutique CX design firm for D2C brands and B2B SaaS.
- We help with:
  - GTM consulting
  - Workflow planning
  - Web and app design
  - Performance marketing
  - Social media growth

2. Core service lines and crucial links:

- GTM Biz Consulting
  URL: https://www.dotswitch.space/gtm-biz-consult
  Description: Helps D2C brand founders find their target audience, plan how to reach them, reduce CAC, improve profit margins, and connect with CXOs and solutions that can help them.

- CX Web Design
  URL: https://www.dotswitch.space/cx-design-for-web
  Description: CX & CX Web Design helps businesses find innovative ways to showcase their products and solutions through UX/UI and overall customer experience on web/app.

- Optimize Social Media
  URL: https://www.dotswitch.space/optimize-social-media
  Description: Social media growth strategy aligned to GTM and target audience.

- Webstore Design
  URL: https://www.dotswitch.space/webstore-design
  Description: Shopify, WordPress, Instapages webstore design to grow ecommerce.

- SEO & AIO
  URL: https://www.dotswitch.space/seo-ai-search
  Description: Boost search discovery on AI LLMs (GPT, Claude, Perplexity) and on Google/Bing via keyword-based content growth on the website.

- Cataloging
  URL: https://www.dotswitch.space/a-content-cataloging
  Description: Marketplace cataloging with discovery-optimised content aligned to platform rules, reducing CAC.

- Content Marketing
  URL: https://www.dotswitch.space/ai-content-generation
  Description: Product and brand marketing content across blogs, videos, website, and social media to drive search and performance-led growth.

- Performance Marketing
  URL: https://www.dotswitch.space/performance-marketing
  Description: Google, Meta, and marketplace ads; CPC and CAC management to improve ROAS so founders can focus on product while Dotswitch focuses on sales outcomes.

- Product Analytics
  URL: https://www.dotswitch.space/product-sense
  Description: Understand the marketing funnel, best-performing growth channels, and conversion behaviour. We help with tools like PostHog and Mixpanel, from cross-channel traffic to conversion attribution.

3. Products:

- Vero
  URL: https://www.dotswitch.space/vero
  Description: In-house tool for personalised, brand-toned SEO content. Generates LinkedIn and website SEO content in bulk without compromising writing style or hitting calendar limits.

4. Pricing:

- Pricing is scope-based.
- We understand the use case and create a custom plan.
- Typical monthly marketing budgets range from ₹20,000 to ₹2,00,000.
- There is a free audit + pricing discussion when people reach out.

ANSWERING RULES
----------------
- Keep answers short and focused unless the user asks for deep detail.
- When a question clearly maps to a service, name the service and explain it simply.
- If relevant, mention that detailed pricing is custom and scope-based.
- If the user wants to talk to someone or discuss a plan, encourage sharing their email in the chat.
- If you don’t know something from this KB, say so gently and suggest contacting the team.
"""

GATED_RESOURCES = [
    {
        "label": "Dotswitch Portfolio (PDF)",
        "url": "https://drive.google.com/file/d/18gFKXY6_1PDeGRE5ZnHJn4pgNWAe5Emz/view?usp=sharing",
        "keywords": ["portfolio", "capabilities deck", "deck", "showreel", "case study deck", "work samples"],
    },
    {
        "label": "AI Fashion Lookbook (PDF)",
        "url": "https://drive.google.com/file/d/1z_z78EXGHvoh9FOgns-FG7KLR7eyY7ZQ/view?usp=drive_link",
        "keywords": ["fashion lookbook", "lookbook", "ai fashion", "fashion brands", "fashion examples"],
    },
]

KNOWLEDGE_LINKS = [
    {
        "label": "GTM Biz Consulting",
        "url": "https://www.dotswitch.space/gtm-biz-consult",
        "keywords": ["gtm", "go-to-market", "biz consult", "consulting", "strategy", "market entry"],
    },
    {
        "label": "CX Web Design",
        "url": "https://www.dotswitch.space/cx-design-for-web",
        "keywords": ["cx design", "cx web", "ux", "ui", "website design", "product pages", "landing page"],
    },
    {
        "label": "Optimize Social Media",
        "url": "https://www.dotswitch.space/optimize-social-media",
        "keywords": ["social media", "instagram", "linkedin", "social growth", "social strategy"],
    },
    {
        "label": "Webstore Design",
        "url": "https://www.dotswitch.space/webstore-design",
        "keywords": ["webstore", "shopify", "wordpress", "woocommerce", "instapage", "ecommerce"],
    },
    {
        "label": "SEO & AIO",
        "url": "https://www.dotswitch.space/seo-ai-search",
        "keywords": ["seo", "search", "aio", "ai search", "google", "bing", "perplexity", "gpt"],
    },
    {
        "label": "Cataloging",
        "url": "https://www.dotswitch.space/a-content-cataloging",
        "keywords": ["catalog", "cataloging", "marketplace", "flipkart", "myntra", "ajio", "product listing"],
    },
    {
        "label": "Content Marketing",
        "url": "https://www.dotswitch.space/ai-content-generation",
        "keywords": ["content", "blog", "blogs", "video", "content marketing", "copywriting"],
    },
    {
        "label": "Performance Marketing",
        "url": "https://www.dotswitch.space/performance-marketing",
        "keywords": ["ads", "performance", "google ads", "meta ads", "facebook ads", "roas", "cpc", "cac"],
    },
    {
        "label": "Product Analytics",
        "url": "https://www.dotswitch.space/product-sense",
        "keywords": ["analytics", "product analytics", "posthog", "mixpanel", "funnels", "conversion"],
    },
    {
        "label": "Vero – SEO Content Tool",
        "url": "https://www.dotswitch.space/vero",
        "keywords": ["vero", "seo tool", "ai content", "bulk content"],
    },
]

def get_relevant_links(user_message: str):
    """
    Very simple keyword-based matcher to surface up to 3 relevant links
    based on the latest user message.
    """
    if not user_message:
        return []

    text = user_message.lower()
    matches = []

    for entry in KNOWLEDGE_LINKS:
        if any(kw in text for kw in entry["keywords"]):
            matches.append({"label": entry["label"], "url": entry["url"]})

    # If no match but they mention dotswitch in general, suggest a couple of core links
    if not matches and "dotswitch" in text:
        matches.append(
            {"label": "GTM Biz Consulting", "url": "https://www.dotswitch.space/gtm-biz-consult"}
        )
        matches.append(
            {"label": "CX Web Design", "url": "https://www.dotswitch.space/cx-design-for-web"}
        )

    # Limit to 3 buttons to keep UI clean
    return matches[:3]  


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def chat_message(request):
    """
    Request body:
    {
      "session_id": 1 (optional),
      "message": "User's question"
    }
    """
    session_id = request.data.get("session_id")
    user_message = request.data.get("message")

    if not user_message:
        return Response({"error": "message is required"}, status=status.HTTP_400_BAD_REQUEST)

    # 1. Get or create session
    if session_id:
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            session = None
    else:
        session = None

    if session is None:
        # New session: capture IP, UA, and first_message_at
        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")

        session = ChatSession.objects.create(
            ip_address=ip,
            user_agent=ua,
            first_message_at=timezone.now(),
            last_message_at=timezone.now(),
            user_message_count=1,  # we'll count the current user message immediately
        )
        # Geo-lookup (non-blocking best-effort)
        enrich_session_geo(session, session.ip_address)
    else:
        # Existing session: increment counters & timestamps
        session.user_message_count += 1
        session.last_message_at = timezone.now()
        session.save(update_fields=["user_message_count", "last_message_at"])

    # 2. Save user message
    Message.objects.create(session=session, role='user', text=user_message)

    # 3. Build conversation history for the model
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in session.messages.order_by('created_at'):
        history.append({"role": m.role, "content": m.text})

    # 4. Call OpenAI
    try:
        completion = client.chat.completions.create(
            model="gpt-5-nano",
            messages=history,
        )
        bot_reply = completion.choices[0].message.content
    except Exception as e:
        print("OpenAI error:", e)  # debug
        bot_reply = "I ran into an issue fetching an answer. Please try again in a moment."

    # 5. Save bot message
    Message.objects.create(session=session, role='assistant', text=bot_reply)

    # 6. Determine relevant links for this user message
    links = get_relevant_links(user_message)

    # 7. Determine gated links (PDFs, etc.)
    gated_links = get_gated_links(user_message)
    needs_lead_for_links = bool(gated_links)

    # 8. Determine if we should prompt for contact even without gated links
    lead_suggestion = None

    if needs_lead_for_links:
        lead_suggestion = (
            "I can share our detailed PDF for this. "
            "Drop your name and email so I can unlock the link for you."
        )
    elif looks_like_contact_intent(user_message):
        lead_suggestion = (
            "It sounds like you'd like to talk to the Dotswitch team or discuss a custom plan. "
            "Share your email and I'll have Sid reach out personally."
        )

    # 7. Return updated session with messages + links
    data = {
        "session_id": session.id,
        "messages": [
            {
                "role": m.role,
                "text": m.text,
                "created_at": m.created_at
            }
            for m in session.messages.order_by('created_at')
        ],
        "links": links,
        "gated_links": gated_links,
        "needs_lead_for_links": needs_lead_for_links,
        "lead_suggestion": lead_suggestion,
    }
    return Response(data, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def submit_lead(request):
    """
    Request body:
    {
      "session_id": 1,
      "name": "Visitor Name",
      "email": "visitor@example.com",
      "lead_type": "contact",            # or "gated_info" later
      "message": "I want to discuss..."  # optional
    }
    """
    data = request.data
    email = data.get("email")
    name = data.get("name", "")
    lead_type = data.get("lead_type", "contact")
    free_text = data.get("message", "")

    if not email:
        return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)

    session = None
    session_id = data.get("session_id")
    if session_id:
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            session = None

    # Create lead record
    lead = Lead.objects.create(
        session=session,
        name=name,
        email=email,
        lead_type=lead_type,
        message=free_text,
    )

    # Update session counters if available
    if session:
        session.lead_count += 1
        if lead.lead_type == "gated_info":
            session.gated_lead_count += 1
        session.save(update_fields=["lead_count", "gated_lead_count"])

    # Build chat transcript (if session exists)
    transcript_lines = []
    if session:
        for m in session.messages.order_by("created_at"):
            label = "User" if m.role == "user" else "Dotswitch Bot"
            transcript_lines.append(f"{label}: {m.text}")
    transcript = "\n".join(transcript_lines) if transcript_lines else "(no transcript available)"

    # Compose email
    subject = f"[Dotswitch Chatbot Lead] {lead.email} ({lead.lead_type})"
    body = f"""
New chatbot lead from Dotswitch website.

Name: {lead.name or "(not provided)"}
Email: {lead.email}
Lead type: {lead.lead_type}
Free-text message: {lead.message or "(none)"}

--- Chat Transcript ---

{transcript}
""".strip()

    to_email = getattr(settings, "LEAD_NOTIFICATION_EMAIL", None)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "crew@dotswitch.space")

    if to_email:
        try:
            send_mail(
                subject,
                body,
                from_email,
                [to_email],
                fail_silently=False,
            )
        except Exception as e:
            print("Email send error:", e)

    return Response(
        {
            "status": "ok",
            "lead_id": lead.id,
            "message": "Lead captured successfully.",
        },
        status=status.HTTP_201_CREATED,
    )

def get_gated_links(user_message: str):
    """Return a list of gated links based on the user message."""
    if not user_message:
        return []

    text = user_message.lower()
    matches = []

    for entry in GATED_RESOURCES:
        if any(kw in text for kw in entry["keywords"]):
            matches.append({"label": entry["label"], "url": entry["url"]})

    return matches

def looks_like_contact_intent(user_message: str) -> bool:
    """Heuristic: does this sound like 'talk to human / pricing / audit' intent?"""
    if not user_message:
        return False

    text = user_message.lower()
    contact_keywords = [
        "talk to you",
        "talk to someone",
        "reach out",
        "contact you",
        "speak to",
        "schedule a call",
        "book a call",
        "jump on a call",
        "ai fashion",
        "lookbook",
        "rate card",
        "portfolio",
        "contact",
        "pdf",
        "quote",
        "proposal",
        "gtm audit",
        "free audit",
        "marketing audit",
        "scope",
        "custom plan",
    ]

    return any(kw in text for kw in contact_keywords)

def get_client_ip(request):
    """Best-effort extraction of client IP (works behind proxies too)."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # may be a list like "1.2.3.4, 5.6.7.8"
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def enrich_session_geo(session, ip):
    """Call external geo API once per session (skip local IPs)."""
    if not ip:
        return

    # Local/private IPs – don't bother geolocating
    private_prefixes = ("127.", "10.", "192.168.", "172.16.")
    if ip.startswith(private_prefixes):
        session.ip_address = ip
        session.save(update_fields=["ip_address"])
        return

    try:
        resp = requests.get(f"https://ipapi.co/{ip}/json/", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            session.ip_address = ip
            session.country = data.get("country_name") or ""
            session.region = data.get("region") or ""
            session.city = data.get("city") or ""
            session.save(update_fields=["ip_address", "country", "region", "city"])
        else:
            session.ip_address = ip
            session.save(update_fields=["ip_address"])
    except Exception as e:
        print("Geo lookup error:", e)
        session.ip_address = ip
        session.save(update_fields=["ip_address"])

@api_view(['GET'])
@permission_classes([AllowAny])  # NOTE: in prod, lock this down!
def chat_stats(request):
    total_sessions = ChatSession.objects.count()
    total_leads = Lead.objects.count()
    total_gated_leads = Lead.objects.filter(lead_type="gated_info").count()

    totals = ChatSession.objects.aggregate(
        total_user_msgs=Sum("user_message_count"),
        total_bot_msgs=Sum("bot_message_count"),
    )

    sessions_by_country = list(
        ChatSession.objects
        .values("country")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    return Response(
        {
            "total_sessions": total_sessions,
            "total_leads": total_leads,
            "total_gated_leads": total_gated_leads,
            "total_user_messages": totals["total_user_msgs"] or 0,
            "total_bot_messages": totals["total_bot_msgs"] or 0,
            "sessions_by_country": sessions_by_country,
        },
        status=status.HTTP_200_OK,
    )

@login_required
def chatbot_dashboard(request):
    """HTML dashboard with high-level metrics and charts."""
    # Totals
    total_sessions = ChatSession.objects.count()
    total_leads = Lead.objects.count()
    total_gated_leads = Lead.objects.filter(lead_type="gated_info").count()

    totals = ChatSession.objects.aggregate(
        total_user_msgs=Sum("user_message_count"),
        total_bot_msgs=Sum("bot_message_count"),
    )

    total_user_messages = totals["total_user_msgs"] or 0
    total_bot_messages = totals["total_bot_msgs"] or 0

    # Conversion rate (sessions → any lead)
    conversion_rate = 0
    if total_sessions > 0:
        conversion_rate = round((total_leads / total_sessions) * 100, 1)

    # Last 14 days sessions & leads
    today = timezone.now().date()
    start_date = today - timedelta(days=13)

    # Sessions per day
    daily_sessions_qs = (
        ChatSession.objects.filter(created_at__date__gte=start_date)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    # Leads per day
    daily_leads_qs = (
        Lead.objects.filter(created_at__date__gte=start_date)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    # Normalize to full 14-day range for chart labels
    day_labels = []
    sessions_counts = []
    leads_counts = []

    daily_sessions_map = {entry["day"]: entry["count"] for entry in daily_sessions_qs}
    daily_leads_map = {entry["day"]: entry["count"] for entry in daily_leads_qs}

    for i in range(14):
        day = start_date + timedelta(days=i)
        day_labels.append(day.strftime("%Y-%m-%d"))
        sessions_counts.append(daily_sessions_map.get(day, 0))
        leads_counts.append(daily_leads_map.get(day, 0))

    # Sessions by country
    sessions_by_country = (
        ChatSession.objects.values("country")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Recent sessions
    recent_sessions = ChatSession.objects.order_by("-created_at")[:20]

    context = {
        "total_sessions": total_sessions,
        "total_leads": total_leads,
        "total_gated_leads": total_gated_leads,
        "total_user_messages": total_user_messages,
        "total_bot_messages": total_bot_messages,
        "conversion_rate": conversion_rate,
        "day_labels": day_labels,
        "sessions_counts": sessions_counts,
        "leads_counts": leads_counts,
        "sessions_by_country": sessions_by_country,
        "recent_sessions": recent_sessions,
    }
    return render(request, "chat/dashboard.html", context)

@login_required
def lead_list(request):
    """HTML table of leads (recent first)."""
    leads = (
        Lead.objects.select_related("session")
        .order_by("-created_at")[:200]
    )

    # Unique emails summary (basic)
    unique_emails = (
        Lead.objects.values("email")
        .annotate(
            first_seen=Min("created_at"),
            last_seen=Max("created_at"),
            lead_count=Count("id"),
        )
        .order_by("-last_seen")
    )

    context = {
        "leads": leads,
        "unique_emails": unique_emails,
    }
    return render(request, "chat/leads.html", context)
