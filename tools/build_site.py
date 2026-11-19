#!/usr/bin/env python3
"""
ComputeSight site builder — generates every page except the hand-built homepage body.

    python3 tools/build_site.py          # build all pages + SEO files
    python3 tools/build_site.py --og     # also render 1200x630 social images (needs Google Chrome)

Edit CONFIG below for domain, email, legal details, form/newsletter endpoints, analytics and social links.
Blog articles live in tools/posts/<slug>.html and are listed in POSTS.
"""
import html, json, math, random, re, shutil, subprocess, sys, tempfile
from datetime import date
from pathlib import Path

# Always read and write UTF-8, whatever the OS default (Windows defaults to cp1252 and crashes on "→").
_read_text, _write_text = Path.read_text, Path.write_text
Path.read_text = lambda self, encoding="utf-8", errors=None: _read_text(self, encoding=encoding, errors=errors)
Path.write_text = lambda self, data, encoding="utf-8", errors=None, newline=None: _write_text(self, data, encoding=encoding, errors=errors, newline=newline)

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "tools" / "posts"

# ════════════════════════════════════════════════════════════════════
# CONFIG — the one place to change site-wide settings
# ════════════════════════════════════════════════════════════════════
CONFIG = {
    "site": "https://www.computesight.com",        # production URL, no trailing slash
    "name": "ComputeSight",
    "email": "hello@computesight.com",             # public contact address
    "careers_email": "careers@computesight.com",
    "legal_name": "",                             # e.g. "ComputeSight Ltd" — shown on legal pages & footer
    "address": "",                                # registered/office address — shown on contact & legal pages
    "jurisdiction": "",                           # governing law for Terms, e.g. "England and Wales"
    "legal_updated": "2026-11-19",
    "form_endpoint": "",                          # Formspree/Basin/Getform/your API URL for the contact form
    "newsletter_endpoint": "",                    # Mailchimp/Buttondown/ConvertKit form-post URL
    "analytics": {"provider": "", "domain": "", "id": ""},   # {"provider": "plausible", "domain": "computesight.com"} or {"provider": "ga4", "id": "G-XXXX"}
    "cookie_banner": True,
    "social": {"linkedin": "", "x": "", "youtube": "", "github": ""},   # full URLs; empty = hidden
}
SITE = CONFIG["site"]

# ════════════════════════════════════════════════════════════════════
# helpers
# ════════════════════════════════════════════════════════════════════
e = lambda s: html.escape(s, quote=True)
ICON = '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M3 16s5-8.5 13-8.5S29 16 29 16s-5 8.5-13 8.5S3 16 3 16z"/><circle cx="16" cy="16" r="4.2"/></svg>'
CHEV = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>'
ORG = {"@type": "Organization", "name": CONFIG["name"], "url": f"{SITE}/",
       "logo": {"@type": "ImageObject", "url": f"{SITE}/assets/logo-512.png", "width": 512, "height": 512}}
ICONS = {
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "shield": '<path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z"/><path d="M9 12l2 2 4-4"/>',
    "ball": '<circle cx="12" cy="12" r="9"/><path d="M12 7l4 3-1.5 5h-5L8 10z"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 17.5h7M17.5 14v7"/>',
    "factory": '<path d="M3 20h18M5 20V9l5 3V9l5 3V5h4v15"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "video": '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3"/>',
    "pin": '<path d="M12 21s-7-6-7-11a7 7 0 0114 0c0 5-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 018 0v3"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5M16 4.5a3.5 3.5 0 010 7M18 14.6c2 .7 3.2 2.6 3.5 5.4"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
    "rocket": '<path d="M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2M9 15l-3-3c1-4 4.5-8.5 12-9-0.5 7.5-5 11-9 12z"/><circle cx="14.5" cy="9.5" r="1.5"/>',
    "book": '<path d="M4 4h6a3 3 0 013 3v13a2.5 2.5 0 00-2.5-2.5H4zM20 4h-6a3 3 0 00-3 3"/><path d="M20 4v13.5h-6.5A2.5 2.5 0 0011 20"/>',
}
SOCIAL_SVG = {
    "linkedin": '<path d="M4.98 3.5a2.5 2.5 0 11-.01 5 2.5 2.5 0 01.01-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.5c0-1.3-.02-3-1.83-3-1.83 0-2.12 1.43-2.12 2.9V21H9z"/>',
    "x": '<path d="M17.5 3h3.1l-6.8 7.8L21.8 21h-6.3l-4.9-6.4L5 21H1.9l7.3-8.3L1.5 3h6.4l4.4 5.8zm-1.1 16.2h1.7L7.2 4.7H5.4z"/>',
    "youtube": '<path d="M23 7.2a3 3 0 00-2.1-2.1C19 4.6 12 4.6 12 4.6s-7 0-8.9.5A3 3 0 001 7.2 31 31 0 00.5 12 31 31 0 001 16.8a3 3 0 002.1 2.1c1.9.5 8.9.5 8.9.5s7 0 8.9-.5a3 3 0 002.1-2.1 31 31 0 00.5-4.8 31 31 0 00-.5-4.8zM9.75 15.02V8.98L15.5 12z"/>',
    "github": '<path d="M12 .5a11.5 11.5 0 00-3.6 22.4c.6.1.8-.3.8-.6v-2c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 015.8 0C17.3 4.8 18.3 5.1 18.3 5.1c.6 1.6.2 2.8.1 3.1.8.8 1.2 1.8 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A11.5 11.5 0 0012 .5z"/>',
}


def home(R):
    """Link to the homepage; on the homepage itself, anchors stay in-page."""
    return "" if R == "" else f"{R}index.html"


def icon(name):
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def ph(value, placeholder):
    """Show config value, or a highlighted placeholder if it hasn't been set yet."""
    return e(value) if value else f"<mark>{e(placeholder)}</mark>"


def human_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def breadcrumb_ld(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}


def crumbs(R, items):
    lis = [f'<li><a href="{R}index.html">Home</a></li>']
    for name, href in items[:-1]:
        lis.append(f'<li><a href="{href}">{e(name)}</a></li>')
    lis.append(f'<li><span aria-current="page">{e(items[-1][0])}</span></li>')
    return f'<nav aria-label="Breadcrumb"><ol class="crumbs">{"".join(lis)}</ol></nav>'


