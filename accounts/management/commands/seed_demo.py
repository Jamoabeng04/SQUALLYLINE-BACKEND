"""
Seed demo data for Squally Line.

Creates:
  * Users: admin@ (role=admin), tailor (apprentice), two customers
  * Appointment tiers (normal / urgent / express) and a few upcoming slots
  * Categories (Men, Women, Kids), subcategories, tags
  * Products + styles across categories, with images from picsum where none exist

Idempotent: re-running skips what already exists.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from accounts.models import Profile, Person
from products.models import Category, Tag, Product, Style
from appointments.models import AppointmentTier, AppointmentSlot

User = get_user_model()

# picsum serves stable images per seed; swap for real catalogue shots later
def _img(seed, w=900, h=1200):
    return f"https://picsum.photos/seed/{seed}/{w}/{h}"


class Command(BaseCommand):
    help = "Seed demo users, catalogue, tiers and slots."

    def handle(self, *args, **options):
        # ---------------- Users ----------------
        admin, _ = User.objects.get_or_create(
            email="admin@squallyline.com",
            defaults=dict(username="admin", role="admin", first_name="Ama", last_name="Asante", is_staff=True),
        )
        admin.set_password("Admin@123")
        admin.save()
        Profile.objects.get_or_create(user=admin, defaults=dict(phone="+233 24 000 0001", gender="F"))

        apprentice, _ = User.objects.get_or_create(
            email="tailor@squallyline.com",
            defaults=dict(username="tailor", role="apprentice", first_name="Kofi", last_name="Mensah", is_staff=True),
        )
        apprentice.set_password("Tailor@123")
        apprentice.save()
        Profile.objects.get_or_create(user=apprentice, defaults=dict(phone="+233 24 000 0002", gender="M"))

        customer1, _ = User.objects.get_or_create(
            email="customer@squallyline.com",
            defaults=dict(username="customer", role="customer", first_name="Efua", last_name="Owusu"),
        )
        customer1.set_password("Customer@123")
        customer1.save()
        profile1, _ = Profile.objects.get_or_create(user=customer1, defaults=dict(phone="+233 24 000 0003", gender="F"))
        Person.objects.get_or_create(user=customer1, name="Efua Owusu", defaults=dict(relationship="other", phone="+233 24 000 0003"))

        customer2, _ = User.objects.get_or_create(
            email="kwame@squallyline.com",
            defaults=dict(username="kwame", role="customer", first_name="Kwame", last_name="Asante"),
        )
        customer2.set_password("Customer@123")
        customer2.save()
        Profile.objects.get_or_create(user=customer2, defaults=dict(phone="+233 24 000 0004", gender="M"))
        Person.objects.get_or_create(user=customer2, name="Kwame Asante", defaults=dict(relationship="other", phone="+233 24 000 0004"))

        self.stdout.write(self.style.SUCCESS(f"Users ready (admin@squallyline.com / Admin@123)"))

        # ---------------- Appointment tiers + slots ----------------
        tiers = {
            "normal": dict(fee="50.00", description="Standard appointment"),
            "urgent": dict(fee="150.00", description="Priority within 48h"),
            "express": dict(fee="200.00", description="Same/next-day slot"),
        }
        for name, data in tiers.items():
            AppointmentTier.objects.get_or_create(name=name, defaults=data)

        # Times live in the lookup, not in defaults — putting them in both makes
        # every slot collapse onto the same 09:00-17:00 row.
        slot_defaults = dict(normal_slots=3, express_slots=1, is_active=True)
        for day in range(1, 8):
            d = timezone.now().date() + timedelta(days=day)
            for start, end in (("09:00", "12:00"), ("14:00", "17:00")):
                AppointmentSlot.objects.get_or_create(
                    date=d,
                    start_time=timezone.datetime.strptime(start, "%H:%M").time(),
                    end_time=timezone.datetime.strptime(end, "%H:%M").time(),
                    defaults=slot_defaults,
                )
        self.stdout.write(self.style.SUCCESS("Tiers + 14 slots created"))

        # ---------------- Catalogue ----------------
        tags = {}
        for name in ("wedding", "office", "casual", "african", "evening", "bespoke", "kids"):
            tag, _ = Tag.objects.get_or_create(name=name, defaults=dict(slug=name))
            tags[name] = tag

        # Top-level categories
        cat_men, _ = Category.objects.get_or_create(slug="men", defaults=dict(name="Men", description="Men's tailoring", order=1))
        cat_women, _ = Category.objects.get_or_create(slug="women", defaults=dict(name="Women", description="Women's tailoring", order=2))
        cat_kids, _ = Category.objects.get_or_create(slug="kids", defaults=dict(name="Kids", description="Kids' clothing", order=3))

        # Subcategories.
        # Category.slug is globally unique, so subcategory slugs are namespaced
        # by parent ("men-kente") even though the display name is just "Kente".
        sub = {}
        def ensure_sub(parent, slug, name):
            c, _ = Category.objects.get_or_create(parent=parent, slug=slug, defaults=dict(name=name, description=name, order=0))
            return c

        sub["men_suits"] = ensure_sub(cat_men, "men-suits", "Suits")
        sub["men_kente"] = ensure_sub(cat_men, "men-kente", "Kente & Traditional")
        sub["men_shirts"] = ensure_sub(cat_men, "men-shirts", "Shirts")
        sub["women_dresses"] = ensure_sub(cat_women, "women-dresses", "Dresses")
        sub["women_kente"] = ensure_sub(cat_women, "women-kente", "Kente & Traditional")
        sub["women_skirts"] = ensure_sub(cat_women, "women-skirts", "Skirts & Tops")
        sub["kids_boys"] = ensure_sub(cat_kids, "kids-boys", "Boys")
        sub["kids_girls"] = ensure_sub(cat_kids, "kids-girls", "Girls")

        products = [
            dict(name="Classic Two-Piece Suit", slug="classic-two-piece-suit", category=sub["men_suits"], price="1850.00", gender="M", size="M", stock=6, desc="Sharp single-breasted suit in deep charcoal wool blend.", tags=["office", "bespoke"]),
            dict(name="Modern Slim-Fit Suit", slug="modern-slim-fit-suit", category=sub["men_suits"], price="2100.00", gender="M", size="L", stock=4, desc="Slim-cut suit with soft shoulder, for the contemporary man.", tags=["office"]),
            dict(name="Kente Heritage Outfit", slug="kente-heritage-outfit", category=sub["men_kente"], price="1450.00", gender="M", size="M", stock=8, desc="Hand-woven kente for ceremonies and celebrations.", tags=["african", "wedding"]),
            dict(name="Kente Dinner Jacket", slug="kente-dinner-jacket", category=sub["men_kente"], price="980.00", gender="M", size="L", stock=5, desc="Statement kente dinner jacket over a white shirt.", tags=["african", "evening"]),
            dict(name="Crisp Linen Shirt", slug="crisp-linen-shirt", category=sub["men_shirts"], price="320.00", gender="M", size="M", stock=20, desc="Breathable pure linen, perfect for the Accra heat.", tags=["casual"]),
            dict(name="Mermaid Evening Gown", slug="mermaid-evening-gown", category=sub["women_dresses"], price="2600.00", gender="F", size="S", stock=3, desc="Body-hugging mermaid gown in champagne silk.", tags=["evening", "wedding"]),
            dict(name="A-line Cocktail Dress", slug="a-line-cocktail-dress", category=sub["women_dresses"], price="1200.00", gender="F", size="M", stock=7, desc="A-line dress with elegant draping, knee length.", tags=["evening", "casual"]),
            dict(name="Kente Wrap Dress", slug="kente-wrap-dress", category=sub["women_kente"], price="1500.00", gender="F", size="M", stock=6, desc="Vibrant kente wrap dress with modern cut.", tags=["african", "wedding"]),
            dict(name="Kente Bridal Gown", slug="kente-bridal-gown", category=sub["women_kente"], price="4200.00", gender="F", size="S", stock=2, desc="Show-stopping kente bridal gown, custom fit available.", tags=["wedding"]),
            dict(name="High-Waist Skirt Set", slug="high-waist-skirt-set", category=sub["women_skirts"], price="780.00", gender="F", size="M", stock=10, desc="High-waist skirt with matching crop top.", tags=["casual", "african"]),
            dict(name="Boys Kente Set", slug="boys-kente-set", category=sub["kids_boys"], price="450.00", gender="K", size="S", stock=12, desc="Mini kente outfit for little gentlemen.", tags=["african", "kids"]),
            dict(name="Girls Party Dress", slug="girls-party-dress", category=sub["kids_girls"], price="380.00", gender="K", size="M", stock=15, desc="Frilled party dress, machine washable.", tags=["casual", "kids"]),
        ]
        for p in products:
            obj, created = Product.objects.get_or_create(slug=p["slug"], defaults=dict(
                name=p["name"], category=p["category"], price=p["price"],
                gender=p["gender"], size=p["size"], stock_quantity=p["stock"],
                description=p["desc"], is_active=True, is_featured=(p["slug"] in ("kente-heritage-outfit", "kente-bridal-gown", "classic-two-piece-suit")),
                bust_measurement="36.00" if p["gender"] == "F" else None,
                waist_measurement="28.00", hip_measurement="38.00" if p["gender"] == "F" else None,
                shoulder_measurement="18.00",
            ))
            if created:
                obj.tags.set(tags[t] for t in p["tags"])

        styles = [
            dict(name="Signature Bespoke Suit", slug="signature-bespoke-suit", category=sub["men_suits"], price="2400.00", days=10, desc="Fully custom suit, cut to your exact measurements.", tags=["bespoke", "wedding"]),
            dict(name="Agbada Royal", slug="agbada-royal", category=sub["men_kente"], price="1900.00", days=7, desc="Regal agbada with embroidery.", tags=["african", "wedding"]),
            dict(name="Bridal Kente Fantasy", slug="bridal-kente-fantasy", category=sub["women_kente"], price="5000.00", days=14, desc="One-of-a-kind bridal kente design.", tags=["wedding"]),
            dict(name="Tailored Linen Dress", slug="tailored-linen-dress", category=sub["women_dresses"], price="1100.00", days=5, desc="Made-to-measure linen dress.", tags=["casual"]),
            dict(name="Kente Family Set", slug="kente-family-set", category=sub["women_kente"], price="2600.00", days=12, desc="Coordinated family outfit package.", tags=["african", "wedding"]),
        ]
        for s in styles:
            obj, created = Style.objects.get_or_create(slug=s["slug"], defaults=dict(
                name=s["name"], category=s["category"], base_price=s["price"],
                estimated_making_time=s["days"], description=s["desc"], is_active=True,
            ))
            if created:
                obj.tags.set(tags[t] for t in s["tags"])

        self.stdout.write(self.style.SUCCESS(
            f"Catalogue ready: {Category.objects.count()} categories, {Product.objects.count()} products, {Style.objects.count()} styles"
        ))