# ════════════════════════════════════════════════════════════════════
# CONTENT: solutions
# ════════════════════════════════════════════════════════════════════
SOLUTIONS = [
    dict(slug="computer-vision", name="Computer Vision Services", short="Detection, tracking, OCR & pose", ic="eye", accent="#9aabff",
         cats=["Computer Vision", "AI Trends", "Engineering"], tags=["person 0.97", "forklift 0.94", "pallet 0.91"],
         seo_title="Computer Vision Services & Video Analytics Development",
         desc="Computer vision services from ComputeSight: object detection, tracking, segmentation, OCR and pose models built on your footage and deployed at the edge or in the cloud.",
         h1="Computer vision, built around your cameras and your data.",
         lead="We design, train and deploy detection, tracking, segmentation, OCR and pose models that work on your real footage, not just in a demo.",
         points=["Works with existing IP cameras", "Proof of concept in 4–8 weeks", "Edge, cloud or on-prem"],
         benefits_title="Production-grade vision, without building a team from scratch.",
         benefits=[("Accurate on your footage", "Models are fine-tuned and validated on your cameras, lighting and edge cases, with precision and recall reported per class."),
                   ("Fast to production", "Foundation models and our reusable pipeline cut months off the typical build-from-scratch timeline."),
                   ("Built to run for years", "Monitoring, drift detection and retraining keep accuracy high as products, layouts and seasons change.")],
         features=[("Object detection", "Find people, vehicles, products, tools and anything specific to your business."),
                   ("Multi-object tracking", "Follow every object across frames and cameras to measure movement and dwell."),
                   ("Segmentation", "Pixel-accurate masks for measurement, area coverage and fine-grained inspection."),
                   ("OCR & ANPR", "Read labels, serial numbers, containers and licence plates in the wild."),
                   ("Pose estimation", "Body keypoints for safety, ergonomics, sports and behaviour analysis."),
                   ("Vision-language search", "Ask questions of your footage in plain English and search video by description.")],
         steps=[("Discover", "Audit cameras, data and KPIs; agree measurable success criteria."), ("Prototype", "Label your footage and fine-tune models into a working proof of concept."),
                ("Deploy", "Optimise for edge or cloud and integrate with your systems."), ("Improve", "Monitor drift, retrain and add new use cases on the same stack.")],
         kpis=[("4–8 wks", "to a proof of concept on your footage"), ("40 ms", "typical edge inference latency"), ("1 API", "for every model and deployment target")],
         usecases=["Counting and classifying objects", "Zone, dwell and occupancy analytics", "Reading labels, codes and plates", "Measuring and verifying parts", "Searching archives by description", "Custom events unique to your operation"],
         integrations=["RTSP / ONVIF cameras", "Video management systems (VMS)", "REST & webhooks", "Python & JS SDKs", "AWS", "Azure", "GCP", "NVIDIA Jetson", "On-prem GPU"],
         faqs=[("Which cameras do you support?", "Most IP cameras that stream RTSP or ONVIF at 720p or higher, plus video files, images and broadcast feeds (SRT/HLS)."),
               ("How much training data do we need?", "Thanks to foundation models, many projects start with a few hundred to a few thousand labelled images per class. We assess this during discovery."),
               ("Who owns the models?", "We agree ownership up front. Models trained on your data for your use case are typically yours to keep."),
               ("Can it run without the internet?", "Yes. Edge deployments run fully on-site; cloud connectivity is only needed for dashboards and updates.")]),
    dict(slug="loss-prevention", name="AI Loss Prevention", short="Self-checkout, POS & theft detection", ic="shield", accent="#9aabff",
         cats=["Loss Prevention"], tags=["non-scan 0.91", "concealment 0.93", "paid ✓"],
         seo_title="AI Loss Prevention Software for Retail | Self-Checkout Theft Detection",
         desc="AI loss prevention that combines computer vision and POS data to detect self-checkout non-scans, sweethearting, concealment and refund fraud in real time.",
         h1="Stop shrink at the moment it happens.",
         lead="ComputeSight links your CCTV to your point of sale. When what the camera sees doesn't match the receipt, your team gets an alert and an evidence clip in seconds.",
         points=["No facial recognition by default", "Works with existing CCTV", "Alerts to handhelds or SOC"],
         benefits_title="Recover more, investigate less, and keep customers happy.",
         benefits=[("Prevent, don't just record", "Real-time alerts and on-screen prompts recover items before the customer leaves."),
                   ("Evidence, not suspicion", "Every alert comes with a short clip matched to the transaction, so staff act on facts."),
                   ("Fewer false alarms over time", "Reviewer feedback retrains the models, so precision keeps improving.")],
         features=[("Self-checkout non-scans", "Detect items that go from basket to bag without a successful scan."),
                   ("Product switching", "Spot when the item bagged doesn't match the barcode or PLU entered."),
                   ("Sweethearting", "Reconcile staffed-lane video with transactions to surface missed scans."),
                   ("Concealment & shelf sweeps", "Flag high-risk behaviour in aisles with high-value goods."),
                   ("Refund & return fraud", "Match return transactions with video at the service desk."),
                   ("ORC pattern analysis", "Identify repeated methods across stores without identifying faces.")],
         steps=[("Detect", "Track items, hands, bags and scanner zones frame by frame."), ("Reconcile", "Match every visual event to POS data as it happens."),
                ("Alert", "Push a 10-second evidence clip to staff or your SOC."), ("Learn", "Reviewer feedback retrains models to cut false alerts.")],
         kpis=[("30–45%", "target reduction in self-checkout loss"), ("< 2 s", "from event to staff alert"), ("70%", "fewer false alerts with feedback loops")],
         usecases=["Self-checkout lanes", "Staffed POS lanes", "High-value aisles", "Customer service desks", "Store exits", "Back-of-house and receiving"],
         integrations=["Leading POS platforms", "Custom POS via API", "Video management systems (VMS)", "Handheld & mobile apps", "SOC tools", "Webhooks"],
         faqs=[("Do customers need to be identified?", "No. We detect actions and items, not identities. Facial recognition is off by default and only considered where it's lawful and proportionate."),
               ("Will it slow down checkout?", "No. Detection runs in parallel; on-screen prompts appear only when an item looks unscanned."),
               ("Which POS systems do you support?", "We integrate with major POS vendors and any system that can export transaction events in near real time."),
               ("How do you measure results?", "Pilots compare loss per lane against control stores, alongside alert precision and customer complaints.")]),
    dict(slug="sports-analytics", name="Sports Analytics", short="Player & ball tracking from video", ic="ball", accent="#9aabff",
         cats=["Sports Analytics"], tags=["#10 28.4 km/h", "ball 0.81", "#7 24.9 km/h"],
         seo_title="AI Sports Analytics & Player Tracking Software (No Wearables)",
         desc="Computer vision sports analytics: player and ball tracking, physical metrics, tactical heatmaps and automated highlights from broadcast or wide-angle video.",
         h1="Elite-level tracking data from a single camera.",
         lead="Track every player and the ball, measure physical output, analyse tactics and clip highlights automatically, with no wearables required.",
         points=["Broadcast or fixed camera", "Full report in minutes", "API & CSV exports"],
         benefits_title="The data top clubs use, at a fraction of the cost.",
         benefits=[("No wearables needed", "Optical tracking captures both teams and the ball from video alone."),
                   ("Context in every metric", "Every sprint, press and pass links straight to the video moment."),
                   ("Works on any footage", "Analyse live matches, training sessions, archives and opposition video.")],
         features=[("Player & ball tracking", "Positions for every player and the ball, up to 25 times per second."),
                   ("Physical metrics", "Distance, high-speed running, sprints, top speed, accelerations."),
                   ("Tactical analysis", "Shape, lines, pressing, passing networks and transitions."),
                   ("Event detection", "Passes, shots, turnovers and set pieces tagged automatically."),
                   ("Automated highlights", "Clip goals, chances and player moments for coaches and media."),
                   ("Broadcast graphics", "Data overlays and AR-style visuals for streams and broadcasts.")],
         steps=[("Capture", "Use broadcast feeds or a fixed wide-angle camera."), ("Track", "Detect, track and identify every player and the ball."),
                ("Analyse", "Generate physical, tactical and event data automatically."), ("Share", "Deliver reports, clips and API data to your staff.")],
         kpis=[("25 Hz", "tracking frequency"), ("22 + ball", "tracked at once"), ("5 min", "from final whistle to report")],
         usecases=["Professional clubs and academies", "College and school programmes", "Leagues and federations", "Broadcasters and streamers", "Scouting and recruitment", "Performance research"],
         integrations=["Broadcast feeds (SRT/HLS)", "Panoramic cameras", "Video analysis tools", "CSV / JSON exports", "REST API", "Webhooks", "BI dashboards"],
         faqs=[("Which sports do you support?", "Football is our most mature pipeline, with basketball, rugby, cricket and tennis also supported. Ask us about others."),
               ("Do we need special cameras?", "No. Broadcast footage works; a fixed elevated wide-angle camera gives the best accuracy and is affordable."),
               ("How accurate is optical tracking?", "Accuracy depends mainly on camera height and angle. We validate against manually annotated samples of your footage."),
               ("Does it replace GPS vests?", "Many teams use both: wearables for training load, video for matches, tactics and opposition analysis.")]),
    dict(slug="custom-ai", name="Custom AI Solutions", short="Bespoke models & vision-language agents", ic="grid", accent="#9aabff",
         cats=["Custom AI", "AI Trends"], tags=["custom 0.95", "agent ✓", "VLM"],
         seo_title="Custom AI & Computer Vision Development Services",
         desc="Custom AI solutions from ComputeSight: bespoke computer vision models, vision-language agents and data pipelines for problems off-the-shelf tools can't solve.",
         h1="Custom AI for the problems no product solves.",
         lead="When off-the-shelf tools fall short, we build bespoke models, vision-language agents and data pipelines, and run them in production with you.",
         points=["Fixed-price discovery", "You own your models", "Production, not prototypes"],
         benefits_title="A partner that ships, not just experiments.",
         benefits=[("Problem first", "We start with the business outcome and the metric, then choose the technology."),
                   ("Production-minded", "Every project includes deployment, monitoring and retraining, not just a notebook."),
                   ("Transparent and flexible", "Clear milestones, honest feasibility checks and no lock-in.")],
         features=[("Bespoke vision models", "Detection, segmentation and classification trained for your domain."),
                   ("Vision-language agents", "AI that answers questions about images and video and takes action."),
                   ("Data & labelling pipelines", "Model-assisted labelling, synthetic data and quality control."),
                   ("Edge optimisation", "Quantised, compiled models that run fast on small devices."),
                   ("MLOps", "Versioning, monitoring, drift detection and safe rollouts."),
                   ("Integration", "APIs and connectors into ERP, MES, POS, VMS and your apps.")],
         steps=[("Define", "Turn the problem into measurable success criteria."), ("Prove", "Fixed-price proof of concept on your real data."),
                ("Build", "Production pipeline, integrations and hardening."), ("Operate", "Monitoring, retraining and continuous improvement.")],
         kpis=[("4–8 wks", "to a go/no-go proof of concept"), ("100%", "of trained models owned by you, by default"), ("1 team", "from discovery to production support")],
         usecases=["Rare or unusual defects", "Specialist equipment and assets", "Aerial, thermal and satellite imagery", "Document and label understanding", "Video question-answering", "Automated inspection reports"],
         integrations=["PyTorch", "ONNX", "TensorRT", "NVIDIA DeepStream", "Kubernetes", "AWS", "Azure", "GCP", "REST & gRPC"],
         faqs=[("How do you price custom work?", "Discovery and proofs of concept are fixed-price. Production work is scoped by milestone, with optional ongoing support."),
               ("What if it's not feasible?", "A proof of concept is designed to answer that quickly. If the data can't support the goal, we'll tell you early."),
               ("Can our team take it over?", "Yes. We document everything and can hand over code, models and pipelines, or train your engineers."),
               ("Do you sign NDAs?", "Yes, before any data is shared.")]),
    dict(slug="quality-inspection", name="Quality Inspection", short="Automated visual defect detection", ic="factory", accent="#9aabff",
         cats=["Custom AI", "Engineering", "Computer Vision"], tags=["defect 0.94", "OK 0.99", "label 0.87"],
         seo_title="AI Visual Inspection & Automated Defect Detection for Manufacturing",
         desc="AI visual inspection for manufacturing: detect surface defects, verify assemblies, check labels and measure parts at full line speed with computer vision.",
         h1="Inspect every part, at full line speed.",
         lead="AI visual inspection that finds defects, verifies assemblies and checks labels inline, then automatically rejects bad parts and shows you why.",
         points=["Learns from a few hundred images", "Inline, real-time rejection", "Integrates with PLC & MES"],
         benefits_title="Consistent quality, without manual spot checks.",
         benefits=[("100% inspection", "Every part is checked, every shift, at line speed."),
                   ("Catches what rules miss", "Deep learning handles natural variation that rule-based vision struggles with."),
                   ("Traceable decisions", "Every reject is stored with an image and reason for audits and root-cause analysis.")],
         features=[("Surface defects", "Scratches, dents, cracks, stains and contamination."),
                   ("Assembly verification", "Missing, misaligned or wrong components."),
                   ("Label & print checks", "Presence, position, legibility and barcode grading."),
                   ("Dimensional measurement", "Gauge sizes and positions from calibrated cameras."),
                   ("Automatic rejection", "Trigger rejectors and alarms via PLC integration."),
                   ("Quality analytics", "Defect trends by line, shift, supplier and batch.")],
         steps=[("Capture", "Set up cameras and lighting at the inspection point."), ("Train", "Teach models with good and defective examples."),
                ("Integrate", "Connect to PLC, rejector and MES."), ("Improve", "Review edge cases and retrain continuously.")],
         kpis=[("90%+", "target reduction in defect escapes"), ("< 100 ms", "per inspection decision"), ("24/7", "consistent inspection")],
         usecases=["Packaging and labelling lines", "Automotive components", "Electronics and PCBs", "Food and beverage", "Pharmaceutical packaging", "Textiles and materials"],
         integrations=["PLC integration", "OPC UA", "Modbus", "MES / ERP", "Industrial cameras (GigE Vision)", "NVIDIA Jetson", "Edge GPU servers"],
         faqs=[("How many defect images do we need?", "Often a few hundred examples per defect type is enough to start, plus good parts. Synthetic data can help with rare defects."),
               ("Can it keep up with our line?", "Models are optimised for your throughput; typical decisions take well under 100 ms per part."),
               ("Do we need new cameras?", "Industrial inspection usually benefits from dedicated cameras and controlled lighting. We specify the right setup."),
               ("What happens when products change?", "New variants are added by collecting examples and retraining, usually in days rather than months.")]),
]

# ════════════════════════════════════════════════════════════════════
# CONTENT: blog posts (newest first)
# ════════════════════════════════════════════════════════════════════
POSTS = [
    dict(slug="ai-video-analytics-guide", date="2026-11-18", cat="Computer Vision", accent="#9aabff",
         title="AI Video Analytics in 2026: What It Is, How It Works and Where It Pays Off",
         seo_title="AI Video Analytics in 2026: Complete Guide & Use Cases",
         desc="What AI video analytics is, how it works, the highest-ROI use cases by industry, natural-language video search, and how to choose a platform in 2026.",
         keywords=["AI video analytics", "intelligent video analytics", "video analytics software", "AI CCTV", "natural language video search"],
         tags=["person 0.97", "vehicle 0.94", "event ↑"]),
    dict(slug="vision-language-models-video-analytics", date="2026-11-18", cat="AI Trends", accent="#9aabff",
         title="Vision-Language Models for Video: What VLMs Can (and Can't) Do Yet",
         seo_title="Vision-Language Models (VLMs) for Video Analytics Explained",
         desc="How vision-language models are changing computer vision: where VLMs shine, their limitations, and the detector + VLM cascade used in production video analytics.",
         keywords=["vision language models", "VLM", "multimodal AI", "VLM video analytics", "visual question answering"],
         tags=["“hi-vis jacket?”", "yes · 0.91", "scaffold"]),
    dict(slug="semi-automated-offside-technology-explained", date="2026-11-18", cat="Sports Analytics", accent="#9aabff",
         title="Semi-Automated Offside Technology Explained: How Computer Vision Makes the Call",
         seo_title="Semi-Automated Offside Technology (SAOT) Explained",
         desc="How semi-automated offside technology works: tracking cameras, 3D limb tracking, kick-point detection and VAR validation, and what clubs can learn from it.",
         keywords=["semi-automated offside technology", "SAOT", "VAR offside", "offside technology", "football computer vision"],
         tags=["#9 offside", "kick 0.99", "#4 last def."]),
    dict(slug="eu-ai-act-computer-vision-compliance", date="2026-11-18", cat="Compliance", accent="#9aabff",
         title="The EU AI Act and Computer Vision: What Businesses Using Cameras Need to Know",
         seo_title="EU AI Act & Computer Vision: Compliance Guide for Cameras",
         desc="How the EU AI Act applies to computer vision and video analytics: timeline, prohibited practices, high-risk uses, GDPR overlap and practical compliance steps.",
         keywords=["EU AI Act", "AI Act computer vision", "AI Act video surveillance", "AI compliance", "facial recognition regulation"],
         tags=["risk: minimal", "masked ✓", "audit log"]),
    dict(slug="computer-vision-project-cost", date="2026-11-18", cat="Custom AI", accent="#9aabff",
         title="How Much Does a Computer Vision Project Cost? A 2026 Budgeting Guide",
         seo_title="How Much Does Computer Vision Cost? 2026 Pricing Guide",
         desc="What a computer vision project costs in 2026: indicative budgets, the main cost drivers, hidden costs and how to cut cost without hurting results.",
         keywords=["computer vision cost", "computer vision pricing", "AI project cost", "video analytics cost", "computer vision development cost"],
         tags=["PoC", "pilot", "rollout"]),
    dict(slug="ai-loss-prevention-computer-vision-retail-shrink", date="2026-11-18", cat="Loss Prevention", accent="#9aabff",
         title="AI Loss Prevention: How Computer Vision Is Cutting Retail Shrink",
         seo_title="AI Loss Prevention: How Computer Vision Cuts Retail Shrink",
         desc="How AI loss prevention uses computer vision and POS data to detect theft, self-checkout loss and sweethearting in real time, plus how to measure ROI.",
         keywords=["AI loss prevention", "retail shrink", "computer vision loss prevention", "retail theft detection", "shrink reduction"],
         tags=["concealment 0.93", "person 0.97", "bag 0.88"]),
    dict(slug="self-checkout-theft-detection-computer-vision", date="2026-11-18", cat="Loss Prevention", accent="#9aabff",
         title="Self-Checkout Theft: How Computer Vision Detects Non-Scans and Product Switching",
         seo_title="Self-Checkout Theft Detection with Computer Vision",
         desc="The most common self-checkout loss behaviours, how computer vision detects each one, and how to design interventions customers won't resent.",
         keywords=["self-checkout theft", "self-checkout loss prevention", "non-scan detection", "banana trick", "SCO shrink"],
         tags=["non-scan 0.91", "hand 0.96", "item 0.89"]),
    dict(slug="computer-vision-sports-analytics-player-tracking", date="2026-11-18", cat="Sports Analytics", accent="#9aabff",
         title="Computer Vision Sports Analytics: Player Tracking Without Wearables",
         seo_title="Computer Vision Sports Analytics & Player Tracking Guide",
         desc="How optical player tracking works, what it measures, which camera setup to choose, and how it compares with GPS wearables for clubs and academies.",
         keywords=["computer vision sports analytics", "player tracking", "optical tracking", "AI sports analytics", "football analytics"],
         tags=["#10 28.4 km/h", "ball 0.81", "#7 24.9 km/h"]),
    dict(slug="edge-ai-vs-cloud-computer-vision", date="2026-11-18", cat="Engineering", accent="#9aabff",
         title="Edge AI vs Cloud: Where Should Your Computer Vision Run?",
         seo_title="Edge AI vs Cloud for Computer Vision: How to Choose",
         desc="Edge AI vs cloud for computer vision: latency, bandwidth, privacy and cost compared, with the hybrid architecture most production systems use.",
         keywords=["edge AI vs cloud", "edge computer vision", "edge AI", "video analytics architecture", "NVIDIA Jetson"],
         tags=["edge · 38 ms", "stream 1080p", "event ↑"]),
    dict(slug="custom-computer-vision-solutions-guide", date="2026-11-18", cat="Custom AI", accent="#9aabff",
         title="Custom Computer Vision Solutions: A Practical Guide from Idea to Production",
         seo_title="Custom Computer Vision Solutions: Build vs Buy Guide",
         desc="When to build custom computer vision, how foundation models changed the cost, the full project lifecycle, and the questions to ask a vision AI partner.",
         keywords=["custom computer vision solutions", "computer vision development", "custom AI solutions", "build vs buy AI", "computer vision consulting"],
         tags=["defect 0.94", "part 0.99", "label 0.87"]),
]

# registry of generated URLs for the sitemap: (path, lastmod, priority)
URLS = []


# ════════════════════════════════════════════════════════════════════
# shared layout
# ════════════════════════════════════════════════════════════════════
def head(title, desc, path, R, og_image="home", og_type="website", extra_meta="", jsonld=(), robots="index, follow, max-image-preview:large"):
    url = f"{SITE}/{path}"
    ld = "".join(f'\n  <script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in jsonld)
    img = f"{SITE}/assets/og/{og_image}.png"
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{e(title)}</title>
  <meta name="description" content="{e(desc)}" />
  <meta name="robots" content="{robots}" />
  <link rel="canonical" href="{url}" />
  <meta name="theme-color" content="#ffffff" />
  <meta property="og:site_name" content="{CONFIG['name']}" />
  <meta property="og:type" content="{og_type}" />
  <meta property="og:title" content="{e(title)}" />
  <meta property="og:description" content="{e(desc)}" />
  <meta property="og:url" content="{url}" />
  <meta property="og:image" content="{img}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:locale" content="en_US" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{e(title)}" />
  <meta name="twitter:description" content="{e(desc)}" />
  <meta name="twitter:image" content="{img}" />{extra_meta}
  <link rel="icon" href="{R}assets/favicon.svg" type="image/svg+xml" />
  <link rel="apple-touch-icon" href="{R}assets/apple-touch-icon.png" />
  <link rel="manifest" href="{R}site.webmanifest" />
  <link rel="alternate" type="application/rss+xml" title="ComputeSight Insights" href="{R}blog/feed.xml" />
  <link rel="preload" href="{R}assets/fonts/inter-var.woff2" as="font" type="font/woff2" crossorigin />
  <link rel="stylesheet" href="{R}css/styles.css" />{ld}
</head>'''


def nav(R, active=""):
    def cur(k):
        return ' class="current" aria-current="page"' if active == k else ""
    items = "".join(f'''
          <a href="{R}solutions/{s['slug']}/index.html"><span class="dd-ic">{icon(s['ic'])}</span><span><b>{e(s['name'])}</b><small>{e(s['short'])}</small></span></a>''' for s in SOLUTIONS)
    return f'''<a class="skip" href="#top">Skip to content</a>
  <header class="nav" id="nav">
    <a href="{R}index.html" class="brand" aria-label="ComputeSight home">{ICON}<span>Compute<b>Sight</b></span></a>
    <nav class="nav-links" id="navLinks" aria-label="Main">
      <div class="dd">
        <button class="dd-btn{' current' if active == 'solutions' else ''}" type="button" aria-expanded="false" aria-controls="dd-solutions">Solutions {CHEV}</button>
        <div class="dd-menu" id="dd-solutions">{items}
          <a class="dd-foot" href="{home(R)}#lab">See all of it running in the live demo <span>→</span></a>
        </div>
      </div>
      <a href="{home(R)}#industries">Industries</a>
      <a href="{R}pricing/index.html"{cur('pricing')}>Pricing</a>
      <a href="{R}blog/index.html"{cur('blog')}>Blog</a>
      <a href="{R}about/index.html"{cur('about')}>About</a>
      <a href="{R}contact/index.html" class="btn btn-sm">Book a demo</a>
    </nav>
    <button class="nav-toggle" id="navToggle" aria-label="Open menu" aria-expanded="false"><span></span><span></span></button>
  </header>'''


def footer(R, extra_scripts=""):
    socials = "".join(f'<a href="{e(u)}" aria-label="{k.title()}" rel="noopener" target="_blank"><svg viewBox="0 0 24 24" aria-hidden="true">{SOCIAL_SVG[k]}</svg></a>'
                      for k, u in CONFIG["social"].items() if u)
    socials += f'<a href="{R}blog/feed.xml" aria-label="RSS feed"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4a16 16 0 0116 16h-3A13 13 0 004 7zm0 6a10 10 0 0110 10h-3a7 7 0 00-7-7zm2 6a2 2 0 110 4 2 2 0 010-4z"/></svg></a>'
    sol = "".join(f'\n          <a href="{R}solutions/{s["slug"]}/index.html">{e(s["name"])}</a>' for s in SOLUTIONS)
    legal = CONFIG["legal_name"] or CONFIG["name"]
    return f'''<footer class="footer">
    <div class="container">
      <div class="footer-top">
        <div class="footer-about">
          <a href="{R}index.html" class="brand">{ICON}<span>Compute<b>Sight</b></span></a>
          <p>Computer vision and custom AI that turns cameras into real-time decisions.</p>
          <form class="newsletter" novalidate>
            <label for="nl-email">Get our monthly vision AI briefing</label>
            <div class="newsletter-row">
              <input id="nl-email" name="email" type="email" placeholder="you@company.com" autocomplete="email" required />
              <button class="btn" type="submit">Subscribe</button>
            </div>
            <p class="newsletter-status" role="status"></p>
          </form>
        </div>
        <nav class="footer-col" aria-label="Solutions">
          <h4>Solutions</h4>{sol}
        </nav>
        <nav class="footer-col" aria-label="Company">
          <h4>Company</h4>
          <a href="{R}about/index.html">About</a>
          <a href="{R}careers/index.html">Careers</a>
          <a href="{R}pricing/index.html">Pricing</a>
          <a href="{R}contact/index.html">Contact</a>
        </nav>
        <nav class="footer-col" aria-label="Resources">
          <h4>Resources</h4>
          <a href="{R}blog/index.html">Blog</a>
          <a href="{home(R)}#lab">Live demo</a>
          <a href="{home(R)}#developers">Developers</a>
          <a href="{home(R)}#faq">FAQ</a>
        </nav>
        <nav class="footer-col" aria-label="Legal">
          <h4>Legal</h4>
          <a href="{R}legal/privacy/index.html">Privacy policy</a>
          <a href="{R}legal/terms/index.html">Terms of use</a>
          <a href="{R}legal/cookies/index.html">Cookie policy</a>
          <button class="link-btn" type="button" data-cookie-settings>Cookie settings</button>
        </nav>
      </div>
      <div class="footer-inner">
        <p class="small">© <span id="year"></span> {e(legal)}. All rights reserved.</p>
        <div class="socials">{socials}</div>
      </div>
    </div>
  </footer>
  <script src="{R}js/config.js" defer></script>
  <script src="{R}js/main.js" defer></script>{extra_scripts}'''


def page(path, R, title, desc, body, active="", og="home", og_type="website", extra_meta="", jsonld=(), extra_scripts="",
         priority="0.6", lastmod=None, robots="index, follow, max-image-preview:large", sitemap=True):
    html_ = f'''{head(title, desc, path, R, og, og_type, extra_meta, jsonld, robots)}
<body data-root="{R}">
  {nav(R, active)}

  <main id="top">
{body}
  </main>

  {footer(R, extra_scripts)}
</body>
</html>
'''
    out = ROOT / path / "index.html" if path and not path.endswith(".html") else ROOT / (path or "index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_)
    if sitemap:
        URLS.append((path, lastmod or CONFIG["legal_updated"], priority))


def cta_band(R, title="See what your cameras could be telling you.", text="Send us 10 minutes of footage. We'll show you what our models detect on it, free and within 48 hours."):
    return f'''    <section class="cta-band">
      <div class="container">
        <div class="cta-card">
          <div>
            <h2>{title}</h2>
            <p>{text}</p>
          </div>
          <div class="cta-actions">
            <a href="{R}contact/index.html" class="btn btn-white btn-lg">Book a demo <span aria-hidden="true">→</span></a>
            <a href="{home(R)}#lab" class="btn btn-outline-white btn-lg">Try the live demo</a>
          </div>
        </div>
      </div>
    </section>'''


def faq_block(title, faqs, center=True):
    items = "".join(f'''
          <details{' open' if i == 0 else ''}>
            <summary>{e(q)}</summary>
            <p>{e(a)}</p>
          </details>''' for i, (q, a) in enumerate(faqs))
    return f'''    <section class="faq">
      <div class="container">
        <div class="section-head{' center' if center else ''}">
          <p class="eyebrow">FAQ</p>
          <h2>{title}</h2>
        </div>
        <div class="faq-list">{items}
        </div>
      </div>
    </section>'''


def faq_ld(faqs):
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}


def cover(p, extra=""):
    rng = random.Random(p["slug"])
    boxes = []
    for i, label in enumerate(p["tags"]):
        x = 46 + i * 16 + rng.uniform(-2, 2)
        y = rng.uniform(22, 48)
        boxes.append(f'<span class="cb" style="left:{x:.1f}%;top:{y:.1f}%;width:{rng.uniform(10, 14):.1f}%;'
                     f'height:{min(rng.uniform(26, 44), 92 - y):.1f}%"><b>{e(label)}</b></span>')
    label = p.get("cat", "")
    return (f'<div class="cover{extra}" style="--accent-c:{p["accent"]}" aria-hidden="true">' + "".join(boxes)
            + (f'<span class="cover-label">{e(label)}</span>' if label else "") + '</div>')


def post_card(p, prefix, featured=False):
    return f'''<a class="post-card{' featured' if featured else ''}" href="{prefix}{p['slug']}/index.html" data-cat="{e(p['cat'])}">
            {cover(p)}
            <div class="post-card-body">
              <span class="cat">{e(p['cat'])}</span>
              <h3>{e(p['title'])}</h3>
              <p>{e(p['desc'])}</p>
              <span class="meta">{human_date(p['date'])} · {p['mins']} min read</span>
            </div>
          </a>'''


def contact_form(R):
    return f'''<form class="form card-glass" id="contactForm" novalidate data-endpoint="" data-email="{e(CONFIG['email'])}">
          <label class="hp" aria-hidden="true">Leave this empty<input name="website" tabindex="-1" autocomplete="off" /></label>
          <div class="row">
            <label><span>Name</span><input name="name" required autocomplete="name" /></label>
            <label><span>Work email</span><input name="email" type="email" required autocomplete="email" /></label>
          </div>
          <label><span>Company</span><input name="company" autocomplete="organization" /></label>
          <fieldset>
            <legend>Interested in</legend>
            <div class="pills">
              <label><input type="checkbox" name="interest" value="cv" /><span>Computer Vision</span></label>
              <label><input type="checkbox" name="interest" value="lp" /><span>Loss Prevention</span></label>
              <label><input type="checkbox" name="interest" value="sports" /><span>Sports Analytics</span></label>
              <label><input type="checkbox" name="interest" value="custom" /><span>Custom AI</span></label>
              <label><input type="checkbox" name="interest" value="qc" /><span>Quality Inspection</span></label>
            </div>
          </fieldset>
          <label><span>Tell us about the project</span><textarea name="message" rows="5" required></textarea></label>
          <button class="btn btn-block btn-lg" type="submit">Send request <span aria-hidden="true">→</span></button>
          <p class="fine">By submitting, you agree to our <a href="{R}legal/privacy/index.html">privacy policy</a>. We'll only use your details to respond.</p>
          <p class="form-status" id="formStatus" role="status"></p>
        </form>'''


# ════════════════════════════════════════════════════════════════════
# pages
# ════════════════════════════════════════════════════════════════════
def build_solutions():
    R = "../../"
    for s in SOLUTIONS:
        path = f"solutions/{s['slug']}/"
        benefits = "".join(f'''
          <article class="card"><div class="card-icon">{icon(s['ic'])}</div><h3>{e(t)}</h3><p>{e(d)}</p></article>''' for t, d in s["benefits"])
        features = "".join(f'<div><h3>{e(t)}</h3><p>{e(d)}</p></div>' for t, d in s["features"])
        steps = "".join(f'<div class="tl-item"><span>STEP {i + 1:02d}</span><h3>{e(t)}</h3><p>{e(d)}</p></div>' for i, (t, d) in enumerate(s["steps"]))
        kpis = "".join(f'<div class="why-item"><strong>{e(v)}</strong><p>{e(l)}</p></div>' for v, l in s["kpis"])
        uses = "".join(f"<li>{e(u)}</li>" for u in s["usecases"])
        ints = "".join(f"<span>{e(i)}</span>" for i in s["integrations"])
        rel = [p for p in POSTS if p["cat"] in s["cats"]][:3]
        related = ""
        if rel:
            related = f'''    <section class="related">
      <div class="container">
        <h2>Related guides</h2>
        <div class="post-grid">
          {"".join(post_card(p, R + "blog/") for p in rel)}
        </div>
      </div>
    </section>'''
        others = "".join(f'<a class="card" href="../{o["slug"]}/index.html"><div class="card-icon">{icon(o["ic"])}</div><h3>{e(o["name"])}</h3><p>{e(o["short"])}</p><span class="card-more">Learn more →</span></a>'
                         for o in SOLUTIONS if o is not s)
        body = f'''    <section class="sub-hero">
      <div class="container sub-hero-grid">
        <div>
          {crumbs(R, [("Solutions", f"{home(R)}#services"), (s['name'], '')])}
          <p class="eyebrow">{e(s['name'])}</p>
          <h1>{e(s['h1'])}</h1>
          <p class="lead">{e(s['lead'])}</p>
          <div class="hero-cta">
            <a href="{R}contact/index.html" class="btn btn-lg">Book a demo</a>
            <a href="{home(R)}#lab" class="btn btn-ghost btn-lg">See the live demo</a>
          </div>
          <ul class="hero-points">{"".join(f"<li>{e(x)}</li>" for x in s['points'])}</ul>
        </div>
        {cover(dict(slug=s['slug'], accent=s['accent'], tags=s['tags'], cat=s['name']))}
      </div>
    </section>

    <section>
      <div class="container">
        <div class="section-head">
          <p class="eyebrow">Why ComputeSight</p>
          <h2>{e(s['benefits_title'])}</h2>
        </div>
        <div class="grid-3">{benefits}
        </div>
      </div>
    </section>

    <section class="soft">
      <div class="container">
        <div class="section-head">
          <p class="eyebrow">Capabilities</p>
          <h2>Everything you need, <span class="grad">built in.</span></h2>
        </div>
        <div class="feature-grid">{features}</div>
      </div>
    </section>

    <section class="process">
      <div class="container">
        <div class="section-head">
          <p class="eyebrow">How it works</p>
          <h2>From camera to action in four steps.</h2>
        </div>
        <div class="timeline">{steps}</div>
      </div>
    </section>

    <section class="why" aria-label="Key figures">
      <div class="container why-grid three">{kpis}</div>
    </section>

    <section>
      <div class="container grid-2">
        <div>
          <p class="eyebrow">Use cases</p>
          <h2>Where teams start.</h2>
          <ul class="list-check">{uses}</ul>
        </div>
        <div>
          <p class="eyebrow">Integrations</p>
          <h2>Works with your stack.</h2>
          <p>Connect to the cameras, systems and tools you already use, through native connectors or our REST API and webhooks.</p>
          <div class="chip-cloud">{ints}</div>
        </div>
      </div>
    </section>

{faq_block(f"Questions about {e(s['name'])}", s['faqs'])}

{related}

    <section>
      <div class="container">
        <div class="section-head"><p class="eyebrow">Explore more</p><h2>Other solutions</h2></div>
        <div class="cards">{others}</div>
      </div>
    </section>

{cta_band(R)}'''
        ld = [{"@context": "https://schema.org", "@type": "Service", "name": s["name"], "serviceType": s["name"], "description": s["desc"],
               "provider": ORG, "areaServed": "Worldwide", "url": f"{SITE}/{path}"},
              faq_ld(s["faqs"]),
              breadcrumb_ld([("Home", f"{SITE}/"), ("Solutions", f"{SITE}/#services"), (s["name"], f"{SITE}/{path}")])]
        page(path, R, f"{s['seo_title']} | ComputeSight", s["desc"], body, "solutions", f"sol-{s['slug']}", jsonld=ld, priority="0.9")


def build_about():
    R = "../"
    values = [("target", "Outcomes over models", "We measure success in recovered losses, safer sites and better decisions, not just accuracy scores."),
              ("lock", "Privacy by design", "Behaviour, not identity. Edge processing, masking and short retention are our defaults."),
              ("users", "Humans in the loop", "AI flags, people decide. Every system we ship is designed around the people who use it."),
              ("rocket", "Ship to production", "Prototypes are easy. We build systems that run reliably for years, and we stay to run them.")]
    vals = "".join(f'<div class="trust-item"><div class="card-icon">{icon(i)}</div><h3>{e(t)}</h3><p>{e(d)}</p></div>' for i, t, d in values)
    sols = "".join(f'<a class="card" href="{R}solutions/{s["slug"]}/index.html"><div class="card-icon">{icon(s["ic"])}</div><h3>{e(s["name"])}</h3><p>{e(s["short"])}</p><span class="card-more">Learn more →</span></a>' for s in SOLUTIONS)
    body = f'''    <section class="sub-hero center">
      <div class="container">
        {crumbs(R, [("About", "")])}
        <p class="eyebrow">About ComputeSight</p>
        <h1>We help cameras <span class="grad">understand the world.</span></h1>
        <p class="lead">ComputeSight is a computer vision company. We turn the video organisations already capture into real-time decisions that cut losses, improve safety and sharpen performance.</p>
      </div>
    </section>

    <section>
      <div class="container">
        <p class="big-statement">There are more cameras than ever, and almost all of that footage goes unwatched. Our mission is to make every camera useful: <span class="grad">accurate, responsible and built for the real world.</span></p>
      </div>
    </section>

    <section class="soft">
      <div class="container">
        <div class="section-head"><p class="eyebrow">What we believe</p><h2>Principles we build by.</h2></div>
        <div class="trust-grid">{vals}</div>
      </div>
    </section>

    <section>
      <div class="container">
        <div class="section-head"><p class="eyebrow">What we do</p><h2>One vision stack, many solutions.</h2></div>
        <div class="cards">{sols}</div>
      </div>
    </section>

    <section class="process soft">
      <div class="container">
        <div class="section-head"><p class="eyebrow">How we work</p><h2>From footage to production in weeks, not quarters.</h2></div>
        <div class="timeline">
          <div class="tl-item"><span>WK 01</span><h3>Discover</h3><p>Audit cameras, data and KPIs; define success in numbers.</p></div>
          <div class="tl-item"><span>WK 02–04</span><h3>Prototype</h3><p>Fine-tune models on your footage and prove it works.</p></div>
          <div class="tl-item"><span>WK 05–08</span><h3>Deploy</h3><p>Optimise for edge or cloud and integrate with your systems.</p></div>
          <div class="tl-item"><span>ONGOING</span><h3>Evolve</h3><p>Monitor, retrain and add new use cases.</p></div>
        </div>
      </div>
    </section>

    <section>
      <div class="container grid-2">
        <div class="card"><div class="card-icon">{icon('users')}</div><h3>Join the team</h3><p>We're always interested in exceptional ML engineers, computer vision researchers and solution engineers.</p><a class="card-more" href="{R}careers/index.html">View careers →</a></div>
        <div class="card"><div class="card-icon">{icon('mail')}</div><h3>Work with us</h3><p>Have a problem a camera could solve? Tell us about it and we'll reply within one business day.</p><a class="card-more" href="{R}contact/index.html">Contact us →</a></div>
      </div>
    </section>

{cta_band(R)}'''
    ld = [{"@context": "https://schema.org", "@type": "AboutPage", "name": "About ComputeSight", "url": f"{SITE}/about/", "mainEntity": ORG},
          breadcrumb_ld([("Home", f"{SITE}/"), ("About", f"{SITE}/about/")])]
    page("about/", R, "About ComputeSight | Computer Vision & AI Company",
         "ComputeSight is a computer vision company turning video into real-time decisions for retail, sports, manufacturing and more. Learn about our mission and principles.",
         body, "about", "about", jsonld=ld, priority="0.7")


def build_careers():
    R = "../"
    why = [("target", "Real problems, real impact", "Your models run in stores, factories and stadiums, and their results show up in the numbers."),
           ("rocket", "Research to production", "Work across the whole stack, from foundation models to edge deployment and MLOps."),
           ("book", "Learn every week", "Reading groups, shared experiments and time to explore new techniques.")]
    cards = "".join(f'<article class="card"><div class="card-icon">{icon(i)}</div><h3>{e(t)}</h3><p>{e(d)}</p></article>' for i, t, d in why)
    mail = f"mailto:{CONFIG['careers_email']}?subject={html.escape('Open application')}"
    body = f'''    <section class="sub-hero center">
      <div class="container">
        {crumbs(R, [("Careers", "")])}
        <p class="eyebrow">Careers</p>
        <h1>Build AI that <span class="grad">sees the real world.</span></h1>
        <p class="lead">Join a team shipping computer vision into production, where accuracy, latency and privacy all matter.</p>
        <div class="hero-cta"><a class="btn btn-lg" href="#roles">See open roles</a></div>
      </div>
    </section>

    <section>
      <div class="container">
        <div class="section-head"><p class="eyebrow">Why ComputeSight</p><h2>Work that leaves the lab.</h2></div>
        <div class="grid-3">{cards}</div>
      </div>
    </section>

    <section class="process soft">
      <div class="container">
        <div class="section-head"><p class="eyebrow">How we hire</p><h2>A clear, respectful process.</h2></div>
        <div class="timeline">
          <div class="tl-item"><span>STEP 01</span><h3>Intro call</h3><p>30 minutes to talk about you, the role and what you're looking for.</p></div>
          <div class="tl-item"><span>STEP 02</span><h3>Technical chat</h3><p>A conversation about real problems you've solved, not trivia.</p></div>
          <div class="tl-item"><span>STEP 03</span><h3>Practical session</h3><p>A short, paid or in-interview exercise close to the actual work.</p></div>
          <div class="tl-item"><span>STEP 04</span><h3>Meet the team</h3><p>Meet the people you'd work with, then get a decision quickly.</p></div>
        </div>
      </div>
    </section>

    <section id="roles">
      <div class="container">
        <div class="section-head"><p class="eyebrow">Open roles</p><h2>Current openings</h2></div>
        <div class="empty">
          <h3>No open roles listed right now</h3>
          <p>We're always keen to hear from exceptional machine learning engineers, computer vision researchers, MLOps engineers and solution engineers. Send us your CV and a note about something you've built.</p>
          <a class="btn" href="{mail}">Send an open application</a>
        </div>
      </div>
    </section>'''
    ld = [breadcrumb_ld([("Home", f"{SITE}/"), ("Careers", f"{SITE}/careers/")])]
    page("careers/", R, "Careers at ComputeSight | Computer Vision & ML Jobs",
         "Join ComputeSight and build computer vision that runs in the real world. Learn how we work and hire, and send an open application.",
         body, "careers", "careers", jsonld=ld, priority="0.5")


def build_pricing():
    R = "../"
    faqs = [("Why don't you list prices?", "Every deployment differs in cameras, sites, accuracy needs and integrations. We give a fixed quote after a short discovery call, usually within a week."),
            ("Is the pilot really fixed-price?", "Yes. Scope, deliverables and success criteria are agreed up front, so there are no surprise costs."),
            ("What does per-camera pricing include?", "Software licences, model updates, monitoring, security patches and standard support. Hardware is quoted separately or you can use your own."),
            ("Can we start small?", "Absolutely. Most customers start with one use case at a handful of sites, then expand on the same infrastructure.")]
    plans = [("Pilot", "Fixed price", "4–8 week proof of value on your own footage.", False,
              ["Discovery workshop & camera audit", "Models tuned on your footage", "1–5 sites or lines", "Success metrics & go/no-go report", "Edge or cloud deployment"], "Scope a pilot"),
             ("Production", "Per camera / month", "Everything you need to run vision at scale.", True,
              ["All pilot capabilities", "Unlimited model updates", "Monitoring & drift detection", "Integrations (POS, VMS, PLC, API)", "Dashboards & alerting", "Business-hours support"], "Talk to sales"),
             ("Enterprise", "Custom", "For multi-site estates and bespoke AI.", False,
              ["Custom models & use cases", "On-prem or private cloud", "SSO, audit logs & data residency", "Dedicated success engineer", "24/7 support & SLAs", "Security & compliance reviews"], "Contact us")]
    cards = ""
    for name, price, note, feat, items, cta in plans:
        cards += f'''
          <div class="plan{' featured' if feat else ''}">{'<span class="plan-badge">Most popular</span>' if feat else ''}
            <h3>{name}</h3>
            <p class="price">{price}</p>
            <p class="price-note">{note}</p>
            <ul>{"".join(f"<li>{e(i)}</li>" for i in items)}</ul>
            <a class="btn {'btn-lg' if feat else 'btn-ghost btn-lg'}" href="{R}contact/index.html">{cta}</a>
          </div>'''
    rows = [("Models tuned on your footage", "y", "y", "y"), ("Edge or cloud deployment", "y", "y", "y"), ("Number of sites", "1–5", "Unlimited", "Unlimited"),
            ("Ongoing model updates", "n", "y", "y"), ("Monitoring & drift detection", "n", "y", "y"), ("Standard integrations", "Limited", "y", "y"),
            ("Custom models", "n", "Add-on", "y"), ("On-prem / private cloud", "n", "Add-on", "y"), ("SSO & audit logs", "n", "n", "y"), ("Support", "Project team", "Business hours", "24/7 + SLA")]
    def cell(v):
        return '<td class="y">✓</td>' if v == "y" else ('<td class="n">—</td>' if v == "n" else f"<td>{e(v)}</td>")
    table = "".join(f"<tr><td>{e(r[0])}</td>{cell(r[1])}{cell(r[2])}{cell(r[3])}</tr>" for r in rows)
    body = f'''    <section class="sub-hero center">
      <div class="container">
        {crumbs(R, [("Pricing", "")])}
        <p class="eyebrow">Pricing</p>
        <h1>Simple engagement models, <span class="grad">priced around outcomes.</span></h1>
        <p class="lead">Start with a fixed-price pilot on your own footage. Scale only when the results are proven.</p>
      </div>
    </section>

    <section style="padding-top:24px">
      <div class="container">
        <div class="plans">{cards}
        </div>
      </div>
    </section>

    <section class="soft">
      <div class="container">
        <div class="section-head"><p class="eyebrow">Compare</p><h2>What's included</h2></div>
        <div class="compare">
          <table>
            <thead><tr><th>Feature</th><th>Pilot</th><th>Production</th><th>Enterprise</th></tr></thead>
            <tbody>{table}</tbody>
          </table>
        </div>
        <p class="fine" style="margin-top:14px">Budgeting a project? Read our <a href="{R}blog/computer-vision-project-cost/index.html" style="color:var(--brand)">computer vision cost guide</a>.</p>
      </div>
    </section>

{faq_block("Pricing questions", faqs)}

{cta_band(R, "Get a fixed quote in under a week.", "Tell us about your cameras and goals, and we'll come back with a scoped pilot and a clear price.")}'''
    ld = [faq_ld(faqs), breadcrumb_ld([("Home", f"{SITE}/"), ("Pricing", f"{SITE}/pricing/")])]
    page("pricing/", R, "Pricing | ComputeSight Computer Vision Pilots & Plans",
         "ComputeSight pricing: fixed-price computer vision pilots, per-camera production plans and custom enterprise deployments. See what's included.",
         body, "pricing", "pricing", jsonld=ld, priority="0.8")


def build_contact():
    R = "../"
    addr = f'<div class="info-card"><span class="dd-ic">{icon("pin")}</span><div><b>Office</b><p>{e(CONFIG["address"])}</p></div></div>' if CONFIG["address"] else ""
    body = f'''    <section class="sub-hero">
      <div class="container sub-hero-grid" style="align-items:start">
        <div>
          {crumbs(R, [("Contact", "")])}
          <p class="eyebrow">Contact</p>
          <h1>Let's talk about <span class="grad">your cameras.</span></h1>
          <p class="lead">Tell us what you'd like your cameras to understand. We'll reply within one business day with next steps, usually a short call and a feasibility check on sample footage.</p>
          <div class="contact-info">
            <div class="info-card"><span class="dd-ic">{icon("mail")}</span><div><b>Email</b><a href="mailto:{e(CONFIG['email'])}">{e(CONFIG['email'])}</a></div></div>
            <div class="info-card"><span class="dd-ic">{icon("clock")}</span><div><b>Response time</b><p>Within one business day</p></div></div>
            <div class="info-card"><span class="dd-ic">{icon("video")}</span><div><b>Free feasibility check</b><p>Share 10 minutes of footage under NDA and see what our models detect.</p></div></div>
            {addr}
          </div>
        </div>
        {contact_form(R)}
      </div>
    </section>

    <section class="soft">
      <div class="container">
        <div class="section-head"><p class="eyebrow">What happens next</p><h2>Three simple steps.</h2></div>
        <div class="grid-3">
          <article class="card"><div class="card-icon">{icon("mail")}</div><h3>1. We reply</h3><p>Within one business day, with a few questions and times for a call.</p></article>
          <article class="card"><div class="card-icon">{icon("video")}</div><h3>2. 30-minute call</h3><p>We discuss your goals, cameras and data, and agree what success looks like.</p></article>
          <article class="card"><div class="card-icon">{icon("target")}</div><h3>3. Feasibility &amp; proposal</h3><p>We test sample footage and send a scoped, fixed-price pilot proposal.</p></article>
        </div>
      </div>
    </section>'''
    ld = [{"@context": "https://schema.org", "@type": "ContactPage", "name": "Contact ComputeSight", "url": f"{SITE}/contact/",
           "mainEntity": {**ORG, "email": CONFIG["email"]}},
          breadcrumb_ld([("Home", f"{SITE}/"), ("Contact", f"{SITE}/contact/")])]
    page("contact/", R, "Contact ComputeSight | Book a Computer Vision Demo",
         "Contact ComputeSight to book a demo or a free feasibility check on your footage. We reply within one business day.",
         body, "contact", "contact", jsonld=ld, priority="0.8")


def legal_page(slug, title, desc, content):
    R = "../../"
    body = f'''    <section class="sub-hero center" style="padding-bottom:40px">
      <div class="container">
        {crumbs(R, [("Legal", ""), (title, "")])}
        <h1>{e(title)}</h1>
        <p class="lead">Last updated: {human_date(CONFIG['legal_updated'])}</p>
      </div>
    </section>
    <section class="legal">
      <div class="container">
        <p class="notice">This document is a template provided as a starting point. Highlighted items need completing, and the whole text should be reviewed by qualified legal counsel before publication.</p>
        <div class="prose">
{content}
        </div>
      </div>
    </section>'''
    page(f"legal/{slug}/", R, f"{title} | ComputeSight", desc, body, "", "home", priority="0.3")


def build_legal():
    co = ph(CONFIG["legal_name"], "[Company legal name]")
    addr = ph(CONFIG["address"], "[Registered address]")
    email = e(CONFIG["email"])
    law = ph(CONFIG["jurisdiction"], "[Jurisdiction]")
    legal_page("privacy", "Privacy policy", "How ComputeSight collects, uses and protects personal data on this website.", f'''
<p>This policy explains how {co} ("ComputeSight", "we", "us") collects and uses personal data when you visit this website or contact us. It does not cover data processed on behalf of customers within our products, which is governed by separate customer agreements and data processing agreements.</p>
<h2 id="controller">Who we are</h2>
<p>{co}, {addr}, is the data controller for personal data collected through this website. You can contact us about privacy at <a href="mailto:{email}">{email}</a>.</p>
<h2 id="data">What we collect</h2>
<ul>
  <li><strong>Contact enquiries:</strong> name, work email, company, areas of interest and your message when you use our contact form or email us.</li>
  <li><strong>Newsletter:</strong> your email address if you subscribe.</li>
  <li><strong>Analytics (only with consent):</strong> aggregated information about pages visited, referrers, device and browser type.</li>
  <li><strong>Technical data:</strong> IP address and request logs processed by our hosting provider for security and reliability.</li>
</ul>
<h2 id="use">How we use it, and our legal bases</h2>
<ul>
  <li>To respond to enquiries and prepare proposals (legitimate interests / steps prior to a contract).</li>
  <li>To send our newsletter (consent; you can unsubscribe at any time).</li>
  <li>To understand and improve the website (consent, where analytics are enabled).</li>
  <li>To keep the website secure and operational (legitimate interests).</li>
</ul>
<h2 id="sharing">Who we share it with</h2>
<p>We use trusted service providers to host the website, deliver forms and email, and, if enabled, provide analytics. They process data only on our instructions. We do not sell personal data. <mark>[List your providers, e.g. hosting, form, email and analytics services.]</mark></p>
<h2 id="transfers">International transfers</h2>
<p>Where data is transferred outside the UK/EEA, we use appropriate safeguards such as Standard Contractual Clauses or adequacy decisions.</p>
<h2 id="retention">How long we keep it</h2>
<p>Enquiry data is kept for up to <mark>[24 months]</mark> after our last contact unless we enter into a contract. Newsletter data is kept until you unsubscribe. Server logs are kept for up to <mark>[30 days]</mark>.</p>
<h2 id="rights">Your rights</h2>
<p>Depending on where you live, you may have the right to access, correct, delete or port your data, to restrict or object to processing, and to withdraw consent at any time. To exercise these rights, email <a href="mailto:{email}">{email}</a>. You also have the right to complain to your local data protection authority.</p>
<h2 id="cookies">Cookies</h2>
<p>See our <a href="../cookies/index.html">cookie policy</a> for details of the storage we use and how to manage your choices.</p>
<h2 id="security">Security</h2>
<p>We use appropriate technical and organisational measures to protect personal data, including encryption in transit and access controls.</p>
<h2 id="changes">Changes to this policy</h2>
<p>We may update this policy from time to time. The "last updated" date above shows when it last changed.</p>''')
    legal_page("terms", "Terms of use", "The terms that apply to your use of the ComputeSight website.", f'''
<p>These terms govern your use of this website, operated by {co}, {addr}. By using the website you agree to them. Our products and services are provided under separate written agreements.</p>
<h2 id="use">Using this website</h2>
<p>You may use this website for lawful purposes only. You must not attempt to disrupt it, gain unauthorised access, or use automated means to scrape it in a way that harms its operation.</p>
<h2 id="ip">Intellectual property</h2>
<p>All content on this website, including text, graphics, code and logos, is owned by or licensed to ComputeSight and protected by intellectual property laws. You may share links and short quotations with attribution.</p>
<h2 id="info">Information on this site</h2>
<p>Articles, estimates, calculators and demos are provided for general information only. They are not professional, legal or financial advice. Figures such as savings estimates and target outcomes are illustrative and do not guarantee results. The live demo is a browser simulation, not real footage.</p>
<h2 id="links">Third-party links</h2>
<p>We are not responsible for the content of external websites linked from this site.</p>
<h2 id="liability">Disclaimers and liability</h2>
<p>The website is provided "as is" without warranties of any kind. To the extent permitted by law, we are not liable for any loss arising from your use of the website. Nothing in these terms limits liability that cannot be limited by law.</p>
<h2 id="law">Governing law</h2>
<p>These terms are governed by the laws of {law}, and disputes are subject to the exclusive jurisdiction of its courts.</p>
<h2 id="contact">Contact</h2>
<p>Questions about these terms? Email <a href="mailto:{email}">{email}</a>.</p>''')
    a = CONFIG["analytics"]
    if a.get("provider") == "ga4":
        analytics_row = "<tr><td>_ga, _ga_*</td><td>Analytics (Google Analytics 4)</td><td>Distinguishes visitors to measure usage. Set only after you accept.</td><td>Up to 2 years</td></tr>"
    elif a.get("provider") == "plausible":
        analytics_row = "<tr><td>None</td><td>Analytics (Plausible)</td><td>Cookieless, aggregated statistics. Loaded only after you accept.</td><td>n/a</td></tr>"
    else:
        analytics_row = "<tr><td>None currently</td><td>Analytics</td><td>No analytics are active on this site at present. If added, they will load only after you accept.</td><td>n/a</td></tr>"
    legal_page("cookies", "Cookie policy", "Which cookies and local storage ComputeSight uses and how to manage your choices.", f'''
<p>This policy explains how this website uses cookies and similar technologies such as local storage.</p>
<h2 id="what">What are cookies?</h2>
<p>Cookies and local storage are small pieces of data stored by your browser. Some are essential for a website to work; others help us understand how it is used.</p>
<h2 id="list">What we use</h2>
<div class="table-wrap"><table>
<thead><tr><th>Name</th><th>Type</th><th>Purpose</th><th>Duration</th></tr></thead>
<tbody>
<tr><td>cs-consent</td><td>Essential (local storage)</td><td>Remembers your cookie choice so we don't ask again.</td><td>Until cleared</td></tr>
{analytics_row}
</tbody></table></div>
<p>Fonts and core assets are served from our own domain, so no third-party font cookies are set.</p>
<h2 id="manage">Managing your choices</h2>
<p>You can change your choice at any time using the <button class="link-btn" style="color:var(--brand);text-decoration:underline" type="button" data-cookie-settings>cookie settings</button> link in the footer, or by clearing site data in your browser settings.</p>
<h2 id="contact">Contact</h2>
<p>Questions? Email <a href="mailto:{email}">{email}</a>.</p>''')


def build_404():
    R = "/"
    body = f'''    <section class="nf">
      <div>
        <div class="nf-box"><b>page_not_found 0.99</b>404</div>
        <h1 style="font-size:clamp(1.8rem,4vw,2.6rem)">Our models looked everywhere.</h1>
        <p class="lead" style="margin-inline:auto">The page you're looking for doesn't exist or has moved. Try one of these instead.</p>
        <div class="hero-cta">
          <a class="btn btn-lg" href="/">Back to home</a>
          <a class="btn btn-ghost btn-lg" href="/blog/">Read the blog</a>
          <a class="btn btn-ghost btn-lg" href="/contact/">Contact us</a>
        </div>
      </div>
    </section>'''
    page("404.html", R, "Page not found | ComputeSight", "The page you were looking for could not be found.", body,
         robots="noindex, follow", sitemap=False)


# ════════════════════════════════════════════════════════════════════
# blog
# ════════════════════════════════════════════════════════════════════
def load_posts():
    for p in POSTS:
        body = (POSTS_DIR / f"{p['slug']}.html").read_text()
        p["words"] = len(re.sub(r"<[^>]+>", " ", body).split())
        p["mins"] = max(1, math.ceil(p["words"] / 230))
        p["toc"] = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
        p["body"] = body


def related_posts(p, n=3):
    same = [q for q in POSTS if q is not p and q["cat"] == p["cat"]]
    return (same + [q for q in POSTS if q is not p and q["cat"] != p["cat"]])[:n]


def build_posts():
    R = "../../"
    for p in POSTS:
        path = f"blog/{p['slug']}/"
        url = f"{SITE}/{path}"
        ld = [{"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"], "description": p["desc"],
               "image": [f"{SITE}/assets/og/{p['slug']}.png"], "datePublished": p["date"], "dateModified": p["date"], "author": ORG, "publisher": ORG,
               "mainEntityOfPage": {"@type": "WebPage", "@id": url}, "url": url, "articleSection": p["cat"],
               "keywords": ", ".join(p["keywords"]), "wordCount": p["words"], "inLanguage": "en"},
              breadcrumb_ld([("Home", f"{SITE}/"), ("Blog", f"{SITE}/blog/"), (p["title"], url)])]
        meta = (f'\n  <meta property="article:published_time" content="{p["date"]}" />\n  <meta property="article:modified_time" content="{p["date"]}" />'
                f'\n  <meta property="article:section" content="{e(p["cat"])}" />' + "".join(f'\n  <meta property="article:tag" content="{e(k)}" />' for k in p["keywords"]))
        toc = "\n".join(f'              <li><a href="#{i}">{t}</a></li>' for i, t in p["toc"])
        rel = "\n          ".join(post_card(q, "../") for q in related_posts(p))
        body = f'''    <div class="progress" aria-hidden="true"></div>
    <article>
      <header class="page-head">
        <div class="container">
          {crumbs(R, [("Blog", "../index.html"), (p['cat'], "")])}
          <p class="eyebrow">{e(p['cat'])}</p>
          <h1>{e(p['title'])}</h1>
          <p class="lead">{e(p['desc'])}</p>
          <div class="post-meta">
            <span>By the ComputeSight team</span>
            <span><time datetime="{p['date']}">{human_date(p['date'])}</time></span>
            <span>{p['mins']} min read</span>
          </div>
        </div>
      </header>
      <div class="container">
        {cover(p)}
        <div class="post-layout">
          <nav class="toc" aria-label="Table of contents">
            <p>On this page</p>
            <ol>
{toc}
            </ol>
          </nav>
          <div class="prose">
{p['body']}
            <aside class="post-cta">
              <h2>See it on your own footage</h2>
              <p>Send us a sample clip and within 48 hours we'll reply with a feasibility assessment and a demo plan for your cameras.</p>
              <a class="btn" href="{R}contact/index.html">Book a demo <span aria-hidden="true">→</span></a>
            </aside>
          </div>
        </div>
      </div>
    </article>

    <section class="related" aria-labelledby="related-title">
      <div class="container">
        <h2 id="related-title">Keep reading</h2>
        <div class="post-grid">
          {rel}
        </div>
      </div>
    </section>'''
        page(path, R, f"{p['seo_title']} | ComputeSight", p["desc"], body, "blog", p["slug"], "article", meta, ld,
             f'\n  <script src="{R}js/blog.js" defer></script>', priority="0.7", lastmod=p["date"])


def build_blog_index():
    R = "../"
    desc = "Guides on AI video analytics, vision-language models, loss prevention, sports analytics, the EU AI Act, edge AI and computer vision costs."
    cats = list(dict.fromkeys(p["cat"] for p in POSTS))
    filters = '<button class="filter active" data-filter="all" aria-pressed="true">All</button>' + "".join(
        f'<button class="filter" data-filter="{e(c)}" aria-pressed="false">{e(c)}</button>' for c in cats)
    cards = "\n          ".join(post_card(p, "", i == 0) for i, p in enumerate(POSTS))
    body = f'''    <header class="page-head">
      <div class="container">
        {crumbs(R, [("Blog", "")])}
        <p class="eyebrow">Insights</p>
        <h1>Computer vision &amp; applied AI, explained.</h1>
        <p class="lead">Practical, no-hype guides from the team that builds and deploys vision AI in stores, factories and stadiums.</p>
      </div>
    </header>
    <section class="blog-list" aria-label="Articles">
      <div class="container">
        <div class="filters" role="group" aria-label="Filter by topic">{filters}</div>
        <div class="post-grid" id="postGrid">
          {cards}
        </div>
      </div>
    </section>'''
    ld = [{"@context": "https://schema.org", "@type": "Blog", "name": "ComputeSight Insights", "url": f"{SITE}/blog/", "description": desc, "publisher": ORG,
           "blogPost": [{"@type": "BlogPosting", "headline": p["title"], "url": f"{SITE}/blog/{p['slug']}/", "datePublished": p["date"],
                         "image": f"{SITE}/assets/og/{p['slug']}.png"} for p in POSTS]},
          breadcrumb_ld([("Home", f"{SITE}/"), ("Blog", f"{SITE}/blog/")])]
    page("blog/", R, "Computer Vision & AI Blog | ComputeSight Insights", desc, body, "blog", "blog", jsonld=ld,
         extra_scripts=f'\n  <script src="{R}js/blog.js" defer></script>', priority="0.8", lastmod=max(p["date"] for p in POSTS))


def build_feed():
    items = "".join(f'''
    <item>
      <title>{e(p['title'])}</title>
      <link>{SITE}/blog/{p['slug']}/</link>
      <guid>{SITE}/blog/{p['slug']}/</guid>
      <pubDate>{date.fromisoformat(p['date']).strftime('%a, %d %b %Y 09:00:00 GMT')}</pubDate>
      <category>{e(p['cat'])}</category>
      <description>{e(p['desc'])}</description>
    </item>''' for p in POSTS)
    (ROOT / "blog" / "feed.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>ComputeSight Insights</title>
    <link>{SITE}/blog/</link>
    <description>Guides on computer vision, AI video analytics, loss prevention, sports analytics and custom AI.</description>
    <language>en</language>{items}
  </channel>
</rss>
''')


# ════════════════════════════════════════════════════════════════════
# homepage injection + site files
# ════════════════════════════════════════════════════════════════════
def inject_home():
    idx = ROOT / "index.html"
    s = idx.read_text()
    def sub(name, content):
        nonlocal s
        pat = re.compile(rf"<!-- {name}:START.*?<!-- {name}:END -->", re.S)
        if not pat.search(s):
            print(f"! index.html: {name} markers missing")
            return
        s = pat.sub(lambda m: f"<!-- {name}:START (generated by tools/build_site.py) -->\n  {content}\n  <!-- {name}:END -->", s)
    sub("NAV", nav(""))
    sub("FOOTER", footer(""))
    sub("INSIGHTS", "\n          ".join(post_card(p, "blog/") for p in POSTS[:3]))
    idx.write_text(s)
    URLS.insert(0, ("", max(p["date"] for p in POSTS), "1.0"))


def build_site_files():
    cfg = {"contactEmail": CONFIG["email"], "formEndpoint": CONFIG["form_endpoint"], "newsletterEndpoint": CONFIG["newsletter_endpoint"],
           "analytics": CONFIG["analytics"], "cookieBanner": CONFIG["cookie_banner"]}
    (ROOT / "js" / "config.js").write_text("/* Generated by tools/build_site.py — edit CONFIG there, not here. */\nwindow.CS_CONFIG = "
                                           + json.dumps(cfg, indent=2) + ";\n")
    (ROOT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url>\n    <loc>{SITE}/{p}</loc>\n    <lastmod>{d}</lastmod>\n    <priority>{pr}</priority>\n  </url>\n" for p, d, pr in URLS)
        + "</urlset>\n")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /tools/\n\nSitemap: {SITE}/sitemap.xml\n")
    (ROOT / "site.webmanifest").write_text(json.dumps({
        "name": CONFIG["name"], "short_name": CONFIG["name"], "start_url": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": "#2341c6",
        "icons": [{"src": "/assets/logo-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "/assets/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"}]}, indent=2) + "\n")
    wk = ROOT / ".well-known"
    wk.mkdir(exist_ok=True)
    (wk / "security.txt").write_text(f"Contact: mailto:{CONFIG['email']}\nExpires: {date.today().year + 1}-12-31T23:59:59Z\nPreferred-Languages: en\nCanonical: {SITE}/.well-known/security.txt\n")
    host = SITE.split("://", 1)[1]
    (ROOT / ".htaccess").write_text(f"""# Generated by tools/build_site.py: Apache / LiteSpeed config (Hostinger). Edit the script, not this file.
Options -Indexes
DirectoryIndex index.html
ErrorDocument 404 /404.html
AddType application/manifest+json .webmanifest

<IfModule mod_rewrite.c>
  RewriteEngine On
  # One address only: https://{host}
  RewriteCond %{{HTTPS}} off [OR]
  RewriteCond %{{HTTP_HOST}} !^{re.escape(host)}$ [NC]
  RewriteRule ^ {SITE}%{{REQUEST_URI}} [L,R=301]
  # Keep the build tools, git data and repo files private
  RewriteRule ^(\\.git|tools)(/|$) - [R=404,L]
  RewriteRule ^(README\\.md|\\.gitignore)$ - [R=404,L]
</IfModule>

<IfModule mod_headers.c>
  Header always set X-Content-Type-Options "nosniff"
  Header always set X-Frame-Options "SAMEORIGIN"
  Header always set Referrer-Policy "strict-origin-when-cross-origin"
  Header always set Permissions-Policy "camera=(), microphone=(), geolocation=()"
  Header always set Strict-Transport-Security "max-age=31536000"
  # Pages, styles and scripts are re-checked on every visit, so updates show up immediately
  <FilesMatch "\\.(html|css|js|xml|txt|webmanifest)$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
  <FilesMatch "\\.(png|jpg|jpeg|webp|svg|ico)$">
    Header set Cache-Control "public, max-age=604800"
  </FilesMatch>
  <FilesMatch "\\.woff2$">
    Header set Cache-Control "public, max-age=31536000, immutable"
  </FilesMatch>
</IfModule>

<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/css text/plain text/xml application/javascript application/xml application/rss+xml application/manifest+json image/svg+xml
</IfModule>
""")
    old_headers = ROOT / "_headers"   # Netlify-only file from the original setup; Hostinger uses .htaccess
    if old_headers.exists():
        old_headers.unlink()


# ════════════════════════════════════════════════════════════════════
# social images
# ════════════════════════════════════════════════════════════════════
def render_og():
    chrome = next((c for c in ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                               r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
                   if Path(c).exists() or shutil.which(c)), None)
    if not chrome:
        print("! Chrome not found; skipping social images")
        return
    css = (ROOT / "css" / "styles.css").as_uri()
    out = ROOT / "assets" / "og"
    out.mkdir(parents=True, exist_ok=True)
    pages = [(p["slug"], p["title"], p["cat"], p) for p in POSTS]
    pages += [(f"sol-{s['slug']}", s["h1"], s["name"], dict(slug=s["slug"], accent=s["accent"], tags=s["tags"])) for s in SOLUTIONS]
    pages += [("home", "Computer vision that turns cameras into real-time decisions", "Computer vision · Loss prevention · Sports analytics", dict(slug="home", accent="#9aabff", tags=["person 0.97", "player #7", "defect 0.94"])),
              ("blog", "Computer vision & applied AI, explained", "ComputeSight Insights", dict(slug="blog", accent="#9aabff", tags=["guide", "edge AI", "tracking"])),
              ("about", "We help cameras understand the world", "About ComputeSight", dict(slug="about", accent="#9aabff", tags=["mission", "privacy ✓", "production"])),
              ("careers", "Build AI that sees the real world", "Careers", dict(slug="careers", accent="#9aabff", tags=["ML", "CV", "MLOps"])),
              ("pricing", "Simple engagement models, priced around outcomes", "Pricing", dict(slug="pricing", accent="#9aabff", tags=["pilot", "production", "enterprise"])),
              ("contact", "Let's talk about your cameras", "Contact", dict(slug="contact", accent="#9aabff", tags=["demo", "48 h", "NDA ✓"]))]
    with tempfile.TemporaryDirectory() as tmp:
        for slug, title, cat, art in pages:
            art = {**art, "cat": ""}
            f = Path(tmp) / f"{slug}.html"
            f.write_text(f'''<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{css}">
<style>
html,body{{margin:0;width:1200px;height:630px;overflow:hidden;background:#0a1440}}
.og-cover{{position:absolute;inset:0;aspect-ratio:auto;border-radius:0;border:0}}
.og-cover .cb{{margin-left:8%;margin-top:-90px}} .cb b{{font-size:15px;padding:5px 9px}}
.wrap{{position:absolute;inset:0;padding:64px 72px;display:flex;flex-direction:column}}
.brand{{font-size:30px;color:#fff}} .brand b{{color:#9aabff}} .brand svg{{width:44px;height:44px;stroke:#9aabff}} .brand svg circle{{fill:#e4002b}}
.cat{{margin-top:auto;font:600 18px var(--sans);letter-spacing:.1em;text-transform:uppercase;color:#9aabff}}
h1{{font-size:54px;line-height:1.08;margin:16px 0 0;max-width:640px;color:#fff;letter-spacing:-.03em;font-weight:800}}
</style></head><body>{cover(art, " og-cover")}
<div class="wrap"><div class="brand">{ICON}<span>Compute<b>Sight</b></span></div>
<div class="cat">{e(cat)}</div><h1>{e(title)}</h1></div></body></html>''')
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=3000", "--window-size=1200,630",
                            f"--screenshot={out / (slug + '.png')}", f.as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print(f"rendered {len(pages)} social images → assets/og/")


if __name__ == "__main__":
    load_posts()
    build_solutions()
    build_about()
    build_careers()
    build_pricing()
    build_contact()
    build_legal()
    build_404()
    build_posts()
    build_blog_index()
    build_feed()
    inject_home()
    build_site_files()
    if "--og" in sys.argv:
        render_og()
    print(f"built {len(URLS)} indexable pages + 404")
